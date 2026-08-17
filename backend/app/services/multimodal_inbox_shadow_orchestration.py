from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

from app.services import browser_capture_inbox
from app.services import multimodal_shadow_orchestration


MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION = (
    "multimodal-inbox-shadow-orchestration-v1"
)


class MultimodalInboxShadowError(RuntimeError):
    pass


class MultimodalInboxShadowInputError(
    MultimodalInboxShadowError
):
    pass


class MultimodalInboxShadowBindingError(
    MultimodalInboxShadowError
):
    pass


class MultimodalInboxShadowProviderUnavailable(
    MultimodalInboxShadowError
):
    pass


class MultimodalInboxShadowExecutionError(
    MultimodalInboxShadowError
):
    pass


class MultimodalInboxShadowClaimSelectionError(
    MultimodalInboxShadowExecutionError
):
    pass


class MultimodalInboxShadowIntegrityError(
    MultimodalInboxShadowError
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
        raise MultimodalInboxShadowInputError(
            label + " must be an object."
        )

    return copy.deepcopy(
        dict(value)
    )


def _record_id(
    value: Any,
    *,
    label: str,
) -> str:
    record_id = _clean(value)

    if not record_id:
        raise MultimodalInboxShadowInputError(
            label + " capture record ID is required."
        )

    if len(record_id) > 256:
        raise MultimodalInboxShadowInputError(
            label + " capture record ID is too long."
        )

    return record_id


def _load_capture(
    *,
    record_id: str,
    connection_factory,
    loader,
    label: str,
) -> Dict[str, Any]:
    try:
        loaded = loader(
            capture_record_id=record_id,
            connection_factory=(
                connection_factory
            ),
        )
    except browser_capture_inbox.BrowserCaptureInboxInputError as error:
        raise MultimodalInboxShadowInputError(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxNotFoundError as error:
        raise MultimodalInboxShadowBindingError(
            label
            + " browser capture record does not exist."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxPersistenceError as error:
        raise MultimodalInboxShadowExecutionError(
            "Browser capture inbox lookup failed."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxIntegrityError as error:
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture record failed integrity validation."
        ) from error

    if not isinstance(loaded, Mapping):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture loader returned an invalid result."
        )

    result = copy.deepcopy(
        dict(loaded)
    )

    if (
        _clean(
            result.get("version")
        )
        != browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION
    ):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture inbox version mismatch."
        )

    if (
        _clean(
            result.get("capture_record_id")
        )
        != record_id
    ):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture record scope changed."
        )

    capture = result.get("capture")

    if not isinstance(capture, Mapping):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture payload is missing."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture policy is missing."
        )

    if policy.get(
        "record_is_untrusted"
    ) is not True:
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture trust boundary is missing."
        )

    if policy.get(
        "integrity_rechecked_on_load"
    ) is not True:
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture integrity boundary is missing."
        )

    if bool(
        policy.get("affects_live_merit")
    ):
        raise MultimodalInboxShadowIntegrityError(
            label
            + " browser capture unexpectedly affects Live Merit."
        )

    return {
        "record": result,
        "capture": copy.deepcopy(
            dict(capture)
        ),
    }


