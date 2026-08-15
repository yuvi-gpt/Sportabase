import copy

from typing import (
    Any,
    Dict,
    List,
    Tuple,
)


from app.analysis.confidence_calibration import (
    LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS,
    LOCAL_CONFIDENCE_CALIBRATION_VERSION,
    LOCAL_CONFIDENCE_PROFILE_VERSION,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
    TRUSTED_REFERENCE_DERIVATION_MODES,
    build_multi_evaluator_adjudication,
)


SHADOW_CALIBRATION_VERSION = (
    "shadow-calibration-v2"
)

CONFIDENCE_BUCKETS = {
    "0.00-0.59",
    "0.60-0.79",
    "0.80-0.89",
    "0.90-1.00",
}


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _confidence(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Shadow confidence must be numeric."
        )

    try:
        result = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Shadow confidence must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Shadow confidence must be "
            "between 0 and 1."
        )

    return result


def _bucket(
    confidence: float,
) -> str:
    if confidence < 0.60:
        return "0.00-0.59"

    if confidence < 0.80:
        return "0.60-0.79"

    if confidence < 0.90:
        return "0.80-0.89"

    return "0.90-1.00"


def _normalize_profiles(
    calibration: Any,
) -> Tuple[
    Dict[
        Tuple[str, str, str],
        Dict[str, Any],
    ],
    List[str],
]:
    if not isinstance(
        calibration,
        dict,
    ):
        raise ValueError(
            "Shadow calibration input "
            "must be a dictionary."
        )

    if (
        _clean(
            calibration.get(
                "version"
            )
        )
        != (
            LOCAL_CONFIDENCE_CALIBRATION_VERSION
        )
    ):
        raise ValueError(
            "Shadow integration requires "
            "the current local calibration version."
        )

    profiles = calibration.get(
        "profiles"
    )

    if not isinstance(
        profiles,
        list,
    ):
        raise ValueError(
            "Shadow calibration profiles "
            "must be a list."
        )

    index = {}
    profile_ids = []

    for profile in profiles:
        if not isinstance(
            profile,
            dict,
        ):
            raise ValueError(
                "Shadow calibration profile "
                "must be a dictionary."
            )

        if (
            _clean(
                profile.get(
                    "version"
                )
            )
            != (
                LOCAL_CONFIDENCE_PROFILE_VERSION
            )
        ):
            raise ValueError(
                "Shadow calibration profile "
                "version is unsupported."
            )

        profile_id = _clean(
            profile.get(
                "id"
            )
        )

        field = _clean(
            profile.get(
                "field"
            )
        ).lower()

        family = _clean(
            profile.get(
                "evaluator_family"
            )
        ).lower()

        confidence_bucket = _clean(
            profile.get(
                "confidence_bucket"
            )
        )

        if not profile_id:
            raise ValueError(
                "Shadow calibration profile "
                "ID is required."
            )

        if (
            field
            not in MULTI_EVALUATOR_FIELDS
        ):
            raise ValueError(
                "Shadow calibration field "
                "is unsupported."
            )

        if not family:
            raise ValueError(
                "Shadow calibration evaluator "
                "family is required."
            )

        if (
            confidence_bucket
            not in CONFIDENCE_BUCKETS
        ):
            raise ValueError(
                "Shadow calibration confidence "
                "bucket is unsupported."
            )

        shadow_allowed = profile.get(
            "eligible_for_shadow_adjustment"
        )

        live_allowed = profile.get(
            "eligible_for_live_use"
        )

        if not isinstance(
            shadow_allowed,
            bool,
        ):
            raise ValueError(
                "Shadow calibration eligibility "
                "must be boolean."
            )

        if not isinstance(
            live_allowed,
            bool,
        ):
            raise ValueError(
                "Live calibration eligibility "
                "must be boolean."
            )

        if live_allowed:
            raise ValueError(
                "Live calibration profiles are "
                "forbidden in shadow integration."
            )

        key = (
            field,
            family,
            confidence_bucket,
        )

        if key in index:
            raise ValueError(
                "Shadow calibration contains "
                "duplicate profile scope."
            )

        profile_ids.append(
            profile_id
        )

        if not shadow_allowed:
            index[
                key
            ] = {
                "eligible": False,
                "profile": profile,
            }

            continue

        if (
            _clean(
                profile.get(
                    "status"
                )
            )
            != "shadow_ready"
        ):
            raise ValueError(
                "Shadow-adjustable profile "
                "must be shadow_ready."
            )

        target = _confidence(
            profile.get(
                "shadow_target_confidence"
            )
        )

        distinct_claim_count = (
            profile.get(
                "distinct_claim_count"
            )
        )

        if isinstance(
            distinct_claim_count,
            bool,
        ):
            raise ValueError(
                "Calibration distinct claim "
                "count must be an integer."
            )

        try:
            distinct_claim_count = int(
                distinct_claim_count
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "Calibration distinct claim "
                "count must be an integer."
            ) from exc

        if (
            distinct_claim_count
            < (
                LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS
            )
        ):
            raise ValueError(
                "Shadow-ready profile lacks "
                "enough distinct claims."
            )

        supporting_claim_ids = (
            profile.get(
                "supporting_claim_ids"
            )
        )

        if not isinstance(
            supporting_claim_ids,
            list,
        ):
            raise ValueError(
                "Shadow calibration supporting "
                "claim IDs must be a list."
            )

        normalized_claims = {
            _clean(
                value
            )
            for value
            in supporting_claim_ids
            if _clean(
                value
            )
        }

        if (
            len(
                normalized_claims
            )
            != distinct_claim_count
        ):
            raise ValueError(
                "Shadow calibration distinct "
                "claim support is inconsistent."
            )

        index[
            key
        ] = {
            "eligible": True,
            "target": target,
            "profile": profile,
        }

    return (
        index,
        sorted(
            set(
                profile_ids
            )
        ),
    )


