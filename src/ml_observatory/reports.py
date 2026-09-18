"""File: reports.py
Purpose: Render honest dataset, model, evaluation, drift, and benchmark evidence in portable
formats.
Symbols and line locations: see docs/code-index.md; render_model_card makes limitations prominent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ml_observatory.hashing import atomic_write, canonical_json_bytes
from ml_observatory.schemas import DriftReport


def write_json(path: Path, value: Any) -> None:
    """Write machine-readable evidence atomically in canonical JSON."""

    atomic_write(path, canonical_json_bytes(value) + b"\n")


def write_markdown(path: Path, content: str) -> None:
    """Write normalized human-readable evidence atomically."""

    atomic_write(path, f"{content.rstrip()}\n".encode())


def render_dataset_card(metadata: dict[str, object]) -> str:
    """Describe dataset origin, intended use, composition, and non-production limitations."""

    positive_rate = cast(float, metadata["positive_rate"])
    return f"""# Synthetic service-health dataset card

## Summary

This dataset contains **{metadata["record_count"]} entirely synthetic observations** generated
by a seeded simulator. It models whether a synthetic software service experiences a failure in
the following 24 hours. It contains no people, customers, employer data, or production telemetry.

## Provenance

- Generator: `{metadata["generator"]}`
- SHA-256: `{metadata["sha256"]}`
- Observation range: {metadata["observed_from"]} through {metadata["observed_through"]}
- Positive examples: {metadata["positive_count"]} ({positive_rate:.2%})

## Intended use

The dataset exists to test reproducibility, calibration, promotion controls, drift detection, and
rollback mechanics. It must not be used to make operational or human-impacting decisions.

## Known limitations

- Relationships are intentionally simplified and seeded by authored equations.
- Region and service tier are synthetic operational segments, not human demographic attributes.
- Good results demonstrate pipeline behavior on this fixture, not real-world generalization.
- A real deployment would require representative data, subject-matter review, privacy assessment,
  incident ownership, and ongoing outcome collection.
"""


def render_model_card(
    *,
    model_id: str,
    artifact_sha256: str,
    algorithm: str,
    dataset_sha256: str,
    metrics: dict[str, Any],
) -> str:
    """Render a concise model card with measured results and explicit release constraints."""

    return f"""# Model card: {model_id}

## Model details

- Algorithm: `{algorithm}`
- Portable artifact SHA-256: `{artifact_sha256}`
- Dataset SHA-256: `{dataset_sha256}`
- Intended output: probability of a synthetic service failure within 24 hours
- Decision threshold: {metrics["decision_threshold"]:.3f}; the surrounding uncertainty band
  is recorded in the portable artifact and served with every response.

## Locked-test evaluation

| Metric | Result |
|---|---:|
| ROC AUC | {metrics["roc_auc"]:.4f} |
| Brier score | {metrics["brier"]:.4f} |
| Log loss | {metrics["log_loss"]:.4f} |
| F1 | {metrics["f1"]:.4f} |
| Recall | {metrics["recall"]:.4f} |
| Expected calibration error | {metrics["expected_calibration_error"]:.4f} |
| Selective coverage | {metrics["coverage"]:.4f} |
| Selective accuracy | {metrics["selective_accuracy"]:.4f} |
| Maximum subgroup recall gap | {metrics["maximum_subgroup_recall_gap"]:.4f} |

## Release decision

The automated demonstration may promote this model only if ROC AUC is at least 0.68 and the
maximum measured subgroup recall gap is no more than 0.40. Those thresholds are educational
guardrails, not universal production standards.

## Security and provenance

Inference uses reviewed JSON numeric parameters rather than pickle/joblib. The runtime verifies
the artifact content hash, fixed feature order, finite numeric values, layer dimensions, and path
containment before serving it.

## Limitations and prohibited uses

- Trained and tested only on synthetic data.
- Not validated for safety-critical control, employment, credit, health, or access decisions.
- Subgroup checks cover synthetic region and service tier only and do not establish fairness.
- Drift detection signals distribution change; it does not diagnose root cause or prove harm.
- Operators must review alerts, outcomes, rollback evidence, and domain constraints before use.
"""


def render_drift_report(report: DriftReport) -> str:
    """Render feature-level PSI results and threshold meanings."""

    rows = "\n".join(
        f"| `{feature.feature}` | {feature.psi:.4f} | {feature.level} |"
        for feature in report.features
    )
    return f"""# Drift monitoring report

- Artifact: `{report.model_sha256}`
- Samples: {report.sample_count}
- Overall level: **{report.overall_level}**
- Warning threshold: PSI >= {report.warning_threshold:.2f}
- Critical threshold: PSI >= {report.critical_threshold:.2f}

| Feature | PSI | Level |
|---|---:|---|
{rows}

PSI is an alerting heuristic. It does not establish that model quality declined; labeled outcome
evaluation and operator investigation are required before retraining or promotion.
"""
