"""File: artifacts.py
Purpose: Store and load content-addressed, non-executable JSON model bundles with integrity checks.
Symbols and line locations: see docs/code-index.md; ArtifactBundle and PortableModel form
the serving boundary.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ml_observatory.hashing import (
    atomic_write,
    canonical_json_bytes,
    resolve_within,
    sha256_bytes,
    sha256_file,
)
from ml_observatory.schemas import FEATURE_NAMES, Observation

MATRIX_DIMENSIONS = 2
SHA256_HEX_LENGTH = 64


@dataclass(frozen=True, slots=True)
class ArtifactBundle:
    """Verified model bundle identity and absolute model-document path."""

    artifact_sha256: str
    model_path: Path
    manifest_path: Path


class PortableModel:
    """Pure-NumPy inference runtime for reviewed linear and dense neural artifacts."""

    def __init__(self, document: dict[str, Any], artifact_sha256: str) -> None:
        """Validate the portable schema and materialize bounded numeric parameters."""

        if document.get("schema_version") != 1:
            raise ValueError("unsupported artifact schema version")
        if document.get("feature_names") != list(FEATURE_NAMES):
            raise ValueError("artifact feature contract does not match this runtime")
        scaler = document["scaler"]
        network = document["network"]
        self.algorithm = str(document["algorithm"])
        self.artifact_sha256 = artifact_sha256
        self.mean = np.asarray(scaler["mean"], dtype=np.float64)
        self.scale = np.asarray(scaler["scale"], dtype=np.float64)
        self.weights = tuple(np.asarray(layer, dtype=np.float64) for layer in network["weights"])
        self.biases = tuple(np.asarray(layer, dtype=np.float64) for layer in network["biases"])
        self.activations = tuple(str(value) for value in network["activations"])
        calibration = document["calibration"]
        self.calibration_slope = float(calibration["slope"])
        self.calibration_intercept = float(calibration["intercept"])
        decision = document["decision"]
        self.threshold = float(decision["threshold"])
        self.abstention_band = tuple(float(value) for value in decision["abstention_band"])
        self.reference_distribution = document["reference_distribution"]
        self._validate_shapes()

    def _validate_shapes(self) -> None:
        """Reject malformed, non-finite, or dimensionally inconsistent network parameters."""

        if self.mean.shape != (len(FEATURE_NAMES),) or self.scale.shape != self.mean.shape:
            raise ValueError("invalid scaler dimensions")
        if np.any(self.scale <= 0.0):
            raise ValueError("scaler values must be positive")
        if (
            not self.weights
            or len(self.weights) != len(self.biases)
            or len(self.weights) != len(self.activations)
        ):
            raise ValueError("network layers are inconsistent")
        previous = len(FEATURE_NAMES)
        arrays = [self.mean, self.scale, *self.weights, *self.biases]
        if not all(np.all(np.isfinite(array)) for array in arrays):
            raise ValueError("artifact contains non-finite parameters")
        for weights, bias, activation in zip(
            self.weights, self.biases, self.activations, strict=True
        ):
            if weights.ndim != MATRIX_DIMENSIONS or bias.ndim != 1:
                raise ValueError("network parameters must be dense matrices and vectors")
            if weights.shape[0] != previous or weights.shape[1] != bias.shape[0]:
                raise ValueError("network layer dimensions do not compose")
            if activation not in {"identity", "relu"}:
                raise ValueError("unsupported network activation")
            previous = weights.shape[1]
        if previous != 1:
            raise ValueError("binary classifier must have one output")
        lower, upper = self.abstention_band
        if not (0.0 <= lower < self.threshold < upper <= 1.0):
            raise ValueError("invalid decision or abstention thresholds")

    def predict_probability(self, observation: Observation) -> float:
        """Run bounded dense inference and return the calibrated failure probability."""

        values = (
            np.asarray(observation.feature_vector(), dtype=np.float64) - self.mean
        ) / self.scale
        activation = values.reshape(1, -1)
        for weights, bias, activation_name in zip(
            self.weights, self.biases, self.activations, strict=True
        ):
            activation = activation @ weights + bias
            if activation_name == "relu":
                activation = np.maximum(activation, 0.0)
        raw_score = float(activation[0, 0])
        calibrated_score = float(
            np.clip(
                self.calibration_slope * raw_score + self.calibration_intercept,
                -40.0,
                40.0,
            )
        )
        return 1.0 / (1.0 + math.exp(-calibrated_score))

    def decision(self, probability: float) -> str:
        """Map a probability to a transparent prediction or abstention outcome."""

        lower, upper = self.abstention_band
        if lower <= probability <= upper:
            return "abstain"
        return "likely-failure" if probability >= self.threshold else "likely-stable"


def write_artifact(root: Path, document: dict[str, Any]) -> ArtifactBundle:
    """Write a model and manifest beneath a directory named by the model digest."""

    payload = canonical_json_bytes(document) + b"\n"
    digest = sha256_bytes(payload)
    bundle_root = root / digest
    model_path = bundle_root / "model.json"
    manifest_path = bundle_root / "manifest.json"
    manifest = {
        "schema_version": 1,
        "artifact_sha256": digest,
        "model_file": "model.json",
        "model_sha256": digest,
        "algorithm": document["algorithm"],
        "dataset_sha256": document["training"]["dataset_sha256"],
    }
    atomic_write(model_path, payload)
    atomic_write(manifest_path, canonical_json_bytes(manifest) + b"\n")
    return ArtifactBundle(digest, model_path.resolve(), manifest_path.resolve())


def load_artifact(root: Path, artifact_sha256: str) -> PortableModel:
    """Verify digest, manifest, path containment, and schema before loading numeric data."""

    if len(artifact_sha256) != SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in artifact_sha256
    ):
        raise ValueError("artifact digest must be 64 lowercase hexadecimal characters")
    bundle_root = resolve_within(root, root / artifact_sha256)
    manifest_path = resolve_within(root, bundle_root / "manifest.json")
    model_path = resolve_within(root, bundle_root / "model.json")
    with manifest_path.open("r", encoding="utf-8") as source:
        manifest = json.load(source)
    if manifest.get("artifact_sha256") != artifact_sha256:
        raise ValueError("manifest identity does not match requested artifact")
    if manifest.get("model_file") != "model.json":
        raise ValueError("manifest model filename is not permitted")
    if sha256_file(model_path) != artifact_sha256:
        raise ValueError("model content hash verification failed")
    with model_path.open("r", encoding="utf-8") as source:
        document = json.load(source)
    return PortableModel(document, artifact_sha256)
