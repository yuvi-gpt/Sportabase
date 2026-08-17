from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import inbox_candidate_shadow_orchestration


class _StrictCandidateShadowModel(BaseModel):
    class Config:
        extra = "forbid"


class MultimodalInboxCandidateShadowRequest(
    _StrictCandidateShadowModel
):
    anchor_capture_record_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    candidate_capture_record_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    subject_entity_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    legacy_score: Dict[
        str,
        Any,
    ] = Field(...)

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


class MultimodalInboxCandidateShadowResponse(
    BaseModel
):
    version: str

    status: Literal[
        "completed_shadow"
    ]

    claim_id: str
    anchor_capture_record_id: str
    candidate_capture_record_id: str
    subject_entity_id: str

    subject: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    discovery_gate: Dict[
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
    gemini_client_factory=None,
    request_client_key_resolver=None,
    gemini_generator=None,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        (
            "/admin/intelligence/"
            "multimodal-inbox-candidate-shadow-run"
        ),
        response_model=(
            MultimodalInboxCandidateShadowResponse
        ),
    )
    def admin_multimodal_inbox_candidate_shadow(
        req: MultimodalInboxCandidateShadowRequest,
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
                inbox_candidate_shadow_orchestration
                .execute_multimodal_inbox_candidate_shadow(
                    anchor_capture_record_id=(
                        request_payload[
                            "anchor_capture_record_id"
                        ]
                    ),
                    candidate_capture_record_id=(
                        request_payload[
                            "candidate_capture_record_id"
                        ]
                    ),
                    subject_entity_id=(
                        request_payload[
                            "subject_entity_id"
                        ]
                    ),
                    legacy_score=(
                        request_payload[
                            "legacy_score"
                        ]
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
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowDiscoveryError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowBindingError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowProviderUnavailable
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowExecutionError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_shadow_orchestration
            .MultimodalInboxCandidateShadowIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal inbox candidate "
                    "shadow integrity validation failed."
                ),
            ) from error

        return MultimodalInboxCandidateShadowResponse(
            **result
        )

    return router
