import hashlib
import json

from typing import (
    Any,
    Dict,
    List,
)


from app.analysis.adjudication_state import (
    AUTOMATED_ADJUDICATION_STATE_VERSION,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)


AUTOMATIC_CORRECTION_MEMORY_VERSION = (
    "automatic-correction-memory-v1"
)

AUTOMATIC_CORRECTION_EVENT_VERSION = (
    "automatic-correction-event-v1"
)

AUTOMATIC_MEMORY_CANDIDATE_VERSION = (
    "automatic-memory-candidate-v1"
)

PATTERN_MINIMUM_DISTINCT_CLAIMS = 2


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _canonical_copy(
    value: Any,
) -> Any:
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            allow_nan=False,
        )
    )


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )


def _hash(
    value: Any,
    *,
    prefix: str,
) -> str:
    return hashlib.sha256(
        (
            prefix
            + _canonical_json(
                value
            )
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def _string_list(
    value: Any,
    *,
    label: str,
    lower: bool = False,
) -> List[str]:
    if not isinstance(
        value,
        list,
    ):
        raise ValueError(
            f"{label} must be a list."
        )

    result = set()

    for item in value:
        cleaned = _clean(
            item
        )

        if not cleaned:
            continue

        if lower:
            cleaned = (
                cleaned.lower()
            )

        result.add(
            cleaned
        )

    return sorted(
        result
    )


def _validate_revision(
    revision: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(
        revision,
        dict,
    ):
        raise ValueError(
            f"{label} must be a dictionary."
        )

    normalized = _canonical_copy(
        revision
    )

    if (
        _clean(
            normalized.get(
                "version"
            )
        )
        != (
            AUTOMATED_ADJUDICATION_STATE_VERSION
        )
    ):
        raise ValueError(
            f"{label} version is unsupported."
        )

    claim_id = _clean(
        normalized.get(
            "claim_id"
        )
    )

    revision_id = _clean(
        normalized.get(
            "revision_id"
        )
    )

    if not claim_id:
        raise ValueError(
            f"{label} claim ID is required."
        )

    if not revision_id:
        raise ValueError(
            f"{label} revision ID is required."
        )

    fields = normalized.get(
        "fields"
    )

    if not isinstance(
        fields,
        dict,
    ):
        raise ValueError(
            f"{label} fields are required."
        )

    if (
        set(
            fields.keys()
        )
        != set(
            MULTI_EVALUATOR_FIELDS
        )
    ):
        raise ValueError(
            f"{label} field coverage is incomplete."
        )

    return normalized


def _field_packet(
    revision: Dict[str, Any],
    field: str,
) -> Dict[str, Any]:
    packet = revision[
        "fields"
    ].get(
        field
    )

    if not isinstance(
        packet,
        dict,
    ):
        raise ValueError(
            "Correction memory field packet "
            "is invalid."
        )

    state = packet.get(
        "state"
    )

    lineage = packet.get(
        "lineage"
    )

    if not isinstance(
        state,
        dict,
    ):
        raise ValueError(
            "Correction memory state "
            "is invalid."
        )

    if not isinstance(
        lineage,
        dict,
    ):
        raise ValueError(
            "Correction memory lineage "
            "is invalid."
        )

    training_allowed = state.get(
        "training_reference_allowed",
        False,
    )

    if not isinstance(
        training_allowed,
        bool,
    ):
        raise ValueError(
            "Correction memory training "
            "reference permission "
            "must be boolean."
        )

    return {
        "state": {
            "tier": _clean(
                state.get(
                    "tier"
                )
            ).lower(),
            "value": _clean(
                state.get(
                    "value"
                )
            ),
            "confidence": (
                state.get(
                    "confidence"
                )
            ),
            "conflicting_values": (
                _string_list(
                    state.get(
                        "conflicting_values",
                        [],
                    ),
                    label=(
                        "Correction memory "
                        "conflicting values"
                    ),
                )
            ),
            "training_reference_allowed": (
                training_allowed
            ),
        },
        "lineage": {
            "judgment_ids": (
                _string_list(
                    lineage.get(
                        "judgment_ids",
                        [],
                    ),
                    label=(
                        "Correction memory "
                        "judgment IDs"
                    ),
                )
            ),
            "supporting_judgment_ids": (
                _string_list(
                    lineage.get(
                        "supporting_judgment_ids",
                        [],
                    ),
                    label=(
                        "Correction memory "
                        "supporting judgment IDs"
                    ),
                )
            ),
            "supporting_evaluator_families": (
                _string_list(
                    lineage.get(
                        "supporting_evaluator_families",
                        [],
                    ),
                    label=(
                        "Correction memory "
                        "supporting evaluator "
                        "families"
                    ),
                    lower=True,
                )
            ),
            "trusted_hard_reference_judgment_ids": (
                _string_list(
                    lineage.get(
                        (
                            "trusted_hard_reference_"
                            "judgment_ids"
                        ),
                        [],
                    ),
                    label=(
                        "Correction memory trusted "
                        "reference judgment IDs"
                    ),
                )
            ),
        },
    }


def _correction_signature_payload(
    *,
    field: str,
    previous_packet: Dict[
        str,
        Any,
    ],
    corrected_packet: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    previous_state = (
        previous_packet[
            "state"
        ]
    )

    previous_lineage = (
        previous_packet[
            "lineage"
        ]
    )

    corrected_state = (
        corrected_packet[
            "state"
        ]
    )

    return {
        "field": field,
        "previous_tier": (
            previous_state[
                "tier"
            ]
        ),
        "previous_value": (
            previous_state[
                "value"
            ]
        ),
        "previous_training_reference_allowed": (
            previous_state[
                "training_reference_allowed"
            ]
        ),
        "previous_supporting_evaluator_families": (
            previous_lineage[
                "supporting_evaluator_families"
            ]
        ),
        "corrected_value": (
            corrected_state[
                "value"
            ]
        ),
    }


def _correction_signature(
    *,
    field: str,
    previous_packet: Dict[
        str,
        Any,
    ],
    corrected_packet: Dict[
        str,
        Any,
    ],
) -> str:
    return _hash(
        _correction_signature_payload(
            field=field,
            previous_packet=(
                previous_packet
            ),
            corrected_packet=(
                corrected_packet
            ),
        ),
        prefix=(
            "automatic-correction-signature|"
        ),
    )


def _build_correction_event(
    *,
    previous_revision: Dict[
        str,
        Any,
    ],
    current_revision: Dict[
        str,
        Any,
    ],
    field: str,
) -> Dict[str, Any]:
    previous_packet = (
        _field_packet(
            previous_revision,
            field,
        )
    )

    corrected_packet = (
        _field_packet(
            current_revision,
            field,
        )
    )

    signature = (
        _correction_signature(
            field=field,
            previous_packet=(
                previous_packet
            ),
            corrected_packet=(
                corrected_packet
            ),
        )
    )

    trigger = _canonical_copy(
        current_revision.get(
            "trigger",
            {},
        )
    )

    payload = {
        "version": (
            AUTOMATIC_CORRECTION_EVENT_VERSION
        ),
        "claim_id": (
            current_revision[
                "claim_id"
            ]
        ),
        "field": field,
        "previous_revision_id": (
            previous_revision[
                "revision_id"
            ]
        ),
        "current_revision_id": (
            current_revision[
                "revision_id"
            ]
        ),
        "previous_state": (
            previous_packet[
                "state"
            ]
        ),
        "corrected_state": (
            corrected_packet[
                "state"
            ]
        ),
        "previous_lineage": (
            previous_packet[
                "lineage"
            ]
        ),
        "corrected_lineage": (
            corrected_packet[
                "lineage"
            ]
        ),
        "trigger": trigger,
        "signature": signature,
    }

    event_id = _hash(
        payload,
        prefix=(
            "automatic-correction-event|"
        ),
    )

    return {
        **payload,
        "id": event_id,
        "learning_signal_candidate": True,
    }


def _is_genuine_correction(
    *,
    previous_packet: Dict[
        str,
        Any,
    ],
    corrected_packet: Dict[
        str,
        Any,
    ],
) -> bool:
    previous_state = (
        previous_packet[
            "state"
        ]
    )

    corrected_state = (
        corrected_packet[
            "state"
        ]
    )

    corrected_lineage = (
        corrected_packet[
            "lineage"
        ]
    )

    previous_value = _clean(
        previous_state.get(
            "value"
        )
    )

    corrected_value = _clean(
        corrected_state.get(
            "value"
        )
    )

    if not previous_value:
        return False

    if not corrected_value:
        return False

    if previous_value == corrected_value:
        return False

    if (
        corrected_state.get(
            "tier"
        )
        != "auto_gold"
    ):
        return False

    if not bool(
        corrected_state.get(
            "training_reference_allowed"
        )
    ):
        return False

    trusted_ids = (
        corrected_lineage.get(
            (
                "trusted_hard_reference_"
                "judgment_ids"
            ),
            [],
        )
    )

    if not trusted_ids:
        return False

    return True


def _normalize_prior_event(
    event: Any,
) -> Dict[str, Any]:
    if not isinstance(
        event,
        dict,
    ):
        raise ValueError(
            "Prior correction event "
            "must be a dictionary."
        )

    normalized = _canonical_copy(
        event
    )

    if (
        _clean(
            normalized.get(
                "version"
            )
        )
        != (
            AUTOMATIC_CORRECTION_EVENT_VERSION
        )
    ):
        raise ValueError(
            "Prior correction event "
            "version is unsupported."
        )

    event_id = _clean(
        normalized.get(
            "id"
        )
    )

    claim_id = _clean(
        normalized.get(
            "claim_id"
        )
    )

    signature = _clean(
        normalized.get(
            "signature"
        )
    )

    if not all(
        (
            event_id,
            claim_id,
            signature,
        )
    ):
        raise ValueError(
            "Prior correction event "
            "identity is incomplete."
        )

    previous_state = normalized.get(
        "previous_state"
    )

    corrected_state = normalized.get(
        "corrected_state"
    )

    corrected_lineage = normalized.get(
        "corrected_lineage"
    )

    if (
        not isinstance(
            previous_state,
            dict,
        )
        or not isinstance(
            corrected_state,
            dict,
        )
        or not isinstance(
            corrected_lineage,
            dict,
        )
    ):
        raise ValueError(
            "Prior correction event "
            "state is invalid."
        )

    if (
        not _clean(
            previous_state.get(
                "value"
            )
        )
        or not _clean(
            corrected_state.get(
                "value"
            )
        )
        or (
            _clean(
                previous_state.get(
                    "value"
                )
            )
            == _clean(
                corrected_state.get(
                    "value"
                )
            )
        )
    ):
        raise ValueError(
            "Prior correction event "
            "does not contain a correction."
        )

    if (
        _clean(
            corrected_state.get(
                "tier"
            )
        ).lower()
        != "auto_gold"
    ):
        raise ValueError(
            "Prior correction event "
            "is not trusted gold."
        )

    if not bool(
        corrected_state.get(
            "training_reference_allowed"
        )
    ):
        raise ValueError(
            "Prior correction event "
            "is not training-reference trusted."
        )

    if not corrected_lineage.get(
        "trusted_hard_reference_judgment_ids",
        [],
    ):
        raise ValueError(
            "Prior correction event "
            "has no trusted reference lineage."
        )

    return normalized


def _memory_candidate(
    *,
    event: Dict[str, Any],
    matching_events: List[
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    events_by_id = {
        row[
            "id"
        ]: row
        for row
        in matching_events
    }

    events_by_id[
        event[
            "id"
        ]
    ] = event

    events = sorted(
        events_by_id.values(),
        key=lambda row: (
            row[
                "claim_id"
            ],
            row[
                "id"
            ],
        ),
    )

    claim_ids = sorted(
        {
            row[
                "claim_id"
            ]
            for row
            in events
        }
    )

    correction_ids = sorted(
        row[
            "id"
        ]
        for row
        in events
    )

    support_count = len(
        claim_ids
    )

    status = (
        "pattern_candidate"
        if (
            support_count
            >= (
                PATTERN_MINIMUM_DISTINCT_CLAIMS
            )
        )
        else "case_memory"
    )

    signature_payload = {
        "signature": (
            event[
                "signature"
            ]
        ),
        "field": (
            event[
                "field"
            ]
        ),
    }

    candidate_id = _hash(
        signature_payload,
        prefix=(
            "automatic-memory-candidate|"
        ),
    )

    return {
        "version": (
            AUTOMATIC_MEMORY_CANDIDATE_VERSION
        ),
        "id": candidate_id,
        "signature": (
            event[
                "signature"
            ]
        ),
        "field": (
            event[
                "field"
            ]
        ),
        "status": status,
        "support_count": (
            support_count
        ),
        "supporting_claim_ids": (
            claim_ids
        ),
        "supporting_correction_ids": (
            correction_ids
        ),
        "previous_tier": (
            event[
                "previous_state"
            ][
                "tier"
            ]
        ),
        "previous_value": (
            event[
                "previous_state"
            ][
                "value"
            ]
        ),
        "corrected_value": (
            event[
                "corrected_state"
            ][
                "value"
            ]
        ),
        "previous_supporting_evaluator_families": (
            event[
                "previous_lineage"
            ][
                "supporting_evaluator_families"
            ]
        ),
        "eligible_for_automatic_global_rule": (
            False
        ),
    }


def build_automatic_correction_memory(
    *,
    previous_revision: Dict[
        str,
        Any,
    ],
    current_revision: Dict[
        str,
        Any,
    ],
    prior_correction_events: Any = None,
) -> Dict[str, Any]:
    previous = _validate_revision(
        previous_revision,
        label=(
            "Previous adjudication revision"
        ),
    )

    current = _validate_revision(
        current_revision,
        label=(
            "Current adjudication revision"
        ),
    )

    if (
        previous[
            "claim_id"
        ]
        != current[
            "claim_id"
        ]
    ):
        raise ValueError(
            "Correction memory revisions "
            "belong to different claims."
        )

    if (
        _clean(
            current.get(
                "previous_revision_id"
            )
        )
        != (
            previous[
                "revision_id"
            ]
        )
    ):
        raise ValueError(
            "Correction memory requires "
            "direct consecutive revisions."
        )

    if prior_correction_events is None:
        prior_correction_events = []

    if not isinstance(
        prior_correction_events,
        list,
    ):
        raise ValueError(
            "Prior correction events "
            "must be a list."
        )

    normalized_prior = [
        _normalize_prior_event(
            event
        )
        for event
        in prior_correction_events
    ]

    transitions = (
        current.get(
            "transitions",
            []
        )
    )

    if not isinstance(
        transitions,
        list,
    ):
        raise ValueError(
            "Current adjudication transitions "
            "must be a list."
        )

    transition_by_field = {}

    for transition in transitions:
        if not isinstance(
            transition,
            dict,
        ):
            raise ValueError(
                "Current adjudication transition "
                "must be a dictionary."
            )

        field = _clean(
            transition.get(
                "field"
            )
        )

        if field in transition_by_field:
            raise ValueError(
                "Current adjudication contains "
                "duplicate field transitions."
            )

        transition_by_field[
            field
        ] = transition

    corrections = []

    for field in (
        MULTI_EVALUATOR_FIELDS
    ):
        previous_packet = (
            _field_packet(
                previous,
                field,
            )
        )

        corrected_packet = (
            _field_packet(
                current,
                field,
            )
        )

        if not _is_genuine_correction(
            previous_packet=(
                previous_packet
            ),
            corrected_packet=(
                corrected_packet
            ),
        ):
            continue

        transition = (
            transition_by_field.get(
                field
            )
        )

        if not isinstance(
            transition,
            dict,
        ):
            raise ValueError(
                "Trusted correction is missing "
                "its adjudication transition."
            )

        if (
            _canonical_json(
                transition.get(
                    "from_state"
                )
            )
            != _canonical_json(
                previous_packet[
                    "state"
                ]
            )
            or (
                _canonical_json(
                    transition.get(
                        "to_state"
                    )
                )
                != _canonical_json(
                    corrected_packet[
                        "state"
                    ]
                )
            )
        ):
            raise ValueError(
                "Correction transition does not "
                "match revision field states."
            )

        corrections.append(
            _build_correction_event(
                previous_revision=(
                    previous
                ),
                current_revision=(
                    current
                ),
                field=field,
            )
        )

    corrections = sorted(
        corrections,
        key=lambda row: (
            row[
                "field"
            ],
            row[
                "id"
            ],
        ),
    )

    candidates = []

    for event in corrections:
        matching_prior = [
            row
            for row
            in normalized_prior
            if (
                row[
                    "signature"
                ]
                == event[
                    "signature"
                ]
            )
        ]

        candidates.append(
            _memory_candidate(
                event=event,
                matching_events=(
                    matching_prior
                ),
            )
        )

    candidates = sorted(
        candidates,
        key=lambda row: (
            row[
                "field"
            ],
            row[
                "id"
            ],
        ),
    )

    return {
        "version": (
            AUTOMATIC_CORRECTION_MEMORY_VERSION
        ),
        "claim_id": (
            current[
                "claim_id"
            ]
        ),
        "previous_revision_id": (
            previous[
                "revision_id"
            ]
        ),
        "current_revision_id": (
            current[
                "revision_id"
            ]
        ),
        "corrections": corrections,
        "memory_candidates": (
            candidates
        ),
        "summary": {
            "correction_count": len(
                corrections
            ),
            "case_memory_count": len(
                [
                    row
                    for row
                    in candidates
                    if row[
                        "status"
                    ]
                    == "case_memory"
                ]
            ),
            "pattern_candidate_count": len(
                [
                    row
                    for row
                    in candidates
                    if row[
                        "status"
                    ]
                    == "pattern_candidate"
                ]
            ),
        },
        "policy": {
            "only_trusted_auto_gold_can_correct": True,
            "trusted_reference_lineage_required": True,
            "empty_previous_value_is_resolution_not_correction": True,
            "same_value_trust_upgrade_is_not_correction": True,
            "one_correction_remains_case_memory": True,
            "pattern_requires_multiple_distinct_claims": True,
            "pattern_candidate_is_not_an_active_rule": True,
            "automatic_global_rule_promotion_forbidden": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
            "does_not_persist_by_itself": True,
            "human_review_required": False,
        },
    }
