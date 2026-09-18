"""File: test_api.py
Purpose: Verify HTTP contracts, readiness, inference, authorization, promotion,
rollback errors, and real-artifact behavior.
Symbols and line locations: see docs/code-index.md; tests use isolated registries
and real artifacts.
"""

from __future__ import annotations

from pathlib import Path

from conftest import TrainedSystem
from fastapi.testclient import TestClient

from ml_observatory.api import create_app
from ml_observatory.config import Settings
from ml_observatory.registry import Registry


def _prediction_payload(trained_system: TrainedSystem) -> dict[str, object]:
    """Return a JSON-compatible request without training-only fields."""

    record = trained_system.records[0]
    return {
        "request_id": "api-request-0001",
        "observation": record.model_dump(mode="json", exclude={"row_id", "service_failure_24h"}),
    }


def test_liveness_and_empty_readiness_are_distinct(tmp_path: Path) -> None:
    """A running process is live but not ready before a champion exists."""

    settings = Settings(tmp_path / "registry.sqlite3", tmp_path / "models", "test-token")
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/live").json()["status"] == "live"
        readiness = client.get("/health/ready")
        assert readiness.status_code == 503
        prediction = client.post(
            "/v1/predict",
            json={"request_id": "missing-model", "observation": {}},
        )
        assert prediction.status_code == 422
        assert client.get("/v1/models").json() == []


def test_prediction_and_registry_endpoints_use_real_deployment(
    deployed_registry: tuple[Registry, str, str],
    trained_system: TrainedSystem,
) -> None:
    """Ready service returns bounded predictions and provenance for registered models."""

    registry, champion_id, challenger_id = deployed_registry
    settings = Settings(registry.path, trained_system.artifact_root, "test-token")
    with TestClient(create_app(settings)) as client:
        readiness = client.get("/health/ready")
        assert readiness.status_code == 200
        assert readiness.json()["champion_model_id"] == champion_id
        response = client.post("/v1/predict", json=_prediction_payload(trained_system))
        assert response.status_code == 200
        payload = response.json()
        assert payload["model_id"] in {champion_id, challenger_id}
        assert 0.0 <= payload["failure_probability"] <= 1.0
        assert len(client.get("/v1/models").json()) == 2


def test_admin_endpoints_require_token_and_preserve_rollback(
    deployed_registry: tuple[Registry, str, str],
    trained_system: TrainedSystem,
) -> None:
    """Mutations reject missing tokens and preserve a usable prior champion."""

    registry, champion_id, challenger_id = deployed_registry
    settings = Settings(registry.path, trained_system.artifact_root, "test-token")
    headers = {"X-Admin-Token": "test-token"}
    with TestClient(create_app(settings)) as client:
        unauthorized = client.post(
            f"/v1/admin/models/{challenger_id}/promote",
            json={"reason": "canary passed"},
        )
        assert unauthorized.status_code == 401
        missing = client.post(
            "/v1/admin/models/mdl-0000000000000000/promote",
            headers=headers,
            json={"reason": "manual review"},
        )
        assert missing.status_code == 404
        promoted = client.post(
            f"/v1/admin/models/{challenger_id}/promote",
            headers=headers,
            json={"reason": "canary passed"},
        )
        assert promoted.status_code == 200
        assigned = client.post(
            "/v1/admin/challenger",
            headers=headers,
            json={"model_id": champion_id, "traffic_percent": 5},
        )
        assert assigned.status_code == 200
        conflict = client.post(
            "/v1/admin/challenger",
            headers=headers,
            json={"model_id": challenger_id, "traffic_percent": 5},
        )
        assert conflict.status_code == 409
        rolled_back = client.post(
            "/v1/admin/rollback",
            headers=headers,
            json={"reason": "drift threshold exceeded"},
        )
        assert rolled_back.status_code == 200
        assert rolled_back.json()["model_id"] == champion_id


def test_admin_disabled_and_unavailable_rollback_fail_closed(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Absent token configuration and absent history both prevent state changes."""

    no_token = Settings(tmp_path / "empty.sqlite3", trained_system.artifact_root, None)
    with TestClient(create_app(no_token)) as client:
        assert (
            client.post(
                "/v1/admin/rollback",
                headers={"X-Admin-Token": "anything"},
                json={"reason": "operator request"},
            ).status_code
            == 401
        )
