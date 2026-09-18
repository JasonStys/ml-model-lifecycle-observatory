"""File: lifecycle.py
Purpose: Orchestrate a reproducible local lifecycle demonstration and persist reviewable evidence.
Symbols and line locations: see docs/code-index.md; DemoResult summarizes generated artifacts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ml_observatory.artifacts import load_artifact, write_artifact
from ml_observatory.data import (
    dataset_metadata,
    generate_dataset,
    split_dataset,
    write_dataset,
    write_metadata,
)
from ml_observatory.drift import evaluate_drift
from ml_observatory.registry import Registry
from ml_observatory.reports import (
    render_dataset_card,
    render_drift_report,
    render_model_card,
    write_json,
    write_markdown,
)
from ml_observatory.schemas import DatasetRecord
from ml_observatory.training import Candidate, select_candidate, train_candidates


@dataclass(frozen=True, slots=True)
class DemoResult:
    """Paths and identities produced by a successful lifecycle demonstration."""

    registry_path: Path
    dataset_path: Path
    champion_model_id: str
    champion_sha256: str
    challenger_model_id: str
    drift_level: str


def _shifted_observations(records: Sequence[DatasetRecord]) -> tuple[DatasetRecord, ...]:
    """Return a deliberately shifted batch while respecting input schema bounds."""

    return tuple(
        record.model_copy(
            update={
                "cpu_percent": min(100.0, record.cpu_percent + 28.0),
                "error_rate": min(1.0, record.error_rate + 0.16),
                "p95_latency_ms": min(120_000.0, record.p95_latency_ms + 500.0),
            }
        )
        for record in records
    )


def run_demo(workspace: Path, count: int = 1_200, seed: int = 20260917) -> DemoResult:
    """Generate data, train candidates, promote a champion, and produce drift evidence."""

    workspace.mkdir(parents=True, exist_ok=True)
    dataset_path = workspace / "data" / "service-health-v1.jsonl"
    metadata_path = workspace / "data" / "service-health-v1.metadata.json"
    artifact_root = workspace / "models"
    report_root = workspace / "reports"
    registry_path = workspace / "registry.sqlite3"
    records = generate_dataset(count=count, seed=seed)
    dataset_sha256 = write_dataset(dataset_path, records)
    metadata = dataset_metadata(records, dataset_sha256)
    write_metadata(metadata_path, metadata)
    splits = split_dataset(records, seed=seed)
    candidates = train_candidates(splits, dataset_sha256, seed=seed)
    selected = select_candidate(candidates)
    registry = Registry(registry_path)
    registry.initialize()
    registered: dict[str, tuple[Candidate, str]] = {}
    for candidate in candidates:
        bundle = write_artifact(artifact_root, candidate.document)
        record = registry.register(
            bundle,
            algorithm=candidate.algorithm,
            dataset_sha256=dataset_sha256,
            metrics=candidate.metrics,
        )
        registered[candidate.algorithm] = (candidate, record.model_id)
    selected_model_id = registered[selected.algorithm][1]
    challenger = next(
        candidate for candidate in candidates if candidate.algorithm != selected.algorithm
    )
    challenger_model_id = registered[challenger.algorithm][1]
    registry.promote(selected_model_id)
    registry.assign_challenger(challenger_model_id, traffic_percent=10)
    champion_record = registry.get_model(selected_model_id)
    champion_model = load_artifact(artifact_root, champion_record.artifact_sha256)
    shifted = _shifted_observations(splits.test[: min(250, len(splits.test))])
    drift_report = evaluate_drift(champion_model, shifted)
    write_json(
        report_root / "candidate-evaluation.json",
        {candidate.algorithm: candidate.metrics for candidate in candidates},
    )
    write_json(report_root / "drift-report.json", drift_report.model_dump(mode="json"))
    write_markdown(report_root / "dataset-card.md", render_dataset_card(metadata))
    write_markdown(
        report_root / "model-card.md",
        render_model_card(
            model_id=selected_model_id,
            artifact_sha256=champion_record.artifact_sha256,
            algorithm=selected.algorithm,
            dataset_sha256=dataset_sha256,
            metrics=selected.metrics,
        ),
    )
    write_markdown(report_root / "drift-report.md", render_drift_report(drift_report))
    return DemoResult(
        registry_path=registry_path,
        dataset_path=dataset_path,
        champion_model_id=selected_model_id,
        champion_sha256=champion_record.artifact_sha256,
        challenger_model_id=challenger_model_id,
        drift_level=drift_report.overall_level,
    )
