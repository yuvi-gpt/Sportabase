from datetime import (
    datetime,
)

from typing import (
    Any,
    Dict,
    List,
)


AUTOMATED_ADJUDICATION_VERSION = (
    "automated-adjudication-v1"
)

ADJUDICATION_TIERS = (
    "auto_gold",
    "auto_silver",
    "contested",
    "unresolved",
)

ADJUDICATION_FIELDS = (
    "source_role",
    "authority_class",
    "reliability_class",
    "provenance_class",
    "stance",
    "independence_status",
    "authority_state",
    "corroboration_signal",
    "outcome_status",
)

JUDGMENT_BASIS_CLASSES = (
    "canonical_resolution",
    "direct_authority_record",
    "structured_fact",
    "deterministic_rule",
    "provenance_graph",
    "model_inference",
    "heuristic",
)

CORRECTION_SCOPES = (
    "case_only",
    "pattern_candidate",
    "entity_mapping_candidate",
    "global_rule_candidate",
)

HIGH_CONFIDENCE_THRESHOLD = 0.85

AUTO_GOLD_CONFIDENCE_THRESHOLD = 0.95

AUTO_GOLD_BASIS_BY_FIELD = {
    "authority_class": {
        "direct_authority_record",
    },
    "authority_state": {
        "direct_authority_record",
        "canonical_resolution",
    },
    "outcome_status": {
        "canonical_resolution",
    },
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


def _confidence(
    value: Any,
) -> float:
    try:
        result = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Adjudication judgment confidence "
            "must be numeric."
        ) from exc

    if (
        result < 0.0
        or result > 1.0
    ):
        raise ValueError(
            "Adjudication judgment confidence "
            "must be between 0 and 1."
        )

    return result


def _normalize_judgments(
    *,
    field: str,
    judgments: List[
        Dict[str, Any]
    ],
) -> List[
    Dict[str, Any]
]:
    if not isinstance(
        judgments,
        list,
    ):
        raise ValueError(
            "Adjudication judgments "
            "must be a list."
        )

    normalized = {}

    for raw in judgments:
        if not isinstance(
            raw,
            dict,
        ):
            raise ValueError(
                "Each adjudication judgment "
                "must be a dictionary."
            )

        judgment_id = _clean(
            raw.get(
                "id"
            )
        )

        evaluator_id = _clean(
            raw.get(
                "evaluator_id"
            )
        )

        evaluator_family = (
            _clean(
                raw.get(
                    "evaluator_family"
                )
            ).lower()
        )

        value = _clean(
            raw.get(
                "value"
            )
        )

        basis_class = (
            _clean(
                raw.get(
                    "basis_class"
                )
            ).lower()
        )

        if not judgment_id:
            raise ValueError(
                "Adjudication judgment ID "
                "is required."
            )

        if not evaluator_id:
            raise ValueError(
                "Adjudication evaluator ID "
                "is required."
            )

        if not evaluator_family:
            raise ValueError(
                "Adjudication evaluator family "
                "is required."
            )

        if not value:
            raise ValueError(
                "Adjudication judgment value "
                "is required."
            )

        if (
            basis_class
            not in
            JUDGMENT_BASIS_CLASSES
        ):
            raise ValueError(
                "Adjudication judgment basis "
                "class is unsupported."
            )

        evidence_ids = raw.get(
            "evidence_ids",
            [],
        )

        if not isinstance(
            evidence_ids,
            list,
        ):
            raise ValueError(
                "Adjudication evidence IDs "
                "must be a list."
            )

        evidence_ids = sorted(
            {
                _clean(
                    item
                )
                for item
                in evidence_ids
                if _clean(
                    item
                )
            }
        )

        row = {
            "id": judgment_id,
            "field": field,
            "value": value,
            "confidence": (
                _confidence(
                    raw.get(
                        "confidence"
                    )
                )
            ),
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "basis_class": (
                basis_class
            ),
            "evidence_ids": (
                evidence_ids
            ),
        }

        existing = normalized.get(
            judgment_id
        )

        if (
            existing is not None
            and existing != row
        ):
            raise ValueError(
                "Adjudication contains "
                "conflicting duplicate "
                "judgment IDs."
            )

        normalized[
            judgment_id
        ] = row

    return sorted(
        normalized.values(),
        key=lambda row: (
            row[
                "evaluator_family"
            ],
            row[
                "evaluator_id"
            ],
            row[
                "id"
            ],
        ),
    )


