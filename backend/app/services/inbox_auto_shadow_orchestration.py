from __future__ import annotations

import math

from typing import Any, Dict, Mapping

from app.services import inbox_candidate_discovery
from app.services import inbox_candidate_shadow_orchestration


MULTIMODAL_INBOX_AUTO_SHADOW_VERSION = (
    "multimodal-inbox-auto-shadow-v1"
)

MULTIMODAL_INBOX_AUTO_SELECTION_VERSION = (
    "multimodal-inbox-auto-selection-v1"
)


class MultimodalInboxAutoShadowError(RuntimeError):
    pass


class MultimodalInboxAutoShadowInputError(
    MultimodalInboxAutoShadowError
):
    pass


class MultimodalInboxAutoShadowDiscoveryError(
    MultimodalInboxAutoShadowError
):
    pass


class MultimodalInboxAutoShadowSelectionError(
    MultimodalInboxAutoShadowError
):
    pass


class MultimodalInboxAutoShadowProviderUnavailable(
    MultimodalInboxAutoShadowError
):
    pass


class MultimodalInboxAutoShadowExecutionError(
    MultimodalInboxAutoShadowError
):
    pass


class MultimodalInboxAutoShadowIntegrityError(
    MultimodalInboxAutoShadowError
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
        raise MultimodalInboxAutoShadowInputError(
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
        raise MultimodalInboxAutoShadowInputError(
            label + " must be an integer."
        )

    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxAutoShadowInputError(
            label + " must be an integer."
        ) from error

    if result < minimum or result > maximum:
        raise MultimodalInboxAutoShadowInputError(
            label
            + " must be between "
            + str(minimum)
            + " and "
            + str(maximum)
            + "."
        )

    return result


def _validate_discovery(
    value: Any,
    *,
    anchor_capture_record_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
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
        raise MultimodalInboxAutoShadowIntegrityError(
            "Inbox discovery version mismatch."
        )

    if (
        _clean(
            result.get(
                "anchor_capture_record_id"
            )
        )
        != anchor_capture_record_id
    ):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Inbox discovery anchor scope changed."
        )

    status = _clean(
        result.get("status")
    ).lower()

    if status not in {
        "candidates_available",
        "no_candidates",
    }:
        raise MultimodalInboxAutoShadowIntegrityError(
            "Inbox discovery status is invalid."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
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
            raise MultimodalInboxAutoShadowIntegrityError(
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
            raise MultimodalInboxAutoShadowIntegrityError(
                "Inbox discovery enabled forbidden field: "
                + field
            )

    candidates = result.get(
        "pair_candidates"
    )

    if not isinstance(candidates, list):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Inbox discovery candidates are invalid."
        )

    return result


def _candidate_score(row: Mapping[str, Any]) -> float:
    value = row.get("candidate_score")

    if isinstance(value, bool):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate score is invalid."
        )

    try:
        score = float(value)
    except (TypeError, ValueError) as error:
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate score is invalid."
        ) from error

    if (
        not math.isfinite(score)
        or score < 0.0
        or score > 1.0
    ):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate score is outside its contract."
        )

    return score


def _shared_entity_ids(
    candidate: Mapping[str, Any],
) -> list[str]:
    signals = candidate.get("signals")

    if not isinstance(signals, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate signals are missing."
        )

    raw_ids = signals.get(
        "shared_entity_ids"
    )

    if not isinstance(raw_ids, list):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate shared entity scope is invalid."
        )

    values = []
    seen = set()

    for raw in raw_ids:
        value = _clean(raw)

        if not value or value in seen:
            continue

        seen.add(value)
        values.append(value)

    return values


def _validate_candidate_policy(
    candidate: Mapping[str, Any],
) -> None:
    policy = candidate.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate policy is missing."
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
            raise MultimodalInboxAutoShadowIntegrityError(
                "Discovery candidate safety boundary missing: "
                + field
            )

    if bool(policy.get("affects_live_merit")):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Discovery candidate unexpectedly affects Live Merit."
        )


