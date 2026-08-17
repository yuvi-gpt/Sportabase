from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import inbox_history_auto_shadow_orchestration


class _StrictHistoryAutoShadowModel(BaseModel):
    class Config:
        extra = "forbid"


class MultimodalInboxHistoryAutoShadowRequest(
    _StrictHistoryAutoShadowModel
):
    anchor_capture_record_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    target_claim_id: str = Field(
        "",
        max_length=512,
    )

    scan_limit: int = Field(
        100,
        ge=1,
        le=500,
    )

    max_candidates: int = Field(
        12,
        ge=1,
        le=50,
    )


class MultimodalInboxHistoryAutoShadowResponse(
    BaseModel
):
    version: str

    status: Literal[
        "completed_shadow"
    ]

    claim_id: str
    anchor_capture_record_id: str
    selected_candidate_capture_record_id: str
    selected_subject_entity_id: str

    baseline_resolution: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    automatic_selection: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    orchestration: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    policy: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )


def _payload(req) -> Dict[str, Any]:
    if hasattr(req, "model_dump"):
        return req.model_dump(
            mode="python"
        )

    return req.dict()


def build_router(
    *,
    enabled,
    require_admin,
    connection_factory,
    analysis_version,
    scoring_version,
    gemini_client_factory=None,
    request_client_key_resolver=None,
    gemini_generator=None,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        (
            "/admin/intelligence/"
            "multimodal-inbox-auto-shadow-history"
        ),
        response_model=(
            MultimodalInboxHistoryAutoShadowResponse
        ),
    )
    def admin_multimodal_inbox_history_auto_shadow(
        req: MultimodalInboxHistoryAutoShadowRequest,
        request: Request,
    ):
        if not enabled:
            raise HTTPException(
                status_code=404,
                detail="Not found",
            )

        require_admin(request)

        if not callable(gemini_client_factory):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis "
                    "is not configured."
                ),
            )

        try:
            client = gemini_client_factory()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis "
                    "is not configured."
                ),
            ) from error

        if client is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis "
                    "is not configured."
                ),
            )

        if not callable(gemini_generator):
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis "
                    "is not configured."
                ),
            )

        request_payload = _payload(req)

        if callable(request_client_key_resolver):
            client_key = request_client_key_resolver(
                request
            )
        else:
            client_key = "anonymous"

        try:
            result = (
                inbox_history_auto_shadow_orchestration
                .execute_multimodal_inbox_history_auto_shadow(
                    anchor_capture_record_id=(
                        request_payload[
                            "anchor_capture_record_id"
                        ]
                    ),
                    analysis_version=(
                        analysis_version
                    ),
                    scoring_version=(
                        scoring_version
                    ),
                    target_claim_id=(
                        request_payload[
                            "target_claim_id"
                        ]
                    ),
                    scan_limit=(
                        request_payload[
                            "scan_limit"
                        ]
                    ),
                    max_candidates=(
                        request_payload[
                            "max_candidates"
                        ]
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                    gemini_client=client,
                    gemini_client_key=(
                        client_key
                    ),
                    gemini_generator=(
                        gemini_generator
                    ),
                )
            )

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowBaselineUnavailable
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowLookupError
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowProviderUnavailable
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowExecutionError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            inbox_history_auto_shadow_orchestration
            .MultimodalInboxHistoryAutoShadowIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal inbox history-backed "
                    "shadow integrity validation failed."
                ),
            ) from error

        return MultimodalInboxHistoryAutoShadowResponse(
            **result
        )

    return router
