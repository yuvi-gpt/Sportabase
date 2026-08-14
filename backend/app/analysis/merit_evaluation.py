from typing import Any, Dict, List

from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
    build_merit_corroboration_overlay,
)


MERIT_CORROBORATION_EVALUATION_VERSION = (
    "merit-corroboration-evaluation-v1"
)

MERIT_CORROBORATION_GOLDEN_CASE_VERSION = (
    "merit-corroboration-golden-case-v1"
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _numeric(
    value: Any,
    *,
    label: str,
) -> float:
    if isinstance(
        value,
        bool,
    ):
        raise ValueError(
            f"{label} must be numeric."
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
            f"{label} must be numeric."
        ) from exc

    return result


def _same_number(
    left: Any,
    right: Any,
) -> bool:
    return abs(
        _numeric(
            left,
            label="Observed value",
        )
        - _numeric(
            right,
            label="Expected value",
        )
    ) <= 1e-9


def _case_expectations(
    value: Any,
) -> Dict[str, Any]:
    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Golden case expectations "
            "must be a dictionary."
        )

    required = {
        "signal",
        "adjustment",
        "live_total",
        "shadow_total",
    }

    missing = sorted(
        required
        - set(
            value.keys()
        )
    )

    if missing:
        raise ValueError(
            "Golden case expectations are "
            "missing required fields: "
            + ", ".join(
                missing
            )
        )

    return value


