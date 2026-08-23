from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    Mapping,
)


from app.intelligence.canonical_claims import (
    CANONICAL_CLAIM_CONTRACT_VERSION,
    normalize_canonical_claim,
)


CANONICAL_OUTCOME_CONTRACT_VERSION = (
    "canonical-outcome-contract-v1"
)

CANONICAL_OUTCOME_SUPPORTED_EVENT_TYPES = {
    "transfer",
}

CANONICAL_OUTCOME_AGAINST_RULES = {
    (
        "completed",
        False,
        "failed",
        False,
    ): (
        "transfer_completed_then_failed"
    ),
    (
        "completed",
        False,
        "cancelled",
        False,
    ): (
        "transfer_completed_then_cancelled"
    ),
    (
        "completed",
        False,
        "completed",
        True,
    ): (
        "transfer_completed_explicitly_negated"
    ),
}

CANONICAL_OUTCOME_SUPPORT_RULES = {
    (
        "completed",
        False,
        "completed",
        False,
    ): (
        "transfer_completed_confirmed"
    ),
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _timestamp(
    value: Any,
    *,
    label: str,
) -> datetime:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    if text.endswith(
        "Z"
    ):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                text
            )
        )

    except ValueError as exc:
        raise ValueError(
            f"{label} must be ISO-8601."
        ) from exc

    if (
        parsed.tzinfo is None
        or parsed.utcoffset()
        is None
    ):
        raise ValueError(
            f"{label} must include a timezone."
        )

    return parsed


def _policy() -> Dict[str, Any]:
    return {
        "deterministic_only": True,
        "provider_call_performed": False,
        "supported_event_types": [
            "transfer"
        ],
        "requires_later_outcome": True,
        "requires_same_subject": True,
        "requires_same_event_type": True,
        "requires_same_transfer_destination": True,
        "requires_matching_effective_period": True,
        "overlapping_origin_must_not_conflict": True,
        "overlapping_transfer_kind_must_not_conflict": True,
        "state_transition_rules_are_explicit": True,
        "agreement_then_failure_is_not_automatically_false": True,
        "comparison_does_not_verify_source": True,
        "comparison_does_not_verify_authority": True,
        "comparison_does_not_establish_claim_truth": True,
        "comparison_is_not_a_falsehood_label": True,
        "candidate_resolution_is_temporal": True,
        "machine_verified_outcome_required_before_resolved_label": True,
        "numeric_negative_penalty_authorized": False,
        "live_negative_merit_authorized": False,
        "live_merit_changed": False,
    }


def _result(
    *,
    status: str,
    direction: str,
    rule_id: str,
    claim: Dict[str, Any],
    outcome: Dict[str, Any],
    claim_observed_at: datetime,
    outcome_observed_at: datetime,
    reason: str,
) -> Dict[str, Any]:
    return {
        "version": (
            CANONICAL_OUTCOME_CONTRACT_VERSION
        ),
        "status": status,
        "direction": direction,
        "rule_id": rule_id,
        "reason": reason,
        "claim": claim,
        "outcome": outcome,
        "claim_observed_at": (
            claim_observed_at.isoformat()
        ),
        "outcome_observed_at": (
            outcome_observed_at.isoformat()
        ),
        "candidate_resolution": {
            "against_claim": (
                direction
                == "against_claim"
            ),
            "supports_claim": (
                direction
                == "supports_claim"
            ),
            "indeterminate": (
                direction
                == "indeterminate"
            ),
            "claim_truth_established": False,
            "machine_verified": False,
            "source_authority_verified": False,
            "live_merit_effect_enabled": False,
        },
        "policy": _policy(),
    }


def _transfer_occurrence_status(
    *,
    claim: Mapping[str, Any],
    outcome: Mapping[str, Any],
) -> Dict[str, str]:
    claim_roles = claim[
        "roles"
    ]

    outcome_roles = outcome[
        "roles"
    ]

    claim_facets = claim[
        "facets"
    ]

    outcome_facets = outcome[
        "facets"
    ]

    claim_destination = _clean(
        claim_roles.get(
            "destination"
        )
    )

    outcome_destination = _clean(
        outcome_roles.get(
            "destination"
        )
    )

    if (
        not claim_destination
        or not outcome_destination
    ):
        return {
            "status": (
                "resolution_event_identity_insufficient"
            ),
            "reason": (
                "Transfer destination is required "
                "for outcome comparison."
            ),
        }

    if (
        claim_destination
        != outcome_destination
    ):
        return {
            "status": (
                "different_transfer_destination"
            ),
            "reason": (
                "The claim and outcome reference "
                "different transfer destinations."
            ),
        }

    claim_period = _clean(
        claim_facets.get(
            "effective_period"
        )
    )

    outcome_period = _clean(
        outcome_facets.get(
            "effective_period"
        )
    )

    if (
        not claim_period
        or not outcome_period
    ):
        return {
            "status": (
                "resolution_event_identity_insufficient"
            ),
            "reason": (
                "Canonical outcome v1 requires "
                "effective_period on both transfer "
                "records to avoid conflating "
                "different transfer occurrences."
            ),
        }

    if (
        claim_period
        != outcome_period
    ):
        return {
            "status": (
                "different_transfer_occurrence"
            ),
            "reason": (
                "The claim and outcome have "
                "different effective periods."
            ),
        }

    claim_origin = _clean(
        claim_roles.get(
            "origin"
        )
    )

    outcome_origin = _clean(
        outcome_roles.get(
            "origin"
        )
    )

    if (
        claim_origin
        and outcome_origin
        and claim_origin
        != outcome_origin
    ):
        return {
            "status": (
                "material_transfer_conflict"
            ),
            "reason": (
                "The claim and outcome have "
                "conflicting explicit origins."
            ),
        }

    claim_kind = _clean(
        claim_facets.get(
            "transfer_kind"
        )
    )

    outcome_kind = _clean(
        outcome_facets.get(
            "transfer_kind"
        )
    )

    if (
        claim_kind
        and outcome_kind
        and claim_kind
        != outcome_kind
    ):
        return {
            "status": (
                "material_transfer_conflict"
            ),
            "reason": (
                "The claim and outcome have "
                "conflicting explicit transfer kinds."
            ),
        }

    return {
        "status": (
            "same_transfer_occurrence"
        ),
        "reason": "",
    }


