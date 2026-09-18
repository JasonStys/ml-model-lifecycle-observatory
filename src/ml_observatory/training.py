"""File: training.py
Purpose: Train, calibrate, compare, and serialize deterministic linear and neural candidates.
Symbols and line locations: see docs/code-index.md; Candidate and train_candidates define the
pipeline.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Protocol, cast

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from ml_observatory.data import DatasetSplits, records_to_arrays
from ml_observatory.evaluation import (
    abstention_band,
    binary_metrics,
    choose_decision_threshold,
    reference_histograms,
    subgroup_metrics,
)
from ml_observatory.schemas import FEATURE_NAMES

MINIMUM_AUC = 0.68
MAXIMUM_RECALL_GAP = 0.40


class ProbabilisticEstimator(Protocol):
    """Narrow fitted-estimator interface used by the training pipeline."""

    def fit(self, features: np.ndarray, labels: np.ndarray) -> ProbabilisticEstimator:
        """Fit the estimator and return itself."""

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Return two-column class probabilities."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """Portable candidate document and its independent test metrics."""

    algorithm: str
    document: dict[str, Any]
    metrics: dict[str, Any]


def _logit(probabilities: np.ndarray) -> np.ndarray:
    """Convert clipped probabilities to finite log odds."""

    clipped = np.clip(probabilities, 1e-7, 1.0 - 1e-7)
    return cast(np.ndarray, np.log(clipped / (1.0 - clipped)))


def _fit_calibrator(scores: np.ndarray, labels: np.ndarray, seed: int) -> tuple[float, float]:
    """Fit Platt-style sigmoid parameters on data disjoint from model fitting."""

    calibrator = LogisticRegression(C=1_000_000.0, solver="lbfgs", random_state=seed)
    calibrator.fit(scores.reshape(-1, 1), labels)
    return float(calibrator.coef_[0, 0]), float(calibrator.intercept_[0])


def _apply_calibrator(scores: np.ndarray, slope: float, intercept: float) -> np.ndarray:
    """Apply stable sigmoid calibration to a vector of raw scores."""

    values = np.clip(slope * scores + intercept, -40.0, 40.0)
    return cast(np.ndarray, np.asarray(1.0 / (1.0 + np.exp(-values)), dtype=np.float64))


def _json_matrix(matrix: np.ndarray) -> list[list[float]]:
    """Round a two-dimensional parameter array for stable portable artifacts."""

    return [[round(float(value), 15) for value in row] for row in matrix]


def _json_vector(vector: np.ndarray) -> list[float]:
    """Round a one-dimensional parameter array for stable portable artifacts."""

    return [round(float(value), 15) for value in vector]


def _candidate_document(  # noqa: PLR0913
    *,
    algorithm: str,
    estimator: LogisticRegression | MLPClassifier,
    scaler: StandardScaler,
    calibration: tuple[float, float],
    decision_threshold: float,
    metrics: dict[str, Any],
    dataset_sha256: str,
    seed: int,
    split_counts: dict[str, int],
    reference: dict[str, dict[str, list[float]]],
) -> dict[str, Any]:
    """Extract trusted numeric parameters rather than serializing executable Python objects."""

    if isinstance(estimator, LogisticRegression):
        layers = [_json_matrix(estimator.coef_.T)]
        biases = [_json_vector(estimator.intercept_)]
        activations = ["identity"]
    else:
        layers = [_json_matrix(layer) for layer in estimator.coefs_]
        biases = [_json_vector(layer) for layer in estimator.intercepts_]
        activations = ["relu"] * (len(layers) - 1) + ["identity"]
    slope, intercept = calibration
    return {
        "schema_version": 1,
        "artifact_type": "portable-binary-classifier",
        "algorithm": algorithm,
        "feature_names": list(FEATURE_NAMES),
        "scaler": {
            "mean": _json_vector(scaler.mean_),
            "scale": _json_vector(scaler.scale_),
        },
        "network": {
            "weights": layers,
            "biases": biases,
            "activations": activations,
        },
        "calibration": {
            "method": "platt-sigmoid",
            "slope": round(slope, 15),
            "intercept": round(intercept, 15),
        },
        "decision": {
            "threshold": decision_threshold,
            "abstention_band": list(abstention_band(decision_threshold)),
        },
        "evaluation": metrics,
        "reference_distribution": reference,
        "training": {
            "dataset_sha256": dataset_sha256,
            "random_seed": seed,
            "split_counts": split_counts,
            "numpy_version": version("numpy"),
            "scikit_learn_version": version("scikit-learn"),
        },
    }


def _train_one(
    *,
    algorithm: str,
    estimator: LogisticRegression | MLPClassifier,
    splits: DatasetSplits,
    dataset_sha256: str,
    seed: int,
) -> Candidate:
    """Fit one candidate, calibrate it, and evaluate once on the locked test split."""

    train_features, train_labels = records_to_arrays(splits.train)
    calibration_features, calibration_labels = records_to_arrays(splits.calibration)
    test_features, test_labels = records_to_arrays(splits.test)
    scaler = StandardScaler()
    scaled_train = scaler.fit_transform(train_features)
    estimator.fit(scaled_train, train_labels)
    calibration_probabilities = estimator.predict_proba(scaler.transform(calibration_features))[
        :, 1
    ]
    slope, intercept = _fit_calibrator(_logit(calibration_probabilities), calibration_labels, seed)
    calibrated_validation = _apply_calibrator(_logit(calibration_probabilities), slope, intercept)
    decision_threshold = choose_decision_threshold(calibration_labels, calibrated_validation)
    test_scores = _logit(estimator.predict_proba(scaler.transform(test_features))[:, 1])
    probabilities = _apply_calibrator(test_scores, slope, intercept)
    metrics: dict[str, Any] = binary_metrics(test_labels, probabilities, decision_threshold)
    metrics["subgroups"] = {
        "region": subgroup_metrics(
            test_labels,
            probabilities,
            [record.region for record in splits.test],
            decision_threshold,
        ),
        "service_tier": subgroup_metrics(
            test_labels,
            probabilities,
            [record.service_tier for record in splits.test],
            decision_threshold,
        ),
    }
    metrics["maximum_subgroup_recall_gap"] = max(
        metrics["subgroups"][name]["recall_gap"] for name in metrics["subgroups"]
    )
    document = _candidate_document(
        algorithm=algorithm,
        estimator=estimator,
        scaler=scaler,
        calibration=(slope, intercept),
        decision_threshold=decision_threshold,
        metrics=metrics,
        dataset_sha256=dataset_sha256,
        seed=seed,
        split_counts={
            "train": len(splits.train),
            "calibration": len(splits.calibration),
            "test": len(splits.test),
        },
        reference=reference_histograms(train_features, FEATURE_NAMES),
    )
    return Candidate(algorithm=algorithm, document=document, metrics=metrics)


def train_candidates(
    splits: DatasetSplits,
    dataset_sha256: str,
    seed: int = 20260917,
) -> tuple[Candidate, Candidate]:
    """Train a regularized linear baseline and a compact neural-network challenger."""

    linear = LogisticRegression(C=0.8, max_iter=1_000, random_state=seed, solver="lbfgs")
    neural = MLPClassifier(
        hidden_layer_sizes=(12,),
        activation="relu",
        solver="lbfgs",
        alpha=0.02,
        max_iter=1_500,
        random_state=seed,
    )
    return (
        _train_one(
            algorithm="logistic-regression",
            estimator=linear,
            splits=splits,
            dataset_sha256=dataset_sha256,
            seed=seed,
        ),
        _train_one(
            algorithm="compact-mlp",
            estimator=neural,
            splits=splits,
            dataset_sha256=dataset_sha256,
            seed=seed,
        ),
    )


def select_candidate(candidates: tuple[Candidate, ...]) -> Candidate:
    """Choose the lowest-Brier candidate that satisfies explicit quality gates."""

    eligible = [
        candidate
        for candidate in candidates
        if candidate.metrics["roc_auc"] >= MINIMUM_AUC
        and candidate.metrics["maximum_subgroup_recall_gap"] <= MAXIMUM_RECALL_GAP
        and math.isfinite(candidate.metrics["brier"])
    ]
    if not eligible:
        raise ValueError("no candidate satisfies the AUC and subgroup recall-gap gates")
    return min(eligible, key=lambda candidate: (candidate.metrics["brier"], candidate.algorithm))
