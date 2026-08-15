import hashlib
import json

from typing import Any, Dict, List


from app.analysis.adjudication_state import (
    AUTOMATED_ADJUDICATION_STATE_VERSION,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)


LOCAL_CONFIDENCE_CALIBRATION_VERSION = (
    "local-confidence-calibration-v2"
)

LOCAL_CONFIDENCE_CASE_VERSION = (
    "local-confidence-case-v1"
)

LOCAL_CONFIDENCE_PROFILE_VERSION = (
    "local-confidence-profile-v2"
)

LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS = 5

# Preserve v1's two pseudo-observation regularization
# strength, but center the shrinkage prior on the
# evaluator's own reported confidence instead of 0.50.
LOCAL_CALIBRATION_PRIOR_STRENGTH = 2.0


def _clean(value: Any) -> str:
    return " ".join(
        str(value or "").split()
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_copy(value: Any) -> Any:
    return json.loads(
        _canonical_json(value)
    )


def _hash(
    value: Any,
    *,
    prefix: str,
) -> str:
    return hashlib.sha256(
        (
            prefix
            + _canonical_json(value)
        ).encode("utf-8")
    ).hexdigest()


def _confidence(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(
            "Calibration confidence must be numeric."
        )

    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Calibration confidence must be numeric."
        ) from exc

    if not 0.0 <= result <= 1.0:
        raise ValueError(
            "Calibration confidence must be between 0 and 1."
        )

    return result


def _bucket(confidence: float) -> str:
    if confidence < 0.60:
        return "0.00-0.59"

    if confidence < 0.80:
        return "0.60-0.79"

    if confidence < 0.90:
        return "0.80-0.89"

    return "0.90-1.00"


def _string_list(
    value: Any,
    *,
    label: str,
    lower: bool = False,
) -> List[str]:
    if not isinstance(value, list):
        raise ValueError(
            f"{label} must be a list."
        )

    output = set()

    for item in value:
        cleaned = _clean(item)

        if not cleaned:
            continue

        if lower:
            cleaned = cleaned.lower()

        output.add(cleaned)

    return sorted(output)


def _revision(
    value: Any,
    *,
    label: str,
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{label} must be a dictionary."
        )

    revision = _canonical_copy(value)

    if (
        _clean(revision.get("version"))
        != AUTOMATED_ADJUDICATION_STATE_VERSION
    ):
        raise ValueError(
            f"{label} version is unsupported."
        )

    if not _clean(revision.get("claim_id")):
        raise ValueError(
            f"{label} claim ID is required."
        )

    if not _clean(revision.get("revision_id")):
        raise ValueError(
            f"{label} revision ID is required."
        )

    fields = revision.get("fields")

    if (
        not isinstance(fields, dict)
        or set(fields.keys())
        != set(MULTI_EVALUATOR_FIELDS)
    ):
        raise ValueError(
            f"{label} field coverage is invalid."
        )

    return revision


def _packet(
    revision: Dict[str, Any],
    field: str,
) -> Dict[str, Any]:
    packet = revision[
        "fields"
    ].get(field)

    if not isinstance(packet, dict):
        raise ValueError(
            "Calibration field packet is invalid."
        )

    state = packet.get("state")
    lineage = packet.get("lineage")

    if (
        not isinstance(state, dict)
        or not isinstance(lineage, dict)
    ):
        raise ValueError(
            "Calibration field state is invalid."
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
            "Calibration training-reference "
            "permission must be boolean."
        )

    return {
        "state": {
            "tier": _clean(
                state.get("tier")
            ).lower(),
            "value": _clean(
                state.get("value")
            ),
            "confidence": _confidence(
                state.get(
                    "confidence",
                    0.0,
                )
            ),
            "training_reference_allowed": (
                training_allowed
            ),
        },
        "lineage": {
            "supporting_evaluator_families": (
                _string_list(
                    lineage.get(
                        "supporting_evaluator_families",
                        [],
                    ),
                    label=(
                        "Calibration evaluator families"
                    ),
                    lower=True,
                )
            ),
            "trusted_hard_reference_judgment_ids": (
                _string_list(
                    lineage.get(
                        "trusted_hard_reference_judgment_ids",
                        [],
                    ),
                    label=(
                        "Calibration trusted-reference IDs"
                    ),
                )
            ),
        },
    }


def _case_payload(
    *,
    claim_id: str,
    field: str,
    evaluator_family: str,
    previous_revision_id: str,
    current_revision_id: str,
    reported_confidence: float,
    previous_value: str,
    verified_value: str,
    outcome: str,
) -> Dict[str, Any]:
    return {
        "version": (
            LOCAL_CONFIDENCE_CASE_VERSION
        ),
        "claim_id": claim_id,
        "field": field,
        "evaluator_family": (
            evaluator_family
        ),
        "previous_revision_id": (
            previous_revision_id
        ),
        "current_revision_id": (
            current_revision_id
        ),
        "reported_confidence": (
            reported_confidence
        ),
        "confidence_bucket": (
            _bucket(
                reported_confidence
            )
        ),
        "previous_value": (
            previous_value
        ),
        "verified_value": (
            verified_value
        ),
        "outcome": outcome,
    }


def _case_id(
    case: Dict[str, Any],
) -> str:
    payload = {
        key: value
        for key, value
        in case.items()
        if key != "id"
    }

    return _hash(
        payload,
        prefix=(
            "local-confidence-case|"
        ),
    )


def build_local_confidence_cases(
    *,
    previous_revision: Dict[str, Any],
    current_revision: Dict[str, Any],
) -> List[Dict[str, Any]]:
    previous = _revision(
        previous_revision,
        label=(
            "Previous calibration revision"
        ),
    )

    current = _revision(
        current_revision,
        label=(
            "Current calibration revision"
        ),
    )

    if (
        previous["claim_id"]
        != current["claim_id"]
    ):
        raise ValueError(
            "Calibration revisions belong "
            "to different claims."
        )

    if (
        _clean(
            current.get(
                "previous_revision_id"
            )
        )
        != previous["revision_id"]
    ):
        raise ValueError(
            "Calibration requires direct "
            "consecutive revisions."
        )

    adjudication = previous.get(
        "adjudication"
    )

    if not isinstance(
        adjudication,
        dict,
    ):
        raise ValueError(
            "Previous calibration revision "
            "must preserve adjudication lineage."
        )

    evaluators = adjudication.get(
        "evaluators"
    )

    if not isinstance(
        evaluators,
        list,
    ):
        raise ValueError(
            "Previous calibration evaluator "
            "runs must be a list."
        )

    cases = []

    for field in MULTI_EVALUATOR_FIELDS:
        verified_packet = _packet(
            current,
            field,
        )

        verified_state = (
            verified_packet[
                "state"
            ]
        )

        verified_lineage = (
            verified_packet[
                "lineage"
            ]
        )

        verified_value = _clean(
            verified_state.get(
                "value"
            )
        )

        if not verified_value:
            continue

        if (
            verified_state.get(
                "tier"
            )
            != "auto_gold"
        ):
            continue

        if not verified_state.get(
            "training_reference_allowed"
        ):
            continue

        if not verified_lineage.get(
            "trusted_hard_reference_judgment_ids"
        ):
            continue

        for run in evaluators:
            if not isinstance(
                run,
                dict,
            ):
                raise ValueError(
                    "Calibration evaluator run "
                    "must be a dictionary."
                )

            evaluator_family = (
                _clean(
                    run.get(
                        "evaluator_family"
                    )
                ).lower()
            )

            if not evaluator_family:
                raise ValueError(
                    "Calibration evaluator family "
                    "is required."
                )

            judgments = run.get(
                "judgments",
                [],
            )

            if not isinstance(
                judgments,
                list,
            ):
                raise ValueError(
                    "Calibration evaluator judgments "
                    "must be a list."
                )

            for judgment in judgments:
                if not isinstance(
                    judgment,
                    dict,
                ):
                    raise ValueError(
                        "Calibration evaluator judgment "
                        "must be a dictionary."
                    )

                judgment_field = (
                    _clean(
                        judgment.get(
                            "field"
                        )
                    ).lower()
                )

                if judgment_field != field:
                    continue

                judgment_family = (
                    _clean(
                        judgment.get(
                            "evaluator_family"
                        )
                    ).lower()
                )

                if (
                    judgment_family
                    != evaluator_family
                ):
                    raise ValueError(
                        "Calibration judgment family "
                        "does not match evaluator run."
                    )

                previous_value = _clean(
                    judgment.get(
                        "value"
                    )
                )

                if not previous_value:
                    continue

                reported_confidence = (
                    _confidence(
                        judgment.get(
                            "confidence"
                        )
                    )
                )

                outcome = (
                    "confirmed"
                    if (
                        previous_value
                        == verified_value
                    )
                    else "corrected"
                )

                payload = _case_payload(
                    claim_id=(
                        current[
                            "claim_id"
                        ]
                    ),
                    field=field,
                    evaluator_family=(
                        evaluator_family
                    ),
                    previous_revision_id=(
                        previous[
                            "revision_id"
                        ]
                    ),
                    current_revision_id=(
                        current[
                            "revision_id"
                        ]
                    ),
                    reported_confidence=(
                        reported_confidence
                    ),
                    previous_value=(
                        previous_value
                    ),
                    verified_value=(
                        verified_value
                    ),
                    outcome=outcome,
                )

                cases.append(
                    {
                        **payload,
                        "id": _case_id(
                            payload
                        ),
                    }
                )

    return sorted(
        cases,
        key=lambda row: (
            row["field"],
            row[
                "evaluator_family"
            ],
            row["id"],
        ),
    )

def _normalize_case(
    value: Any,
) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(
            "Calibration case must "
            "be a dictionary."
        )

    case = _canonical_copy(value)

    if (
        _clean(case.get("version"))
        != LOCAL_CONFIDENCE_CASE_VERSION
    ):
        raise ValueError(
            "Calibration case version "
            "is unsupported."
        )

    required = (
        "id",
        "claim_id",
        "field",
        "evaluator_family",
        "previous_revision_id",
        "current_revision_id",
        "previous_value",
        "verified_value",
        "outcome",
    )

    if not all(
        _clean(case.get(key))
        for key in required
    ):
        raise ValueError(
            "Calibration case identity "
            "is incomplete."
        )

    if (
        case["field"]
        not in MULTI_EVALUATOR_FIELDS
    ):
        raise ValueError(
            "Calibration case field "
            "is unsupported."
        )

    case[
        "evaluator_family"
    ] = _clean(
        case[
            "evaluator_family"
        ]
    ).lower()

    confidence = _confidence(
        case[
            "reported_confidence"
        ]
    )

    case[
        "reported_confidence"
    ] = confidence

    expected_bucket = _bucket(
        confidence
    )

    if (
        _clean(
            case.get(
                "confidence_bucket"
            )
        )
        != expected_bucket
    ):
        raise ValueError(
            "Calibration case confidence "
            "bucket is inconsistent."
        )

    outcome = _clean(
        case["outcome"]
    ).lower()

    if outcome not in {
        "confirmed",
        "corrected",
    }:
        raise ValueError(
            "Calibration case outcome "
            "is unsupported."
        )

    case["outcome"] = outcome

    if (
        _clean(case["id"])
        != _case_id(case)
    ):
        raise ValueError(
            "Calibration case deterministic "
            "identity is invalid."
        )

    if (
        outcome == "confirmed"
        and (
            case["previous_value"]
            != case["verified_value"]
        )
    ):
        raise ValueError(
            "Confirmed calibration case "
            "has different values."
        )

    if (
        outcome == "corrected"
        and (
            case["previous_value"]
            == case["verified_value"]
        )
    ):
        raise ValueError(
            "Corrected calibration case "
            "has identical values."
        )

    return case


def build_local_confidence_calibration(
    *,
    cases: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(cases, list):
        raise ValueError(
            "Calibration cases must "
            "be a list."
        )

    unique = {}

    for raw_case in cases:
        case = _normalize_case(
            raw_case
        )

        case_id = case["id"]

        if case_id in unique:
            if (
                _canonical_json(
                    unique[case_id]
                )
                != _canonical_json(
                    case
                )
            ):
                raise ValueError(
                    "Calibration case ID "
                    "collision detected."
                )

            continue

        unique[
            case_id
        ] = case

    normalized_cases = sorted(
        unique.values(),
        key=lambda row: (
            row["field"],
            row[
                "evaluator_family"
            ],
            row[
                "confidence_bucket"
            ],
            row["id"],
        ),
    )

    groups = {}

    for case in normalized_cases:
        key = (
            case["field"],
            case[
                "evaluator_family"
            ],
            case[
                "confidence_bucket"
            ],
        )

        groups.setdefault(
            key,
            [],
        ).append(case)

    profiles = []

    for (
        field,
        evaluator_family,
        confidence_bucket,
    ), rows in sorted(
        groups.items()
    ):
        claim_ids = sorted(
            {
                row[
                    "claim_id"
                ]
                for row in rows
            }
        )

        confirmed = sum(
            1
            for row in rows
            if (
                row["outcome"]
                == "confirmed"
            )
        )

        corrected = sum(
            1
            for row in rows
            if (
                row["outcome"]
                == "corrected"
            )
        )

        sample_count = len(rows)

        mean_confidence = (
            sum(
                row[
                    "reported_confidence"
                ]
                for row in rows
            )
            / sample_count
        )

        observed_accuracy = (
            confirmed
            / sample_count
        )

        # v2 uses reported-confidence-centered
        # shrinkage. Verified outcomes move the target
        # away from the model's own mean confidence only
        # in the direction justified by calibration data.
        smoothed_accuracy = (
            (
                confirmed
                + (
                    LOCAL_CALIBRATION_PRIOR_STRENGTH
                    * mean_confidence
                )
            )
            / (
                sample_count
                + LOCAL_CALIBRATION_PRIOR_STRENGTH
            )
        )

        brier_score = (
            sum(
                (
                    row[
                        "reported_confidence"
                    ]
                    - (
                        1.0
                        if (
                            row["outcome"]
                            == "confirmed"
                        )
                        else 0.0
                    )
                )
                ** 2
                for row in rows
            )
            / sample_count
        )

        shadow_target_brier_score = (
            sum(
                (
                    smoothed_accuracy
                    - (
                        1.0
                        if (
                            row["outcome"]
                            == "confirmed"
                        )
                        else 0.0
                    )
                )
                ** 2
                for row in rows
            )
            / sample_count
        )

        distinct_claim_count = len(
            claim_ids
        )

        enough_claims = (
            distinct_claim_count
            >= (
                LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS
            )
        )

        calibration_gain = (
            shadow_target_brier_score
            < brier_score
            - 1e-12
        )

        shadow_ready = bool(
            enough_claims
            and calibration_gain
        )

        scope_payload = {
            "field": field,
            "evaluator_family": (
                evaluator_family
            ),
            "confidence_bucket": (
                confidence_bucket
            ),
        }

        scope_id = _hash(
            scope_payload,
            prefix=(
                "local-confidence-scope|"
            ),
        )

        profile_payload = {
            "version": (
                LOCAL_CONFIDENCE_PROFILE_VERSION
            ),
            "scope_id": scope_id,
            **scope_payload,
            "sample_count": sample_count,
            "distinct_claim_count": (
                distinct_claim_count
            ),
            "confirmed_count": confirmed,
            "corrected_count": corrected,
            "mean_reported_confidence": round(
                mean_confidence,
                6,
            ),
            "observed_accuracy": round(
                observed_accuracy,
                6,
            ),
            "smoothing_prior_mean": round(
                mean_confidence,
                6,
            ),
            "smoothing_prior_strength": (
                LOCAL_CALIBRATION_PRIOR_STRENGTH
            ),
            "smoothed_accuracy": round(
                smoothed_accuracy,
                6,
            ),
            "calibration_gap": round(
                (
                    observed_accuracy
                    - mean_confidence
                ),
                6,
            ),
            "brier_score": round(
                brier_score,
                6,
            ),
            "shadow_target_brier_score": round(
                shadow_target_brier_score,
                6,
            ),
            "shadow_target_improves_calibration_brier": (
                calibration_gain
            ),
            "supporting_claim_ids": (
                claim_ids
            ),
            "supporting_case_ids": sorted(
                row["id"]
                for row in rows
            ),
            "status": (
                "shadow_ready"
                if shadow_ready
                else (
                    "no_calibration_gain"
                    if enough_claims
                    else "insufficient_data"
                )
            ),
            "eligible_for_shadow_adjustment": (
                shadow_ready
            ),
            "shadow_target_confidence": (
                round(
                    smoothed_accuracy,
                    6,
                )
                if shadow_ready
                else None
            ),
            "eligible_for_live_use": False,
        }

        profiles.append(
            {
                **profile_payload,
                "id": _hash(
                    profile_payload,
                    prefix=(
                        "local-confidence-profile|"
                    ),
                ),
            }
        )

    return {
        "version": (
            LOCAL_CONFIDENCE_CALIBRATION_VERSION
        ),
        "cases": normalized_cases,
        "profiles": profiles,
        "summary": {
            "case_count": len(
                normalized_cases
            ),
            "profile_count": len(
                profiles
            ),
            "shadow_ready_profile_count": sum(
                1
                for profile
                in profiles
                if profile[
                    "eligible_for_shadow_adjustment"
                ]
            ),
        },
        "policy": {
            "uses_only_later_trusted_gold_outcomes": True,
            "confirmed_and_corrected_cases_both_count": True,
            "calibration_is_field_family_and_bucket_local": True,
            "distinct_claim_minimum": (
                LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS
            ),
            "small_samples_do_not_adjust": True,
            "shadow_target_is_smoothed": True,
            "shadow_target_shrinks_verified_accuracy_toward_reported_confidence": True,
            "shadow_target_prior_strength": (
                LOCAL_CALIBRATION_PRIOR_STRENGTH
            ),
            "shadow_adjustment_requires_calibration_brier_gain": True,
            "eligible_for_live_use": False,
            "does_not_change_adjudication": True,
            "does_not_establish_truth": True,
            "does_not_train_model": True,
            "does_not_change_live_merit": True,
            "does_not_persist_by_itself": True,
            "human_review_required": False,
        },
    }
