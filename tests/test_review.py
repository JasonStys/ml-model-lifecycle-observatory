"""File: test_review.py
Purpose: Validate independent review gate arithmetic, provenance, context and non-mutation.
Author: Jason Stys. Variables: registries/artifact copies and report files are test-owned only.
Symbols and line locations: docs/code-index.md.
"""

from __future__ import annotations

import copy
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from conftest import TrainedSystem
from fastapi.testclient import TestClient

from ml_observatory.api import create_app
from ml_observatory.artifacts import load_artifact, write_artifact
from ml_observatory.cli import main
from ml_observatory.config import Settings
from ml_observatory.drift import evaluate_drift
from ml_observatory.registry import Registry
from ml_observatory.review import (
    MAX_REVIEW_INPUT_BYTES,
    model_review,
    quality_gates,
    read_drift_context,
)


@pytest.mark.parametrize("bad", [None, "bad", True, -1, 2, float("inf"), float("nan")])
def test_gate_contract_failures(bad: Any) -> None:
    assert not any(
        quality_gates({"roc_auc": bad, "maximum_subgroup_recall_gap": bad, "brier": bad}).values()
    )
    assert quality_gates({"roc_auc": 0.68, "maximum_subgroup_recall_gap": 0.40, "brier": 0}) == {
        "roc_auc": True,
        "subgroup_recall_gap": True,
        "finite_brier": True,
    }
    assert quality_gates({"roc_auc": 0.679, "maximum_subgroup_recall_gap": 0.401, "brier": 1}) == {
        "roc_auc": False,
        "subgroup_recall_gap": False,
        "finite_brier": True,
    }


