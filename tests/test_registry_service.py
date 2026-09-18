"""File: test_registry_service.py
Purpose: Verify registry transactions, audit history, rollback, canary routing, and input-free logs.
Symbols and line locations: see docs/code-index.md; tests exercise lifecycle state transitions.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from conftest import TrainedSystem

from ml_observatory.registry import Registry
from ml_observatory.schemas import Observation, PredictRequest
from ml_observatory.service import ModelService


def _request(trained_system: TrainedSystem, request_id: str) -> PredictRequest:
    """Build a valid prediction request without labels or row identifiers."""

    record = trained_system.records[0]
    observation = Observation.model_validate(
        record.model_dump(exclude={"row_id", "service_failure_24h"})
    )
    return PredictRequest(request_id=request_id, observation=observation)


def test_registry_registration_is_idempotent_and_queryable(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Repeated content registration returns one candidate and one registration audit event."""

    registry = Registry(tmp_path / "registry.sqlite3")
    registry.initialize()
    candidate = trained_system.candidates[0]
    bundle = trained_system.bundles[candidate.algorithm]
    first = registry.register(
        bundle,
        algorithm=candidate.algorithm,
        dataset_sha256=trained_system.dataset_sha256,
        metrics=candidate.metrics,
    )
    second = registry.register(
        bundle,
        algorithm=candidate.algorithm,
        dataset_sha256=trained_system.dataset_sha256,
        metrics=candidate.metrics,
    )
    assert first.model_id == second.model_id
    assert registry.get_model(first.model_id) == second
    assert len(registry.list_models()) == 1
    assert [event["event_type"] for event in registry.audit_events()] == ["model-registered"]
    with pytest.raises(KeyError):
        registry.get_model("mdl-0000000000000000")
    with pytest.raises(ValueError, match="different metadata"):
        registry.register(
            bundle,
            algorithm="changed",
            dataset_sha256=trained_system.dataset_sha256,
            metrics=candidate.metrics,
        )


def test_concurrent_registration_converges_on_one_identity(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Concurrent duplicate deliveries do not create duplicate model identities."""

    registry = Registry(tmp_path / "registry.sqlite3")
    registry.initialize()
    candidate = trained_system.candidates[0]
    bundle = trained_system.bundles[candidate.algorithm]

    def register() -> str:
        return registry.register(
            bundle,
            algorithm=candidate.algorithm,
            dataset_sha256=trained_system.dataset_sha256,
            metrics=candidate.metrics,
        ).model_id

    with ThreadPoolExecutor(max_workers=4) as executor:
        identifiers = tuple(executor.map(lambda _: register(), range(8)))
    assert len(set(identifiers)) == 1
    assert len(registry.list_models()) == 1


def test_promote_challenger_clear_and_rollback_state_machine(
    deployed_registry: tuple[Registry, str, str],
) -> None:
    """Promotion closes experiments, rollback restores history, and every transition is audited."""

    registry, champion_id, challenger_id = deployed_registry
    snapshot = registry.deployment_snapshot()
    assert snapshot.champion.model_id == champion_id
    assert snapshot.challenger is not None
    assert snapshot.challenger.model_id == challenger_id
    registry.clear_challenger()
    assert registry.deployment_snapshot().challenger is None
    registry.assign_challenger(challenger_id, 25)
    registry.promote(challenger_id, reason="canary-passed")
    promoted = registry.deployment_snapshot()
    assert promoted.champion.model_id == challenger_id
    assert promoted.challenger is None
    assert registry.get_model(champion_id).status == "retired"
    restored = registry.rollback()
    assert restored == champion_id
    assert registry.deployment_snapshot().champion.model_id == champion_id
    assert "champion-promoted" in {event["event_type"] for event in registry.audit_events()}


def test_registry_rejects_invalid_transitions(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Unknown models, unsafe exposure, missing champions, and unavailable rollback fail clearly."""

    registry = Registry(tmp_path / "registry.sqlite3")
    registry.initialize()
    with pytest.raises(RuntimeError, match="no champion"):
        registry.deployment_snapshot()
    with pytest.raises(KeyError):
        registry.promote("mdl-0000000000000000")
    candidate = trained_system.candidates[0]
    model = registry.register(
        trained_system.bundles[candidate.algorithm],
        algorithm=candidate.algorithm,
        dataset_sha256=trained_system.dataset_sha256,
        metrics=candidate.metrics,
    )
    with pytest.raises(RuntimeError, match="champion is required"):
        registry.assign_challenger(model.model_id)
    registry.promote(model.model_id)
    registry.promote(model.model_id)
    with pytest.raises(ValueError, match="different"):
        registry.assign_challenger(model.model_id)
    with pytest.raises(ValueError, match="between 0 and 50"):
        registry.assign_challenger("mdl-0000000000000000", 51)
    with pytest.raises(RuntimeError, match="no prior"):
        registry.rollback()


def test_service_runs_shadow_and_deterministic_canary_predictions(
    deployed_registry: tuple[Registry, str, str],
    trained_system: TrainedSystem,
) -> None:
    """Stable routing evaluates both models and never stores raw feature payloads."""

    registry, champion_id, challenger_id = deployed_registry
    service = ModelService(registry, trained_system.artifact_root)
    champion_request_id = next(
        f"request-champion-{index}"
        for index in range(200)
        if not service._canary_selected(f"request-champion-{index}", 10)
    )
    challenger_request_id = next(
        f"request-challenger-{index}"
        for index in range(200)
        if service._canary_selected(f"request-challenger-{index}", 10)
    )
    champion_response = service.predict(_request(trained_system, champion_request_id))
    challenger_response = service.predict(_request(trained_system, challenger_request_id))
    assert champion_response.model_id == champion_id
    assert challenger_response.model_id == challenger_id
    assert champion_response.challenger_model_id == challenger_id
    assert champion_response.challenger_probability is not None
    assert service.predict(_request(trained_system, champion_request_id)) == champion_response
    assert service._cache


def test_service_without_champion_fails_readiness(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Inference fails before model loading when no champion is deployed."""

    registry = Registry(tmp_path / "empty.sqlite3")
    registry.initialize()
    service = ModelService(registry, trained_system.artifact_root)
    with pytest.raises(RuntimeError, match="no champion"):
        service.predict(_request(trained_system, "request-empty-0001"))
