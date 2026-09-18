"""File: schemas.py
Purpose: Define strict contracts for synthetic observations, predictions, and monitoring reports.
Symbols and line locations: see docs/code-index.md; FEATURE_NAMES fixes model input order.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FEATURE_NAMES = (
    "request_rate",
    "p95_latency_ms",
    "error_rate",
    "cpu_percent",
    "memory_percent",
    "deploy_age_hours",
    "change_failure_rate",
    "saturation_events_15m",
)
Region = Literal["americas", "emea", "apac"]
ServiceTier = Literal["critical", "standard", "batch"]


class Observation(BaseModel):
    """Validated service-health snapshot used for training and online prediction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    service_id: Annotated[str, Field(pattern=r"^svc-[a-z0-9-]{3,40}$")]
    observed_at: datetime
    request_rate: Annotated[float, Field(ge=0.0, le=1_000_000.0)]
    p95_latency_ms: Annotated[float, Field(ge=0.0, le=120_000.0)]
    error_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    cpu_percent: Annotated[float, Field(ge=0.0, le=100.0)]
    memory_percent: Annotated[float, Field(ge=0.0, le=100.0)]
    deploy_age_hours: Annotated[float, Field(ge=0.0, le=87_600.0)]
    change_failure_rate: Annotated[float, Field(ge=0.0, le=1.0)]
    saturation_events_15m: Annotated[int, Field(ge=0, le=10_000)]
    region: Region
    service_tier: ServiceTier

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous timestamps and normalize accepted values to UTC."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(UTC)

    def feature_vector(self) -> list[float]:
        """Return numeric features in the immutable model-contract order."""

        return [float(getattr(self, name)) for name in FEATURE_NAMES]


class DatasetRecord(Observation):
    """Synthetic labeled row with a stable identifier and binary outcome."""

    row_id: Annotated[str, Field(pattern=r"^row-[0-9]{6}$")]
    service_failure_24h: Literal[0, 1]


class PredictRequest(BaseModel):
    """Online prediction request with an idempotent routing key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: Annotated[str, Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
    observation: Observation


class PredictionResponse(BaseModel):
    """Prediction result with provenance, abstention, and optional shadow evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    model_id: str
    model_sha256: str
    failure_probability: float
    decision: Literal["likely-stable", "likely-failure", "abstain"]
    threshold: float
    abstention_band: tuple[float, float]
    challenger_model_id: str | None = None
    challenger_probability: float | None = None


class DriftFeature(BaseModel):
    """Population-stability result for one numeric input feature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    feature: str
    psi: float
    level: Literal["stable", "warning", "critical"]


class DriftReport(BaseModel):
    """Aggregate drift result with explicit thresholds and sample size."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_sha256: str
    sample_count: int
    warning_threshold: float
    critical_threshold: float
    overall_level: Literal["stable", "warning", "critical"]
    features: tuple[DriftFeature, ...]