def _automatic_reference(
    *,
    field: str,
    judgments: List[
        Dict[str, Any]
    ],
) -> Dict[str, Any]:
    high_confidence = [
        row
        for row in judgments
        if row[
            "confidence"
        ]
        >= (
            HIGH_CONFIDENCE_THRESHOLD
        )
    ]

    values = sorted(
        {
            row[
                "value"
            ]
            for row
            in high_confidence
        }
    )

    if len(
        values
    ) > 1:
        return {
            "tier": "contested",
            "value": "",
            "confidence": 0.0,
            "supporting_judgment_ids": [],
            "supporting_evaluator_families": [],
            "conflicting_values": (
                values
            ),
        }

    gold_basis = (
        AUTO_GOLD_BASIS_BY_FIELD.get(
            field,
            set(),
        )
    )

    hard_reference = [
        row
        for row in judgments
        if (
            row[
                "basis_class"
            ]
            in gold_basis
            and row[
                "confidence"
            ]
            >= (
                AUTO_GOLD_CONFIDENCE_THRESHOLD
            )
        )
    ]

    hard_values = sorted(
        {
            row[
                "value"
            ]
            for row
            in hard_reference
        }
    )

    if len(
        hard_values
    ) > 1:
        return {
            "tier": "contested",
            "value": "",
            "confidence": 0.0,
            "supporting_judgment_ids": [],
            "supporting_evaluator_families": [],
            "conflicting_values": (
                hard_values
            ),
        }

    if (
        len(
            hard_values
        )
        == 1
    ):
        value = hard_values[0]

        supporting = [
            row
            for row
            in judgments
            if row[
                "value"
            ]
            == value
        ]

        return {
            "tier": "auto_gold",
            "value": value,
            "confidence": max(
                row[
                    "confidence"
                ]
                for row
                in hard_reference
            ),
            "supporting_judgment_ids": (
                sorted(
                    row[
                        "id"
                    ]
                    for row
                    in supporting
                )
            ),
            "supporting_evaluator_families": (
                sorted(
                    {
                        row[
                            "evaluator_family"
                        ]
                        for row
                        in supporting
                    }
                )
            ),
            "conflicting_values": [],
        }

    if len(
        values
    ) == 1:
        value = values[0]

        supporting = [
            row
            for row
            in high_confidence
            if row[
                "value"
            ]
            == value
        ]

        families = sorted(
            {
                row[
                    "evaluator_family"
                ]
                for row
                in supporting
            }
        )

        if len(
            families
        ) >= 2:
            return {
                "tier": "auto_silver",
                "value": value,
                "confidence": min(
                    row[
                        "confidence"
                    ]
                    for row
                    in supporting
                ),
                "supporting_judgment_ids": (
                    sorted(
                        row[
                            "id"
                        ]
                        for row
                        in supporting
                    )
                ),
                "supporting_evaluator_families": (
                    families
                ),
                "conflicting_values": [],
            }

    return {
        "tier": "unresolved",
        "value": "",
        "confidence": 0.0,
        "supporting_judgment_ids": [],
        "supporting_evaluator_families": [],
        "conflicting_values": (
            values
            if len(
                values
            ) > 1
            else []
        ),
    }


def _normalize_correction(
    correction: Any,
) -> Dict[str, Any]:
    if correction is None:
        return {}

    if not isinstance(
        correction,
        dict,
    ):
        raise ValueError(
            "Adjudication correction "
            "must be a dictionary."
        )

    value = _clean(
        correction.get(
            "value"
        )
    )

    reason = _clean(
        correction.get(
            "reason"
        )
    )

    corrected_by = _clean(
        correction.get(
            "corrected_by"
        )
    )

    scope = (
        _clean(
            correction.get(
                "scope",
                "case_only",
            )
        ).lower()
    )

    if not value:
        raise ValueError(
            "Adjudication correction value "
            "is required."
        )

    if not reason:
        raise ValueError(
            "Adjudication correction reason "
            "is required."
        )

    if not corrected_by:
        raise ValueError(
            "Adjudication correction actor "
            "is required."
        )

    if (
        scope
        not in
        CORRECTION_SCOPES
    ):
        raise ValueError(
            "Adjudication correction scope "
            "is unsupported."
        )

    return {
        "value": value,
        "reason": reason,
        "corrected_by": (
            corrected_by
        ),
        "corrected_at": (
            _timestamp(
                correction.get(
                    "corrected_at"
                ),
                label=(
                    "Adjudication correction "
                    "corrected_at"
                ),
            )
        ),
        "scope": scope,
    }


