from __future__ import annotations

from typing import Any, Dict, Mapping

from app.services import browser_capture_inbox
from app.services import inbox_auto_shadow_orchestration
from app.services import inbox_candidate_shadow_orchestration


MULTIMODAL_INBOX_NO_MERIT_AUTO_SHADOW_VERSION = (
    "multimodal-inbox-no-merit-auto-shadow-v1"
)

SUPPORTED_NON_ARTICLE_PLATFORMS = frozenset({
    "youtube",
    "x",
    "instagram",
    "tiktok",
    "reddit",
    "facebook",
})


class MultimodalInboxNoMeritAutoShadowError(RuntimeError):
    pass


class MultimodalInboxNoMeritAutoShadowInputError(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


class MultimodalInboxNoMeritAutoShadowNotReady(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


class MultimodalInboxNoMeritAutoShadowLookupError(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


class MultimodalInboxNoMeritAutoShadowProviderUnavailable(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


class MultimodalInboxNoMeritAutoShadowExecutionError(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


class MultimodalInboxNoMeritAutoShadowIntegrityError(
    MultimodalInboxNoMeritAutoShadowError
):
    pass


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _bounded_int(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise MultimodalInboxNoMeritAutoShadowInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _load_anchor_scope(
    *,
    anchor_capture_record_id: str,
    connection_factory,
    capture_loader,
) -> Dict[str, Any]:
    try:
        loaded = capture_loader(
            capture_record_id=(
                anchor_capture_record_id
            ),
            connection_factory=(
                connection_factory
            ),
        )
    except browser_capture_inbox.BrowserCaptureInboxInputError as error:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            str(error)
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxNotFoundError as error:
        raise MultimodalInboxNoMeritAutoShadowNotReady(
            "Anchor browser capture record does not exist."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxPersistenceError as error:
        raise MultimodalInboxNoMeritAutoShadowLookupError(
            "Anchor browser capture lookup failed."
        ) from error
    except browser_capture_inbox.BrowserCaptureInboxIntegrityError as error:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture failed integrity validation."
        ) from error

    if not isinstance(loaded, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture loader returned an invalid result."
        )

    result = dict(loaded)

    if (
        _clean(result.get("version"))
        != browser_capture_inbox.BROWSER_CAPTURE_INBOX_VERSION
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture inbox version mismatch."
        )

    if (
        _clean(
            result.get("capture_record_id")
        )
        != anchor_capture_record_id
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture scope changed."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture policy is missing."
        )

    if policy.get("record_is_untrusted") is not True:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture trust boundary is missing."
        )

    if policy.get("integrity_rechecked_on_load") is not True:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture integrity boundary is missing."
        )

    if bool(policy.get("affects_live_merit")):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture unexpectedly affects Live Merit."
        )

    capture = result.get("capture")

    if not isinstance(capture, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture payload is missing."
        )

    payload = capture.get("payload")

    if not isinstance(payload, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture content payload is missing."
        )

    platform = _clean(
        result.get("platform")
    ).lower()
    surface = _clean(
        result.get("platform_surface")
    ).lower()
    payload_platform = _clean(
        payload.get("platform")
    ).lower()
    payload_surface = _clean(
        payload.get("surface")
    ).lower()

    if (
        not platform
        or not surface
        or platform != payload_platform
        or surface != payload_surface
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Anchor browser capture platform scope changed."
        )

    if platform == "web" and surface == "article":
        raise MultimodalInboxNoMeritAutoShadowInputError(
            "Web article anchors require the persisted legacy Merit baseline path."
        )

    if platform not in SUPPORTED_NON_ARTICLE_PLATFORMS:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            "Automatic no-Merit shadow execution does not support this capture platform."
        )

    return {
        "record": result,
        "platform": platform,
        "surface": surface,
    }


def _validate_selection(
    value: Any,
    *,
    anchor_capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != inbox_auto_shadow_orchestration.MULTIMODAL_INBOX_AUTO_SELECTION_VERSION
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection version mismatch."
        )

    if _clean(result.get("status")).lower() != "selected":
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection did not select a pair."
        )

    if (
        _clean(
            result.get("anchor_capture_record_id")
        )
        != anchor_capture_record_id
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection changed the anchor scope."
        )

    candidate_id = _clean(
        result.get("candidate_capture_record_id")
    )
    subject_id = _clean(
        result.get("subject_entity_id")
    )

    if not candidate_id or not subject_id:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection is incomplete."
        )

    if candidate_id == anchor_capture_record_id:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection returned the anchor as its own peer."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection policy is missing."
        )

    required_true = (
        "automatic_selection_is_candidate_routing_only",
        "automatic_selection_requires_exactly_one_eligible_candidate",
        "eligible_candidate_requires_exactly_one_shared_entity",
        "candidate_score_is_not_a_truth_confidence",
        "candidate_score_is_not_an_authority_confidence",
        "candidate_score_is_not_an_independence_confidence",
        "discovery_gate_is_read_only",
        "selected_subject_is_exact_entity_candidate_only",
        "selected_subject_is_not_verified_by_auto_selection",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxNoMeritAutoShadowIntegrityError(
                "Automatic inbox selection safety boundary missing: "
                + field
            )

    if bool(policy.get("affects_live_merit")):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "Automatic inbox selection unexpectedly affects Live Merit."
        )

    return result