def _decision_packet(
    result: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    automatic = result[
        "automatic"
    ]

    reference_gate = result[
        "reference_gate"
    ]

    return {
        "tier": (
            automatic[
                "tier"
            ]
        ),
        "value": (
            automatic[
                "value"
            ]
        ),
        "confidence": (
            automatic[
                "confidence"
            ]
        ),
        "conflicting_values": (
            list(
                automatic[
                    "conflicting_values"
                ]
            )
        ),
        "training_reference_allowed": (
            bool(
                reference_gate[
                    "training_reference_allowed"
                ]
            )
        ),
        "supporting_judgment_ids": (
            list(
                automatic[
                    "supporting_judgment_ids"
                ]
            )
        ),
        "supporting_evaluator_families": (
            list(
                automatic[
                    "supporting_evaluator_families"
                ]
            )
        ),
    }


def _comparison(
    *,
    field: str,
    baseline: Dict[
        str,
        Any,
    ],
    shadow: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    baseline_packet = (
        _decision_packet(
            baseline
        )
    )

    shadow_packet = (
        _decision_packet(
            shadow
        )
    )

    decision_keys = (
        "tier",
        "value",
        "confidence",
        "conflicting_values",
        "training_reference_allowed",
    )

    lineage_keys = (
        "supporting_judgment_ids",
        "supporting_evaluator_families",
    )

    decision_changes = [
        key
        for key
        in decision_keys
        if (
            baseline_packet[
                key
            ]
            != shadow_packet[
                key
            ]
        )
    ]

    lineage_changes = [
        key
        for key
        in lineage_keys
        if (
            baseline_packet[
                key
            ]
            != shadow_packet[
                key
            ]
        )
    ]

    return {
        "field": field,
        "baseline": (
            baseline_packet
        ),
        "shadow": (
            shadow_packet
        ),
        "decision_changed": (
            bool(
                decision_changes
            )
        ),
        "lineage_changed": (
            bool(
                lineage_changes
            )
        ),
        "decision_change_types": (
            decision_changes
        ),
        "lineage_change_types": (
            lineage_changes
        ),
    }


def build_shadow_calibrated_adjudication(
    *,
    claim_id: str,
    evaluator_runs: List[
        Dict[str, Any]
    ],
    calibration: Dict[
        str,
        Any,
    ],
) -> Dict[str, Any]:
    normalized_claim_id = _clean(
        claim_id
    )

    if not normalized_claim_id:
        raise ValueError(
            "Shadow calibration claim ID "
            "is required."
        )

    if not isinstance(
        evaluator_runs,
        list,
    ):
        raise ValueError(
            "Shadow calibration evaluator "
            "runs must be a list."
        )

    baseline = (
        build_multi_evaluator_adjudication(
            claim_id=(
                normalized_claim_id
            ),
            evaluator_runs=(
                evaluator_runs
            ),
        )
    )

    (
        profile_index,
        profile_ids,
    ) = _normalize_profiles(
        calibration
    )

    shadow_runs = copy.deepcopy(
        baseline[
            "evaluators"
        ]
    )

    adjustments = []

    for run in shadow_runs:
        derivation_mode = _clean(
            run.get(
                "derivation_mode"
            )
        ).lower()

        evaluator_family = (
            _clean(
                run.get(
                    "evaluator_family"
                )
            ).lower()
        )

        if (
            derivation_mode
            in (
                TRUSTED_REFERENCE_DERIVATION_MODES
            )
        ):
            continue

        for judgment in run[
            "judgments"
        ]:
            field = _clean(
                judgment.get(
                    "field"
                )
            ).lower()

            original_confidence = (
                _confidence(
                    judgment.get(
                        "confidence"
                    )
                )
            )

            confidence_bucket = (
                _bucket(
                    original_confidence
                )
            )

            profile_entry = (
                profile_index.get(
                    (
                        field,
                        evaluator_family,
                        confidence_bucket,
                    )
                )
            )

            if not profile_entry:
                continue

            if not profile_entry[
                "eligible"
            ]:
                continue

            shadow_confidence = (
                profile_entry[
                    "target"
                ]
            )

            if (
                shadow_confidence
                == original_confidence
            ):
                continue

            profile = (
                profile_entry[
                    "profile"
                ]
            )

            judgment[
                "confidence"
            ] = shadow_confidence

            adjustments.append(
                {
                    "judgment_id": (
                        judgment[
                            "id"
                        ]
                    ),
                    "field": field,
                    "evaluator_id": (
                        run[
                            "evaluator_id"
                        ]
                    ),
                    "evaluator_family": (
                        evaluator_family
                    ),
                    "profile_id": (
                        profile[
                            "id"
                        ]
                    ),
                    "scope_id": (
                        profile.get(
                            "scope_id"
                        )
                    ),
                    "confidence_bucket": (
                        confidence_bucket
                    ),
                    "baseline_value": (
                        judgment[
                            "value"
                        ]
                    ),
                    "shadow_value": (
                        judgment[
                            "value"
                        ]
                    ),
                    "baseline_confidence": (
                        original_confidence
                    ),
                    "shadow_confidence": (
                        shadow_confidence
                    ),
                    "delta": round(
                        (
                            shadow_confidence
                            - original_confidence
                        ),
                        6,
                    ),
                }
            )

    shadow = (
        build_multi_evaluator_adjudication(
            claim_id=(
                normalized_claim_id
            ),
            evaluator_runs=(
                shadow_runs
            ),
        )
    )

    comparisons = [
        _comparison(
            field=field,
            baseline=(
                baseline[
                    "fields"
                ][
                    field
                ]
            ),
            shadow=(
                shadow[
                    "fields"
                ][
                    field
                ]
            ),
        )
        for field
        in MULTI_EVALUATOR_FIELDS
    ]

    comparisons = sorted(
        comparisons,
        key=lambda row: (
            row[
                "field"
            ]
        ),
    )

    adjustments = sorted(
        adjustments,
        key=lambda row: (
            row[
                "field"
            ],
            row[
                "evaluator_family"
            ],
            row[
                "judgment_id"
            ],
        ),
    )

    return {
        "version": (
            SHADOW_CALIBRATION_VERSION
        ),
        "claim_id": (
            normalized_claim_id
        ),
        "baseline_adjudication": (
            baseline
        ),
        "shadow_adjudication": (
            shadow
        ),
        "adjustments": adjustments,
        "comparisons": comparisons,
        "calibration_profile_ids": (
            profile_ids
        ),
        "summary": {
            "adjusted_judgment_count": len(
                adjustments
            ),
            "decision_changed_field_count": sum(
                1
                for row
                in comparisons
                if row[
                    "decision_changed"
                ]
            ),
            "lineage_changed_field_count": sum(
                1
                for row
                in comparisons
                if row[
                    "lineage_changed"
                ]
            ),
        },
        "policy": {
            "shadow_only": True,
            "baseline_is_preserved": True,
            "trusted_reference_runs_are_not_adjusted": True,
            "only_shadow_ready_profiles_apply": True,
            "calibration_is_field_family_and_bucket_local": True,
            "shadow_adjustments_preserve_judgment_value": True,
            "shadow_output_cannot_establish_truth": True,
            "shadow_output_cannot_train_model": True,
            "shadow_output_is_not_live_adjudication": True,
            "does_not_persist": True,
            "does_not_change_live_merit": True,
            "human_review_required": False,
        },
    }