def test_dossier_provenance_context_and_no_writes(
    deployed_registry: tuple[Registry, str, str],
    trained_system: TrainedSystem,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry, champion, challenger = deployed_registry
    before = registry.audit_events()
    report = model_review(registry, trained_system.artifact_root, champion)
    assert report["provenance_verified"]
    assert report["dataset_bytes_verified"] is False
    assert report["eligible_on_recorded_quality"]
    assert report["failed_gates"] == []
    assert report["dataset_sha256"] == trained_system.dataset_sha256
    assert sum(report["split_counts"].values()) == 1200
    assert report["drift_context"]["state"] == "not_supplied"
    assert report["rollback_context"]["prior_candidate"] is None
    assert "artifact_path" not in json.dumps(report)
    registry.promote(challenger)
    later = model_review(registry, trained_system.artifact_root, challenger)
    assert later["rollback_context"]["prior_candidate"] == champion
    assert later["rollback_context"]["verified_for_rollback"] is False
    model_id = challenger

    model = load_artifact(
        trained_system.artifact_root, registry.get_model(model_id).artifact_sha256
    )
    drift = evaluate_drift(model, trained_system.records[:50])
    path = tmp_path / "drift.json"
    path.write_text(drift.model_dump_json())
    context = model_review(
        registry, trained_system.artifact_root, model_id, read_drift_context(path)
    )
    assert context["drift_context"]["sample_context"] == "small_sample_review"
    assert context["drift_context"]["sample_count"] == 50
    output = tmp_path / "review.json"
    arguments = [
        "review",
        model_id,
        "--registry",
        str(registry.path),
        "--artifact-root",
        str(trained_system.artifact_root),
    ]
    assert main([*arguments, "--drift-report", str(path), "--report", str(output)]) == 0
    assert json.loads(capsys.readouterr().out)["drift_context"]["sample_count"] == 50
    assert json.loads(output.read_text())["model_id"] == model_id
    assert main(arguments) == 0
    capsys.readouterr()
    with pytest.raises(FileExistsError):
        main([*arguments, "--report", str(output)])
    assert registry.audit_events()[: len(before)] == before
    assert len(registry.audit_events()) == len(before) + 1
    stable = drift.model_copy(
        update={
            "sample_count": 100,
            "overall_level": "stable",
            "features": tuple(
                item.model_copy(update={"psi": 0.0, "level": "stable"}) for item in drift.features
            ),
        }
    )
    assert (
        model_review(registry, trained_system.artifact_root, model_id, stable)["drift_context"][
            "sample_context"
        ]
        == "review_required"
    )
    for level, psi in [("warning", 0.1), ("critical", 0.25)]:
        changed = stable.model_copy(
            update={
                "overall_level": level,
                "features": tuple(
                    item.model_copy(update={"psi": psi, "level": level}) for item in stable.features
                ),
            }
        )
        assert (
            model_review(registry, trained_system.artifact_root, model_id, changed)[
                "drift_context"
            ]["report"]["overall_level"]
            == level
        )


def test_rejects_mismatched_context_and_metadata(
    deployed_registry: tuple[Registry, str, str], trained_system: TrainedSystem, tmp_path: Path
) -> None:
    registry, champion, _ = deployed_registry

    drift = evaluate_drift(
        load_artifact(trained_system.artifact_root, registry.get_model(champion).artifact_sha256),
        trained_system.records[:100],
    )
    for update in [
        {"model_sha256": "0" * 64},
        {"sample_count": 0},
        {"features": drift.features[:-1]},
        {"warning_threshold": float("nan")},
        {"critical_threshold": 0.01},
        {"features": (drift.features[0].model_copy(update={"psi": -1}), *drift.features[1:])},
        {"overall_level": "stable" if drift.overall_level != "stable" else "critical"},
    ]:
        with pytest.raises(ValueError, match="drift context"):
            model_review(
                registry, trained_system.artifact_root, champion, drift.model_copy(update=update)
            )
    oversized = tmp_path / "large.json"
    oversized.write_bytes(b" " * (MAX_REVIEW_INPUT_BYTES + 1))
    with pytest.raises(ValueError, match="limit"):
        read_drift_context(oversized)
    with registry._session() as connection:
        connection.execute(
            "UPDATE models SET dataset_sha256=? WHERE model_id=?", ("0" * 64, champion)
        )
    with pytest.raises(ValueError, match="provenance"):
        model_review(registry, trained_system.artifact_root, champion)


def test_http_auth_tamper_empty_and_bounded_history(
    deployed_registry: tuple[Registry, str, str], trained_system: TrainedSystem, tmp_path: Path
) -> None:
    registry, champion, challenger = deployed_registry
    artifacts = tmp_path / "copies"
    shutil.copytree(trained_system.artifact_root, artifacts)
    client = TestClient(create_app(Settings(registry.path, artifacts, "test-review-token")))
    url = f"/v1/admin/models/{champion}/review"
    assert client.get(url).status_code == 401
    headers = {"X-Admin-Token": "test-review-token"}
    assert client.get(url, headers=headers).status_code == 200
    assert client.get("/v1/admin/models/missing/review", headers=headers).status_code == 404
    model = registry.get_model(champion)
    (artifacts / model.artifact_sha256 / "model.json").write_bytes(b"tamper")
    response = client.get(url, headers=headers)
    assert response.status_code == 409
    assert str(tmp_path) not in response.text
    empty = Registry(tmp_path / "empty.sqlite3")
    empty.initialize()
    with pytest.raises(KeyError):
        model_review(empty, artifacts, "missing")
    for index in range(102):
        registry.promote(challenger if index % 2 == 0 else champion)
    _, snapshot = registry.review_snapshot(champion)
    assert snapshot["history_total"] == 103
    assert len(snapshot["recent_history"]) == 100
    assert snapshot["history_truncated"]
    absent_path = tmp_path / "never-created.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        Registry(absent_path).review_snapshot(champion)
    assert not absent_path.exists()


@pytest.mark.parametrize("mutation", ["missing_counts", "zero_count", "oversized"])
def test_rejects_invalid_declared_split_or_oversized_bundle(
    trained_system: TrainedSystem, tmp_path: Path, mutation: str
) -> None:
    document = copy.deepcopy(trained_system.candidates[0].document)
    if mutation == "missing_counts":
        document["training"].pop("split_counts")
    elif mutation == "zero_count":
        document["training"]["split_counts"]["test"] = 0
    else:
        document["padding"] = "x" * (MAX_REVIEW_INPUT_BYTES + 1)
    root = tmp_path / "models"
    bundle = write_artifact(root, document)
    registry = Registry(tmp_path / "review.sqlite3")
    registry.initialize()
    record = registry.register(
        bundle,
        algorithm=document["algorithm"],
        dataset_sha256=trained_system.dataset_sha256,
        metrics=document["evaluation"],
    )
    with pytest.raises(ValueError):
        model_review(registry, root, record.model_id)
