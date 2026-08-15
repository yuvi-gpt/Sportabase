from typing import Any, Dict, Iterable, List, Optional, Tuple


from app.analysis.confidence_calibration import (
    LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS,
    LOCAL_CONFIDENCE_CALIBRATION_VERSION,
    LOCAL_CONFIDENCE_CASE_VERSION,
    LOCAL_CONFIDENCE_PROFILE_VERSION,
)

from app.analysis.corpus_expansion import (
    VALIDATION_CORPUS_EXPANSION_VERSION,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
)

from app.analysis.shadow_calibration import (
    SHADOW_CALIBRATION_VERSION,
)


MERIT_LIVE_RELEASE_GATE_VERSION = (
    "merit-live-release-gate-v2"
)

MERIT_LIVE_MIN_HOLDOUT_CLAIMS = 5

MERIT_LIVE_REQUIRED_FIELD_COVERAGE = tuple(
    sorted(
        MULTI_EVALUATOR_FIELDS
    )
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(
            value or ""
        ).split()
    )


def _key(
    value: Any,
) -> str:
    return _clean(
        value
    ).lower()


def _confidence(
    value: Any,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            "Merit release confidence "
            "must be numeric."
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
            "Merit release confidence "
            "must be numeric."
        ) from exc

    if not (
        0.0
        <= result
        <= 1.0
    ):
        raise ValueError(
            "Merit release confidence must "
            "be between 0 and 1."
        )

    return result


def _positive_int(
    value: Any,
    *,
    label: str,
) -> int:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be an integer."
        )

    try:
        result = int(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{label} must be an integer."
        ) from exc

    if result < 1:
        raise ValueError(
            f"{label} must be at least 1."
        )

    return result


def _training_context(
    calibration: Any,
):
    blockers = []

    case_ids = set()
    claim_ids = set()
    ready_profile_ids = []

    if not isinstance(
        calibration,
        dict,
    ):
        return (
            [
                "calibration_missing"
            ],
            case_ids,
            claim_ids,
            ready_profile_ids,
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
        blockers.append(
            "calibration_version_invalid"
        )

        return (
            blockers,
            case_ids,
            claim_ids,
            ready_profile_ids,
        )

    profiles = calibration.get(
        "profiles"
    )

    cases = calibration.get(
        "cases"
    )

    if not isinstance(
        profiles,
        list,
    ):
        blockers.append(
            "calibration_profiles_invalid"
        )

        profiles = []

    if not isinstance(
        cases,
        list,
    ):
        blockers.append(
            "calibration_cases_invalid"
        )

        cases = []

    for case in cases:
        if not isinstance(
            case,
            dict,
        ):
            blockers.append(
                "calibration_case_invalid"
            )

            continue

        if (
            _clean(
                case.get(
                    "version"
                )
            )
            != (
                LOCAL_CONFIDENCE_CASE_VERSION
            )
        ):
            blockers.append(
                "calibration_case_version_invalid"
            )

            continue

        case_id = _clean(
            case.get(
                "id"
            )
        )

        claim_id = _clean(
            case.get(
                "claim_id"
            )
        )

        if not case_id or not claim_id:
            blockers.append(
                "calibration_case_identity_invalid"
            )

            continue

        case_ids.add(
            case_id
        )

        claim_ids.add(
            claim_id
        )

    for profile in profiles:
        if not isinstance(
            profile,
            dict,
        ):
            blockers.append(
                "calibration_profile_invalid"
            )

            continue

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
            blockers.append(
                "calibration_profile_version_invalid"
            )

            continue

        if profile.get(
            "eligible_for_live_use"
        ) is True:
            blockers.append(
                "calibration_profile_live_flag_forbidden"
            )

        if not profile.get(
            "eligible_for_shadow_adjustment",
            False,
        ):
            continue

        if (
            _clean(
                profile.get(
                    "status"
                )
            )
            != "shadow_ready"
        ):
            blockers.append(
                "calibration_profile_not_shadow_ready"
            )

            continue

        try:
            distinct_claim_count = (
                _positive_int(
                    profile.get(
                        "distinct_claim_count"
                    ),
                    label=(
                        "Calibration profile "
                        "distinct claim count"
                    ),
                )
            )

        except ValueError:
            blockers.append(
                "calibration_profile_support_invalid"
            )

            continue

        if (
            distinct_claim_count
            < (
                LOCAL_CALIBRATION_MIN_DISTINCT_CLAIMS
            )
        ):
            blockers.append(
                "calibration_profile_support_insufficient"
            )

            continue

        supporting_claim_ids = (
            profile.get(
                "supporting_claim_ids"
            )
        )

        if not isinstance(
            supporting_claim_ids,
            list,
        ):
            blockers.append(
                "calibration_profile_support_invalid"
            )

            continue

        normalized_support = {
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
                normalized_support
            )
            != distinct_claim_count
        ):
            blockers.append(
                "calibration_profile_support_invalid"
            )

            continue

        profile_id = _clean(
            profile.get(
                "id"
            )
        )

        if not profile_id:
            blockers.append(
                "calibration_profile_identity_invalid"
            )

            continue

        ready_profile_ids.append(
            profile_id
        )

        claim_ids.update(
            normalized_support
        )

    if not ready_profile_ids:
        blockers.append(
            "no_shadow_ready_profiles"
        )

    return (
        sorted(
            set(
                blockers
            )
        ),
        case_ids,
        claim_ids,
        sorted(
            set(
                ready_profile_ids
            )
        ),
    )


