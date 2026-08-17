from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import multimodal_binding_registration


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


def _payload(req: MultimodalBindingRequest) -> Dict[str, Any]:
    if hasattr(req, "model_dump"):
        return req.model_dump(
            mode="python"
        )

    return req.dict()


def build_router(
    enabled,
    require_admin,
    connection_factory,
) -> APIRouter:
    router = APIRouter()

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

    return router
