from __future__ import annotations

import copy
import math

from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from fastapi import HTTPException

from app.models import intelligence_bridge as bridge_models
from app.services import multimodal_intelligence_runtime
from app.services import semantic_execution


MULTIMODAL_SHADOW_API_VERSION = (
    "multimodal-shadow-api-v1"
)


class MultimodalShadowApiError(RuntimeError):
    pass


class MultimodalShadowApiInputError(
    MultimodalShadowApiError
):
    pass


class MultimodalShadowApiBindingError(
    MultimodalShadowApiError
):
    pass


class MultimodalShadowApiProviderUnavailable(
    MultimodalShadowApiError
):
    pass


class MultimodalShadowApiExecutionError(
    MultimodalShadowApiError
):
    pass


class MultimodalShadowApiIntegrityError(
    MultimodalShadowApiError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _mapping(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        Mapping,
    ):
        raise MultimodalShadowApiInputError(
            label + " must be an object."
        )

    return copy.deepcopy(
        dict(value)
    )


def _finite_number(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(value, bool):
        raise MultimodalShadowApiInputError(
            label + " must be numeric."
        )

    try:
        result = float(value)
    except (
        TypeError,
        ValueError,
    ) as error:
        raise MultimodalShadowApiInputError(
            label + " must be numeric."
        ) from error

    if not math.isfinite(result):
        raise MultimodalShadowApiInputError(
            label + " must be finite."
        )

    return result


def _legacy_score(
    value: Any,
) -> Dict[str, Any]:
    score = _mapping(
        value,
        label="Legacy Merit score",
    )

    total = _finite_number(
        score.get("total"),
        label="Legacy Merit total",
    )

    if (
        total < 0.0
        or total > 100.0
    ):
        raise MultimodalShadowApiInputError(
            "Legacy Merit total must be "
            "between 0 and 100."
        )

    score["total"] = total

    return score


def _side(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    side = _mapping(
        value,
        label=label + " side",
    )

    capture = _mapping(
        side.get("capture"),
        label=label + " capture",
    )

    if not capture:
        raise MultimodalShadowApiInputError(
            label + " capture cannot be empty."
        )

    source_id = _clean(
        side.get("source_id")
    )
    media_item_id = _clean(
        side.get("media_item_id")
    )
    story_id = _clean(
        side.get("story_id")
    )

    if not source_id:
        raise MultimodalShadowApiInputError(
            label + " source ID is required."
        )

    if not media_item_id:
        raise MultimodalShadowApiInputError(
            label + " media item ID is required."
        )

    return {
        "capture": capture,
        "source_id": source_id,
        "media_item_id": media_item_id,
        "story_id": story_id,
    }


def _one(
    conn,
    sql: str,
    parameters=(),
):
    row = conn.execute(
        sql,
        parameters,
    ).fetchone()

    if row is None:
        return None

    return dict(row)


def _require_subject(
    conn,
    subject_key: str,
) -> Dict[str, Any]:
    row = _one(
        conn,
        """
        SELECT
          id,
          entity_key,
          entity_type,
          canonical_name
        FROM canonical_entities
        WHERE entity_key = ?
        """,
        (
            subject_key,
        ),
    )

    if row is None:
        raise MultimodalShadowApiBindingError(
            "Subject key is not backed by "
            "a canonical entity record."
        )

    if (
        _clean(
            row.get("entity_key")
        )
        != subject_key
    ):
        raise MultimodalShadowApiIntegrityError(
            "Canonical subject lookup changed "
            "the requested subject key."
        )

    return row


def _verified_binding(
    conn,
    side: Mapping[str, Any],
    *,
    subject_key: str,
    label: str,
) -> bridge_models.BridgeBindings:
    source_id = _clean(
        side.get("source_id")
    )
    media_item_id = _clean(
        side.get("media_item_id")
    )
    story_id = _clean(
        side.get("story_id")
    )

    source = _one(
        conn,
        """
        SELECT id
        FROM intelligence_sources
        WHERE id = ?
        """,
        (
            source_id,
        ),
    )

    if source is None:
        raise MultimodalShadowApiBindingError(
            label
            + " source record does not exist."
        )

    media = _one(
        conn,
        """
        SELECT
          id,
          source_id,
          canonical_url
        FROM media_items
        WHERE id = ?
        """,
        (
            media_item_id,
        ),
    )

    if media is None:
        raise MultimodalShadowApiBindingError(
            label
            + " media item record does not exist."
        )

    if (
        _clean(
            media.get("source_id")
        )
        != source_id
    ):
        raise MultimodalShadowApiBindingError(
            label
            + " media item is not bound "
              "to the requested source."
        )

    story_verified = False

    if story_id:
        story = _one(
            conn,
            """
            SELECT id
            FROM intelligence_stories
            WHERE id = ?
            """,
            (
                story_id,
            ),
        )

        if story is None:
            raise MultimodalShadowApiBindingError(
                label
                + " story record does not exist."
            )

        link = _one(
            conn,
            """
            SELECT
              story_id,
              media_item_id
            FROM story_media_links
            WHERE story_id = ?
              AND media_item_id = ?
            """,
            (
                story_id,
                media_item_id,
            ),
        )

        if link is None:
            raise MultimodalShadowApiBindingError(
                label
                + " story/media binding is not "
                  "persisted in story_media_links."
            )

        story_verified = True

    return bridge_models.BridgeBindings(
        subject_key=subject_key,
        subject_resolution={},
        source_id=source_id,
        source_record_verified=True,
        media_item_id=media_item_id,
        media_item_record_verified=True,
        story_id=story_id,
        story_record_verified=(
            story_verified
        ),
        downstream_source_observation_id="",
        upstream_targets_by_item_id={},
    )


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def _request_parts(
    request_payload: Mapping[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    request = _mapping(
        request_payload,
        label="Multimodal shadow request",
    )

    subject_key = _clean(
        request.get("subject_key")
    )

    if not subject_key:
        raise MultimodalShadowApiInputError(
            "Subject key is required."
        )

    left = _side(
        request.get("left"),
        label="Left",
    )

    right = _side(
        request.get("right"),
        label="Right",
    )

    if (
        left["media_item_id"]
        == right["media_item_id"]
    ):
        raise MultimodalShadowApiInputError(
            "Multimodal shadow evaluation "
            "requires two distinct media items."
        )

    target_claim_id = _clean(
        request.get(
            "target_claim_id"
        )
    )

    legacy_score = _legacy_score(
        request.get(
            "legacy_score"
        )
    )

    return {
        "subject_key": subject_key,
        "left": left,
        "right": right,
        "target_claim_id": (
            target_claim_id
        ),
        "legacy_score": legacy_score,
    }


def _validate_runtime_result(
    raw: Any,
    *,
    subject_key: str,
    left_media_item_id: str,
    right_media_item_id: str,
) -> Dict[str, Any]:
    result = _mapping(
        raw,
        label="End-to-end multimodal result",
    )

    if (
        _clean(
            result.get("version")
        )
        != (
            multimodal_intelligence_runtime
            .MULTIMODAL_INTELLIGENCE_RUNTIME_VERSION
        )
    ):
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal runtime "
            "version mismatch."
        )

    if (
        _clean(
            result.get("status")
        ).lower()
        != "completed_shadow"
    ):
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal runtime "
            "did not complete in shadow mode."
        )

    if (
        _clean(
            result.get("subject_key")
        )
        != subject_key
    ):
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal result "
            "changed the verified subject."
        )

    if (
        _clean(
            result.get(
                "left_media_item_id"
            )
        )
        != left_media_item_id
        or _clean(
            result.get(
                "right_media_item_id"
            )
        )
        != right_media_item_id
    ):
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal result "
            "changed the verified media scope."
        )

    claim_id = _clean(
        result.get("claim_id")
    )

    if not claim_id:
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal result "
            "did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(
        policy,
        Mapping,
    ):
        raise MultimodalShadowApiIntegrityError(
            "End-to-end multimodal safety "
            "policy is missing."
        )

    required_true = (
        "exact_common_claim_required",
        "verified_bindings_rechecked_downstream",
        "adjudication_intake_is_candidate_scoped",
        "multimodal_evidence_remains_unverified",
        "model_output_does_not_establish_truth",
        "model_output_does_not_establish_independence",
        "independence_uses_existing_verifier_only",
        "merit_shadow_only",
        "live_release_not_called",
        "release_certificate_not_consumed",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalShadowApiIntegrityError(
                "End-to-end multimodal safety "
                "boundary missing: "
                + field
            )

    required_false = (
        "heuristic_cross_item_claim_matching",
        "live_enablement_authorized",
        "score_effect_applied",
        "establishes_truth",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(
            policy.get(field)
        ):
            raise MultimodalShadowApiIntegrityError(
                "End-to-end multimodal result "
                "enabled forbidden policy field: "
                + field
            )

    return result


def execute_multimodal_shadow_api(
    *,
    request_payload: Mapping[
        str,
        Any,
    ],
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    runtime_runner=(
        multimodal_intelligence_runtime
        .run_multimodal_intelligence_runtime
    ),
    interpreter_factory=(
        semantic_execution
        .GeminiSemanticInterpreter
    ),
    now_provider=_utc_now,
) -> Dict[str, Any]:
    parts = _request_parts(
        request_payload
    )

    if connection_factory is None:
        raise MultimodalShadowApiInputError(
            "Connection factory is required."
        )

    if gemini_client is None:
        raise MultimodalShadowApiProviderUnavailable(
            "Gemini multimodal client "
            "is not configured."
        )

    if not callable(
        gemini_generator
    ):
        raise MultimodalShadowApiProviderUnavailable(
            "Gemini generator is unavailable."
        )

    normalized_client_key = (
        _clean(
            gemini_client_key
        )
        or "anonymous"
    )

    conn = connection_factory()

    if conn is None:
        raise MultimodalShadowApiBindingError(
            "Connection factory returned "
            "no database connection."
        )

    try:
        _require_subject(
            conn,
            parts[
                "subject_key"
            ],
        )

        left_bindings = (
            _verified_binding(
                conn,
                parts["left"],
                subject_key=(
                    parts[
                        "subject_key"
                    ]
                ),
                label="Left",
            )
        )

        right_bindings = (
            _verified_binding(
                conn,
                parts["right"],
                subject_key=(
                    parts[
                        "subject_key"
                    ]
                ),
                label="Right",
            )
        )

    finally:
        conn.close()

    now = _clean(
        now_provider()
    )

    if not now:
        raise MultimodalShadowApiIntegrityError(
            "Server adjudication timestamp "
            "is unavailable."
        )

    try:
        interpreter = (
            interpreter_factory(
                client_factory=(
                    lambda: gemini_client
                ),
                generator=(
                    gemini_generator
                ),
                client_key=(
                    normalized_client_key
                ),
            )
        )
    except Exception as error:
        raise MultimodalShadowApiProviderUnavailable(
            "Multimodal semantic interpreter "
            "could not be initialized."
        ) from error

    try:
        runtime_result = runtime_runner(
            left_capture=(
                parts[
                    "left"
                ][
                    "capture"
                ]
            ),
            right_capture=(
                parts[
                    "right"
                ][
                    "capture"
                ]
            ),
            left_bindings=(
                left_bindings
            ),
            right_bindings=(
                right_bindings
            ),
            legacy_score=copy.deepcopy(
                parts[
                    "legacy_score"
                ]
            ),
            as_of=now,
            connection_factory=(
                connection_factory
            ),
            semantic_interpreter=(
                interpreter
            ),
            gemini_client=(
                gemini_client
            ),
            gemini_client_key=(
                normalized_client_key
            ),
            gemini_generator=(
                gemini_generator
            ),
            target_claim_id=(
                parts[
                    "target_claim_id"
                ]
            ),
            recorded_at=now,
        )
    except (
        multimodal_intelligence_runtime
        .MultimodalIntelligenceRuntimeError
    ) as error:
        raise MultimodalShadowApiExecutionError(
            str(error)
        ) from error

    result = _validate_runtime_result(
        runtime_result,
        subject_key=(
            parts[
                "subject_key"
            ]
        ),
        left_media_item_id=(
            parts[
                "left"
            ][
                "media_item_id"
            ]
        ),
        right_media_item_id=(
            parts[
                "right"
            ][
                "media_item_id"
            ]
        ),
    )

    return {
        "version": (
            MULTIMODAL_SHADOW_API_VERSION
        ),
        "status": "completed_shadow",
        "result": result,
        "policy": {
            "admin_only_endpoint": True,
            "dedicated_feature_flag_required": True,
            "bindings_verified_server_side": True,
            "caller_cannot_set_verification_flags": True,
            "server_generated_adjudication_time": True,
            "exact_two_media_scope": True,
            "exact_common_claim_required": True,
            "multimodal_evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_independence": True,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "affects_live_merit": False,
        },
    }


def execute_multimodal_shadow_http(
    *,
    req,
    request,
    enabled: bool,
    require_admin,
    gemini_client_factory,
    request_client_key_resolver,
    gemini_generator,
    connection_factory,
    response_model,
):
    """HTTP adapter for the admin-only multimodal shadow endpoint.

    This keeps route/auth/provider/error mapping outside app.main while
    delegating all intelligence work to execute_multimodal_shadow_api.
    It does not enable live Merit or consume a release certificate.
    """

    if not enabled:
        raise HTTPException(
            status_code=404,
            detail="Not found",
        )

    require_admin(request)

    client = gemini_client_factory()

    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini multimodal analysis "
                "is not configured."
            ),
        )

    if hasattr(
        req,
        "model_dump",
    ):
        request_payload = req.model_dump(
            mode="python"
        )
    else:
        request_payload = req.dict()

    try:
        payload = execute_multimodal_shadow_api(
            request_payload=request_payload,
            connection_factory=connection_factory,
            gemini_client=client,
            gemini_client_key=(
                request_client_key_resolver(
                    request
                )
            ),
            gemini_generator=gemini_generator,
        )

    except MultimodalShadowApiInputError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except MultimodalShadowApiBindingError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    except MultimodalShadowApiProviderUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    except MultimodalShadowApiExecutionError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    except MultimodalShadowApiIntegrityError as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Multimodal shadow integrity "
                "validation failed."
            ),
        ) from error

    return response_model(
        **payload
    )
