from typing import Any, Dict

from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_EVALUATION_VERSION,
    evaluate_merit_corroboration_cases,
)
from app.analysis.merit_goldens import (
    validate_merit_corroboration_golden_dataset,
)


MERIT_LIVE_RELEASE_GATE_VERSION = (
    "merit-live-release-gate-v1"
)


MERIT_LIVE_MIN_APPROVED_REAL_WORLD_CASES = 5


MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE = (
    "verified_corroboration",
    "verified_corroboration_contested",
    "support_dependency_present",
    "support_independence_unknown",
    "no_verified_corroboration_boost",
)


def _clean(
    value: Any,
) -> str:
    return " ".join(
        str(value or "").split()
    )


def _evaluation_blockers(
    evaluation: Dict[str, Any],
):
    blockers = []

    if not isinstance(
        evaluation,
        dict,
    ):
        return [
            "evaluation_result_invalid"
        ]

    if (
        _clean(
            evaluation.get(
                "version"
            )
        )
        != MERIT_CORROBORATION_EVALUATION_VERSION
    ):
        blockers.append(
            "evaluation_version_invalid"
        )

        return blockers

    if (
        _clean(
            evaluation.get(
                "status"
            )
        ).lower()
        != "passed"
    ):
        blockers.append(
            "evaluation_not_passed"
        )

    metrics = evaluation.get(
        "metrics",
        {},
    )

    if not isinstance(
        metrics,
        dict,
    ):
        blockers.append(
            "evaluation_metrics_invalid"
        )

        return blockers

    safety_violations = int(
        metrics.get(
            "safety_violations",
            0,
        )
        or 0
    )

    expectation_failures = int(
        metrics.get(
            "expectations_failed",
            0,
        )
        or 0
    )

    invariance_failures = int(
        metrics.get(
            "invariance_failures",
            0,
        )
        or 0
    )

    if safety_violations:
        blockers.append(
            "evaluation_safety_violations"
        )

    if expectation_failures:
        blockers.append(
            "evaluation_expectation_failures"
        )

    if invariance_failures:
        blockers.append(
            "evaluation_invariance_failures"
        )

    return blockers


def build_merit_live_release_gate(
    *,
    dataset: Dict[str, Any],
    request_live: bool = False,
    minimum_approved_cases: int = (
        MERIT_LIVE_MIN_APPROVED_REAL_WORLD_CASES
    ),
    evaluator=(
        evaluate_merit_corroboration_cases
    ),
) -> Dict[str, Any]:
    if (
        isinstance(
            minimum_approved_cases,
            bool,
        )
        or not isinstance(
            minimum_approved_cases,
            int,
        )
        or minimum_approved_cases < 1
    ):
        raise ValueError(
            "Minimum approved real-world "
            "case count must be a positive "
            "integer."
        )

    validated = (
        validate_merit_corroboration_golden_dataset(
            dataset
        )
    )

    approved_cases = list(
        validated.get(
            "approved_real_world_cases",
            [],
        )
    )

    approved_count = len(
        approved_cases
    )

    approved_signals = sorted(
        {
            _clean(
                case.get(
                    "expectations",
                    {},
                ).get(
                    "signal"
                )
            )
            for case in approved_cases
            if (
                isinstance(
                    case,
                    dict,
                )
                and isinstance(
                    case.get(
                        "expectations"
                    ),
                    dict,
                )
                and _clean(
                    case[
                        "expectations"
                    ].get(
                        "signal"
                    )
                )
            )
        }
    )

    required_signals = set(
        MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE
    )

    missing_signals = sorted(
        required_signals
        - set(
            approved_signals
        )
    )

    blockers = []

    if (
        approved_count
        < minimum_approved_cases
    ):
        blockers.append(
            "insufficient_approved_real_world_cases"
        )

    if missing_signals:
        blockers.append(
            "required_signal_coverage_missing"
        )

    evaluation = None

    # Only evaluate when curation has already
    # satisfied the real-world quantity and
    # safety-state coverage requirements.
    if not blockers:
        try:
            evaluation = evaluator(
                cases=(
                    approved_cases
                )
            )

        except Exception as exc:
            blockers.append(
                "evaluation_error:"
                + type(exc).__name__
            )

        else:
            blockers.extend(
                _evaluation_blockers(
                    evaluation
                )
            )

    live_authorized = bool(
        request_live
        and not blockers
        and evaluation is not None
    )

    # A production release remains safe while
    # live evidence-aware Merit is NOT requested.
    #
    # If someone explicitly requests live Merit,
    # every gate above must pass.
    release_authorized = bool(
        not request_live
        or live_authorized
    )

    if live_authorized:
        mode = "live_authorized"
        reason = (
            "Approved real-world golden "
            "coverage and deterministic "
            "evaluation satisfy the live "
            "Merit release gate."
        )

    elif request_live:
        mode = "live_blocked"
        reason = (
            "Live evidence-aware Merit was "
            "requested but the release gate "
            "is not satisfied."
        )

    else:
        mode = "shadow_safe"
        reason = (
            "Evidence-aware Merit remains "
            "non-live, so the release may "
            "proceed without changing the "
            "user-facing legacy Merit score."
        )

    counts = validated.get(
        "counts",
        {},
    )

    if not isinstance(
        counts,
        dict,
    ):
        counts = {}

    return {
        "version": (
            MERIT_LIVE_RELEASE_GATE_VERSION
        ),
        "status": mode,
        "request_live": bool(
            request_live
        ),
        "release_authorized": (
            release_authorized
        ),
        "live_merit_authorized": (
            live_authorized
        ),
        "minimum_approved_real_world_cases": (
            minimum_approved_cases
        ),
        "approved_real_world_cases": (
            approved_count
        ),
        "required_signal_coverage": list(
            MERIT_LIVE_REQUIRED_SIGNAL_COVERAGE
        ),
        "approved_signal_coverage": (
            approved_signals
        ),
        "missing_signal_coverage": (
            missing_signals
        ),
        "blockers": blockers,
        "reason": reason,
        "dataset": {
            "status": (
                validated.get(
                    "status"
                )
            ),
            "evaluation_ready": bool(
                validated.get(
                    "evaluation_ready",
                    False,
                )
            ),
            "counts": dict(
                counts
            ),
        },
        "evaluation": (
            evaluation
        ),
        "policy": {
            (
                "draft_cases_never_"
                "authorize_live_merit"
            ): True,
            (
                "synthetic_cases_never_"
                "count_as_real_world_"
                "validation"
            ): True,
            (
                "human_reviewed_real_world_"
                "cases_are_required"
            ): True,
            (
                "positive_and_safety_states_"
                "require_coverage"
            ): True,
            (
                "deterministic_evaluation_"
                "must_pass"
            ): True,
            (
                "safety_violations_block_"
                "live_release"
            ): True,
            (
                "shadow_release_can_proceed_"
                "without_live_merit"
            ): True,
        },
    }
