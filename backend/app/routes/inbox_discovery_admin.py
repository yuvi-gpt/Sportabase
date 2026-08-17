from __future__ import annotations

from typing import Any, Dict, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services import inbox_candidate_discovery


class _StrictDiscoveryModel(BaseModel):
    class Config:
        extra = "forbid"


class MultimodalInboxDiscoveryRequest(
    _StrictDiscoveryModel
):
    anchor_capture_record_id: str = Field(
        ...,
        min_length=1,
        max_length=256,
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

    semantic_assessments: int = Field(
        4,
        ge=0,
        le=20,
    )


class MultimodalInboxDiscoveryResponse(BaseModel):
    version: str

    status: Literal[
        "candidates_available",
        "no_candidates",
    ]

    anchor_capture_record_id: str

    anchor: Dict[
        str,
        Any,
    ] = Field(
        default_factory=dict
    )

    pair_candidates: list[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    load_failures: list[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    counts: Dict[
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
        "/admin/intelligence/multimodal-inbox-discovery",
        response_model=(
            MultimodalInboxDiscoveryResponse
        ),
    )
    def admin_multimodal_inbox_discovery(
        req: MultimodalInboxDiscoveryRequest,
        request: Request,
    ):
        if not enabled:
            raise HTTPException(
                status_code=404,
                detail="Not found",
            )

        require_admin(request)

        request_payload = _payload(req)

        semantic_limit = int(
            request_payload[
                "semantic_assessments"
            ]
        )

        client = None

        if (
            semantic_limit > 0
            and callable(
                gemini_client_factory
            )
        ):
            try:
                client = (
                    gemini_client_factory()
                )
            except Exception:
                client = None

        if callable(
            request_client_key_resolver
        ):
            client_key = (
                request_client_key_resolver(
                    request
                )
            )
        else:
            client_key = "anonymous"

        try:
            result = (
                inbox_candidate_discovery
                .discover_multimodal_inbox_candidates(
                    anchor_capture_record_id=(
                        request_payload[
                            "anchor_capture_record_id"
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
                    semantic_assessments=(
                        semantic_limit
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
            inbox_candidate_discovery
            .InboxCandidateDiscoveryInputError
        ) as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_discovery
            .InboxCandidateDiscoveryNotFoundError
        ) as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_discovery
            .InboxCandidateDiscoveryLookupError
        ) as error:
            raise HTTPException(
                status_code=503,
                detail=str(error),
            ) from error

        except (
            inbox_candidate_discovery
            .InboxCandidateDiscoveryIntegrityError
        ) as error:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Multimodal inbox candidate discovery "
                    "integrity validation failed."
                ),
            ) from error

        return MultimodalInboxDiscoveryResponse(
            **result
        )

    return router