def _automatic_selection(
    discovery: Mapping[str, Any],
) -> Dict[str, Any]:
    candidates = discovery.get(
        "pair_candidates",
        [],
    )

    if not candidates:
        raise MultimodalInboxAutoShadowSelectionError(
            "No current inbox discovery candidate is available for automatic shadow evaluation."
        )

    eligible = []
    rejected = []
    seen_candidate_ids = set()

    for raw in candidates:
        if not isinstance(raw, Mapping):
            raise MultimodalInboxAutoShadowIntegrityError(
                "Inbox discovery candidate is invalid."
            )

        candidate = dict(raw)
        candidate_id = _clean(
            candidate.get("capture_record_id")
        )

        if not candidate_id:
            raise MultimodalInboxAutoShadowIntegrityError(
                "Inbox discovery candidate ID is missing."
            )

        if candidate_id in seen_candidate_ids:
            raise MultimodalInboxAutoShadowIntegrityError(
                "Inbox discovery returned duplicate candidate IDs."
            )

        seen_candidate_ids.add(candidate_id)

        _validate_candidate_policy(
            candidate
        )

        score = _candidate_score(
            candidate
        )

        shared_ids = _shared_entity_ids(
            candidate
        )

        if len(shared_ids) != 1:
            rejected.append({
                "capture_record_id": candidate_id,
                "reason": (
                    "no_shared_exact_entity"
                    if not shared_ids
                    else "multiple_shared_exact_entities"
                ),
                "shared_entity_count": len(
                    shared_ids
                ),
                "candidate_score": score,
            })
            continue

        eligible.append({
            "capture_record_id": candidate_id,
            "subject_entity_id": shared_ids[0],
            "candidate_score": score,
            "candidate_reasons": list(
                candidate.get(
                    "candidate_reasons",
                    [],
                )
            )
            if isinstance(
                candidate.get(
                    "candidate_reasons",
                    [],
                ),
                list,
            )
            else [],
            "shared_entity_ids": shared_ids,
        })

    if not eligible:
        raise MultimodalInboxAutoShadowSelectionError(
            "No current discovery candidate has exactly one shared exact entity candidate."
        )

    if len(eligible) != 1:
        raise MultimodalInboxAutoShadowSelectionError(
            "Automatic inbox selection is ambiguous; manual candidate selection is required."
        )

    selected = eligible[0]

    return {
        "selected": selected,
        "eligible_count": len(eligible),
        "rejected_count": len(rejected),
        "rejected": rejected,
    }



def select_automatic_inbox_candidate(
    *,
    anchor_capture_record_id: str,
    scan_limit: int = 100,
    max_candidates: int = 12,
    connection_factory,
    discovery_runner=(
        inbox_candidate_discovery
        .discover_multimodal_inbox_candidates
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )

    if not anchor_id:
        raise MultimodalInboxAutoShadowInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxAutoShadowInputError(
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
        raise MultimodalInboxAutoShadowInputError(
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
        raise MultimodalInboxAutoShadowInputError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryNotFoundError
    ) as error:
        raise MultimodalInboxAutoShadowDiscoveryError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryLookupError
    ) as error:
        raise MultimodalInboxAutoShadowDiscoveryError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryIntegrityError
    ) as error:
        raise MultimodalInboxAutoShadowIntegrityError(
            str(error)
        ) from error

    discovery = _validate_discovery(
        discovery_raw,
        anchor_capture_record_id=anchor_id,
    )

    selection = _automatic_selection(
        discovery
    )

    selected = selection["selected"]

    return {
        "version": MULTIMODAL_INBOX_AUTO_SELECTION_VERSION,
        "status": "selected",
        "anchor_capture_record_id": anchor_id,
        "candidate_capture_record_id": selected[
            "capture_record_id"
        ],
        "subject_entity_id": selected[
            "subject_entity_id"
        ],
        "candidate_score": selected[
            "candidate_score"
        ],
        "candidate_reasons": selected[
            "candidate_reasons"
        ],
        "shared_entity_ids": selected[
            "shared_entity_ids"
        ],
        "eligible_candidate_count": selection[
            "eligible_count"
        ],
        "rejected_candidate_count": selection[
            "rejected_count"
        ],
        "rejected_candidates": selection[
            "rejected"
        ],
        "policy": {
            "automatic_selection_is_candidate_routing_only": True,
            "automatic_selection_requires_exactly_one_eligible_candidate": True,
            "eligible_candidate_requires_exactly_one_shared_entity": True,
            "candidate_score_is_not_a_truth_confidence": True,
            "candidate_score_is_not_an_authority_confidence": True,
            "candidate_score_is_not_an_independence_confidence": True,
            "discovery_gate_is_read_only": True,
            "selected_subject_is_exact_entity_candidate_only": True,
            "selected_subject_is_not_verified_by_auto_selection": True,
            "affects_live_merit": False,
        },
    }