def _validate_candidate_shadow(
    value: Any,
    *,
    anchor_capture_record_id: str,
    candidate_capture_record_id: str,
    subject_entity_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != inbox_candidate_shadow_orchestration.MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow version mismatch."
        )

    if _clean(result.get("status")).lower() != "completed_shadow":
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow did not complete."
        )

    if (
        _clean(result.get("anchor_capture_record_id"))
        != anchor_capture_record_id
        or _clean(result.get("candidate_capture_record_id"))
        != candidate_capture_record_id
        or _clean(result.get("subject_entity_id"))
        != subject_entity_id
    ):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow changed pair or subject scope."
        )

    claim_id = _clean(result.get("claim_id"))

    if not claim_id:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow policy is missing."
        )

    required_true = (
        "candidate_must_be_currently_discovered",
        "discovery_gate_is_read_only",
        "subject_entity_must_be_shared_exact_candidate",
        "subject_descriptor_loaded_server_side",
        "downstream_exact_common_claim_required",
        "binding_ids_generated_server_side",
        "shadow_adapter_reverifies_bindings",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxNoMeritAutoShadowIntegrityError(
                "No-Merit candidate shadow safety boundary missing: "
                + field
            )

    if policy.get("merit_baseline_mode") != "not_applicable":
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow baseline mode changed."
        )

    if bool(policy.get("merit_baseline_available")):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow unexpectedly has a Merit baseline."
        )

    if bool(policy.get("merit_shadow_evaluated")):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow unexpectedly evaluated the Merit overlay."
        )

    if bool(policy.get("synthetic_merit_baseline_used")):
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            "No-Merit candidate shadow used a synthetic Merit baseline."
        )

    for field in (
        "score_effect_applied",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    ):
        if bool(policy.get(field)):
            raise MultimodalInboxNoMeritAutoShadowIntegrityError(
                "No-Merit candidate shadow enabled forbidden field: "
                + field
            )

    return result


