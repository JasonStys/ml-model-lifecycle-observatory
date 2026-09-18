"""File: drift.py
Purpose: Compare live feature distributions with training references using population stability
index. Symbols and line locations: see docs/code-index.md; WARNING_PSI and CRITICAL_PSI are
actionable gates.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ml_observatory.artifacts import PortableModel
from ml_observatory.schemas import FEATURE_NAMES, DriftFeature, DriftReport, Observation

WARNING_PSI = 0.10
CRITICAL_PSI = 0.25
EPSILON = 1e-6


def population_stability_index(expected: np.ndarray, observed: np.ndarray) -> float:
    """Calculate PSI with symmetric epsilon smoothing for empty bins."""

    if expected.shape != observed.shape or expected.ndim != 1:
        raise ValueError("expected and observed distributions must align")
    if np.any(expected < 0.0) or np.any(observed < 0.0):
        raise ValueError("distribution proportions cannot be negative")
    expected_total = float(np.sum(expected))
    observed_total = float(np.sum(observed))
    if expected_total <= 0.0 or observed_total <= 0.0:
        raise ValueError("distribution proportions must have positive mass")
    expected_safe = np.clip(expected / expected_total, EPSILON, None)
    observed_safe = np.clip(observed / observed_total, EPSILON, None)
    expected_safe /= np.sum(expected_safe)
    observed_safe /= np.sum(observed_safe)
    return float(np.sum((observed_safe - expected_safe) * np.log(observed_safe / expected_safe)))


def evaluate_drift(model: PortableModel, observations: Sequence[Observation]) -> DriftReport:
    """Evaluate each feature and promote the worst level to the overall drift state."""

    if not observations:
        raise ValueError("drift evaluation requires observations")
    matrix = np.asarray([observation.feature_vector() for observation in observations])
    results: list[DriftFeature] = []
    for index, name in enumerate(FEATURE_NAMES):
        reference = model.reference_distribution[name]
        edges = np.asarray(reference["edges"], dtype=np.float64)
        expected = np.asarray(reference["proportions"], dtype=np.float64)
        counts, _ = np.histogram(matrix[:, index], bins=edges)
        psi = population_stability_index(expected, counts.astype(np.float64))
        if psi >= CRITICAL_PSI:
            level = "critical"
        elif psi >= WARNING_PSI:
            level = "warning"
        else:
            level = "stable"
        results.append(DriftFeature(feature=name, psi=psi, level=level))
    levels = {result.level for result in results}
    overall = "critical" if "critical" in levels else "warning" if "warning" in levels else "stable"
    return DriftReport(
        model_sha256=model.artifact_sha256,
        sample_count=len(observations),
        warning_threshold=WARNING_PSI,
        critical_threshold=CRITICAL_PSI,
        overall_level=overall,
        features=tuple(results),
    )