def _holdout_context(
    *,
    holdout_cases: Any,
    training_case_ids,
    training_claim_ids,
    minimum_claims: int,
):
    blockers = []

    if not isinstance(
        holdout_cases,
        list,
    ):
        return (
            [
                "holdout_validation_missing"
            ],
            [],
            [],
        )

    outcomes = {}

    for case in holdout_cases:
        if not isinstance(
            case,
            dict,
        ):
            blockers.append(
                "holdout_case_invalid"
            )

            continue

        if (
            _clean(
                case.get(
                    "version"
                )
            )
            != (
                LOCAL_CONFIDENCE_CASE_VERSION
            )
        ):
            blockers.append(
                "holdout_case_version_invalid"
            )

            continue

        case_id = _clean(
            case.get(
                "id"
            )
        )

        claim_id = _clean(
            case.get(
                "claim_id"
            )
        )

        field = _key(
            case.get(
                "field"
            )
        )

        verified_value = _clean(
            case.get(
                "verified_value"
            )
        )

        if (
            not case_id
            or not claim_id
            or not verified_value
        ):
            blockers.append(
                "holdout_case_identity_invalid"
            )

            continue

        if (
            field
            not in (
                MULTI_EVALUATOR_FIELDS
            )
        ):
            blockers.append(
                "holdout_field_invalid"
            )

            continue

        if (
            case_id
            in training_case_ids
        ):
            blockers.append(
                "holdout_case_reused_for_calibration"
            )

        if (
            claim_id
            in training_claim_ids
        ):
            blockers.append(
                "holdout_claim_reused_for_calibration"
            )

        key = (
            claim_id,
            field,
        )

        existing = outcomes.get(
            key
        )

        if (
            existing is not None
            and existing[
                "verified_value"
            ]
            != verified_value
        ):
            blockers.append(
                "holdout_reference_conflict"
            )

            continue

        outcomes[
            key
        ] = {
            "case_id": case_id,
            "claim_id": claim_id,
            "field": field,
            "verified_value": (
                verified_value
            ),
        }

    normalized = sorted(
        outcomes.values(),
        key=lambda row: (
            row[
                "claim_id"
            ],
            row[
                "field"
            ],
        ),
    )

    holdout_claim_ids = sorted(
        {
            row[
                "claim_id"
            ]
            for row
            in normalized
        }
    )

    if (
        len(
            holdout_claim_ids
        )
        < minimum_claims
    ):
        blockers.append(
            "insufficient_holdout_claims"
        )

    covered_fields = {
        row[
            "field"
        ]
        for row
        in normalized
    }

    missing_fields = sorted(
        set(
            MERIT_LIVE_REQUIRED_FIELD_COVERAGE
        )
        - covered_fields
    )

    if missing_fields:
        blockers.append(
            "required_field_coverage_missing"
        )

    return (
        sorted(
            set(
                blockers
            )
        ),
        normalized,
        missing_fields,
    )