def compare_canonical_claim_to_outcome(
    *,
    claim_candidate: Mapping[
        str,
        Any,
    ],
    outcome_candidate: Mapping[
        str,
        Any,
    ],
    claim_observed_at: str,
    outcome_observed_at: str,
) -> Dict[str, Any]:
    claim = normalize_canonical_claim(
        claim_candidate
    )

    outcome = normalize_canonical_claim(
        outcome_candidate
    )

    if (
        claim.get(
            "version"
        )
        != CANONICAL_CLAIM_CONTRACT_VERSION
        or outcome.get(
            "version"
        )
        != CANONICAL_CLAIM_CONTRACT_VERSION
    ):
        raise ValueError(
            "Canonical outcome comparison "
            "requires the current canonical "
            "claim contract."
        )

    claim_time = _timestamp(
        claim_observed_at,
        label=(
            "Canonical claim observed_at"
        ),
    )

    outcome_time = _timestamp(
        outcome_observed_at,
        label=(
            "Canonical outcome observed_at"
        ),
    )

    if (
        outcome_time
        <= claim_time
    ):
        return _result(
            status=(
                "outcome_not_later_than_claim"
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "Outcome evidence must be later "
                "than the claim observation for "
                "resolution analysis."
            ),
        )

    if (
        claim[
            "subject_key"
        ]
        != outcome[
            "subject_key"
        ]
    ):
        return _result(
            status=(
                "claim_subject_mismatch"
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "The claim and outcome reference "
                "different canonical subjects."
            ),
        )

    if (
        claim[
            "event_type"
        ]
        != outcome[
            "event_type"
        ]
    ):
        return _result(
            status=(
                "event_type_mismatch"
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "The claim and outcome reference "
                "different canonical event types."
            ),
        )

    event_type = claim[
        "event_type"
    ]

    if (
        event_type
        not in (
            CANONICAL_OUTCOME_SUPPORTED_EVENT_TYPES
        )
    ):
        return _result(
            status=(
                "event_type_not_supported_for_resolution"
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "Canonical outcome v1 supports "
                "transfer resolution only."
            ),
        )

    occurrence = (
        _transfer_occurrence_status(
            claim=claim,
            outcome=outcome,
        )
    )

    if (
        occurrence[
            "status"
        ]
        != "same_transfer_occurrence"
    ):
        return _result(
            status=(
                occurrence[
                    "status"
                ]
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                occurrence[
                    "reason"
                ]
            ),
        )

    if (
        claim[
            "negated"
        ]
        is True
    ):
        return _result(
            status=(
                "claim_semantics_not_supported_by_v1"
            ),
            direction="indeterminate",
            rule_id="",
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "Canonical outcome v1 evaluates "
                "positive completed-transfer claims "
                "only."
            ),
        )

    transition = (
        claim[
            "state"
        ],
        claim[
            "negated"
        ],
        outcome[
            "state"
        ],
        outcome[
            "negated"
        ],
    )

    against_rule = (
        CANONICAL_OUTCOME_AGAINST_RULES.get(
            transition
        )
    )

    if against_rule:
        return _result(
            status=(
                "resolution_against_claim_candidate"
            ),
            direction=(
                "against_claim"
            ),
            rule_id=(
                against_rule
            ),
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "The later structured transfer "
                "outcome is deterministically "
                "incompatible with the earlier "
                "completed-transfer claim under "
                "the canonical outcome v1 rule set. "
                "Source and authority verification "
                "are still required before this "
                "may become a resolved label."
            ),
        )

    support_rule = (
        CANONICAL_OUTCOME_SUPPORT_RULES.get(
            transition
        )
    )

    if support_rule:
        return _result(
            status=(
                "resolution_supports_claim_candidate"
            ),
            direction=(
                "supports_claim"
            ),
            rule_id=(
                support_rule
            ),
            claim=claim,
            outcome=outcome,
            claim_observed_at=(
                claim_time
            ),
            outcome_observed_at=(
                outcome_time
            ),
            reason=(
                "The later structured transfer "
                "outcome is consistent with the "
                "earlier completed-transfer claim. "
                "This is a semantic resolution "
                "candidate only."
            ),
        )

    return _result(
        status=(
            "state_transition_not_decisive"
        ),
        direction="indeterminate",
        rule_id="",
        claim=claim,
        outcome=outcome,
        claim_observed_at=(
            claim_time
        ),
        outcome_observed_at=(
            outcome_time
        ),
        reason=(
            "The observed state transition is "
            "not treated as proof against the "
            "earlier claim. Sequential sports "
            "states can both have been accurate "
            "at different times."
        ),
    )
