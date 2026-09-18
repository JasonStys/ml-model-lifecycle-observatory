"""File: conftest.py
Purpose: Build deterministic shared model artifacts and isolated registries for the test suite.
Symbols and line locations: see docs/code-index.md; TrainedSystem prevents duplicate training work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from ml_observatory.artifacts import ArtifactBundle, write_artifact
from ml_observatory.data import dataset_payload, generate_dataset, split_dataset
from ml_observatory.hashing import sha256_bytes
from ml_observatory.registry import Registry
from ml_observatory.schemas import DatasetRecord
from ml_observatory.training import Candidate, select_candidate, train_candidates


@dataclass(frozen=True, slots=True)
class TrainedSystem:
    """Shared deterministic data, candidates, and content-addressed bundles."""

    records: tuple[DatasetRecord, ...]
    candidates: tuple[Candidate, Candidate]
    bundles: dict[str, ArtifactBundle]
    artifact_root: Path
    dataset_sha256: str


@pytest.fixture(scope="session")
def trained_system(tmp_path_factory: pytest.TempPathFactory) -> TrainedSystem:
    """Train both candidates once and store verified artifacts for all tests."""

    root = tmp_path_factory.mktemp("trained-system")
    artifact_root = root / "models"
    records = generate_dataset(count=1_200)
    dataset_sha256 = sha256_bytes(dataset_payload(records))
    candidates = train_candidates(split_dataset(records), dataset_sha256)
    bundles = {
        candidate.algorithm: write_artifact(artifact_root, candidate.document)
        for candidate in candidates
    }
    return TrainedSystem(records, candidates, bundles, artifact_root, dataset_sha256)


@pytest.fixture
def deployed_registry(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> tuple[Registry, str, str]:
    """Register two models and activate a champion plus ten-percent challenger."""

    registry = Registry(tmp_path / "registry.sqlite3")
    registry.initialize()
    identifiers: dict[str, str] = {}
    for candidate in trained_system.candidates:
        model = registry.register(
            trained_system.bundles[candidate.algorithm],
            algorithm=candidate.algorithm,
            dataset_sha256=trained_system.dataset_sha256,
            metrics=candidate.metrics,
        )
        identifiers[candidate.algorithm] = model.model_id
    selected = select_candidate(trained_system.candidates)
    challenger = next(
        candidate
        for candidate in trained_system.candidates
        if candidate.algorithm != selected.algorithm
    )
    registry.promote(identifiers[selected.algorithm])
    registry.assign_challenger(identifiers[challenger.algorithm], traffic_percent=10)
    return registry, identifiers[selected.algorithm], identifiers[challenger.algorithm]