def _corpus_context(
    corpus_expansion: Any,
):
    blockers = []

    if not isinstance(
        corpus_expansion,
        dict,
    ):
        return (
            [
                "corpus_expansion_missing"
            ],
            [],
        )

    if (
        _clean(
            corpus_expansion.get(
                "version"
            )
        )
        != (
            VALIDATION_CORPUS_EXPANSION_VERSION
        )
    ):
        return (
            [
                "corpus_expansion_version_invalid"
            ],
            [],
        )

    target_sports = corpus_expansion.get(
        "target_sports"
    )

    coverage = corpus_expansion.get(
        "coverage"
    )

    queue = corpus_expansion.get(
        "expansion_queue"
    )

    if (
        not isinstance(
            target_sports,
            list,
        )
        or not target_sports
    ):
        blockers.append(
            "corpus_target_sports_invalid"
        )

        target_sports = []

    if not isinstance(
        coverage,
        list,
    ):
        blockers.append(
            "corpus_coverage_invalid"
        )

        coverage = []

    if not isinstance(
        queue,
        list,
    ):
        blockers.append(
            "corpus_expansion_queue_invalid"
        )

        queue = []

    coverage_by_sport = {}

    for row in coverage:
        if not isinstance(
            row,
            dict,
        ):
            blockers.append(
                "corpus_coverage_invalid"
            )

            continue

        sport_key = _key(
            row.get(
                "sport_key"
            )
        )

        if not sport_key:
            blockers.append(
                "corpus_coverage_invalid"
            )

            continue

        coverage_by_sport[
            sport_key
        ] = row

    incomplete = []

    for sport in target_sports:
        sport_key = _key(
            sport
        )

        row = coverage_by_sport.get(
            sport_key
        )

        if row is None:
            incomplete.append(
                sport_key
            )

            continue

        try:
            deficit = int(
                row.get(
                    "deficit",
                    0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            deficit = 1

        if (
            _key(
                row.get(
                    "coverage_status"
                )
            )
            != "covered"
            or deficit != 0
        ):
            incomplete.append(
                sport_key
            )

    if incomplete:
        blockers.append(
            "corpus_coverage_incomplete"
        )

    if queue:
        blockers.append(
            "corpus_expansion_still_pending"
        )

    return (
        sorted(
            set(
                blockers
            )
        ),
        sorted(
            set(
                incomplete
            )
        ),
    )


def _confidence_loss(
    *,
    predicted_value: str,
    confidence: float,
    verified_value: str,
) -> float:
    if not predicted_value:
        return 1.0

    if (
        predicted_value
        == verified_value
    ):
        return (
            1.0
            - confidence
        ) ** 2

    return confidence ** 2


def _shadow_context(
    *,
    shadow_results: Any,
    holdout_outcomes: List[
        Dict[str, Any]
    ],
):
    blockers = []

    if not isinstance(
        shadow_results,
        list,
    ):
        return (
            [
                "shadow_results_missing"
            ],
            {},
        )

    by_claim = {}

    total_adjustments = 0

    for result in shadow_results:
        if not isinstance(
            result,
            dict,
        ):
            blockers.append(
                "shadow_result_invalid"
            )

            continue

        if (
            _clean(
                result.get(
                    "version"
                )
            )
            != (
                SHADOW_CALIBRATION_VERSION
            )
        ):
            blockers.append(
                "shadow_result_version_invalid"
            )

            continue

        claim_id = _clean(
            result.get(
                "claim_id"
            )
        )

        if not claim_id:
            blockers.append(
                "shadow_result_identity_invalid"
            )

            continue

        if claim_id in by_claim:
            blockers.append(
                "duplicate_shadow_claim"
            )

            continue

        policy = result.get(
            "policy"
        )

        if not isinstance(
            policy,
            dict,
        ):
            blockers.append(
                "shadow_policy_invalid"
            )

            continue

        if (
            policy.get(
                "shadow_only"
            )
            is not True
            or policy.get(
                "baseline_is_preserved"
            )
            is not True
            or policy.get(
                "does_not_change_live_merit"
            )
            is not True
        ):
            blockers.append(
                "shadow_policy_invalid"
            )

        comparisons = result.get(
            "comparisons"
        )

        if not isinstance(
            comparisons,
            list,
        ):
            blockers.append(
                "shadow_comparisons_invalid"
            )

            comparisons = []

        comparison_map = {}

        for comparison in comparisons:
            if not isinstance(
                comparison,
                dict,
            ):
                blockers.append(
                    "shadow_comparison_invalid"
                )

                continue

            field = _key(
                comparison.get(
                    "field"
                )
            )

            if (
                field
                not in (
                    MULTI_EVALUATOR_FIELDS
                )
            ):
                blockers.append(
                    "shadow_comparison_field_invalid"
                )

                continue

            if field in comparison_map:
                blockers.append(
                    "duplicate_shadow_field"
                )

                continue

            comparison_map[
                field
            ] = comparison

        adjustments = result.get(
            "adjustments",
            [],
        )

        if not isinstance(
            adjustments,
            list,
        ):
            blockers.append(
                "shadow_adjustments_invalid"
            )

            adjustments = []

        total_adjustments += len(
            adjustments
        )

        by_claim[
            claim_id
        ] = comparison_map

    baseline_correct = 0
    shadow_correct = 0
    regressions = 0
    improvements = 0
    reference_promotions = 0
    untrusted_gold = 0

    baseline_losses = []
    shadow_losses = []

    evaluated = 0

    for outcome in holdout_outcomes:
        claim_id = outcome[
            "claim_id"
        ]

        field = outcome[
            "field"
        ]

        verified_value = outcome[
            "verified_value"
        ]

        comparison_map = (
            by_claim.get(
                claim_id
            )
        )

        if comparison_map is None:
            blockers.append(
                "holdout_shadow_result_missing"
            )

            continue

        comparison = (
            comparison_map.get(
                field
            )
        )

        if comparison is None:
            blockers.append(
                "holdout_shadow_field_missing"
            )

            continue

        baseline = comparison.get(
            "baseline"
        )

        shadow = comparison.get(
            "shadow"
        )

        if (
            not isinstance(
                baseline,
                dict,
            )
            or not isinstance(
                shadow,
                dict,
            )
        ):
            blockers.append(
                "shadow_decision_packet_invalid"
            )

            continue

        try:
            baseline_confidence = (
                _confidence(
                    baseline.get(
                        "confidence",
                        0.0,
                    )
                )
            )

            shadow_confidence = (
                _confidence(
                    shadow.get(
                        "confidence",
                        0.0,
                    )
                )
            )

        except ValueError:
            blockers.append(
                "shadow_confidence_invalid"
            )

            continue

        baseline_value = _clean(
            baseline.get(
                "value"
            )
        )

        shadow_value = _clean(
            shadow.get(
                "value"
            )
        )

        baseline_reference = (
            baseline.get(
                "training_reference_allowed"
            )
            is True
        )

        shadow_reference = (
            shadow.get(
                "training_reference_allowed"
            )
            is True
        )

        if (
            not baseline_reference
            and shadow_reference
        ):
            reference_promotions += 1

        if (
            _key(
                shadow.get(
                    "tier"
                )
            )
            == "auto_gold"
            and not shadow_reference
        ):
            untrusted_gold += 1

        baseline_is_correct = (
            baseline_value
            == verified_value
        )

        shadow_is_correct = (
            shadow_value
            == verified_value
        )

        baseline_correct += int(
            baseline_is_correct
        )

        shadow_correct += int(
            shadow_is_correct
        )

        if (
            baseline_is_correct
            and not shadow_is_correct
        ):
            regressions += 1

        if (
            not baseline_is_correct
            and shadow_is_correct
        ):
            improvements += 1

        baseline_losses.append(
            _confidence_loss(
                predicted_value=(
                    baseline_value
                ),
                confidence=(
                    baseline_confidence
                ),
                verified_value=(
                    verified_value
                ),
            )
        )

        shadow_losses.append(
            _confidence_loss(
                predicted_value=(
                    shadow_value
                ),
                confidence=(
                    shadow_confidence
                ),
                verified_value=(
                    verified_value
                ),
            )
        )

        evaluated += 1

    if total_adjustments == 0:
        blockers.append(
            "no_shadow_adjustments_observed"
        )

    if regressions:
        blockers.append(
            "shadow_decision_regression"
        )

    if reference_promotions:
        blockers.append(
            "shadow_reference_gate_promotion"
        )

    if untrusted_gold:
        blockers.append(
            "shadow_untrusted_auto_gold"
        )

    if evaluated:
        baseline_loss = sum(
            baseline_losses
        ) / evaluated

        shadow_loss = sum(
            shadow_losses
        ) / evaluated

        if (
            shadow_loss
            > baseline_loss
            + 1e-12
        ):
            blockers.append(
                "shadow_confidence_degraded"
            )

        if (
            improvements == 0
            and not (
                shadow_loss
                < baseline_loss
                - 1e-12
            )
        ):
            blockers.append(
                "no_measurable_shadow_improvement"
            )

    else:
        baseline_loss = None
        shadow_loss = None

        blockers.append(
            "no_holdout_shadow_evaluations"
        )

    return (
        sorted(
            set(
                blockers
            )
        ),
        {
            "evaluated_case_count": (
                evaluated
            ),
            "baseline_correct_count": (
                baseline_correct
            ),
            "shadow_correct_count": (
                shadow_correct
            ),
            "decision_improvement_count": (
                improvements
            ),
            "decision_regression_count": (
                regressions
            ),
            "reference_gate_promotion_count": (
                reference_promotions
            ),
            "untrusted_auto_gold_count": (
                untrusted_gold
            ),
            "adjusted_judgment_count": (
                total_adjustments
            ),
            "baseline_confidence_loss": (
                round(
                    baseline_loss,
                    6,
                )
                if baseline_loss
                is not None
                else None
            ),
            "shadow_confidence_loss": (
                round(
                    shadow_loss,
                    6,
                )
                if shadow_loss
                is not None
                else None
            ),
        },
    )


def build_merit_live_release_gate(
    *,
    request_live: bool = False,
    calibration: Optional[
        Dict[str, Any]
    ] = None,
    holdout_cases: Optional[
        List[Dict[str, Any]]
    ] = None,
    shadow_results: Optional[
        List[Dict[str, Any]]
    ] = None,
    corpus_expansion: Optional[
        Dict[str, Any]
    ] = None,
    minimum_holdout_claims: int = (
        MERIT_LIVE_MIN_HOLDOUT_CLAIMS
    ),

    # Legacy arguments remain accepted so
    # callers fail closed instead of crashing.
    # They no longer authorize live Merit.
    dataset: Optional[
        Dict[str, Any]
    ] = None,
    minimum_approved_cases: Optional[
        int
    ] = None,
    evaluator=None,
) -> Dict[str, Any]:
    if not isinstance(
        request_live,
        bool,
    ):
        raise ValueError(
            "request_live must be boolean."
        )

    minimum_claims = (
        _positive_int(
            minimum_holdout_claims,
            label=(
                "Minimum holdout claim count"
            ),
        )
    )

    (
        calibration_blockers,
        training_case_ids,
        training_claim_ids,
        ready_profile_ids,
    ) = _training_context(
        calibration
    )

    (
        holdout_blockers,
        holdout_outcomes,
        missing_fields,
    ) = _holdout_context(
        holdout_cases=(
            holdout_cases
        ),
        training_case_ids=(
            training_case_ids
        ),
        training_claim_ids=(
            training_claim_ids
        ),
        minimum_claims=(
            minimum_claims
        ),
    )

    (
        corpus_blockers,
        incomplete_sports,
    ) = _corpus_context(
        corpus_expansion
    )

    (
        shadow_blockers,
        shadow_metrics,
    ) = _shadow_context(
        shadow_results=(
            shadow_results
        ),
        holdout_outcomes=(
            holdout_outcomes
        ),
    )

    blockers = sorted(
        set(
            calibration_blockers
            + holdout_blockers
            + corpus_blockers
            + shadow_blockers
        )
    )

    live_authorized = bool(
        request_live
        and not blockers
    )

    release_authorized = bool(
        not request_live
        or live_authorized
    )

    if live_authorized:
        status = "live_authorized"

        reason = (
            "Automated calibration, "
            "non-overlapping trusted holdout "
            "validation, shadow comparison, "
            "and corpus coverage satisfy the "
            "conditional Merit release gate."
        )

    elif request_live:
        status = "live_blocked"

        reason = (
            "Live Merit was requested but "
            "the automated release conditions "
            "are not satisfied."
        )

    else:
        status = "shadow_safe"

        reason = (
            "Live Merit was not requested. "
            "Existing production scoring "
            "remains unchanged."
        )

    holdout_claim_ids = sorted(
        {
            row[
                "claim_id"
            ]
            for row
            in holdout_outcomes
        }
    )

    legacy_input_detected = bool(
        dataset is not None
        or minimum_approved_cases
        is not None
        or evaluator is not None
    )

    return {
        "version": (
            MERIT_LIVE_RELEASE_GATE_VERSION
        ),
        "status": status,
        "request_live": request_live,
        "release_authorized": (
            release_authorized
        ),
        "live_merit_authorized": (
            live_authorized
        ),
        "blockers": blockers,
        "reason": reason,
        "minimum_holdout_claims": (
            minimum_claims
        ),
        "required_field_coverage": list(
            MERIT_LIVE_REQUIRED_FIELD_COVERAGE
        ),
        "missing_field_coverage": (
            missing_fields
        ),
        "incomplete_corpus_sports": (
            incomplete_sports
        ),
        "calibration": {
            "shadow_ready_profile_ids": (
                ready_profile_ids
            ),
            "shadow_ready_profile_count": (
                len(
                    ready_profile_ids
                )
            ),
            "training_case_count": (
                len(
                    training_case_ids
                )
            ),
            "training_claim_count": (
                len(
                    training_claim_ids
                )
            ),
        },
        "holdout": {
            "case_count": len(
                holdout_outcomes
            ),
            "claim_count": len(
                holdout_claim_ids
            ),
            "claim_ids": (
                holdout_claim_ids
            ),
        },
        "shadow_metrics": (
            shadow_metrics
        ),
        "legacy_input_detected": (
            legacy_input_detected
        ),
        "policy": {
            "automated_validation_only": True,
            "human_review_required": False,
            "calibration_and_holdout_must_not_overlap": True,
            "holdout_requires_later_trusted_outcomes": True,
            "all_adjudication_fields_require_holdout_coverage": True,
            "shadow_decision_regressions_block_release": True,
            "shadow_reference_gate_promotions_block_release": True,
            "untrusted_shadow_auto_gold_blocks_release": True,
            "measurable_shadow_improvement_required": True,
            "corpus_coverage_must_be_complete": True,
            "legacy_human_curated_gate_is_not_authoritative": True,
            "gate_does_not_activate_product": True,
            "production_wiring_required_separately": True,
            "does_not_modify_merit_score": True,
            "does_not_train_model": True,
            "does_not_persist": True,
        },
    }
