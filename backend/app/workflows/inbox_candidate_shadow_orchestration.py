from __future__ import annotations

import sqlite3

from typing import Any, Dict, Mapping

from app.services import inbox_candidate_discovery
from app.services import multimodal_inbox_shadow_orchestration


MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION = (
    "multimodal-inbox-candidate-shadow-v1"
)


class MultimodalInboxCandidateShadowError(RuntimeError):
    pass


class MultimodalInboxCandidateShadowInputError(
    MultimodalInboxCandidateShadowError
):
    pass


class MultimodalInboxCandidateShadowDiscoveryError(
    MultimodalInboxCandidateShadowError
):
    pass


class MultimodalInboxCandidateShadowBindingError(
    MultimodalInboxCandidateShadowError
):
    pass


class MultimodalInboxCandidateShadowProviderUnavailable(
    MultimodalInboxCandidateShadowError
):
    pass


class MultimodalInboxCandidateShadowExecutionError(
    MultimodalInboxCandidateShadowError
):
    pass


class MultimodalInboxCandidateShadowClaimSelectionError(
    MultimodalInboxCandidateShadowExecutionError
):
    pass


class MultimodalInboxCandidateShadowIntegrityError(
    MultimodalInboxCandidateShadowError
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
        raise MultimodalInboxCandidateShadowInputError(
            label + " must be an object."
        )

    return dict(value)


def _bounded_int(
    value: Any,
    *,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise MultimodalInboxCandidateShadowInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxCandidateShadowInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise MultimodalInboxCandidateShadowInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _connect(connection_factory):
    if connection_factory is None:
        raise MultimodalInboxCandidateShadowInputError(
            "Connection factory is required."
        )

    try:
        conn = connection_factory()
    except Exception as error:
        raise MultimodalInboxCandidateShadowBindingError(
            "Canonical entity lookup is unavailable."
        ) from error

    if conn is None:
        raise MultimodalInboxCandidateShadowBindingError(
            "Canonical entity lookup is unavailable."
        )

    return conn


def _entity_ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()

    return {
        _clean(row.get("id"))
        for row in value
        if (
            isinstance(row, Mapping)
            and _clean(row.get("id"))
        )
    }


def _validate_discovery(
    value: Any,
    *,
    anchor_capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != (
            inbox_candidate_discovery
            .MULTIMODAL_INBOX_CANDIDATE_DISCOVERY_VERSION
        )
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery version mismatch."
        )

    status = _clean(
        result.get("status")
    ).lower()

    if status not in {
        "candidates_available",
        "no_candidates",
    }:
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery status is invalid."
        )

    if (
        _clean(
            result.get(
                "anchor_capture_record_id"
            )
        )
        != anchor_capture_record_id
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery anchor scope changed."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery policy is missing."
        )

    required_true = (
        "read_only_discovery",
        "inbox_records_remain_untrusted",
        "entity_candidates_do_not_verify_subject",
        "deterministic_score_is_ranking_only",
        "candidate_discovery_does_not_establish_corroboration",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Inbox discovery safety boundary missing: "
                + field
            )

    required_false = (
        "creates_claim",
        "creates_evidence",
        "creates_verified_binding",
        "establishes_truth",
        "establishes_authority",
        "establishes_independence",
        "affects_live_merit",
    )

    for field in required_false:
        if bool(policy.get(field)):
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Inbox discovery enabled forbidden field: "
                + field
            )

    candidates = result.get(
        "pair_candidates"
    )

    if not isinstance(candidates, list):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery candidates are invalid."
        )

    anchor = result.get("anchor")

    if not isinstance(anchor, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery anchor descriptor is missing."
        )

    return result


def _selected_candidate(
    discovery: Mapping[str, Any],
    *,
    candidate_capture_record_id: str,
) -> Dict[str, Any]:
    matches = []

    for raw in discovery.get(
        "pair_candidates",
        [],
    ):
        if not isinstance(raw, Mapping):
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Inbox discovery candidate is invalid."
            )

        row = dict(raw)

        if (
            _clean(
                row.get("capture_record_id")
            )
            == candidate_capture_record_id
        ):
            matches.append(row)

    if len(matches) > 1:
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery returned duplicate selected candidates."
        )

    if not matches:
        raise MultimodalInboxCandidateShadowDiscoveryError(
            "Selected capture is not a current discovery candidate."
        )

    candidate = matches[0]

    policy = candidate.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Selected discovery candidate policy is missing."
        )

    required_true = (
        "candidate_only",
        "same_story_not_established",
        "same_claim_not_established",
        "subject_not_verified",
        "independence_not_established",
        "corroboration_not_established",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Selected discovery candidate safety boundary missing: "
                + field
            )

    if bool(policy.get("affects_live_merit")):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Selected discovery candidate unexpectedly affects Live Merit."
        )

    signals = candidate.get("signals")

    if not isinstance(signals, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Selected discovery candidate signals are missing."
        )

    shared_ids = signals.get(
        "shared_entity_ids"
    )

    if not isinstance(shared_ids, list):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Selected discovery candidate shared entity scope is invalid."
        )

    return candidate


