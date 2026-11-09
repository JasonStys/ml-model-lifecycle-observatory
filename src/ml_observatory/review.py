"""File: review.py
Purpose: Build a read-only model-release dossier with verified provenance and gate reasons.
Author: Jason Stys. Variables: snapshot is registry evidence; drift remains contextual advice.
Symbols and line locations: docs/code-index.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from ml_observatory.artifacts import load_artifact
from ml_observatory.hashing import resolve_within, sha256_bytes
from ml_observatory.registry import Registry
from ml_observatory.schemas import FEATURE_NAMES, DriftReport
from ml_observatory.training import MAXIMUM_RECALL_GAP, MINIMUM_AUC

MAX_REVIEW_INPUT_BYTES = 2 * 1024 * 1024
MIN_CONTEXT_SAMPLES = 100


def quality_gates(metrics: dict[str, Any]) -> dict[str, bool]:
    """Expose selection gates plus probability-domain sanity bounds; missing evidence fails."""

    def number(name: str) -> float:
        """Treat missing, boolean and nonnumeric evidence as an unknown numeric value."""
        value = metrics.get(name)
        return (
            float(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else math.nan
        )

    auc, gap, brier = number("roc_auc"), number("maximum_subgroup_recall_gap"), number("brier")
    return {
        "roc_auc": math.isfinite(auc) and MINIMUM_AUC <= auc <= 1,
        "subgroup_recall_gap": math.isfinite(gap) and 0 <= gap <= MAXIMUM_RECALL_GAP,
        "finite_brier": math.isfinite(brier) and 0 <= brier <= 1,
    }


def model_review(
    registry: Registry, artifact_root: Path, model_id: str, drift: DriftReport | None = None
) -> dict[str, Any]:
    """Verify the content-addressed bundle before exposing a path-free, read-only review.

    Artifact identity/metadata matching is checked, not independently retrained performance.
    The snapshot can become stale after return; no promotion or rollback is executed.
    """
    record, snapshot = registry.review_snapshot(model_id)
    document_path = resolve_within(
        artifact_root, artifact_root / record.artifact_sha256 / "model.json"
    )
    with document_path.open("rb") as source:
        payload = source.read(MAX_REVIEW_INPUT_BYTES + 1)
    if len(payload) > MAX_REVIEW_INPUT_BYTES or sha256_bytes(payload) != record.artifact_sha256:
        raise ValueError("review artifact size or identity changed")
    model = load_artifact(artifact_root, record.artifact_sha256)
    document = json.loads(payload)
    training = document.get("training")
    if not isinstance(training, dict) or not isinstance(training.get("split_counts"), dict):
        raise ValueError("artifact training provenance is missing")
    split_counts = training["split_counts"]
    if set(split_counts) != {"train", "calibration", "test"} or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 1
        for value in split_counts.values()
    ):
        raise ValueError("artifact split counts must identify positive train/calibration/test rows")
    if (
        document["algorithm"] != record.algorithm
        or training.get("dataset_sha256") != record.dataset_sha256
        or document.get("evaluation") != record.metrics
    ):
        raise ValueError("registry metadata does not match verified artifact provenance")
    gates = quality_gates(record.metrics)
    drift_context: dict[str, Any] = {
        "state": "not_supplied",
        "sample_count": 0,
        "notice": "No drift evidence supplied; this is not a stability finding.",
    }
    if drift is not None:
        if (
            drift.model_sha256 != record.artifact_sha256
            or drift.sample_count < 1
            or {item.feature for item in drift.features} != set(FEATURE_NAMES)
            or len(drift.features) != len(FEATURE_NAMES)
            or not math.isfinite(drift.warning_threshold)
            or not math.isfinite(drift.critical_threshold)
            or not 0 < drift.warning_threshold < drift.critical_threshold
            or any(not math.isfinite(item.psi) or item.psi < 0 for item in drift.features)
        ):
            raise ValueError("drift context identity, samples or feature contract is invalid")
        expected = [
            "critical"
            if item.psi >= drift.critical_threshold
            else "warning"
            if item.psi >= drift.warning_threshold
            else "stable"
            for item in drift.features
        ]
        overall = (
            "critical"
            if "critical" in expected
            else "warning"
            if "warning" in expected
            else "stable"
        )
        if overall != drift.overall_level or any(
            item.level != level for item, level in zip(drift.features, expected, strict=True)
        ):
            raise ValueError("drift context levels disagree with its stated thresholds")
        drift_context = {
            "state": "supplied",
            "report": drift.model_dump(mode="json"),
            "sample_count": drift.sample_count,
            "minimum_context_samples": MIN_CONTEXT_SAMPLES,
            "sample_context": "small_sample_review"
            if drift.sample_count < MIN_CONTEXT_SAMPLES
            else "review_required",
            "notice": "Sample heuristic is not statistical confidence. "
            "Drift does not prove performance change or authorize promotion.",
        }
    current = next(
        (item["model_id"] for item in snapshot["deployments"] if item["role"] == "champion"), None
    )
    prior = next(
        (
            item["from_model_id"]
            for item in snapshot["recent_history"]
            if item["to_model_id"] == current and item["from_model_id"] is not None
        ),
        None,
    )
    return {
        "schema_version": 1,
        "model_id": record.model_id,
        "status": record.status,
        "artifact_sha256": record.artifact_sha256,
        "dataset_sha256": record.dataset_sha256,
        "algorithm": record.algorithm,
        "provenance_verified": True,
        "dataset_bytes_verified": False,
        "verification_scope": "Bundle content/manifest/schema and registry metadata agreement; "
        "raw dataset bytes and recorded evaluation are not rerun.",
        "feature_names": list(FEATURE_NAMES),
        "split_counts": split_counts,
        "calibration_method": document["calibration"].get("method", "not_declared"),
        "decision_threshold": model.threshold,
        "abstention_band": model.abstention_band,
        "metrics": record.metrics,
        "quality_gates": gates,
        "eligible_on_recorded_quality": all(gates.values()),
        "failed_gates": [name for name, passed in gates.items() if not passed],
        "drift_context": drift_context,
        "registry_snapshot": snapshot,
        "rollback_context": {
            "current_champion": current,
            "prior_candidate": prior,
            "verified_for_rollback": False,
        },
        "notice": "Read-only synthetic service-health model dossier. "
        "Recorded test metrics are not rerun. Review provenance, split/sample counts, "
        "subgroup evidence and context before an independent operator decision. "
        "History is bounded to100latest entries; prior rollback candidate is unverified. "
        "No promotion or rollback occurs.",
    }


def read_drift_context(path: Path) -> DriftReport:
    """Read bounded local JSON only; never fetch URLs or deserialize executable models."""
    with path.open("rb") as source:
        payload = source.read(MAX_REVIEW_INPUT_BYTES + 1)
    if len(payload) > MAX_REVIEW_INPUT_BYTES:
        raise ValueError("drift report exceeds review input limit")
    return DriftReport.model_validate_json(payload)
