import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.analysis.corroboration import (
    CLAIM_CORROBORATION_POLICY_VERSION,
)
from app.analysis.merit import (
    MERIT_CORROBORATION_OVERLAY_VERSION,
)
from app.analysis.merit_evaluation import (
    MERIT_CORROBORATION_EVALUATION_VERSION,
    MERIT_CORROBORATION_GOLDEN_CASE_VERSION,
    evaluate_merit_corroboration_cases,
)


class MeritCorroborationEvaluationTests(
    unittest.TestCase
):
    def legacy(
        self,
        total=60,
    ):
        return {
            "total": total,
            "components": {
                "corroboration": 4,
            },
        }

    def state(
        self,
        *,
        status,
        established=False,
        contested=False,
        independent=False,
        source_ids=None,
        claim_id="claim-1",
    ):
        return {
            "version": (
                CLAIM_CORROBORATION_POLICY_VERSION
            ),
            "claims": [
                {
                    "claim_id": (
                        claim_id
                    ),
                    "status": (
                        status
                    ),
                    "corroboration_established": (
                        established
                    ),
                    "contested": (
                        contested
                    ),
                    "contradiction_present": (
                        contested
                    ),
                    (
                        "independent_support_"
                        "established"
                    ): (
                        independent
                    ),
                    "supporting_source_ids": (
                        source_ids
                        if source_ids is not None
                        else [
                            "source-a",
                            "source-b",
                        ]
                    ),
                },
            ],
        }

    def case(
        self,
        *,
        case_id,
        state,
        signal,
        adjustment,
        live_total=60,
        shadow_total=60,
        invariance_group="",
        version=None,
    ):
        return {
            "version": (
                MERIT_CORROBORATION_GOLDEN_CASE_VERSION
                if version is None
                else version
            ),
            "id": (
                case_id
            ),
            "claim_id": (
                "claim-1"
            ),
            "legacy_score": (
                self.legacy(
                    live_total
                )
            ),
            "corroboration_state": (
                state
            ),
            "expectations": {
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
            "invariance_group": (
                invariance_group
            ),
        }

    def verified_case(
        self,
        *,
        case_id="verified",
        source_ids=None,
        invariance_group="",
    ):
        return self.case(
            case_id=(
                case_id
            ),
            state=(
                self.state(
                    status=(
                        "corroboration_established"
                    ),
                    established=True,
                    contested=False,
                    independent=True,
                    source_ids=(
                        source_ids
                    ),
                )
            ),
            signal=(
                "verified_corroboration"
            ),
            adjustment=6,
            live_total=60,
            shadow_total=66,
            invariance_group=(
                invariance_group
            ),
        )

    def test_verified_case_passes(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.verified_case(),
                ]
            )
        )

        self.assertEqual(
            result["version"],
            MERIT_CORROBORATION_EVALUATION_VERSION,
        )

        self.assertEqual(
            result["status"],
            "passed",
        )

        self.assertEqual(
            result["metrics"][
                "expectations_passed"
            ],
            1,
        )

    def test_mixed_policy_cases_pass(
        self,
    ):
        cases = [
            self.verified_case(),
            self.case(
                case_id="contested",
                state=(
                    self.state(
                        status=(
                            "corroboration_established"
                        ),
                        established=True,
                        contested=True,
                        independent=True,
                    )
                ),
                signal=(
                    "verified_corroboration_"
                    "contested"
                ),
                adjustment=0,
                shadow_total=60,
            ),
            self.case(
                case_id="unknown",
                state=(
                    self.state(
                        status=(
                            "support_independence_"
                            "unknown"
                        )
                    )
                ),
                signal=(
                    "support_independence_"
                    "unknown"
                ),
                adjustment=0,
                shadow_total=60,
            ),
            self.case(
                case_id="dependency",
                state=(
                    self.state(
                        status=(
                            "recorded_support_"
                            "dependency_present"
                        )
                    )
                ),
                signal=(
                    "support_dependency_present"
                ),
                adjustment=0,
                shadow_total=60,
            ),
            self.case(
                case_id="no-support",
                state=(
                    self.state(
                        status=(
                            "no_explicit_support"
                        ),
                        source_ids=[],
                    )
                ),
                signal=(
                    "no_verified_"
                    "corroboration_boost"
                ),
                adjustment=0,
                shadow_total=60,
            ),
        ]

        result = (
            evaluate_merit_corroboration_cases(
                cases=cases
            )
        )

        self.assertEqual(
            result["status"],
            "passed",
        )

        self.assertEqual(
            result["metrics"]["cases"],
            5,
        )

        self.assertEqual(
            result["metrics"][
                "safety_violations"
            ],
            0,
        )

    def test_expectation_mismatch_is_reported(
        self,
    ):
        case = self.verified_case()

        case[
            "expectations"
        ][
            "adjustment"
        ] = 5

        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    case,
                ]
            )
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertEqual(
            result["metrics"][
                "expectations_failed"
            ],
            1,
        )

        self.assertFalse(
            result["cases"][0][
                "checks"
            ][
                "adjustment"
            ]
        )

    def fake_overlay(
        self,
        *,
        adjustment,
        live_total=60,
        established=False,
        contested=False,
        signal=(
            "support_independence_unknown"
        ),
    ):
        return {
            "version": (
                MERIT_CORROBORATION_OVERLAY_VERSION
            ),
            "signal": (
                signal
            ),
            "corroboration_established": (
                established
            ),
            "contested": (
                contested
            ),
            "proposed": {
                "adjustment": (
                    adjustment
                ),
                "shadow_total": (
                    live_total
                    + adjustment
                ),
            },
            "live": {
                "total": (
                    live_total
                ),
            },
        }

    def base_unknown_case(
        self,
    ):
        return self.case(
            case_id="unknown",
            state=(
                self.state(
                    status=(
                        "support_independence_unknown"
                    )
                )
            ),
            signal=(
                "support_independence_unknown"
            ),
            adjustment=0,
            shadow_total=60,
        )

    def test_unverified_positive_effect_is_safety_violation(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.base_unknown_case(),
                ],
                overlay_builder=(
                    lambda **kwargs: (
                        self.fake_overlay(
                            adjustment=4,
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

        self.assertEqual(
            result["metrics"][
                "unverified_positive_adjustments"
            ],
            1,
        )

    def test_contested_positive_effect_is_safety_violation(
        self,
    ):
        case = self.case(
            case_id="contested",
            state=(
                self.state(
                    status=(
                        "corroboration_established"
                    ),
                    established=True,
                    contested=True,
                    independent=True,
                )
            ),
            signal=(
                "verified_corroboration_"
                "contested"
            ),
            adjustment=0,
            shadow_total=60,
        )

        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    case,
                ],
                overlay_builder=(
                    lambda **kwargs: (
                        self.fake_overlay(
                            adjustment=3,
                            established=True,
                            contested=True,
                            signal=(
                                "verified_corroboration"
                            ),
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            result["metrics"][
                "contested_positive_adjustments"
            ],
            1,
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_live_score_change_is_safety_violation(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.base_unknown_case(),
                ],
                overlay_builder=(
                    lambda **kwargs: (
                        self.fake_overlay(
                            adjustment=0,
                            live_total=61,
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            result["metrics"][
                "live_score_changes"
            ],
            1,
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_negative_adjustment_is_safety_violation(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.base_unknown_case(),
                ],
                overlay_builder=(
                    lambda **kwargs: (
                        self.fake_overlay(
                            adjustment=-2,
                        )
                    )
                ),
            )
        )

        self.assertEqual(
            result["metrics"][
                "negative_adjustments"
            ],
            1,
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_source_count_invariance_group_passes(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.verified_case(
                        case_id="two-sources",
                        source_ids=[
                            "a",
                            "b",
                        ],
                        invariance_group=(
                            "source-count"
                        ),
                    ),
                    self.verified_case(
                        case_id="six-sources",
                        source_ids=[
                            "a",
                            "b",
                            "c",
                            "d",
                            "e",
                            "f",
                        ],
                        invariance_group=(
                            "source-count"
                        ),
                    ),
                ]
            )
        )

        self.assertEqual(
            result["metrics"][
                "invariance_groups_checked"
            ],
            1,
        )

        self.assertEqual(
            result["metrics"][
                "invariance_failures"
            ],
            0,
        )

        self.assertEqual(
            result["status"],
            "passed",
        )

    def test_invariance_failure_is_reported(
        self,
    ):
        first = self.verified_case(
            case_id="first",
            invariance_group="group-1",
        )

        second = self.verified_case(
            case_id="second",
            invariance_group="group-1",
        )

        calls = {
            "count": 0,
        }

        def builder(
            **kwargs,
        ):
            calls["count"] += 1

            adjustment = (
                6
                if calls["count"] == 1
                else 7
            )

            return self.fake_overlay(
                adjustment=adjustment,
                established=True,
                contested=False,
                signal=(
                    "verified_corroboration"
                ),
            )

        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    first,
                    second,
                ],
                overlay_builder=builder,
            )
        )

        self.assertEqual(
            result["metrics"][
                "invariance_failures"
            ],
            1,
        )

        self.assertEqual(
            result["status"],
            "failed",
        )

    def test_duplicate_case_id_is_rejected(
        self,
    ):
        first = self.verified_case(
            case_id="duplicate",
        )

        second = self.verified_case(
            case_id="duplicate",
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be unique",
        ):
            (
                evaluate_merit_corroboration_cases(
                    cases=[
                        first,
                        second,
                    ]
                )
            )

    def test_wrong_case_version_is_rejected(
        self,
    ):
        case = self.verified_case()

        case["version"] = (
            "golden-case-v999"
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported",
        ):
            (
                evaluate_merit_corroboration_cases(
                    cases=[
                        case,
                    ]
                )
            )

    def test_empty_case_set_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "at least one",
        ):
            (
                evaluate_merit_corroboration_cases(
                    cases=[]
                )
            )

    def test_passing_evaluation_requires_machine_score_release_certificate(
        self,
    ):
        result = (
            evaluate_merit_corroboration_cases(
                cases=[
                    self.verified_case(),
                ]
            )
        )

        self.assertEqual(
            result["status"],
            "passed",
        )

        self.assertFalse(
            result[
                "enablement"
            ][
                "live_enablement_authorized"
            ]
        )

        self.assertEqual(
            result[
                "enablement"
            ][
                "recommendation"
            ],
            (
                "machine_score_release_"
                "certificate_required"
            ),
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "machine_verified_real_world_score_certificate_is_required_before_enablement"
            ]
        )

        self.assertNotIn(
            (
                "curated_golden_set_is_"
                "required_before_enablement"
            ),
            result[
                "policy"
            ],
        )


if __name__ == "__main__":
    unittest.main()