def execute_multimodal_inbox_no_merit_auto_shadow(
    *,
    anchor_capture_record_id: str,
    target_claim_id: str = "",
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    capture_loader=(
        browser_capture_inbox.load_browser_capture_record
    ),
    selection_runner=(
        inbox_auto_shadow_orchestration
        .select_automatic_inbox_candidate
    ),
    candidate_shadow_runner=(
        inbox_candidate_shadow_orchestration
        .execute_multimodal_inbox_candidate_shadow
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )

    if not anchor_id:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            "Anchor capture record ID is too long."
        )

    scan_limit = _bounded_int(
        scan_limit,
        label="Inbox scan limit",
        minimum=1,
        maximum=500,
    )

    max_candidates = _bounded_int(
        max_candidates,
        label="Candidate limit",
        minimum=1,
        maximum=50,
    )

    if connection_factory is None:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            "Connection factory is required."
        )

    if gemini_client is None:
        raise MultimodalInboxNoMeritAutoShadowProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalInboxNoMeritAutoShadowProviderUnavailable(
            "Gemini generator is unavailable."
        )

    anchor = _load_anchor_scope(
        anchor_capture_record_id=anchor_id,
        connection_factory=connection_factory,
        capture_loader=capture_loader,
    )

    try:
        selection_raw = selection_runner(
            anchor_capture_record_id=anchor_id,
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            connection_factory=connection_factory,
        )
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowInputError as error:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            str(error)
        ) from error
    except (
        inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowDiscoveryError,
        inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowSelectionError,
    ) as error:
        raise MultimodalInboxNoMeritAutoShadowNotReady(
            str(error)
        ) from error
    except inbox_auto_shadow_orchestration.MultimodalInboxAutoShadowIntegrityError as error:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            str(error)
        ) from error

    selection = _validate_selection(
        selection_raw,
        anchor_capture_record_id=anchor_id,
    )

    candidate_id = _clean(
        selection.get("candidate_capture_record_id")
    )
    subject_id = _clean(
        selection.get("subject_entity_id")
    )

    try:
        shadow_raw = candidate_shadow_runner(
            anchor_capture_record_id=anchor_id,
            candidate_capture_record_id=candidate_id,
            subject_entity_id=subject_id,
            legacy_score=None,
            merit_baseline_mode="not_applicable",
            target_claim_id=_clean(target_claim_id),
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            connection_factory=connection_factory,
            gemini_client=gemini_client,
            gemini_client_key=(
                _clean(gemini_client_key)
                or "anonymous"
            ),
            gemini_generator=gemini_generator,
        )
    except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowInputError as error:
        raise MultimodalInboxNoMeritAutoShadowInputError(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowDiscoveryError,
        inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowBindingError,
    ) as error:
        raise MultimodalInboxNoMeritAutoShadowNotReady(
            str(error)
        ) from error
    except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowProviderUnavailable as error:
        raise MultimodalInboxNoMeritAutoShadowProviderUnavailable(
            str(error)
        ) from error
    except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowExecutionError as error:
        raise MultimodalInboxNoMeritAutoShadowExecutionError(
            str(error)
        ) from error
    except inbox_candidate_shadow_orchestration.MultimodalInboxCandidateShadowIntegrityError as error:
        raise MultimodalInboxNoMeritAutoShadowIntegrityError(
            str(error)
        ) from error

    shadow = _validate_candidate_shadow(
        shadow_raw,
        anchor_capture_record_id=anchor_id,
        candidate_capture_record_id=candidate_id,
        subject_entity_id=subject_id,
    )

    return {
        "version": MULTIMODAL_INBOX_NO_MERIT_AUTO_SHADOW_VERSION,
        "status": "completed_shadow",
        "claim_id": shadow["claim_id"],
        "anchor_capture_record_id": anchor_id,
        "selected_candidate_capture_record_id": candidate_id,
        "selected_subject_entity_id": subject_id,
        "baseline_resolution": {
            "mode": "not_applicable",
            "reason": "no_legacy_merit_baseline_for_non_article",
            "platform": anchor["platform"],
            "surface": anchor["surface"],
            "legacy_score": None,
            "synthetic_merit_baseline_used": False,
        },
        "automatic_selection": selection,
        "orchestration": shadow,
        "policy": {
            "non_article_anchor_required": True,
            "supported_non_article_platform_required": True,
            "automatic_selection_is_candidate_routing_only": True,
            "downstream_candidate_gate_revalidates_selection": True,
            "downstream_exact_common_claim_required": True,
            "no_legacy_merit_baseline_exists": True,
            "synthetic_merit_baseline_used": False,
            "video_component_scores_not_reinterpreted_as_merit": True,
            "merit_baseline_mode": "not_applicable",
            "merit_baseline_available": False,
            "merit_shadow_evaluated": False,
            "live_merit_shadow_only": True,
            "live_release_not_called": True,
            "release_certificate_not_consumed": True,
            "score_effect_applied": False,
            "establishes_truth": False,
            "establishes_authority": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    }
