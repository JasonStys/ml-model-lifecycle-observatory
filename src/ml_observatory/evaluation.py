"""File: evaluation.py
Purpose: Compute classification, calibration, abstention, and subgroup evidence without hidden
defaults. Symbols and line locations: see docs/code-index.md; constants define metric behavior.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    fbeta_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

DEFAULT_BINS = 10
DECISION_THRESHOLD = 0.5
ABSTENTION_MARGIN = 0.06
MINIMUM_BINS = 2
MATRIX_DIMENSIONS = 2
MINIMUM_HISTOGRAM_EDGES = 3


def expected_calibration_error(
    labels: np.ndarray,
    probabilities: np.ndarray,
    bins: int = DEFAULT_BINS,
) -> float:
    """Calculate weighted absolute confidence error across equal-width bins."""

    if bins < MINIMUM_BINS:
        raise ValueError("bins must be at least 2")
    edges = np.linspace(0.0, 1.0, bins + 1)
    assignments = np.minimum(np.digitize(probabilities, edges[1:-1]), bins - 1)
    error = 0.0
    for index in range(bins):
        mask = assignments == index
        if not np.any(mask):
            continue
        confidence = float(np.mean(probabilities[mask]))
        observed = float(np.mean(labels[mask]))
        error += float(np.mean(mask)) * abs(confidence - observed)
    return error


def choose_decision_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    """Select the calibration-set threshold with the best recall-weighted F2 score."""

    candidates = np.linspace(0.05, 0.80, 151)
    ranked = []
    for threshold in candidates:
        decisions = probabilities >= threshold
        ranked.append(
            (
                float(f1_score(labels, decisions, zero_division=0)),
                float(fbeta_score(labels, decisions, beta=2.0, zero_division=0)),
                float(recall_score(labels, decisions, zero_division=0)),
                -abs(float(threshold) - DECISION_THRESHOLD),
                float(threshold),
            )
        )
    return max(ranked, key=lambda row: (row[1], row[2], row[0], row[3]))[-1]


def abstention_band(threshold: float) -> tuple[float, float]:
    """Return a bounded uncertainty interval centered on the selected threshold."""

    return max(0.0, threshold - ABSTENTION_MARGIN), min(1.0, threshold + ABSTENTION_MARGIN)


def binary_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float = DECISION_THRESHOLD,
) -> dict[str, float]:
    """Return threshold, ranking, calibration, and selective-prediction metrics."""

    if labels.ndim != 1 or probabilities.ndim != 1 or labels.size != probabilities.size:
        raise ValueError("labels and probabilities must be equal one-dimensional arrays")
    if labels.size == 0 or not np.all(np.isfinite(probabilities)):
        raise ValueError("metrics require finite, non-empty probabilities")
    if np.min(probabilities) < 0.0 or np.max(probabilities) > 1.0:
        raise ValueError("probabilities must be within [0, 1]")
    if not 0.0 < threshold < 1.0:
        raise ValueError("threshold must be between zero and one")
    decisions = probabilities >= threshold
    lower, upper = abstention_band(threshold)
    accepted = (probabilities < lower) | (probabilities > upper)
    selective_accuracy = (
        float(accuracy_score(labels[accepted], decisions[accepted])) if np.any(accepted) else 0.0
    )
    return {
        "accuracy": float(accuracy_score(labels, decisions)),
        "precision": float(precision_score(labels, decisions, zero_division=0)),
        "recall": float(recall_score(labels, decisions, zero_division=0)),
        "f1": float(f1_score(labels, decisions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "brier": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "expected_calibration_error": expected_calibration_error(labels, probabilities),
        "coverage": float(np.mean(accepted)),
        "selective_accuracy": selective_accuracy,
        "decision_threshold": threshold,
    }


def subgroup_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    groups: Sequence[str],
    threshold: float = DECISION_THRESHOLD,
) -> dict[str, Any]:
    """Measure support, positive rate, accuracy, and recall for each named subgroup."""

    if len(groups) != labels.size:
        raise ValueError("groups must align with labels")
    decisions = probabilities >= threshold
    results: dict[str, dict[str, float | int]] = {}
    recalls: list[float] = []
    group_array = np.asarray(groups)
    for group in sorted(set(groups)):
        mask = group_array == group
        group_labels = labels[mask]
        group_decisions = decisions[mask]
        recall = float(recall_score(group_labels, group_decisions, zero_division=0))
        recalls.append(recall)
        results[group] = {
            "support": int(np.sum(mask)),
            "positive_rate": float(np.mean(group_labels)),
            "accuracy": float(accuracy_score(group_labels, group_decisions)),
            "recall": recall,
        }
    return {
        "groups": results,
        "recall_gap": max(recalls) - min(recalls) if recalls else 0.0,
    }


def reference_histograms(
    features: np.ndarray,
    feature_names: Sequence[str],
    bins: int = DEFAULT_BINS,
) -> dict[str, dict[str, list[float]]]:
    """Build quantile-edged reference histograms for bounded PSI monitoring."""

    if features.ndim != MATRIX_DIMENSIONS or features.shape[1] != len(feature_names):
        raise ValueError("feature matrix does not match feature names")
    quantiles = np.linspace(0.0, 1.0, bins + 1)
    result: dict[str, dict[str, list[float]]] = {}
    for index, name in enumerate(feature_names):
        column = features[:, index]
        edges = np.unique(np.quantile(column, quantiles))
        if edges.size < MINIMUM_HISTOGRAM_EDGES:
            center = float(column[0])
            edges = np.asarray([center - 1.0, center, center + 1.0])
        # JSON does not permit infinities; these finite sentinels still cover every
        # value accepted by the bounded input contract.
        edges[0] = -1.0e308
        edges[-1] = 1.0e308
        counts, _ = np.histogram(column, bins=edges)
        proportions = counts / max(int(np.sum(counts)), 1)
        result[name] = {
            "edges": [float(value) for value in edges],
            "proportions": [float(value) for value in proportions],
        }
    return result