def _validate_orchestration(
    value: Any,
    *,
    merit_baseline_mode: str,
) -> Dict[str, Any]:
    result = _mapping(
        value,
        label="Multimodal shadow orchestration result",
    )

    if (
        _clean(
            result.get("version")
        )
        != (
            multimodal_shadow_orchestration
            .MULTIMODAL_SHADOW_ORCHESTRATION_VERSION
        )
    ):
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow orchestration version mismatch."
        )

    if (
        _clean(
            result.get("status")
        ).lower()
        != "completed_shadow"
    ):
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow orchestration did not complete."
        )

    claim_id = _clean(
        result.get("claim_id")
    )

    if not claim_id:
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow orchestration did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow orchestration policy is missing."
        )

    required_true = (
        "caller_cannot_supply_binding_ids",
        "binding_ids_generated_server_side",
        "shadow_adapter_reverifies_bindings",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxShadowIntegrityError(
                "Multimodal shadow safety boundary missing: "
                + field
            )

    required_false = (
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(policy.get(field)):
            raise MultimodalInboxShadowIntegrityError(
                "Multimodal shadow enabled forbidden field: "
                + field
            )


    if policy.get("merit_baseline_mode") != merit_baseline_mode:
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow Merit baseline mode changed."
        )
    if bool(policy.get("synthetic_merit_baseline_used")):
        raise MultimodalInboxShadowIntegrityError(
            "Multimodal shadow used a synthetic Merit baseline."
        )
    if merit_baseline_mode == "legacy_merit":
        if (
            policy.get("merit_baseline_available") is not True
            or policy.get("merit_shadow_evaluated") is not True
        ):
            raise MultimodalInboxShadowIntegrityError(
                "Legacy Merit shadow state is incomplete."
            )
    elif (
        bool(policy.get("merit_baseline_available"))
        or bool(policy.get("merit_shadow_evaluated"))
    ):
        raise MultimodalInboxShadowIntegrityError(
            "No-Merit shadow unexpectedly evaluated Merit."
        )
    return result


def execute_multimodal_inbox_shadow_orchestration(
    *,
    subject: Mapping[str, Any],
    left_capture_record_id: str,
    right_capture_record_id: str,
    legacy_score: Any,
    merit_baseline_mode: str = "legacy_merit",
    target_claim_id: str = "",
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    capture_loader=(
        browser_capture_inbox
        .load_browser_capture_record
    ),
    orchestration_runner=(
        multimodal_shadow_orchestration
        .execute_multimodal_shadow_orchestration
    ),
) -> Dict[str, Any]:
    left_id = _record_id(
        left_capture_record_id,
        label="Left",
    )

    right_id = _record_id(
        right_capture_record_id,
        label="Right",
    )

    if left_id == right_id:
        raise MultimodalInboxShadowInputError(
            "Inbox shadow evaluation requires two distinct capture records."
        )

    if connection_factory is None:
        raise MultimodalInboxShadowInputError(
            "Connection factory is required."
        )

    if gemini_client is None:
        raise MultimodalInboxShadowProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalInboxShadowProviderUnavailable(
            "Gemini generator is unavailable."
        )

    normalized_subject = _mapping(
        subject,
        label="Subject",
    )

    normalized_merit_baseline_mode = _clean(
        merit_baseline_mode
    ).lower() or "legacy_merit"

    if normalized_merit_baseline_mode == "legacy_merit":
        normalized_score = _mapping(
            legacy_score,
            label="Legacy Merit score",
        )
    elif normalized_merit_baseline_mode == "not_applicable":
        if legacy_score is not None:
            raise MultimodalInboxShadowInputError(
                "No-Merit execution must not receive a legacy Merit score."
            )
        normalized_score = None
    else:
        raise MultimodalInboxShadowInputError(
            "Unsupported Merit baseline mode."
        )

    left = _load_capture(
        record_id=left_id,
        connection_factory=connection_factory,
        loader=capture_loader,
        label="Left",
    )

    right = _load_capture(
        record_id=right_id,
        connection_factory=connection_factory,
        loader=capture_loader,
        label="Right",
    )

    try:
        orchestration_raw = orchestration_runner(
            subject=normalized_subject,
            left_capture=left["capture"],
            right_capture=right["capture"],
            legacy_score=normalized_score,
            merit_baseline_mode=(
                normalized_merit_baseline_mode
            ),
            target_claim_id=_clean(
                target_claim_id
            ),
            connection_factory=(
                connection_factory
            ),
            gemini_client=gemini_client,
            gemini_client_key=(
                _clean(gemini_client_key)
                or "anonymous"
            ),
            gemini_generator=gemini_generator,
        )
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationInputError
    ) as error:
        raise MultimodalInboxShadowInputError(
            str(error)
        ) from error
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationBindingError
    ) as error:
        raise MultimodalInboxShadowBindingError(
            str(error)
        ) from error
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationProviderUnavailable
    ) as error:
        raise MultimodalInboxShadowProviderUnavailable(
            str(error)
        ) from error
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationClaimSelectionError
    ) as error:
        raise MultimodalInboxShadowClaimSelectionError(
            str(error)
        ) from error
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationExecutionError
    ) as error:
        raise MultimodalInboxShadowExecutionError(
            str(error)
        ) from error
    except (
        multimodal_shadow_orchestration
        .MultimodalShadowOrchestrationIntegrityError
    ) as error:
        raise MultimodalInboxShadowIntegrityError(
            str(error)
        ) from error

    orchestration = _validate_orchestration(
        orchestration_raw,
        merit_baseline_mode=(
            normalized_merit_baseline_mode
        ),
    )

    return {
        "version": (
            MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": orchestration[
            "claim_id"
        ],
        "left_capture_record_id": left_id,
        "right_capture_record_id": right_id,
        "orchestration": orchestration,
        "policy": {
            "admin_endpoint_uses_stored_capture_ids_only": True,
            "raw_capture_not_accepted_by_admin_endpoint": True,
            "inbox_records_remain_untrusted": True,
            "capture_integrity_rechecked_before_orchestration": True,
            "inbox_lookup_is_read_only": True,
            "subject_is_admin_supplied": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
            "evidence_remains_unverified": True,
            "model_output_does_not_establish_truth": True,
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
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
