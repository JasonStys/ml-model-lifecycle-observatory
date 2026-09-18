"""File: test_data_schemas.py
Purpose: Verify deterministic data generation, strict validation, persistence,
metadata, and splits.
Symbols and line locations: see docs/code-index.md; tests cover the input and
dataset trust boundary.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from ml_observatory.data import (
    dataset_metadata,
    dataset_payload,
    generate_dataset,
    read_dataset,
    records_to_arrays,
    split_dataset,
    write_dataset,
    write_metadata,
)
from ml_observatory.schemas import FEATURE_NAMES, DatasetRecord, Observation, PredictRequest


def test_generation_is_deterministic_and_seed_sensitive() -> None:
    """The same seed is byte-identical while a different seed changes the snapshot."""

    first = generate_dataset(240, seed=7)
    second = generate_dataset(240, seed=7)
    different = generate_dataset(240, seed=8)
    assert dataset_payload(first) == dataset_payload(second)
    assert dataset_payload(first) != dataset_payload(different)
    assert 0.05 < sum(row.service_failure_24h for row in first) / len(first) < 0.50


def test_generation_and_split_reject_insufficient_or_one_class_data() -> None:
    """Small or one-class datasets cannot silently produce misleading evaluations."""

    with pytest.raises(ValueError, match="at least 200"):
        generate_dataset(199)
    records = generate_dataset(240)
    with pytest.raises(ValueError, match="at least 20"):
        split_dataset(records[:19])
    one_class = tuple(record.model_copy(update={"service_failure_24h": 0}) for record in records)
    with pytest.raises(ValueError, match="both outcome classes"):
        split_dataset(one_class)


def test_split_is_stratified_reproducible_and_disjoint() -> None:
    """Locked partitions retain both outcomes without row overlap."""

    records = generate_dataset(600)
    first = split_dataset(records, seed=42)
    second = split_dataset(records, seed=42)
    assert first == second
    identifiers = [
        {row.row_id for row in first.train},
        {row.row_id for row in first.calibration},
        {row.row_id for row in first.test},
    ]
    assert not identifiers[0] & identifiers[1]
    assert not identifiers[0] & identifiers[2]
    assert not identifiers[1] & identifiers[2]
    assert sum(map(len, identifiers)) == len(records)
    for partition in (first.train, first.calibration, first.test):
        assert {row.service_failure_24h for row in partition} == {0, 1}


def test_dataset_round_trip_metadata_and_arrays(tmp_path: Path) -> None:
    """JSON Lines, digest metadata, and numeric feature order remain consistent."""

    records = generate_dataset(240)
    dataset_path = tmp_path / "nested" / "dataset.jsonl"
    digest = write_dataset(dataset_path, records)
    loaded = read_dataset(dataset_path)
    assert loaded == records
    metadata = dataset_metadata(loaded, digest)
    metadata_path = tmp_path / "metadata.json"
    write_metadata(metadata_path, metadata)
    assert digest in metadata_path.read_text(encoding="utf-8")
    features, labels = records_to_arrays(loaded)
    assert features.shape == (240, len(FEATURE_NAMES))
    assert labels.shape == (240,)
    assert features[0].tolist() == records[0].feature_vector()
    with pytest.raises(ValueError, match="cannot be empty"):
        records_to_arrays(())


def test_dataset_reader_reports_empty_and_malformed_rows(tmp_path: Path) -> None:
    """Bad fixtures identify their physical row instead of leaking parser internals."""

    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="dataset is empty"):
        read_dataset(empty)
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="row 1"):
        read_dataset(malformed)


def test_observation_contract_rejects_ambiguous_and_extra_input() -> None:
    """Online inputs require timezones, stable identifiers, bounds, and no unknown fields."""

    record = generate_dataset(200)[0]
    payload = record.model_dump(exclude={"row_id", "service_failure_24h"})
    payload["observed_at"] = datetime(2026, 1, 1)
    with pytest.raises(ValidationError, match="timezone"):
        Observation.model_validate(payload)
    payload["observed_at"] = "2026-01-01T00:00:00Z"
    payload["unknown"] = True
    with pytest.raises(ValidationError, match="extra"):
        Observation.model_validate(payload)
    payload.pop("unknown")
    payload["cpu_percent"] = 101
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_prediction_request_and_dataset_identifiers_are_strict() -> None:
    """Routing and row identifiers reject whitespace and malformed values."""

    record = generate_dataset(200)[0]
    observation = Observation.model_validate(
        record.model_dump(exclude={"row_id", "service_failure_24h"})
    )
    with pytest.raises(ValidationError):
        PredictRequest(request_id="bad id", observation=observation)
    with pytest.raises(ValidationError):
        DatasetRecord.model_validate({**record.model_dump(), "row_id": "unsafe"})
