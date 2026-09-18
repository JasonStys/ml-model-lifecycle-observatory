"""File: data.py
Purpose: Generate, persist, hash, load, and split a deterministic synthetic service-health dataset.
Symbols and line locations: see docs/code-index.md; BASE_TIME and SPLIT_RATIOS define
reproducibility.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from ml_observatory.hashing import atomic_write, canonical_json_bytes, sha256_bytes
from ml_observatory.schemas import DatasetRecord

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)
SPLIT_RATIOS = (0.70, 0.15, 0.15)
MIN_GENERATED_RECORDS = 200
MIN_SPLIT_RECORDS = 20


@dataclass(frozen=True, slots=True)
class DatasetSplits:
    """Non-overlapping, reproducible training, calibration, and test partitions."""

    train: tuple[DatasetRecord, ...]
    calibration: tuple[DatasetRecord, ...]
    test: tuple[DatasetRecord, ...]


def _sigmoid(value: float) -> float:
    """Evaluate a numerically stable scalar logistic function."""

    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1.0 + exp_value)


def generate_dataset(count: int = 2_400, seed: int = 20260917) -> tuple[DatasetRecord, ...]:
    """Create labeled service observations containing controlled nonlinear risk signals."""

    if count < MIN_GENERATED_RECORDS:
        raise ValueError("count must be at least 200 for stable three-way evaluation")
    random = np.random.default_rng(seed)
    regions = ("americas", "emea", "apac")
    tiers = ("critical", "standard", "batch")
    records: list[DatasetRecord] = []
    for index in range(count):
        region = regions[index % len(regions)]
        service_tier = tiers[(index // len(regions)) % len(tiers)]
        request_rate = max(1.0, float(random.lognormal(5.3, 0.75)))
        cpu_percent = float(np.clip(random.normal(52.0, 19.0), 3.0, 99.5))
        memory_percent = float(np.clip(random.normal(58.0, 17.0), 4.0, 99.5))
        error_rate = float(np.clip(random.beta(1.3, 22.0), 0.0, 0.65))
        latency_base = 45.0 + request_rate * 0.18 + cpu_percent * 1.4
        p95_latency_ms = float(np.clip(random.normal(latency_base, 55.0), 4.0, 8_000.0))
        deploy_age_hours = float(np.clip(random.exponential(96.0), 0.0, 2_000.0))
        change_failure_rate = float(np.clip(random.beta(1.7, 9.0), 0.0, 1.0))
        saturation_lambda = max(0.1, (cpu_percent - 58.0) / 12.0 + error_rate * 12.0)
        saturation_events = int(random.poisson(saturation_lambda))
        nonlinear_pressure = max(cpu_percent - 82.0, 0.0) * max(memory_percent - 80.0, 0.0)
        tier_effect = {"critical": 0.35, "standard": 0.0, "batch": -0.20}[service_tier]
        region_effect = {"americas": 0.0, "emea": 0.08, "apac": -0.05}[region]
        score = (
            -5.0
            + error_rate * 24.0
            + p95_latency_ms / 550.0
            + max(cpu_percent - 62.0, 0.0) / 13.0
            + max(memory_percent - 70.0, 0.0) / 20.0
            + change_failure_rate * 3.0
            + saturation_events * 0.30
            + nonlinear_pressure / 550.0
            + tier_effect
            + region_effect
        )
        outcome = int(random.random() < _sigmoid(score))
        records.append(
            DatasetRecord(
                row_id=f"row-{index:06d}",
                service_id=f"svc-{index % 120:03d}",
                observed_at=BASE_TIME + timedelta(minutes=15 * index),
                request_rate=round(request_rate, 6),
                p95_latency_ms=round(p95_latency_ms, 6),
                error_rate=round(error_rate, 8),
                cpu_percent=round(cpu_percent, 6),
                memory_percent=round(memory_percent, 6),
                deploy_age_hours=round(deploy_age_hours, 6),
                change_failure_rate=round(change_failure_rate, 8),
                saturation_events_15m=saturation_events,
                region=region,
                service_tier=service_tier,
                service_failure_24h=outcome,
            )
        )
    return tuple(records)


def dataset_payload(records: Sequence[DatasetRecord]) -> bytes:
    """Return canonical JSON Lines with a terminal newline for stable snapshots."""

    rows = [canonical_json_bytes(record.model_dump(mode="json")) for record in records]
    return b"\n".join(rows) + b"\n"


def write_dataset(path: Path, records: Sequence[DatasetRecord]) -> str:
    """Persist a dataset atomically and return its content digest."""

    payload = dataset_payload(records)
    atomic_write(path, payload)
    return sha256_bytes(payload)


def read_dataset(path: Path) -> tuple[DatasetRecord, ...]:
    """Load and validate each non-empty JSON Lines record."""

    records: list[DatasetRecord] = []
    with path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                records.append(DatasetRecord.model_validate_json(line))
            except ValueError as error:
                raise ValueError(f"invalid dataset row {line_number}: {error}") from error
    if not records:
        raise ValueError("dataset is empty")
    return tuple(records)


def split_dataset(records: Sequence[DatasetRecord], seed: int = 20260917) -> DatasetSplits:
    """Stratify deterministic partitions while preserving a locked final test set."""

    if len(records) < MIN_SPLIT_RECORDS:
        raise ValueError("at least 20 records are required")
    by_label: dict[int, list[DatasetRecord]] = {0: [], 1: []}
    for record in records:
        by_label[record.service_failure_24h].append(record)
    if not all(by_label.values()):
        raise ValueError("both outcome classes are required")
    random = np.random.default_rng(seed)
    partitions: list[list[DatasetRecord]] = [[], [], []]
    for label_records in by_label.values():
        indexes = random.permutation(len(label_records))
        first = int(len(indexes) * SPLIT_RATIOS[0])
        second = first + int(len(indexes) * SPLIT_RATIOS[1])
        for partition, selected in zip(
            partitions,
            (indexes[:first], indexes[first:second], indexes[second:]),
            strict=True,
        ):
            partition.extend(label_records[int(index)] for index in selected)
    for partition in partitions:
        partition.sort(key=lambda record: record.row_id)
    return DatasetSplits(*(tuple(partition) for partition in partitions))


def records_to_arrays(records: Iterable[DatasetRecord]) -> tuple[np.ndarray, np.ndarray]:
    """Convert validated rows to dense numeric features and integer labels."""

    materialized = tuple(records)
    if not materialized:
        raise ValueError("records cannot be empty")
    features = np.asarray([record.feature_vector() for record in materialized], dtype=np.float64)
    labels = np.asarray([record.service_failure_24h for record in materialized], dtype=np.int64)
    return features, labels


def dataset_metadata(records: Sequence[DatasetRecord], digest: str) -> dict[str, object]:
    """Describe data provenance, class balance, and collection bounds."""

    positives = sum(record.service_failure_24h for record in records)
    return {
        "schema_version": 1,
        "generator": "ml_observatory.data.generate_dataset",
        "record_count": len(records),
        "positive_count": positives,
        "positive_rate": positives / len(records),
        "observed_from": min(record.observed_at for record in records).isoformat(),
        "observed_through": max(record.observed_at for record in records).isoformat(),
        "sha256": digest,
        "synthetic": True,
    }


def write_metadata(path: Path, metadata: dict[str, object]) -> None:
    """Persist dataset metadata in canonical, reviewable JSON."""

    atomic_write(path, canonical_json_bytes(metadata) + b"\n")
