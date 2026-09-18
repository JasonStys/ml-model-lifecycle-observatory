"""File: service.py
Purpose: Serve verified champions, shadow challengers, deterministic canaries, and prediction
provenance.
Symbols and line locations: see docs/code-index.md; ModelService owns the trusted runtime cache.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from ml_observatory.artifacts import PortableModel, load_artifact
from ml_observatory.registry import ModelRecord, Registry
from ml_observatory.schemas import PredictionResponse, PredictRequest


class ModelService:
    """Coordinate registry state with a digest-keyed, integrity-checked model cache."""

    def __init__(self, registry: Registry, artifact_root: Path) -> None:
        """Bind service dependencies while deferring model loading until a request arrives."""

        self.registry = registry
        self.artifact_root = artifact_root
        self._cache: dict[str, PortableModel] = {}

    def _model(self, record: ModelRecord) -> PortableModel:
        """Load and cache only artifacts whose digest and schema have been verified."""

        if record.artifact_sha256 not in self._cache:
            self._cache[record.artifact_sha256] = load_artifact(
                self.artifact_root, record.artifact_sha256
            )
        return self._cache[record.artifact_sha256]

    @staticmethod
    def _canary_selected(request_id: str, traffic_percent: int) -> bool:
        """Map a stable request identifier to one of one hundred traffic buckets."""

        bucket = (
            int.from_bytes(hashlib.sha256(request_id.encode("utf-8")).digest()[:4], "big") % 100
        )
        return bucket < traffic_percent

    def predict(self, request: PredictRequest) -> PredictionResponse:
        """Evaluate champion and challenger, choose the served model, and record provenance."""

        started = time.perf_counter()
        deployment = self.registry.deployment_snapshot()
        champion_model = self._model(deployment.champion)
        champion_probability = champion_model.predict_probability(request.observation)
        challenger_probability: float | None = None
        served_record = deployment.champion
        served_model = champion_model
        if deployment.challenger is not None:
            challenger_model = self._model(deployment.challenger)
            challenger_probability = challenger_model.predict_probability(request.observation)
            if self._canary_selected(request.request_id, deployment.challenger_traffic_percent):
                served_record = deployment.challenger
                served_model = challenger_model
        served_probability = (
            challenger_probability
            if served_record == deployment.challenger
            else champion_probability
        )
        if served_probability is None:
            raise RuntimeError("selected model did not produce a probability")
        decision = served_model.decision(served_probability)
        elapsed_ms = (time.perf_counter() - started) * 1_000.0
        self.registry.record_prediction(
            request_id=request.request_id,
            served_model_id=served_record.model_id,
            champion_probability=champion_probability,
            challenger_probability=challenger_probability,
            decision=decision,
            latency_ms=elapsed_ms,
        )
        return PredictionResponse(
            request_id=request.request_id,
            model_id=served_record.model_id,
            model_sha256=served_record.artifact_sha256,
            failure_probability=served_probability,
            decision=decision,
            threshold=served_model.threshold,
            abstention_band=served_model.abstention_band,
            challenger_model_id=(
                deployment.challenger.model_id if deployment.challenger is not None else None
            ),
            challenger_probability=challenger_probability,
        )
