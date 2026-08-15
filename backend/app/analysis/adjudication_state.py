import hashlib
import json

from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)


from app.analysis.adjudication import (
    ADJUDICATION_TIERS,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_ADJUDICATION_VERSION,
    MULTI_EVALUATOR_FIELDS,
)


AUTOMATED_ADJUDICATION_STATE_VERSION = (
    "automated-adjudication-state-v1"
)

ADJUDICATION_STATE_TRIGGER_TYPES = {
    "initial_evaluation",
    "evidence_added",
    "evidence_verified",
    "canonical_outcome",
    "evaluator_refresh",
}

EVIDENCE_TRIGGER_TYPES = {
    "evidence_added",
    "evidence_verified",
    "canonical_outcome",
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
) -> str:
    text = _clean(
        value
    )

    if not text:
        raise ValueError(
            f"{label} is required."
        )

    candidate = text

    if candidate.endswith(
        "Z"
    ):
        candidate = (
            candidate[:-1]
            + "+00:00"
        )

    try:
        parsed = (
            datetime.fromisoformat(
                candidate
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

    return parsed.isoformat()


def _canonical_copy(
    value: Any,
) -> Any:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return json.loads(
        text
    )


def _content_hash(
    value: Any,
    *,
    prefix: str,
) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        allow_nan=False,
    )

    return hashlib.sha256(
        (
            prefix
            + canonical
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

    normalized = set()

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

        normalized.add(
            cleaned
        )

    return sorted(
        normalized
    )


def _normalize_trigger_evidence_ids(
    values: Any,
) -> List[str]:
    if values is None:
        values = []

    return _string_list(
        values,
        label=(
            "Adjudication trigger "
            "evidence IDs"
        ),
    )


def _field_packet(
    *,
    field: str,
    result: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    if not isinstance(
        result,
        dict,
    ):
        raise ValueError(
            "Adjudication field result "
            f"{field} must be a dictionary."
        )

    correction = result.get(
        "correction",
        {},
    )

    if correction:
        raise ValueError(
            "Automated adjudication state "
            "cannot contain manual corrections."
        )

    automatic = result.get(
        "automatic"
    )

    reference_gate = result.get(
        "reference_gate"
    )

    judgments = result.get(
        "judgments",
        [],
    )

    if not isinstance(
        automatic,
        dict,
    ):
        raise ValueError(
            "Adjudication automatic result "
            f"{field} is missing."
        )

    if not isinstance(
        reference_gate,
        dict,
    ):
        raise ValueError(
            "Adjudication reference gate "
            f"{field} is missing."
        )

    if not isinstance(
        judgments,
        list,
    ):
        raise ValueError(
            "Adjudication judgments "
            f"{field} must be a list."
        )

    tier = (
        _clean(
            automatic.get(
                "tier"
            )
        ).lower()
    )

    if tier not in ADJUDICATION_TIERS:
        raise ValueError(
            "Adjudication field tier "
            f"{field} is unsupported."
        )

    confidence = automatic.get(
        "confidence",
        0.0,
    )

    if isinstance(
        confidence,
        bool,
    ):
        raise ValueError(
            "Adjudication field confidence "
            "must be numeric."
        )

    try:
        confidence = float(
            confidence
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Adjudication field confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= confidence
        <= 1.0
    ):
        raise ValueError(
            "Adjudication field confidence "
            "must be between 0 and 1."
        )

    training_reference_allowed = (
        reference_gate.get(
            "training_reference_allowed",
            False,
        )
    )

    if not isinstance(
        training_reference_allowed,
        bool,
    ):
        raise ValueError(
            "Adjudication training reference "
            "permission must be boolean."
        )

    judgment_ids = []

    for judgment in judgments:
        if not isinstance(
            judgment,
            dict,
        ):
            raise ValueError(
                "Adjudication judgment "
                "must be a dictionary."
            )

        judgment_id = _clean(
            judgment.get(
                "id"
            )
        )

        if judgment_id:
            judgment_ids.append(
                judgment_id
            )

    state = {
        "tier": tier,
        "value": _clean(
            automatic.get(
                "value"
            )
        ),
        "confidence": confidence,
        "conflicting_values": (
            _string_list(
                automatic.get(
                    "conflicting_values",
                    [],
                ),
                label=(
                    "Adjudication conflicting "
                    "values"
                ),
            )
        ),
        "training_reference_allowed": (
            training_reference_allowed
        ),
    }

    lineage = {
        "judgment_ids": sorted(
            set(
                judgment_ids
            )
        ),
        "supporting_judgment_ids": (
            _string_list(
                automatic.get(
                    "supporting_judgment_ids",
                    [],
                ),
                label=(
                    "Adjudication supporting "
                    "judgment IDs"
                ),
            )
        ),
        "supporting_evaluator_families": (
            _string_list(
                automatic.get(
                    "supporting_evaluator_families",
                    [],
                ),
                label=(
                    "Adjudication supporting "
                    "evaluator families"
                ),
                lower=True,
            )
        ),
        "trusted_hard_reference_judgment_ids": (
            _string_list(
                reference_gate.get(
                    (
                        "trusted_hard_reference_"
                        "judgment_ids"
                    ),
                    [],
                ),
                label=(
                    "Adjudication trusted hard "
                    "reference judgment IDs"
                ),
            )
        ),
    }

    return {
        "state": state,
        "lineage": lineage,
    }


def _transition_kind(
    previous_state: Optional[
        Dict[str, Any]
    ],
    current_state: Dict[
        str,
        Any,
    ],
) -> str:
    if previous_state is None:
        return "initialized"

    changed = [
        key
        for key
        in current_state
        if (
            previous_state.get(
                key
            )
            != current_state.get(
                key
            )
        )
    ]

    if not changed:
        return ""

    if changed == [
        "tier"
    ]:
        return "tier_changed"

    if changed == [
        "value"
    ]:
        return "value_changed"

    if changed == [
        "confidence"
    ]:
        return "confidence_changed"

    if changed == [
        "conflicting_values"
    ]:
        return "conflict_set_changed"

    if changed == [
        "training_reference_allowed"
    ]:
        return (
            "reference_gate_changed"
        )

    return "state_changed"


def build_adjudication_state_revision(
    *,
    adjudication: Dict[
        str,
        Any,
    ],
    as_of: str,
    trigger_type: str,
    trigger_evidence_ids: Any = None,
    previous_revision: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:
    if not isinstance(
        adjudication,
        dict,
    ):
        raise ValueError(
            "Adjudication state input "
            "must be a dictionary."
        )

    normalized_adjudication = (
        _canonical_copy(
            adjudication
        )
    )

    if (
        _clean(
            normalized_adjudication.get(
                "version"
            )
        )
        != (
            MULTI_EVALUATOR_ADJUDICATION_VERSION
        )
    ):
        raise ValueError(
            "Adjudication state requires the "
            "current multi-evaluator "
            "adjudication version."
        )

    claim_id = _clean(
        normalized_adjudication.get(
            "claim_id"
        )
    )

    if not claim_id:
        raise ValueError(
            "Adjudication state claim ID "
            "is required."
        )

    fields = (
        normalized_adjudication.get(
            "fields"
        )
    )

    if not isinstance(
        fields,
        dict,
    ):
        raise ValueError(
            "Adjudication state fields "
            "are required."
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
            "Adjudication state requires "
            "complete multi-evaluator "
            "field coverage."
        )

    summary = (
        normalized_adjudication.get(
            "summary",
            {},
        )
    )

    if not isinstance(
        summary,
        dict,
    ):
        raise ValueError(
            "Adjudication state summary "
            "must be a dictionary."
        )

    if summary.get(
        "corrected_fields",
        [],
    ):
        raise ValueError(
            "Automated adjudication state "
            "cannot contain corrected fields."
        )

    normalized_as_of = _timestamp(
        as_of,
        label=(
            "Adjudication state as_of"
        ),
    )

    normalized_trigger_type = (
        _clean(
            trigger_type
        ).lower()
    )

    if (
        normalized_trigger_type
        not in
        ADJUDICATION_STATE_TRIGGER_TYPES
    ):
        raise ValueError(
            "Adjudication state trigger type "
            "is unsupported."
        )

    evidence_ids = (
        _normalize_trigger_evidence_ids(
            trigger_evidence_ids
        )
    )

    if (
        normalized_trigger_type
        in EVIDENCE_TRIGGER_TYPES
        and not evidence_ids
    ):
        raise ValueError(
            "Evidence-triggered adjudication "
            "requires at least one evidence ID."
        )

    field_packets = {
        field: _field_packet(
            field=field,
            result=fields[
                field
            ],
        )
        for field
        in MULTI_EVALUATOR_FIELDS
    }

    previous_revision_id = ""
    previous_fields = {}

    if previous_revision is not None:
        if not isinstance(
            previous_revision,
            dict,
        ):
            raise ValueError(
                "Previous adjudication revision "
                "must be a dictionary."
            )

        if (
            _clean(
                previous_revision.get(
                    "version"
                )
            )
            != (
                AUTOMATED_ADJUDICATION_STATE_VERSION
            )
        ):
            raise ValueError(
                "Previous adjudication revision "
                "version is unsupported."
            )

        if (
            _clean(
                previous_revision.get(
                    "claim_id"
                )
            )
            != claim_id
        ):
            raise ValueError(
                "Previous adjudication revision "
                "belongs to a different claim."
            )

        previous_revision_id = (
            _clean(
                previous_revision.get(
                    "revision_id"
                )
            )
        )

        if not previous_revision_id:
            raise ValueError(
                "Previous adjudication revision "
                "ID is required."
            )

        previous_as_of = _timestamp(
            previous_revision.get(
                "as_of"
            ),
            label=(
                "Previous adjudication "
                "revision as_of"
            ),
        )

        if (
            datetime.fromisoformat(
                normalized_as_of
            )
            < datetime.fromisoformat(
                previous_as_of
            )
        ):
            raise ValueError(
                "Adjudication revisions cannot "
                "move backward in time."
            )

        previous_fields = (
            previous_revision.get(
                "fields"
            )
        )

        if not isinstance(
            previous_fields,
            dict,
        ):
            raise ValueError(
                "Previous adjudication revision "
                "fields are required."
            )

        if (
            set(
                previous_fields.keys()
            )
            != set(
                MULTI_EVALUATOR_FIELDS
            )
        ):
            raise ValueError(
                "Previous adjudication revision "
                "has incomplete field coverage."
            )

    adjudication_sha256 = (
        _content_hash(
            normalized_adjudication,
            prefix=(
                "multi-evaluator-adjudication|"
            ),
        )
    )

    revision_identity = {
        "version": (
            AUTOMATED_ADJUDICATION_STATE_VERSION
        ),
        "claim_id": claim_id,
        "as_of": normalized_as_of,
        "trigger": {
            "type": (
                normalized_trigger_type
            ),
            "evidence_ids": (
                evidence_ids
            ),
        },
        "adjudication_sha256": (
            adjudication_sha256
        ),
        "previous_revision_id": (
            previous_revision_id
        ),
    }

    revision_id = (
        _content_hash(
            revision_identity,
            prefix=(
                "adjudication-state-revision|"
            ),
        )
    )

    transitions = []

    for field in (
        MULTI_EVALUATOR_FIELDS
    ):
        current_state = (
            field_packets[
                field
            ][
                "state"
            ]
        )

        previous_state = None

        if previous_revision is not None:
            previous_packet = (
                previous_fields.get(
                    field
                )
            )

            if not isinstance(
                previous_packet,
                dict,
            ):
                raise ValueError(
                    "Previous adjudication "
                    f"field {field} is invalid."
                )

            previous_state = (
                previous_packet.get(
                    "state"
                )
            )

            if not isinstance(
                previous_state,
                dict,
            ):
                raise ValueError(
                    "Previous adjudication "
                    f"field {field} state "
                    "is invalid."
                )

        kind = _transition_kind(
            previous_state,
            current_state,
        )

        if not kind:
            continue

        transition_payload = {
            "field": field,
            "kind": kind,
            "from_state": (
                previous_state
            ),
            "to_state": (
                current_state
            ),
        }

        transition_id = (
            _content_hash(
                {
                    "revision_id": (
                        revision_id
                    ),
                    **transition_payload,
                },
                prefix=(
                    "adjudication-state-"
                    "transition|"
                ),
            )
        )

        transitions.append(
            {
                "id": transition_id,
                **transition_payload,
            }
        )

    return {
        "version": (
            AUTOMATED_ADJUDICATION_STATE_VERSION
        ),
        "revision_id": (
            revision_id
        ),
        "claim_id": claim_id,
        "adjudication_version": (
            MULTI_EVALUATOR_ADJUDICATION_VERSION
        ),
        "adjudication_sha256": (
            adjudication_sha256
        ),
        "as_of": normalized_as_of,
        "previous_revision_id": (
            previous_revision_id
        ),
        "trigger": {
            "type": (
                normalized_trigger_type
            ),
            "evidence_ids": (
                evidence_ids
            ),
        },
        "fields": (
            field_packets
        ),
        "transitions": sorted(
            transitions,
            key=lambda row: (
                row[
                    "field"
                ],
                row[
                    "id"
                ],
            ),
        ),
        "adjudication": (
            normalized_adjudication
        ),
        "policy": {
            "state_is_machine_derived": True,
            "manual_corrections_are_rejected": True,
            "revision_identity_is_deterministic": True,
            "revisions_are_time_ordered": True,
            "evidence_changes_without_decision_changes_are_not_transitions": True,
            "state_transition_does_not_establish_truth": True,
            "state_transition_does_not_train_model": True,
            "state_transition_does_not_change_live_merit": True,
            "state_revision_does_not_persist_by_itself": True,
        },
    }