def evaluate_merit_corroboration_cases(
    *,
    cases: List[Dict[str, Any]],
    overlay_builder=(
        build_merit_corroboration_overlay
    ),
) -> Dict[str, Any]:
    if not isinstance(
        cases,
        list,
    ):
        raise ValueError(
            "Merit corroboration golden "
            "cases must be a list."
        )

    if not cases:
        raise ValueError(
            "Merit corroboration evaluation "
            "requires at least one golden case."
        )

    seen_case_ids = set()
    results = []
    invariance_groups = {}

    metrics = {
        "cases": 0,
        "expectations_passed": 0,
        "expectations_failed": 0,
        "safety_violations": 0,
        "live_score_changes": 0,
        "positive_adjustments": 0,
        "negative_adjustments": 0,
        "unverified_positive_adjustments": 0,
        "contested_positive_adjustments": 0,
        "invariance_groups_checked": 0,
        "invariance_failures": 0,
    }

    for case in cases:
        if not isinstance(
            case,
            dict,
        ):
            raise ValueError(
                "Each Merit corroboration "
                "golden case must be a "
                "dictionary."
            )

        if (
            _clean(
                case.get(
                    "version"
                )
            )
            != MERIT_CORROBORATION_GOLDEN_CASE_VERSION
        ):
            raise ValueError(
                "Unsupported Merit "
                "corroboration golden "
                "case version."
            )

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

        if not case_id:
            raise ValueError(
                "Golden case ID is required."
            )

        if case_id in seen_case_ids:
            raise ValueError(
                "Golden case IDs must "
                "be unique."
            )

        seen_case_ids.add(
            case_id
        )

        if not claim_id:
            raise ValueError(
                "Golden case claim ID "
                "is required."
            )

        legacy_score = case.get(
            "legacy_score"
        )

        corroboration_state = case.get(
            "corroboration_state"
        )

        if not isinstance(
            legacy_score,
            dict,
        ):
            raise ValueError(
                "Golden case legacy score "
                "must be a dictionary."
            )

        if not isinstance(
            corroboration_state,
            dict,
        ):
            raise ValueError(
                "Golden case corroboration "
                "state must be a dictionary."
            )

        expectations = (
            _case_expectations(
                case.get(
                    "expectations"
                )
            )
        )

        overlay = overlay_builder(
            legacy_score=(
                legacy_score
            ),
            corroboration_state=(
                corroboration_state
            ),
            claim_id=(
                claim_id
            ),
        )

        if not isinstance(
            overlay,
            dict,
        ):
            raise ValueError(
                "Merit overlay builder "
                "must return a dictionary."
            )

        if (
            _clean(
                overlay.get(
                    "version"
                )
            )
            != MERIT_CORROBORATION_OVERLAY_VERSION
        ):
            raise ValueError(
                "Unsupported Merit "
                "corroboration overlay "
                "version."
            )

        signal = _clean(
            overlay.get(
                "signal"
            )
        )

        proposed = overlay.get(
            "proposed",
            {},
        )

        live = overlay.get(
            "live",
            {},
        )

        if not isinstance(
            proposed,
            dict,
        ) or not isinstance(
            live,
            dict,
        ):
            raise ValueError(
                "Merit overlay result is "
                "missing score sections."
            )

        adjustment = _numeric(
            proposed.get(
                "adjustment"
            ),
            label=(
                "Proposed Merit adjustment"
            ),
        )

        shadow_total = _numeric(
            proposed.get(
                "shadow_total"
            ),
            label=(
                "Shadow Merit total"
            ),
        )

        live_total = _numeric(
            live.get(
                "total"
            ),
            label=(
                "Live Merit total"
            ),
        )

        legacy_total = _numeric(
            legacy_score.get(
                "total"
            ),
            label=(
                "Legacy Merit total"
            ),
        )

        corroboration_established = bool(
            overlay.get(
                "corroboration_established",
                False,
            )
        )

        contested = bool(
            overlay.get(
                "contested",
                False,
            )
        )

        safety = []

        if not _same_number(
            live_total,
            legacy_total,
        ):
            safety.append(
                "live_score_changed"
            )

            metrics[
                "live_score_changes"
            ] += 1

        if adjustment < 0:
            safety.append(
                "negative_adjustment"
            )

            metrics[
                "negative_adjustments"
            ] += 1

        if adjustment > 0:
            metrics[
                "positive_adjustments"
            ] += 1

            if (
                not corroboration_established
                or signal
                != "verified_corroboration"
            ):
                safety.append(
                    (
                        "positive_adjustment_"
                        "without_verified_"
                        "corroboration"
                    )
                )

                metrics[
                    "unverified_positive_"
                    "adjustments"
                ] += 1

            if contested:
                safety.append(
                    (
                        "positive_adjustment_"
                        "while_contested"
                    )
                )

                metrics[
                    "contested_positive_"
                    "adjustments"
                ] += 1

        checks = {
            "signal": (
                signal
                == _clean(
                    expectations.get(
                        "signal"
                    )
                )
            ),
            "adjustment": (
                _same_number(
                    adjustment,
                    expectations.get(
                        "adjustment"
                    ),
                )
            ),
            "live_total": (
                _same_number(
                    live_total,
                    expectations.get(
                        "live_total"
                    ),
                )
            ),
            "shadow_total": (
                _same_number(
                    shadow_total,
                    expectations.get(
                        "shadow_total"
                    ),
                )
            ),
        }

        expectations_passed = all(
            checks.values()
        )

        if expectations_passed:
            metrics[
                "expectations_passed"
            ] += 1
        else:
            metrics[
                "expectations_failed"
            ] += 1

        if safety:
            metrics[
                "safety_violations"
            ] += len(
                safety
            )

        invariance_group = _clean(
            case.get(
                "invariance_group"
            )
        )

        if invariance_group:
            invariance_groups.setdefault(
                invariance_group,
                [],
            ).append(
                {
                    "case_id": (
                        case_id
                    ),
                    "adjustment": (
                        adjustment
                    ),
                }
            )

        results.append(
            {
                "case_id": (
                    case_id
                ),
                "claim_id": (
                    claim_id
                ),
                "expectations_passed": (
                    expectations_passed
                ),
                "checks": (
                    checks
                ),
                "safety_violations": (
                    safety
                ),
                "observed": {
                    "signal": (
                        signal
                    ),
                    "adjustment": (
                        adjustment
                    ),
                    "live_total": (
                        live_total
                    ),
                    "shadow_total": (
                        shadow_total
                    ),
                },
                "expected": {
                    "signal": (
                        _clean(
                            expectations.get(
                                "signal"
                            )
                        )
                    ),
                    "adjustment": (
                        _numeric(
                            expectations.get(
                                "adjustment"
                            ),
                            label=(
                                "Expected adjustment"
                            ),
                        )
                    ),
                    "live_total": (
                        _numeric(
                            expectations.get(
                                "live_total"
                            ),
                            label=(
                                "Expected live total"
                            ),
                        )
                    ),
                    "shadow_total": (
                        _numeric(
                            expectations.get(
                                "shadow_total"
                            ),
                            label=(
                                "Expected shadow total"
                            ),
                        )
                    ),
                },
                "invariance_group": (
                    invariance_group
                ),
            }
        )

        metrics[
            "cases"
        ] += 1

    invariance_results = []

    for group_id in sorted(
        invariance_groups
    ):
        rows = invariance_groups[
            group_id
        ]

        if len(rows) < 2:
            continue

        metrics[
            "invariance_groups_checked"
        ] += 1

        first_adjustment = rows[0][
            "adjustment"
        ]

        passed = all(
            _same_number(
                row[
                    "adjustment"
                ],
                first_adjustment,
            )
            for row in rows[1:]
        )

        if not passed:
            metrics[
                "invariance_failures"
            ] += 1

        invariance_results.append(
            {
                "group_id": (
                    group_id
                ),
                "passed": (
                    passed
                ),
                "cases": (
                    rows
                ),
            }
        )

    passed = bool(
        metrics[
            "expectations_failed"
        ]
        == 0
        and metrics[
            "safety_violations"
        ]
        == 0
        and metrics[
            "invariance_failures"
        ]
        == 0
    )

    return {
        "version": (
            MERIT_CORROBORATION_EVALUATION_VERSION
        ),
        "status": (
            "passed"
            if passed
            else "failed"
        ),
        "metrics": (
            metrics
        ),
        "cases": (
            results
        ),
        "invariance_groups": (
            invariance_results
        ),
        "enablement": {
            "live_enablement_authorized": (
                False
            ),
            "recommendation": (
                "shadow_only"
            ),
            "reason": (
                "Passing this deterministic "
                "evaluation contract does not "
                "validate the proposed Merit "
                "weight on a curated real-world "
                "golden set."
            ),
        },
        "policy": {
            (
                "evaluation_does_not_enable_"
                "live_scoring"
            ): True,
            (
                "synthetic_policy_cases_are_"
                "not_real_world_validation"
            ): True,
            (
                "curated_golden_set_is_"
                "required_before_enablement"
            ): True,
            (
                "live_score_changes_are_"
                "safety_violations"
            ): True,
            (
                "unverified_positive_effects_"
                "are_safety_violations"
            ): True,
            (
                "contested_positive_effects_"
                "are_safety_violations"
            ): True,
            (
                "negative_corroboration_"
                "adjustments_are_not_allowed"
            ): True,
            (
                "invariance_groups_can_guard_"
                "against_source_count_scaling"
            ): True,
        },
    }
