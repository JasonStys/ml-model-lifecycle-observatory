"""File: test_training_artifacts.py
Purpose: Verify model quality, reproducibility, portable inference, and artifact integrity failures.
Symbols and line locations: see docs/code-index.md; tests reject executable or malformed artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import TrainedSystem

from ml_observatory.artifacts import PortableModel, load_artifact, write_artifact
from ml_observatory.data import split_dataset
from ml_observatory.hashing import canonical_json_bytes, resolve_within, sha256_bytes, sha256_file
from ml_observatory.schemas import Observation
from ml_observatory.training import select_candidate, train_candidates


def _observation(trained_system: TrainedSystem) -> Observation:
    """Return an unlabeled validated observation from the shared fixture."""

    record = trained_system.records[0]
    return Observation.model_validate(record.model_dump(exclude={"row_id", "service_failure_24h"}))


def test_candidates_meet_gates_and_linear_model_wins_fixture(
    trained_system: TrainedSystem,
) -> None:
    """Both candidates are measured while only eligible lowest-Brier evidence is selected."""

    assert {candidate.algorithm for candidate in trained_system.candidates} == {
        "logistic-regression",
        "compact-mlp",
    }
    selected = select_candidate(trained_system.candidates)
    assert selected.algorithm == "logistic-regression"
    assert selected.metrics["roc_auc"] >= 0.68
    assert selected.metrics["recall"] > 0.40
    assert selected.metrics["maximum_subgroup_recall_gap"] <= 0.40


def test_training_is_reproducible(trained_system: TrainedSystem) -> None:
    """The same data, split, seed, and dependency versions produce identical documents."""

    repeated = train_candidates(
        split_dataset(trained_system.records),
        trained_system.dataset_sha256,
    )
    assert [candidate.document for candidate in repeated] == [
        candidate.document for candidate in trained_system.candidates
    ]


def test_portable_models_load_and_return_bounded_decisions(
    trained_system: TrainedSystem,
) -> None:
    """Every written candidate can run pure-numeric inference with explicit abstention."""

    observation = _observation(trained_system)
    for bundle in trained_system.bundles.values():
        model = load_artifact(trained_system.artifact_root, bundle.artifact_sha256)
        probability = model.predict_probability(observation)
        assert 0.0 <= probability <= 1.0
        assert model.decision(probability) in {"likely-stable", "likely-failure", "abstain"}
        assert model.decision(model.threshold) == "abstain"
        assert model.decision(0.0) == "likely-stable"
        assert model.decision(1.0) == "likely-failure"


def test_artifact_write_is_content_addressed_and_idempotent(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Equal model documents produce one digest directory and verified manifest."""

    document = trained_system.candidates[0].document
    first = write_artifact(tmp_path, document)
    second = write_artifact(tmp_path, document)
    assert first == second
    assert sha256_file(first.model_path) == first.artifact_sha256
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["model_sha256"] == first.artifact_sha256
    assert sha256_bytes(canonical_json_bytes(document) + b"\n") == first.artifact_sha256


def test_artifact_loader_rejects_identity_tampering_and_paths(
    tmp_path: Path,
    trained_system: TrainedSystem,
) -> None:
    """Digest, manifest, and root-containment checks fail closed."""

    bundle = write_artifact(tmp_path, trained_system.candidates[0].document)
    bundle.model_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash verification"):
        load_artifact(tmp_path, bundle.artifact_sha256)
    with pytest.raises(ValueError, match="64 lowercase"):
        load_artifact(tmp_path, "invalid")
    with pytest.raises(ValueError, match="escapes"):
        resolve_within(tmp_path, tmp_path / ".." / "escape")


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"schema_version": 2}, "schema version"),
        ({"feature_names": ["wrong"]}, "feature contract"),
        ({"scaler": {"mean": [0.0], "scale": [1.0]}}, "scaler dimensions"),
        (
            {"network": {"weights": [], "biases": [], "activations": []}},
            "layers are inconsistent",
        ),
    ],
)
def test_portable_model_rejects_malformed_documents(
    mutation: dict[str, object],
    message: str,
    trained_system: TrainedSystem,
) -> None:
    """Schema and dimension validation runs before malformed parameters can execute."""

    document = json.loads(json.dumps(trained_system.candidates[0].document))
    document.update(mutation)
    with pytest.raises(ValueError, match=message):
        PortableModel(document, "0" * 64)


def test_portable_model_rejects_nonfinite_and_bad_thresholds(
    trained_system: TrainedSystem,
) -> None:
    """NaN parameters, unsupported activations, and incoherent decisions fail closed."""

    document = json.loads(json.dumps(trained_system.candidates[0].document))
    document["scaler"]["scale"][0] = 0.0
    with pytest.raises(ValueError, match="positive"):
        PortableModel(document, "0" * 64)
    document = json.loads(json.dumps(trained_system.candidates[0].document))
    document["network"]["activations"][0] = "unsafe"
    with pytest.raises(ValueError, match="unsupported"):
        PortableModel(document, "0" * 64)
    document = json.loads(json.dumps(trained_system.candidates[0].document))
    document["decision"] = {"threshold": 0.5, "abstention_band": [0.6, 0.7]}
    with pytest.raises(ValueError, match="threshold"):
        PortableModel(document, "0" * 64)
    document = json.loads(json.dumps(trained_system.candidates[0].document))
    document["network"]["weights"][0][0][0] = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        PortableModel(document, "0" * 64)


def test_select_candidate_rejects_ineligible_models(trained_system: TrainedSystem) -> None:
    """Promotion selection stops when every candidate violates a quality gate."""

    ineligible = tuple(
        candidate.__class__(
            algorithm=candidate.algorithm,
            document=candidate.document,
            metrics={**candidate.metrics, "roc_auc": 0.5},
        )
        for candidate in trained_system.candidates
    )
    with pytest.raises(ValueError, match="no candidate"):
        select_candidate(ineligible)