def _subject_descriptor(
    discovery: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    subject_entity_id: str,
    connection_factory,
) -> Dict[str, str]:
    anchor = discovery.get("anchor")

    if not isinstance(anchor, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox discovery anchor descriptor is missing."
        )

    anchor_ids = _entity_ids(
        anchor.get("entity_candidates")
    )

    candidate_ids = _entity_ids(
        candidate.get("entity_candidates")
    )

    signals = candidate.get("signals")

    if not isinstance(signals, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Selected discovery candidate signals are missing."
        )

    shared_ids = {
        _clean(value)
        for value in signals.get(
            "shared_entity_ids",
            [],
        )
        if _clean(value)
    }

    if (
        subject_entity_id not in anchor_ids
        or subject_entity_id not in candidate_ids
        or subject_entity_id not in shared_ids
    ):
        raise MultimodalInboxCandidateShadowBindingError(
            "Subject entity must be a shared exact entity candidate "
            "for the selected inbox pair."
        )

    conn = _connect(
        connection_factory
    )

    try:
        row = conn.execute(
            """
            SELECT
              id,
              entity_key,
              entity_type,
              sport_key,
              canonical_name
            FROM canonical_entities
            WHERE id = ?
            """,
            (
                subject_entity_id,
            ),
        ).fetchone()
    except sqlite3.Error as error:
        raise MultimodalInboxCandidateShadowBindingError(
            "Canonical subject lookup failed."
        ) from error
    finally:
        conn.close()

    if row is None:
        raise MultimodalInboxCandidateShadowBindingError(
            "Shared subject entity no longer exists."
        )

    subject = dict(row)

    if _clean(subject.get("id")) != subject_entity_id:
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Canonical subject scope changed."
        )

    descriptor = {
        "entity_key": _clean(
            subject.get("entity_key")
        ).casefold(),
        "entity_type": _clean(
            subject.get("entity_type")
        ).casefold(),
        "canonical_name": _clean(
            subject.get("canonical_name")
        ),
        "sport_key": _clean(
            subject.get("sport_key")
        ).casefold(),
    }

    if (
        not descriptor["entity_key"]
        or not descriptor["entity_type"]
        or not descriptor["canonical_name"]
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Canonical subject descriptor is incomplete."
        )

    return descriptor


def _validate_shadow(
    value: Any,
    *,
    anchor_capture_record_id: str,
    candidate_capture_record_id: str,
    merit_baseline_mode: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != (
            multimodal_inbox_shadow_orchestration
            .MULTIMODAL_INBOX_SHADOW_ORCHESTRATION_VERSION
        )
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration version mismatch."
        )

    if (
        _clean(result.get("status")).lower()
        != "completed_shadow"
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration did not complete."
        )

    if (
        _clean(
            result.get("left_capture_record_id")
        )
        != anchor_capture_record_id
        or _clean(
            result.get("right_capture_record_id")
        )
        != candidate_capture_record_id
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration pair scope changed."
        )

    claim_id = _clean(
        result.get("claim_id")
    )

    if not claim_id:
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow orchestration policy is missing."
        )

    required_true = (
        "admin_endpoint_uses_stored_capture_ids_only",
        "raw_capture_not_accepted_by_admin_endpoint",
        "capture_integrity_rechecked_before_orchestration",
        "binding_ids_generated_server_side",
        "shadow_adapter_reverifies_bindings",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Inbox shadow safety boundary missing: "
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
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Inbox shadow enabled forbidden field: "
                + field
            )


    if policy.get("merit_baseline_mode") != merit_baseline_mode:
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow Merit baseline mode changed."
        )
    if bool(policy.get("synthetic_merit_baseline_used")):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "Inbox shadow used a synthetic Merit baseline."
        )
    if merit_baseline_mode == "legacy_merit":
        if (
            policy.get("merit_baseline_available") is not True
            or policy.get("merit_shadow_evaluated") is not True
        ):
            raise MultimodalInboxCandidateShadowIntegrityError(
                "Legacy Merit shadow state is incomplete."
            )
    elif (
        bool(policy.get("merit_baseline_available"))
        or bool(policy.get("merit_shadow_evaluated"))
    ):
        raise MultimodalInboxCandidateShadowIntegrityError(
            "No-Merit shadow unexpectedly evaluated Merit."
        )
    return result


