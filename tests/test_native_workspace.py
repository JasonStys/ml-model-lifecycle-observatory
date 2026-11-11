"""File: test_native_workspace.py
Purpose: Exercise genuine model-workbench data/registry operations with independent boundary
oracles.
Symbols and variables: see docs/code-index.md; only temporary fictional profiles are used.
"""

import json
from pathlib import Path

import pytest

from desktop.workspace import Workspace, export_new, parse_dataset, read_regular, strict_json


def test_actual_profile_lock_restart_and_unknown_directory(tmp_path: Path) -> None:
    """An identified registry reopens; a second owner and unknown user files are never adopted."""
    directory = tmp_path / "profile"
    first = Workspace(directory)
    marker = (directory / "profile.json").read_bytes()
    try:
        with pytest.raises((OSError, ValueError)):
            Workspace(directory)
        assert first.models() == []
    finally:
        first.close()
    second = Workspace(directory)
    assert second.models() == []
    assert (directory / "profile.json").read_bytes() == marker
    second.close()
    with pytest.raises(ValueError, match="closed"):
        second.models()
    unknown = tmp_path / "important"
    unknown.mkdir()
    (unknown / "preserve.txt").write_text("unchanged fictional bytes")
    with pytest.raises(FileNotFoundError):
        Workspace(unknown)
    assert list(unknown.iterdir()) == [unknown / "preserve.txt"]


@pytest.mark.parametrize("value", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":1e999}'])
def test_ambiguous_or_nonfinite_json_is_rejected(value: str) -> None:
    """Independent literal fixtures must fail, not merely produce self-consistent bad output."""
    with pytest.raises(ValueError):
        strict_json(value)


def test_dataset_validation_precedes_any_training_or_registry_mutation(tmp_path: Path) -> None:
    """Prepared input remains editable; malformed, duplicate and too-small inputs leave the
    registry empty."""
    workspace = Workspace(tmp_path / "profile")
    try:
        text = workspace.prepare(400, 20260917)
        records = parse_dataset(text)
        assert len(records) == 400
        assert {record.service_failure_24h for record in records} == {0, 1}
        assert not workspace.dataset.exists() and workspace.models() == []
        for bad in (
            "",
            text.splitlines()[0],
            text.replace("row-000001", "row-000000"),
            text + "[]",
        ):
            with pytest.raises(ValueError):
                workspace.train(bad, 20260917)
            assert workspace.models() == [] and not workspace.dataset.exists()
        for count, seed in [(True, 2), (399, 2), (4001, 2), (400, -1), (400, True)]:
            with pytest.raises(ValueError):
                workspace.prepare(count, seed)
    finally:
        workspace.close()


def test_actual_models_review_explicit_promotion_prediction_drift_and_durable_restart(  # noqa: PLR0915
    tmp_path: Path,
) -> None:
    """Train both original algorithms; prove no automatic promotion, real prediction and retained
    deployment."""
    directory = tmp_path / "profile"
    workspace = Workspace(directory)
    try:
        text = workspace.prepare(1200, 20260917)
        models = workspace.train(text, 20260917)
        assert len(models) == 2 and {item["algorithm"] for item in models} == {
            "logistic-regression",
            "compact-mlp",
        }
        assert {item["status"] for item in workspace.models()} == {"candidate"}
        assert all("artifact_path" not in item for item in models)
        dossiers = [workspace.review(item["model_id"]) for item in models]
        assert all(item["provenance_verified"] for item in dossiers)
        assert all(not item["dataset_bytes_verified"] for item in dossiers)
        eligible = next(item for item in dossiers if item["eligible_on_recorded_quality"])
        model_id = eligible["model_id"]
        first = parse_dataset(text)[0].model_dump(
            mode="json", exclude={"row_id", "service_failure_24h"}
        )
        with pytest.raises(RuntimeError):
            workspace.predict(json.dumps(first))
        with pytest.raises(ValueError):
            workspace.promote(model_id, "short")
        assert {item["status"] for item in workspace.models()} == {"candidate"}
        promoted = workspace.promote(
            model_id, "Reviewed synthetic quality and original data provenance"
        )
        assert promoted["status"] == "champion"
        challenger = next(item["model_id"] for item in models if item["model_id"] != model_id)
        workspace.challenger(challenger, 0)
        prediction = workspace.predict(json.dumps(first))
        assert (
            prediction["model_id"] == model_id and prediction["challenger_model_id"] == challenger
        )
        assert 0 <= prediction["failure_probability"] <= 1
        drift = workspace.drift(model_id, text)
        assert drift["sample_count"] == 1200 and len(drift["features"]) == 8
        with pytest.raises(ValueError):
            workspace.challenger(challenger, 51)
        export = tmp_path / "new-evidence.json"
        export_new(export, promoted)
        original = export.read_bytes()
        with pytest.raises(FileExistsError):
            export_new(export, {"must": "not overwrite"})
        assert export.read_bytes() == original
        workspace.promote(challenger, "Reviewed the second real candidate before comparison")
        prior_record = workspace.registry.get_model(model_id)
        prior_file = workspace.artifacts / prior_record.artifact_sha256 / "model.json"
        valid_bytes = prior_file.read_bytes()
        prior_file.write_bytes(b"corrupt synthetic test bytes")
        with pytest.raises(ValueError):
            workspace.rollback("Check the actual prior artifact before changing state")
        assert workspace.registry.deployment_snapshot().champion.model_id == challenger
        prior_file.write_bytes(valid_bytes)
        assert workspace.rollback("Restore the verified prior synthetic champion") == model_id
    finally:
        workspace.close()
    reopened = Workspace(directory)
    try:
        assert len(reopened.models()) == 2
        assert reopened.review(model_id)["status"] == "champion"
        assert len(parse_dataset(read_regular(reopened.dataset).decode())) == 1200
    finally:
        reopened.close()


def test_descriptor_budget_and_hardlink_refusal(tmp_path: Path) -> None:
    """Actual bytes and hardlink aliases fail before import, without overwriting their source."""
    path = tmp_path / "data"
    path.write_bytes(b"abcd")
    assert read_regular(path, 4) == b"abcd"
    with pytest.raises(ValueError):
        read_regular(path, 3)
    link = tmp_path / "alias"
    link.hardlink_to(path)
    with pytest.raises(ValueError):
        read_regular(path)
    assert path.read_bytes() == b"abcd"
