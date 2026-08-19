from __future__ import annotations

import copy
import math

from typing import Any, Dict, Mapping

from app.services import multimodal_binding_registration
from app.services import multimodal_shadow_api


MULTIMODAL_SHADOW_ORCHESTRATION_VERSION = (
    "multimodal-shadow-orchestration-v1"
)


class MultimodalShadowOrchestrationError(RuntimeError):
    pass


class MultimodalShadowOrchestrationInputError(
    MultimodalShadowOrchestrationError
):
    pass


class MultimodalShadowOrchestrationBindingError(
    MultimodalShadowOrchestrationError
):
    pass


class MultimodalShadowOrchestrationProviderUnavailable(
    MultimodalShadowOrchestrationError
):
    pass


class MultimodalShadowOrchestrationExecutionError(
    MultimodalShadowOrchestrationError
):
    pass


class MultimodalShadowOrchestrationClaimSelectionError(
    MultimodalShadowOrchestrationExecutionError
):
    pass


class MultimodalShadowOrchestrationIntegrityError(
    MultimodalShadowOrchestrationError
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
    if not isinstance(value, Mapping):
        raise MultimodalShadowOrchestrationInputError(
            label + " must be an object."
        )

    return copy.deepcopy(dict(value))


def _first(
    value: Mapping[str, Any],
    *names: str,
) -> str:
    for name in names:
        result = _clean(value.get(name))
        if result:
            return result
    return ""


def _legacy_score(value: Any) -> Dict[str, Any]:
    score = _mapping(
        value,
        label="Legacy Merit score",
    )

    total = score.get("total")

    if isinstance(total, bool):
        raise MultimodalShadowOrchestrationInputError(
            "Legacy Merit total must be numeric."
        )

    try:
        total = float(total)
    except (TypeError, ValueError) as error:
        raise MultimodalShadowOrchestrationInputError(
            "Legacy Merit total must be numeric."
        ) from error

    if not math.isfinite(total):
        raise MultimodalShadowOrchestrationInputError(
            "Legacy Merit total must be finite."
        )

    if total < 0.0 or total > 100.0:
        raise MultimodalShadowOrchestrationInputError(
            "Legacy Merit total must be between 0 and 100."
        )

    score["total"] = total
    return score


def _validate_registration(value: Any) -> Dict[str, Any]:
    result = _mapping(
        value,
        label="Binding registration result",
    )

    if _clean(result.get("version")) != (
        multimodal_binding_registration
        .MULTIMODAL_BINDING_REGISTRATION_VERSION
    ):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration version mismatch."
        )

    if _clean(result.get("status")).lower() != "registered":
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration did not complete."
        )

    subject_key = _clean(result.get("subject_key"))
    subject = result.get("subject")

    if not subject_key or not isinstance(subject, Mapping):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration subject scope is missing."
        )

    if _clean(subject.get("entity_key")) != subject_key:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration changed the subject scope."
        )

    sides: Dict[str, Dict[str, str]] = {}

    for label in ("left", "right"):
        side = result.get(label)

        if not isinstance(side, Mapping):
            raise MultimodalShadowOrchestrationIntegrityError(
                label.capitalize()
                + " binding registration payload is missing."
            )

        source_id = _clean(side.get("source_id"))
        media_item_id = _clean(side.get("media_item_id"))
        story_id = _clean(side.get("story_id"))

        if not source_id or not media_item_id:
            raise MultimodalShadowOrchestrationIntegrityError(
                label.capitalize()
                + " binding registration identity is incomplete."
            )

        if story_id:
            raise MultimodalShadowOrchestrationIntegrityError(
                "Binding bootstrap unexpectedly created story scope."
            )

        sides[label] = {
            "source_id": source_id,
            "media_item_id": media_item_id,
            "story_id": "",
        }

    if (
        sides["left"]["media_item_id"]
        == sides["right"]["media_item_id"]
    ):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration returned duplicate media scope."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Binding registration safety policy is missing."
        )

    required_true = (
        "subject_record_is_identity_only",
        "source_identity_is_deterministic",
        "stable_actor_identity_required_for_social",
        "source_and_media_persisted_atomically",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalShadowOrchestrationIntegrityError(
                "Binding registration safety boundary missing: "
                + field
            )

    required_false = (
        "story_record_created",
        "verified_source_entity_binding_created",
        "verified_claim_entity_participant_created",
        "claim_created",
        "observation_created",
        "evidence_record_created",
        "model_output_used",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "training_eligible",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(policy.get(field)):
            raise MultimodalShadowOrchestrationIntegrityError(
                "Binding registration enabled forbidden field: "
                + field
            )

    return {
        "result": result,
        "subject_key": subject_key,
        "left": sides["left"],
        "right": sides["right"],
    }


def _validate_shadow(
    value: Any,
    *,
    subject_key: str,
    left_media_item_id: str,
    right_media_item_id: str,
    merit_baseline_mode: str,
) -> Dict[str, Any]:
    shadow = _mapping(
        value,
        label="Multimodal shadow result",
    )

    if _clean(shadow.get("version")) != (
        multimodal_shadow_api.MULTIMODAL_SHADOW_API_VERSION
    ):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow API version mismatch."
        )

    if _clean(shadow.get("status")).lower() != "completed_shadow":
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow API did not complete."
        )

    result = shadow.get("result")

    if not isinstance(result, Mapping):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow runtime result is missing."
        )

    if _clean(result.get("subject_key")) != subject_key:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow result changed the subject scope."
        )

    if (
        _clean(result.get("left_media_item_id"))
        != left_media_item_id
        or _clean(result.get("right_media_item_id"))
        != right_media_item_id
    ):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow result changed the media scope."
        )

    claim_id = _clean(result.get("claim_id"))

    if not claim_id:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow result did not expose a claim ID."
        )

    policy = shadow.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow safety policy is missing."
        )

    required_true = (
        "bindings_verified_server_side",
        "caller_cannot_set_verification_flags",
        "exact_two_media_scope",
        "exact_common_claim_required",
        "multimodal_evidence_remains_unverified",
        "model_output_does_not_establish_truth",
        "model_output_does_not_establish_independence",
        "live_merit_shadow_only",
        "live_release_not_called",
        "release_certificate_not_consumed",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalShadowOrchestrationIntegrityError(
                "Multimodal shadow safety boundary missing: "
                + field
            )

    for field in (
        "live_enablement_authorized",
        "score_effect_applied",
        "establishes_truth",
        "affects_live_merit",
    ):
        if bool(policy.get(field)):
            raise MultimodalShadowOrchestrationIntegrityError(
                "Multimodal shadow enabled forbidden field: "
                + field
            )


    if policy.get("merit_baseline_mode") != merit_baseline_mode:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow Merit baseline mode changed."
        )
    if bool(policy.get("synthetic_merit_baseline_used")):
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow used a synthetic Merit baseline."
        )
    if merit_baseline_mode == "legacy_merit":
        if (
            policy.get("merit_baseline_available") is not True
            or policy.get("merit_shadow_evaluated") is not True
        ):
            raise MultimodalShadowOrchestrationIntegrityError(
                "Legacy Merit shadow state is incomplete."
            )
    elif (
        bool(policy.get("merit_baseline_available"))
        or bool(policy.get("merit_shadow_evaluated"))
    ):
        raise MultimodalShadowOrchestrationIntegrityError(
            "No-Merit shadow unexpectedly evaluated Merit."
        )
    return {
        "result": shadow,
        "claim_id": claim_id,
    }