def execute_multimodal_inbox_candidate_shadow(
    *,
    anchor_capture_record_id: str,
    candidate_capture_record_id: str,
    subject_entity_id: str,
    legacy_score: Any,
    merit_baseline_mode: str = "legacy_merit",
    target_claim_id: str = "",
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    gemini_client: Any,
    gemini_client_key: str,
    gemini_generator,
    discovery_runner=(
        inbox_candidate_discovery
        .discover_multimodal_inbox_candidates
    ),
    shadow_runner=(
        multimodal_inbox_shadow_orchestration
        .execute_multimodal_inbox_shadow_orchestration
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )
    candidate_id = _clean(
        candidate_capture_record_id
    )
    subject_id = _clean(
        subject_entity_id
    )

    if not anchor_id:
        raise MultimodalInboxCandidateShadowInputError(
            "Anchor capture record ID is required."
        )

    if not candidate_id:
        raise MultimodalInboxCandidateShadowInputError(
            "Candidate capture record ID is required."
        )

    if anchor_id == candidate_id:
        raise MultimodalInboxCandidateShadowInputError(
            "Candidate shadow evaluation requires two distinct capture records."
        )

    if not subject_id:
        raise MultimodalInboxCandidateShadowInputError(
            "Subject entity ID is required."
        )

    if len(anchor_id) > 256 or len(candidate_id) > 256:
        raise MultimodalInboxCandidateShadowInputError(
            "Capture record ID is too long."
        )

    if len(subject_id) > 256:
        raise MultimodalInboxCandidateShadowInputError(
            "Subject entity ID is too long."
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
            raise MultimodalInboxCandidateShadowInputError(
                "No-Merit execution must not receive a legacy Merit score."
            )
        normalized_score = None
    else:
        raise MultimodalInboxCandidateShadowInputError(
            "Unsupported Merit baseline mode."
        )

    if connection_factory is None:
        raise MultimodalInboxCandidateShadowInputError(
            "Connection factory is required."
        )

    try:
        discovery_raw = discovery_runner(
            anchor_capture_record_id=anchor_id,
            connection_factory=connection_factory,
            scan_limit=scan_limit,
            max_candidates=max_candidates,
            semantic_assessments=0,
            gemini_client=None,
            gemini_client_key="anonymous",
            gemini_generator=None,
        )
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryInputError
    ) as error:
        raise MultimodalInboxCandidateShadowInputError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryNotFoundError
    ) as error:
        raise MultimodalInboxCandidateShadowDiscoveryError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryLookupError
    ) as error:
        raise MultimodalInboxCandidateShadowExecutionError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryIntegrityError
    ) as error:
        raise MultimodalInboxCandidateShadowIntegrityError(
            str(error)
        ) from error

    discovery = _validate_discovery(
        discovery_raw,
        anchor_capture_record_id=anchor_id,
    )

    candidate = _selected_candidate(
        discovery,
        candidate_capture_record_id=(
            candidate_id
        ),
    )

    subject = _subject_descriptor(
        discovery,
        candidate,
        subject_entity_id=subject_id,
        connection_factory=connection_factory,
    )

    try:
        shadow_raw = shadow_runner(
            subject=subject,
            left_capture_record_id=anchor_id,
            right_capture_record_id=candidate_id,
            legacy_score=normalized_score,
            merit_baseline_mode=(
                normalized_merit_baseline_mode
            ),
            target_claim_id=_clean(
                target_claim_id
            ),
            connection_factory=connection_factory,
            gemini_client=gemini_client,
            gemini_client_key=(
                _clean(gemini_client_key)
                or "anonymous"
            ),
            gemini_generator=gemini_generator,
        )
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowInputError
    ) as error:
        raise MultimodalInboxCandidateShadowInputError(
            str(error)
        ) from error
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowBindingError
    ) as error:
        raise MultimodalInboxCandidateShadowBindingError(
            str(error)
        ) from error
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowProviderUnavailable
    ) as error:
        raise MultimodalInboxCandidateShadowProviderUnavailable(
            str(error)
        ) from error
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowClaimSelectionError
    ) as error:
        raise MultimodalInboxCandidateShadowClaimSelectionError(
            str(error)
        ) from error
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowExecutionError
    ) as error:
        raise MultimodalInboxCandidateShadowExecutionError(
            str(error)
        ) from error
    except (
        multimodal_inbox_shadow_orchestration
        .MultimodalInboxShadowIntegrityError
    ) as error:
        raise MultimodalInboxCandidateShadowIntegrityError(
            str(error)
        ) from error

    shadow = _validate_shadow(
        shadow_raw,
        anchor_capture_record_id=anchor_id,
        candidate_capture_record_id=candidate_id,
        merit_baseline_mode=(
            normalized_merit_baseline_mode
        ),
    )

    return {
        "version": (
            MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": shadow["claim_id"],
        "anchor_capture_record_id": anchor_id,
        "candidate_capture_record_id": candidate_id,
        "subject_entity_id": subject_id,
        "subject": subject,
        "discovery_gate": {
            "discovery_version": discovery[
                "version"
            ],
            "candidate_score": candidate.get(
                "candidate_score"
            ),
            "candidate_reasons": candidate.get(
                "candidate_reasons",
                [],
            ),
            "shared_entity_ids": candidate[
                "signals"
            ]["shared_entity_ids"],
        },
        "orchestration": shadow,
        "policy": {
            "candidate_must_be_currently_discovered": True,
            "discovery_gate_is_read_only": True,
            "discovery_score_is_ranking_only": True,
            "discovery_does_not_establish_same_claim": True,
            "subject_entity_must_be_shared_exact_candidate": True,
            "shared_entity_candidate_does_not_verify_subject": True,
            "subject_descriptor_loaded_server_side": True,
            "caller_cannot_supply_subject_descriptor": True,
            "caller_cannot_supply_binding_ids": True,
            "downstream_exact_common_claim_required": True,
            "capture_integrity_rechecked_downstream": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
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
