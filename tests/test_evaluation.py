"""File: test_evaluation.py
Purpose: Verify calibration, threshold, subgroup, histogram, and edge-case metric behavior.
Symbols and line locations: see docs/code-index.md; tests pin metric definitions used for promotion.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_observatory.evaluation import (
    abstention_band,
    binary_metrics,
    choose_decision_threshold,
    expected_calibration_error,
    reference_histograms,
    subgroup_metrics,
)


def test_calibration_error_and_threshold_selection_are_bounded() -> None:
    """Perfect confidence has no error and threshold optimization favors useful separation."""

    labels = np.asarray([0, 0, 1, 1])
    probabilities = np.asarray([0.01, 0.10, 0.70, 0.95])
    assert expected_calibration_error(labels, np.asarray([0.0, 0.0, 1.0, 1.0])) == 0.0
    threshold = choose_decision_threshold(labels, probabilities)
    assert 0.10 < threshold <= 0.70
    lower, upper = abstention_band(threshold)
    assert 0.0 <= lower < threshold < upper <= 1.0


def test_binary_metrics_include_ranking_calibration_and_selective_results() -> None:
    """The release metric set is finite and uses the caller's calibrated threshold."""

    labels = np.asarray([0, 0, 1, 1])
    probabilities = np.asarray([0.05, 0.25, 0.55, 0.95])
    metrics = binary_metrics(labels, probabilities, threshold=0.40)
    assert metrics["accuracy"] == 1.0
    assert metrics["roc_auc"] == 1.0
    assert metrics["decision_threshold"] == 0.40
    assert 0.0 <= metrics["coverage"] <= 1.0


@pytest.mark.parametrize(
    ("labels", "probabilities", "threshold", "message"),
    [
        (np.asarray([]), np.asarray([]), 0.5, "finite, non-empty"),
        (np.asarray([0, 1]), np.asarray([[0.1, 0.9]]), 0.5, "one-dimensional"),
        (np.asarray([0, 1]), np.asarray([0.1, 1.1]), 0.5, "within"),
        (np.asarray([0, 1]), np.asarray([0.1, 0.9]), 1.0, "between"),
    ],
)
def test_binary_metrics_reject_invalid_inputs(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    message: str,
) -> None:
    """Malformed metric inputs fail before reporting persuasive but invalid numbers."""

    with pytest.raises(ValueError, match=message):
        binary_metrics(labels, probabilities, threshold)
    with pytest.raises(ValueError, match="at least 2"):
        expected_calibration_error(np.asarray([0]), np.asarray([0.0]), bins=1)


def test_subgroup_metrics_report_gap_and_alignment_errors() -> None:
    """Subgroup support and recall disparity remain visible and aligned by row."""

    labels = np.asarray([0, 1, 0, 1])
    probabilities = np.asarray([0.1, 0.9, 0.8, 0.2])
    result = subgroup_metrics(labels, probabilities, ["a", "a", "b", "b"])
    assert result["groups"]["a"]["support"] == 2
    assert result["recall_gap"] == 1.0
    with pytest.raises(ValueError, match="align"):
        subgroup_metrics(labels, probabilities, ["a"])


def test_reference_histograms_cover_constant_and_variable_features() -> None:
    """Quantile references retain normalized mass even for constant columns."""

    features = np.asarray([[1.0, 4.0], [2.0, 4.0], [3.0, 4.0]])
    references = reference_histograms(features, ["variable", "constant"], bins=2)
    assert sum(references["variable"]["proportions"]) == pytest.approx(1.0)
    assert len(references["constant"]["edges"]) == 3
    with pytest.raises(ValueError, match="does not match"):
        reference_histograms(features, ["only-one"])