def execute_multimodal_shadow_orchestration(
    *,
    subject: Mapping[str, Any],
    left_capture: Mapping[str, Any],
    right_capture: Mapping[str, Any],
    legacy_score: Any,
    merit_baseline_mode: str = "legacy_merit",
    target_claim_id: str = "",
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    registration_runner=(
        multimodal_binding_registration.register_multimodal_bindings
    ),
    shadow_runner=(
        multimodal_shadow_api.execute_multimodal_shadow_api
    ),
) -> Dict[str, Any]:
    subject_payload = _mapping(subject, label="Subject")
    left_payload = _mapping(left_capture, label="Left capture")
    right_payload = _mapping(right_capture, label="Right capture")
    normalized_merit_baseline_mode = _clean(
        merit_baseline_mode
    ).lower() or "legacy_merit"

    if normalized_merit_baseline_mode == "legacy_merit":
        score_payload = _legacy_score(legacy_score)
    elif normalized_merit_baseline_mode == "not_applicable":
        if legacy_score is not None:
            raise MultimodalShadowOrchestrationInputError(
                "No-Merit execution must not receive a legacy Merit score."
            )
        score_payload = None
    else:
        raise MultimodalShadowOrchestrationInputError(
            "Unsupported Merit baseline mode."
        )

    target_claim_id = _clean(target_claim_id)

    if connection_factory is None:
        raise MultimodalShadowOrchestrationInputError(
            "Connection factory is required."
        )

    # Provider availability is checked before registration so a simple
    # configuration failure cannot create identity rows as a side effect.
    if gemini_client is None:
        raise MultimodalShadowOrchestrationProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalShadowOrchestrationProviderUnavailable(
            "Gemini generator is unavailable."
        )

    try:
        registration_raw = registration_runner(
            subject=copy.deepcopy(subject_payload),
            left_capture=copy.deepcopy(left_payload),
            right_capture=copy.deepcopy(right_payload),
            connection_factory=connection_factory,
        )
    except multimodal_binding_registration.MultimodalBindingInputError as error:
        raise MultimodalShadowOrchestrationInputError(
            str(error)
        ) from error
    except multimodal_binding_registration.MultimodalBindingIdentityError as error:
        raise MultimodalShadowOrchestrationBindingError(
            str(error)
        ) from error
    except multimodal_binding_registration.MultimodalBindingPersistenceError as error:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal binding persistence failed."
        ) from error
    except multimodal_binding_registration.MultimodalBindingIntegrityError as error:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal binding integrity validation failed."
        ) from error

    registration = _validate_registration(registration_raw)

    shadow_request = {
        "subject_key": registration["subject_key"],
        "left": {
            "capture": copy.deepcopy(left_payload),
            "source_id": registration["left"]["source_id"],
            "media_item_id": registration["left"]["media_item_id"],
            "story_id": "",
        },
        "right": {
            "capture": copy.deepcopy(right_payload),
            "source_id": registration["right"]["source_id"],
            "media_item_id": registration["right"]["media_item_id"],
            "story_id": "",
        },
        "target_claim_id": target_claim_id,
        "legacy_score": copy.deepcopy(score_payload),
        "merit_baseline_mode": (
            normalized_merit_baseline_mode
        ),
    }

    try:
        shadow_raw = shadow_runner(
            request_payload=shadow_request,
            connection_factory=connection_factory,
            gemini_client=gemini_client,
            gemini_client_key=(
                _clean(gemini_client_key) or "anonymous"
            ),
            gemini_generator=gemini_generator,
        )
    except multimodal_shadow_api.MultimodalShadowApiInputError as error:
        raise MultimodalShadowOrchestrationInputError(
            str(error)
        ) from error
    except multimodal_shadow_api.MultimodalShadowApiBindingError as error:
        raise MultimodalShadowOrchestrationBindingError(
            str(error)
        ) from error
    except multimodal_shadow_api.MultimodalShadowApiProviderUnavailable as error:
        raise MultimodalShadowOrchestrationProviderUnavailable(
            str(error)
        ) from error
    except multimodal_shadow_api.MultimodalShadowApiClaimSelectionError as error:
        raise MultimodalShadowOrchestrationClaimSelectionError(
            str(error)
        ) from error
    except multimodal_shadow_api.MultimodalShadowApiExecutionError as error:
        raise MultimodalShadowOrchestrationExecutionError(
            str(error)
        ) from error
    except multimodal_shadow_api.MultimodalShadowApiIntegrityError as error:
        raise MultimodalShadowOrchestrationIntegrityError(
            "Multimodal shadow integrity validation failed."
        ) from error

    shadow = _validate_shadow(
        shadow_raw,
        subject_key=registration["subject_key"],
        left_media_item_id=registration["left"]["media_item_id"],
        right_media_item_id=registration["right"]["media_item_id"],
        merit_baseline_mode=(
            normalized_merit_baseline_mode
        ),
    )

    return {
        "version": MULTIMODAL_SHADOW_ORCHESTRATION_VERSION,
        "status": "completed_shadow",
        "claim_id": shadow["claim_id"],
        "registration": registration["result"],
        "shadow": shadow["result"],
        "policy": {
            "admin_only_endpoint": True,
            "dedicated_feature_flag_required": True,
            "caller_supplies_raw_captures_only": True,
            "caller_cannot_supply_binding_ids": True,
            "caller_cannot_set_verification_flags": True,
            "binding_ids_generated_server_side": True,
            "binding_registration_precedes_shadow": True,
            "shadow_adapter_reverifies_bindings": True,
            "exact_two_media_scope": True,
            "binding_registration_is_identity_only": True,
            "binding_registration_may_persist_if_shadow_fails": True,
            "multimodal_evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
            "model_output_does_not_establish_authority": True,
            "model_output_does_not_establish_independence": True,
            "live_merit_shadow_only": True,
            "merit_baseline_mode": (
                normalized_merit_baseline_mode
            ),
            "merit_baseline_available": (
                normalized_merit_baseline_mode
                == "legacy_merit"
            ),
            "merit_shadow_evaluated": (
                normalized_merit_baseline_mode
                == "legacy_merit"
            ),
            "synthetic_merit_baseline_used": False,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "live_enablement_authorized": False,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