def _validate_candidate_shadow(
    value: Any,
    *,
    anchor_capture_record_id: str,
    candidate_capture_record_id: str,
    subject_entity_id: str,
) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration returned an invalid result."
        )

    result = dict(value)

    if (
        _clean(result.get("version"))
        != (
            inbox_candidate_shadow_orchestration
            .MULTIMODAL_INBOX_CANDIDATE_SHADOW_VERSION
        )
    ):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration version mismatch."
        )

    if (
        _clean(result.get("status")).lower()
        != "completed_shadow"
    ):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration did not complete."
        )

    if (
        _clean(
            result.get(
                "anchor_capture_record_id"
            )
        )
        != anchor_capture_record_id
        or _clean(
            result.get(
                "candidate_capture_record_id"
            )
        )
        != candidate_capture_record_id
        or _clean(
            result.get("subject_entity_id")
        )
        != subject_entity_id
    ):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration scope changed."
        )

    claim_id = _clean(
        result.get("claim_id")
    )

    if not claim_id:
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration did not expose a claim ID."
        )

    policy = result.get("policy")

    if not isinstance(policy, Mapping):
        raise MultimodalInboxAutoShadowIntegrityError(
            "Candidate shadow orchestration policy is missing."
        )

    required_true = (
        "candidate_must_be_currently_discovered",
        "discovery_gate_is_read_only",
        "discovery_score_is_ranking_only",
        "discovery_does_not_establish_same_claim",
        "subject_entity_must_be_shared_exact_candidate",
        "shared_entity_candidate_does_not_verify_subject",
        "subject_descriptor_loaded_server_side",
        "caller_cannot_supply_subject_descriptor",
        "caller_cannot_supply_binding_ids",
        "downstream_exact_common_claim_required",
        "binding_ids_generated_server_side",
        "shadow_adapter_reverifies_bindings",
        "live_merit_shadow_only",
        "live_release_not_called",
    )

    for field in required_true:
        if policy.get(field) is not True:
            raise MultimodalInboxAutoShadowIntegrityError(
                "Candidate shadow safety boundary missing: "
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
            raise MultimodalInboxAutoShadowIntegrityError(
                "Candidate shadow enabled forbidden field: "
                + field
            )

    return result


def execute_multimodal_inbox_auto_shadow(
    *,
    anchor_capture_record_id: str,
    legacy_score: Mapping[str, Any],
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
    candidate_shadow_runner=(
        inbox_candidate_shadow_orchestration
        .execute_multimodal_inbox_candidate_shadow
    ),
) -> Dict[str, Any]:
    anchor_id = _clean(
        anchor_capture_record_id
    )

    if not anchor_id:
        raise MultimodalInboxAutoShadowInputError(
            "Anchor capture record ID is required."
        )

    if len(anchor_id) > 256:
        raise MultimodalInboxAutoShadowInputError(
            "Anchor capture record ID is too long."
        )

    normalized_score = _mapping(
        legacy_score,
        label="Legacy Merit score",
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
        raise MultimodalInboxAutoShadowInputError(
            "Connection factory is required."
        )

    if gemini_client is None:
        raise MultimodalInboxAutoShadowProviderUnavailable(
            "Gemini multimodal client is not configured."
        )

    if not callable(gemini_generator):
        raise MultimodalInboxAutoShadowProviderUnavailable(
            "Gemini generator is unavailable."
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
        raise MultimodalInboxAutoShadowInputError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryNotFoundError
    ) as error:
        raise MultimodalInboxAutoShadowDiscoveryError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryLookupError
    ) as error:
        raise MultimodalInboxAutoShadowExecutionError(
            str(error)
        ) from error
    except (
        inbox_candidate_discovery
        .InboxCandidateDiscoveryIntegrityError
    ) as error:
        raise MultimodalInboxAutoShadowIntegrityError(
            str(error)
        ) from error

    discovery = _validate_discovery(
        discovery_raw,
        anchor_capture_record_id=anchor_id,
    )

    selection = _automatic_selection(
        discovery
    )

    selected = selection[
        "selected"
    ]

    candidate_id = selected[
        "capture_record_id"
    ]
    subject_id = selected[
        "subject_entity_id"
    ]

    try:
        shadow_raw = candidate_shadow_runner(
            anchor_capture_record_id=anchor_id,
            candidate_capture_record_id=candidate_id,
            subject_entity_id=subject_id,
            legacy_score=normalized_score,
            target_claim_id=_clean(
                target_claim_id
            ),
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
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowInputError
    ) as error:
        raise MultimodalInboxAutoShadowInputError(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowDiscoveryError
    ) as error:
        raise MultimodalInboxAutoShadowDiscoveryError(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowBindingError
    ) as error:
        raise MultimodalInboxAutoShadowSelectionError(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowProviderUnavailable
    ) as error:
        raise MultimodalInboxAutoShadowProviderUnavailable(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowExecutionError
    ) as error:
        raise MultimodalInboxAutoShadowExecutionError(
            str(error)
        ) from error
    except (
        inbox_candidate_shadow_orchestration
        .MultimodalInboxCandidateShadowIntegrityError
    ) as error:
        raise MultimodalInboxAutoShadowIntegrityError(
            str(error)
        ) from error

    shadow = _validate_candidate_shadow(
        shadow_raw,
        anchor_capture_record_id=anchor_id,
        candidate_capture_record_id=candidate_id,
        subject_entity_id=subject_id,
    )

    return {
        "version": (
            MULTIMODAL_INBOX_AUTO_SHADOW_VERSION
        ),
        "status": "completed_shadow",
        "claim_id": shadow["claim_id"],
        "anchor_capture_record_id": anchor_id,
        "selected_candidate_capture_record_id": candidate_id,
        "selected_subject_entity_id": subject_id,
        "automatic_selection": {
            "selection_mode": (
                "single_unambiguous_discovery_candidate"
            ),
            "candidate_score": selected[
                "candidate_score"
            ],
            "candidate_reasons": selected[
                "candidate_reasons"
            ],
            "shared_entity_ids": selected[
                "shared_entity_ids"
            ],
            "eligible_candidate_count": selection[
                "eligible_count"
            ],
            "rejected_candidate_count": selection[
                "rejected_count"
            ],
            "rejected_candidates": selection[
                "rejected"
            ],
        },
        "orchestration": shadow,
        "policy": {
            "automatic_selection_is_candidate_routing_only": True,
            "automatic_selection_requires_exactly_one_eligible_candidate": True,
            "eligible_candidate_requires_exactly_one_shared_entity": True,
            "candidate_score_is_not_a_truth_confidence": True,
            "candidate_score_is_not_an_authority_confidence": True,
            "candidate_score_is_not_an_independence_confidence": True,
            "discovery_gate_is_read_only": True,
            "discovery_semantic_assessment_not_used_for_auto_selection": True,
            "selected_subject_is_exact_entity_candidate_only": True,
            "selected_subject_is_not_verified_by_auto_selection": True,
            "caller_cannot_supply_candidate_capture_id": True,
            "caller_cannot_supply_subject_entity_id": True,
            "downstream_candidate_gate_revalidates_selection": True,
            "downstream_exact_common_claim_required": True,
            "binding_ids_generated_server_side": True,
            "shadow_adapter_reverifies_bindings": True,
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
