"""File: test_drift_reports_lifecycle.py
Purpose: Verify PSI behavior, generated evidence, configuration, and the end-to-end lifecycle demo.
Symbols and line locations: see docs/code-index.md; tests validate both JSON and Markdown evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from conftest import TrainedSystem

from ml_observatory.artifacts import load_artifact
from ml_observatory.config import Settings
from ml_observatory.drift import evaluate_drift, population_stability_index
from ml_observatory.lifecycle import run_demo
from ml_observatory.reports import (
    render_dataset_card,
    render_drift_report,
    render_model_card,
    write_json,
    write_markdown,
)
from ml_observatory.schemas import DriftReport, Observation
from ml_observatory.training import select_candidate


def test_population_stability_index_is_zero_for_equal_distributions() -> None:
    """Identical distributions produce zero while invalid distributions fail clearly."""

    values = np.asarray([0.25, 0.75])
    assert population_stability_index(values, values) == pytest.approx(0.0)
    assert population_stability_index(values, np.asarray([0.75, 0.25])) > 0.0
    with pytest.raises(ValueError, match="align"):
        population_stability_index(values, np.asarray([1.0]))
    with pytest.raises(ValueError, match="negative"):
        population_stability_index(values, np.asarray([-1.0, 2.0]))
    with pytest.raises(ValueError, match="positive mass"):
        population_stability_index(values, np.asarray([0.0, 0.0]))


def test_drift_report_detects_shift_and_rejects_empty_input(
    trained_system: TrainedSystem,
) -> None:
    """Large bounded shifts become critical with per-feature evidence."""

    selected = select_candidate(trained_system.candidates)
    bundle = trained_system.bundles[selected.algorithm]
    model = load_artifact(trained_system.artifact_root, bundle.artifact_sha256)
    baseline = tuple(
        Observation.model_validate(record.model_dump(exclude={"row_id", "service_failure_24h"}))
        for record in trained_system.records[:200]
    )
    shifted = tuple(
        observation.model_copy(
            update={
                "error_rate": min(1.0, observation.error_rate + 0.25),
                "cpu_percent": min(100.0, observation.cpu_percent + 30.0),
            }
        )
        for observation in baseline
    )
    report = evaluate_drift(model, shifted)
    assert report.overall_level == "critical"
    assert report.sample_count == 200
    assert any(feature.level == "critical" for feature in report.features)
    with pytest.raises(ValueError, match="requires observations"):
        evaluate_drift(model, ())


def test_report_renderers_and_atomic_writes(tmp_path: Path, trained_system: TrainedSystem) -> None:
    """Human and machine reports state provenance, limitations, and exact metrics."""

    selected = select_candidate(trained_system.candidates)
    metadata = {
        "record_count": 1200,
        "generator": "generator",
        "sha256": trained_system.dataset_sha256,
        "observed_from": "2026-01-01T00:00:00+00:00",
        "observed_through": "2026-01-02T00:00:00+00:00",
        "positive_count": 200,
        "positive_rate": 1 / 6,
    }
    dataset_card = render_dataset_card(metadata)
    model_card = render_model_card(
        model_id="mdl-example",
        artifact_sha256="a" * 64,
        algorithm=selected.algorithm,
        dataset_sha256=trained_system.dataset_sha256,
        metrics=selected.metrics,
    )
    assert "entirely synthetic" in dataset_card
    assert "prohibited uses" in model_card.lower()
    markdown_path = tmp_path / "nested" / "report.md"
    json_path = tmp_path / "nested" / "report.json"
    write_markdown(markdown_path, dataset_card)
    write_json(json_path, {"passed": True})
    assert markdown_path.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"passed": True}


def test_complete_demo_persists_registry_cards_and_critical_drift(tmp_path: Path) -> None:
    """The recruiter workflow runs without hidden services and leaves reviewable evidence."""

    result = run_demo(tmp_path / "demo", count=1_200)
    assert result.registry_path.exists()
    assert result.dataset_path.exists()
    assert result.drift_level == "critical"
    report_root = tmp_path / "demo" / "reports"
    assert "ROC AUC" in (report_root / "model-card.md").read_text(encoding="utf-8")
    drift_json = json.loads((report_root / "drift-report.json").read_text(encoding="utf-8"))
    assert drift_json["overall_level"] == "critical"
    assert "PSI" in render_drift_report(DriftReport.model_validate(drift_json))


def test_settings_read_documented_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment configuration is explicit and an empty admin token disables mutation."""

    monkeypatch.setenv("OBSERVATORY_REGISTRY_PATH", "custom/registry.sqlite3")
    monkeypatch.setenv("OBSERVATORY_ARTIFACT_ROOT", "custom/models")
    monkeypatch.setenv("OBSERVATORY_ADMIN_TOKEN", "secret")
    settings = Settings.from_environment()
    assert settings.registry_path == Path("custom/registry.sqlite3")
    assert settings.artifact_root == Path("custom/models")
    assert settings.admin_token == "secret"  # noqa: S105 - synthetic test credential
    monkeypatch.setenv("OBSERVATORY_ADMIN_TOKEN", "")
    assert Settings.from_environment().admin_token is None
