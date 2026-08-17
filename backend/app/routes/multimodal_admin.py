from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import multimodal_binding_registration
from app.services import multimodal_shadow_orchestration
from app.services import multimodal_inbox_shadow_orchestration
from app.routes import inbox_discovery_admin
from app.routes import inbox_candidate_shadow_admin
from app.routes import inbox_auto_shadow_admin
from app.routes import inbox_history_auto_shadow_admin


class _StrictBindingModel(BaseModel):
    class Config:
        extra = "forbid"


class MultimodalBindingSubjectRequest(
    _StrictBindingModel
):
    entity_key: str = Field(
        ...,
        min_length=1,
        max_length=512,
    )

    entity_type: str = Field(
        ...,
        min_length=1,
        max_length=64,
    )

    canonical_name: str = Field(
        ...,
        min_length=1,
        max_length=512,
    )

    sport_key: str = Field(
        "",
        max_length=128,
    )


class MultimodalBindingRequest(
    _StrictBindingModel
):
    subject: MultimodalBindingSubjectRequest

    left_capture: Dict[
        str,
        Any,
    ] = Field(...)

    right_capture: Dict[
        str,
        Any,
    ] = Field(...)


class MultimodalBindingResponse(BaseModel):
    version: str

    status: Literal[
        "registered"
    ]

    subject: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    subject_key: str

    left: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    right: Dict[
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


class MultimodalShadowRunRequest(
    _StrictBindingModel
):
    subject: MultimodalBindingSubjectRequest

    left_capture: Dict[
        str,
        Any,
    ] = Field(...)

    right_capture: Dict[
        str,
        Any,
    ] = Field(...)

    legacy_score: Dict[
        str,
        Any,
    ] = Field(...)

    target_claim_id: str = Field(
        "",
        max_length=512,
    )


class MultimodalShadowRunResponse(BaseModel):
    version: str

    status: Literal[
        "completed_shadow"
    ]

    claim_id: str

    registration: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    shadow: Dict[
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



class MultimodalInboxShadowRunRequest(
    _StrictBindingModel
):
    subject: MultimodalBindingSubjectRequest

    left_capture_record_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )

    right_capture_record_id: str = Field(
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


class MultimodalInboxShadowRunResponse(BaseModel):
    version: str

    status: Literal[
        "completed_shadow"
    ]

    claim_id: str
    left_capture_record_id: str
    right_capture_record_id: str

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
    enabled,
    require_admin,
    connection_factory,
    gemini_client_factory=None,
    request_client_key_resolver=None,
    gemini_generator=None,
    analysis_version="",
    scoring_version="",
) -> APIRouter:
    router = APIRouter()

    router.include_router(
        inbox_discovery_admin.build_router(
            enabled=enabled,
            require_admin=require_admin,
            connection_factory=connection_factory,
            gemini_client_factory=gemini_client_factory,
            request_client_key_resolver=(
                request_client_key_resolver
            ),
            gemini_generator=gemini_generator,
        )
    )

    router.include_router(
        inbox_candidate_shadow_admin.build_router(
            enabled=enabled,
            require_admin=require_admin,
            connection_factory=connection_factory,
            gemini_client_factory=gemini_client_factory,
            request_client_key_resolver=(
                request_client_key_resolver
            ),
            gemini_generator=gemini_generator,
        )
    )

    router.include_router(
        inbox_auto_shadow_admin.build_router(
            enabled=enabled,
            require_admin=require_admin,
            connection_factory=connection_factory,
            gemini_client_factory=gemini_client_factory,
            request_client_key_resolver=(
                request_client_key_resolver
            ),
            gemini_generator=gemini_generator,
        )
    )

    router.include_router(
        inbox_history_auto_shadow_admin.build_router(
            enabled=enabled,
            require_admin=require_admin,
            connection_factory=connection_factory,
            analysis_version=analysis_version,
            scoring_version=scoring_version,
            gemini_client_factory=gemini_client_factory,
            request_client_key_resolver=(
                request_client_key_resolver
            ),
            gemini_generator=gemini_generator,
        )
    )

    @router.post(
        "/admin/intelligence/multimodal-bindings",
        response_model=MultimodalBindingResponse,
    )
    def admin_multimodal_bindings(
        req: MultimodalBindingRequest,
        request: Request,
    ):
        if not enabled:
            raise HTTPException(
                status_code=404,
                detail="Not found",
            )

        require_admin(request)

        request_payload = _payload(
            req
        )

        try:
            result = (
                multimodal_binding_registration
                .register_multimodal_bindings(
                    subject=(
                        request_payload["subject"]
                    ),
                    left_capture=(
                        request_payload["left_capture"]
                    ),
                    right_capture=(
                        request_payload["right_capture"]
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                )
            )

        except (
            multimodal_binding_registration
            .MultimodalBindingInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            multimodal_binding_registration
            .MultimodalBindingIdentityError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            multimodal_binding_registration
            .MultimodalBindingPersistenceError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal binding persistence failed."
                ),
            ) from error

        except (
            multimodal_binding_registration
            .MultimodalBindingIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal binding integrity validation failed."
                ),
            ) from error

        return MultimodalBindingResponse(
            **result
        )

    @router.post(
        "/admin/intelligence/multimodal-shadow-run",
        response_model=MultimodalShadowRunResponse,
    )
    def admin_multimodal_shadow_run(
        req: MultimodalShadowRunRequest,
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
                    "Gemini multimodal analysis is not configured."
                ),
            )

        try:
            client = gemini_client_factory()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis is not configured."
                ),
            ) from error

        if client is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis is not configured."
                ),
            )

        request_payload = _payload(
            req
        )

        if callable(request_client_key_resolver):
            client_key = request_client_key_resolver(
                request
            )
        else:
            client_key = "anonymous"

        try:
            result = (
                multimodal_shadow_orchestration
                .execute_multimodal_shadow_orchestration(
                    subject=(
                        request_payload["subject"]
                    ),
                    left_capture=(
                        request_payload["left_capture"]
                    ),
                    right_capture=(
                        request_payload["right_capture"]
                    ),
                    legacy_score=(
                        request_payload["legacy_score"]
                    ),
                    target_claim_id=(
                        request_payload[
                            "target_claim_id"
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
            multimodal_shadow_orchestration
            .MultimodalShadowOrchestrationInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            multimodal_shadow_orchestration
            .MultimodalShadowOrchestrationBindingError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            multimodal_shadow_orchestration
            .MultimodalShadowOrchestrationProviderUnavailable
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            multimodal_shadow_orchestration
            .MultimodalShadowOrchestrationExecutionError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            multimodal_shadow_orchestration
            .MultimodalShadowOrchestrationIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal shadow orchestration integrity "
                    "validation failed."
                ),
            ) from error

        return MultimodalShadowRunResponse(
            **result
        )


    @router.post(
        "/admin/intelligence/multimodal-shadow-run-inbox",
        response_model=MultimodalInboxShadowRunResponse,
    )
    def admin_multimodal_shadow_run_inbox(
        req: MultimodalInboxShadowRunRequest,
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
                    "Gemini multimodal analysis is not configured."
                ),
            )

        try:
            client = gemini_client_factory()
        except Exception as error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis is not configured."
                ),
            ) from error

        if client is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Gemini multimodal analysis is not configured."
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
                multimodal_inbox_shadow_orchestration
                .execute_multimodal_inbox_shadow_orchestration(
                    subject=request_payload["subject"],
                    left_capture_record_id=(
                        request_payload[
                            "left_capture_record_id"
                        ]
                    ),
                    right_capture_record_id=(
                        request_payload[
                            "right_capture_record_id"
                        ]
                    ),
                    legacy_score=(
                        request_payload["legacy_score"]
                    ),
                    target_claim_id=(
                        request_payload[
                            "target_claim_id"
                        ]
                    ),
                    connection_factory=(
                        connection_factory
                    ),
                    gemini_client=client,
                    gemini_client_key=client_key,
                    gemini_generator=gemini_generator,
                )
            )

        except (
            multimodal_inbox_shadow_orchestration
            .MultimodalInboxShadowInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            multimodal_inbox_shadow_orchestration
            .MultimodalInboxShadowBindingError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            multimodal_inbox_shadow_orchestration
            .MultimodalInboxShadowProviderUnavailable
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            multimodal_inbox_shadow_orchestration
            .MultimodalInboxShadowExecutionError
        ) as error:
            raise HTTPException(
                status_code=409,
                detail=str(error),
            ) from error

        except (
            multimodal_inbox_shadow_orchestration
            .MultimodalInboxShadowIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal inbox shadow integrity "
                    "validation failed."
                ),
            ) from error

        return MultimodalInboxShadowRunResponse(
            **result
        )

    return router