def build_automated_adjudication(
    *,
    claim_id: str,
    field: str,
    judgments: List[
        Dict[str, Any]
    ],
    correction: Any = None,
) -> Dict[str, Any]:
    normalized_claim_id = (
        _clean(
            claim_id
        )
    )

    normalized_field = (
        _clean(
            field
        ).lower()
    )

    if not normalized_claim_id:
        raise ValueError(
            "Adjudication claim ID "
            "is required."
        )

    if (
        normalized_field
        not in
        ADJUDICATION_FIELDS
    ):
        raise ValueError(
            "Adjudication field "
            "is unsupported."
        )

    normalized_judgments = (
        _normalize_judgments(
            field=normalized_field,
            judgments=judgments,
        )
    )

    automatic = (
        _automatic_reference(
            field=normalized_field,
            judgments=(
                normalized_judgments
            ),
        )
    )

    normalized_correction = (
        _normalize_correction(
            correction
        )
    )

    if normalized_correction:
        effective_value = (
            normalized_correction[
                "value"
            ]
        )

        effective_source = (
            "manual_override"
        )

        learning_signal = {
            "status": (
                "pending_validation"
            ),
            "source": (
                "manual_override"
            ),
            "field": (
                normalized_field
            ),
            "original_value": (
                automatic[
                    "value"
                ]
            ),
            "corrected_value": (
                effective_value
            ),
            "reason": (
                normalized_correction[
                    "reason"
                ]
            ),
            "scope": (
                normalized_correction[
                    "scope"
                ]
            ),
            "training_eligible": (
                False
            ),
        }

    else:
        effective_value = (
            automatic[
                "value"
            ]
        )

        effective_source = (
            automatic[
                "tier"
            ]
        )

        if (
            automatic[
                "tier"
            ]
            == "auto_gold"
        ):
            learning_signal = {
                "status": (
                    "reference_ready"
                ),
                "source": (
                    "auto_gold"
                ),
                "field": (
                    normalized_field
                ),
                "original_value": (
                    automatic[
                        "value"
                    ]
                ),
                "corrected_value": "",
                "reason": "",
                "scope": (
                    "case_only"
                ),
                "training_eligible": (
                    True
                ),
            }

        elif (
            automatic[
                "tier"
            ]
            == "auto_silver"
        ):
            learning_signal = {
                "status": (
                    "calibration_candidate"
                ),
                "source": (
                    "auto_silver"
                ),
                "field": (
                    normalized_field
                ),
                "original_value": (
                    automatic[
                        "value"
                    ]
                ),
                "corrected_value": "",
                "reason": "",
                "scope": (
                    "case_only"
                ),
                "training_eligible": (
                    False
                ),
            }

        else:
            learning_signal = {}

    return {
        "version": (
            AUTOMATED_ADJUDICATION_VERSION
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "field": (
            normalized_field
        ),
        "judgments": (
            normalized_judgments
        ),
        "automatic": (
            automatic
        ),
        "correction": (
            normalized_correction
        ),
        "effective": {
            "value": (
                effective_value
            ),
            "source": (
                effective_source
            ),
        },
        "learning_signal": (
            learning_signal
        ),
        "policy": {
            "auto_gold_requires_hard_reference_evidence": True,
            "auto_silver_requires_distinct_evaluator_families": True,
            "same_family_votes_do_not_create_consensus": True,
            "high_confidence_conflict_becomes_contested": True,
            "manual_override_preserves_automatic_history": True,
            "manual_override_creates_learning_signal": True,
            "manual_override_does_not_immediately_retrain_live_system": True,
            "auto_gold_is_training_eligible": True,
            "auto_silver_is_not_gold_training_data": True,
            "adjudication_does_not_change_live_merit": True,
        },
    }
