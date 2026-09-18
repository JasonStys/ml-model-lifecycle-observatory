"""File: api.py
Purpose: Expose health, prediction, registry, promotion, challenger, and rollback HTTP endpoints.
Symbols and line locations: see docs/code-index.md; create_app supports isolated integration tests.
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ml_observatory import VERSION
from ml_observatory.config import Settings
from ml_observatory.registry import Registry
from ml_observatory.schemas import PredictionResponse, PredictRequest
from ml_observatory.service import ModelService


class PromotionRequest(BaseModel):
    """Auditable operator reason supplied with a champion promotion."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    reason: Annotated[str, Field(min_length=3, max_length=200)] = "operator-approved"


class ChallengerRequest(BaseModel):
    """Bounded canary percentage for an already registered challenger."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    model_id: Annotated[str, Field(pattern=r"^mdl-[0-9a-f]{16}$")]
    traffic_percent: Annotated[int, Field(ge=0, le=50)] = 0


def create_app(settings: Settings | None = None) -> FastAPI:
    """Construct an application with explicit, testable registry and artifact dependencies."""

    runtime_settings = settings or Settings.from_environment()
    registry = Registry(runtime_settings.registry_path)
    registry.initialize()
    model_service = ModelService(registry, runtime_settings.artifact_root)
    application = FastAPI(
        title="ML Model Lifecycle Observatory",
        version=VERSION,
        description="Synthetic model lifecycle, drift, promotion, and rollback evidence.",
    )

    def require_admin(
        x_admin_token: Annotated[str | None, Header()] = None,
    ) -> None:
        """Protect state-changing demo endpoints with constant-time token comparison."""

        expected = runtime_settings.admin_token
        if (
            expected is None
            or x_admin_token is None
            or not hmac.compare_digest(expected, x_admin_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="a valid X-Admin-Token is required",
            )

    @application.get("/health/live", tags=["health"])
    def live() -> dict[str, str]:
        """Report process liveness without touching downstream state."""

        return {"status": "live", "version": VERSION}

    @application.get("/health/ready", tags=["health"])
    def ready() -> dict[str, str]:
        """Report readiness only when a verified champion can be located."""

        try:
            deployment = registry.deployment_snapshot()
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
            ) from error
        return {"status": "ready", "champion_model_id": deployment.champion.model_id}

    @application.post("/v1/predict", response_model=PredictionResponse, tags=["inference"])
    def predict(request: PredictRequest) -> PredictionResponse:
        """Return a provenance-rich prediction or a readiness error."""

        try:
            return model_service.predict(request)
        except RuntimeError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
            ) from error

    @application.get("/v1/models", tags=["registry"])
    def models() -> list[dict[str, object]]:
        """List registered model identity, status, provenance, and evaluation metrics."""

        return [
            {
                "model_id": model.model_id,
                "artifact_sha256": model.artifact_sha256,
                "algorithm": model.algorithm,
                "dataset_sha256": model.dataset_sha256,
                "status": model.status,
                "metrics": model.metrics,
                "created_at": model.created_at,
            }
            for model in registry.list_models()
        ]

    @application.post(
        "/v1/admin/models/{model_id}/promote",
        dependencies=[Depends(require_admin)],
        tags=["administration"],
    )
    def promote(model_id: str, request: PromotionRequest) -> dict[str, str]:
        """Promote a registered model under a transaction and immutable audit record."""

        try:
            registry.promote(model_id, reason=request.reason)
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="model not found"
            ) from error
        return {"status": "promoted", "model_id": model_id}

    @application.post(
        "/v1/admin/challenger",
        dependencies=[Depends(require_admin)],
        tags=["administration"],
    )
    def challenger(request: ChallengerRequest) -> dict[str, object]:
        """Assign a shadow or canary challenger with a maximum fifty-percent exposure."""

        try:
            registry.assign_challenger(request.model_id, request.traffic_percent)
        except KeyError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="model not found"
            ) from error
        except (RuntimeError, ValueError) as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return {
            "status": "challenger-assigned",
            "model_id": request.model_id,
            "traffic_percent": request.traffic_percent,
        }

    @application.post(
        "/v1/admin/rollback",
        dependencies=[Depends(require_admin)],
        tags=["administration"],
    )
    def rollback(request: PromotionRequest) -> dict[str, str]:
        """Restore the most recent prior champion through the same promotion transaction."""

        try:
            model_id = registry.rollback(reason=request.reason)
        except RuntimeError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return {"status": "rolled-back", "model_id": model_id}

    return application


app = create_app()
