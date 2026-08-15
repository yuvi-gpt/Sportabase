import copy
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.analysis.confidence_calibration import (
    LOCAL_CONFIDENCE_CALIBRATION_VERSION,
    LOCAL_CONFIDENCE_CASE_VERSION,
    LOCAL_CONFIDENCE_PROFILE_VERSION,
)

from app.analysis.corpus_expansion import (
    build_validation_corpus_expansion,
)

from app.analysis.merit_release import (
    MERIT_LIVE_RELEASE_GATE_VERSION,
    MERIT_LIVE_REQUIRED_FIELD_COVERAGE,
    build_merit_live_release_gate,
)

from app.analysis.shadow_calibration import (
    SHADOW_CALIBRATION_VERSION,
)

from app.analysis.trusted_validation import (
    TRUSTED_HOLDOUT_CASE_VERSION,
)


class MeritLiveReleaseGateTests(
    unittest.TestCase
):
    def calibration(
        self,
    ):
        training_claims = [
            (
                "training-"
                + str(index)
            )
            for index in range(
                1,
                6,
            )
        ]

        cases = [
            {
                "version": (
                    LOCAL_CONFIDENCE_CASE_VERSION
                ),
                "id": (
                    "training-case-"
                    + str(index)
                ),
                "claim_id": claim_id,
            }
            for index, claim_id
            in enumerate(
                training_claims,
                start=1,
            )
        ]

        return {
            "version": (
                LOCAL_CONFIDENCE_CALIBRATION_VERSION
            ),
            "cases": cases,
            "profiles": [
                {
                    "version": (
                        LOCAL_CONFIDENCE_PROFILE_VERSION
                    ),
                    "id": "profile-1",
                    "status": (
                        "shadow_ready"
                    ),
                    "eligible_for_shadow_adjustment": (
                        True
                    ),
                    "eligible_for_live_use": (
                        False
                    ),
                    "distinct_claim_count": 5,
                    "supporting_claim_ids": (
                        training_claims
                    ),
                }
            ],
        }

    def holdout_cases(
        self,
    ):
        fields = list(
            MERIT_LIVE_REQUIRED_FIELD_COVERAGE
        )

        rows = []

        for index, field in enumerate(
            fields,
            start=1,
        ):
            claim_number = min(
                index,
                5,
            )

            rows.append(
                {
                    "version": (
                        TRUSTED_HOLDOUT_CASE_VERSION
                    ),
                    "id": (
                        "holdout-case-"
                        + str(index)
                    ),
                    "claim_id": (
                        "holdout-"
                        + str(
                            claim_number
                        )
                    ),
                    "field": field,
                    "verified_value": (
                        "verified-"
                        + field
                    ),
                }
            )

        return rows

    def shadow_results(
        self,
        *,
        holdout_cases=None,
    ):
        cases = (
            holdout_cases
            or self.holdout_cases()
        )

        by_claim = {}

        for case in cases:
            by_claim.setdefault(
                case[
                    "claim_id"
                ],
                [],
            ).append(
                case
            )

        results = []

        for claim_id in sorted(
            by_claim
        ):
            comparisons = []
            adjustments = []

            for case in by_claim[
                claim_id
            ]:
                value = case[
                    "verified_value"
                ]

                comparisons.append(
                    {
                        "field": (
                            case[
                                "field"
                            ]
                        ),
                        "baseline": {
                            "tier": "auto_silver",
                            "value": value,
                            "confidence": 0.60,
                            "conflicting_values": [],
                            "training_reference_allowed": False,
                            "supporting_judgment_ids": [],
                            "supporting_evaluator_families": [],
                        },
                        "shadow": {
                            "tier": "auto_silver",
                            "value": value,
                            "confidence": 0.80,
                            "conflicting_values": [],
                            "training_reference_allowed": False,
                            "supporting_judgment_ids": [],
                            "supporting_evaluator_families": [],
                        },
                    }
                )

                adjustments.append(
                    {
                        "judgment_id": (
                            "adjustment-"
                            + case[
                                "id"
                            ]
                        ),
                        "field": (
                            case[
                                "field"
                            ]
                        ),
                        "evaluator_id": "test-model-v1",
                        "evaluator_family": "test_model",
                        "profile_id": "profile-1",
                        "scope_id": "scope-profile-1",
                        "confidence_bucket": "0.60-0.79",
                        "baseline_value": value,
                        "shadow_value": value,
                        "baseline_confidence": 0.60,
                        "shadow_confidence": 0.80,
                        "delta": 0.20,
                    }
                )

            results.append(
                {
                    "version": (
                        SHADOW_CALIBRATION_VERSION
                    ),
                    "claim_id": claim_id,
                    "comparisons": comparisons,
                    "adjustments": adjustments,
                    "policy": {
                        "shadow_only": True,
                        "baseline_is_preserved": True,
                        "does_not_change_live_merit": True,
                    },
                }
            )

        return results


    def corpus(
        self,
    ):
        sports = [
            "american_football",
            "baseball",
            "basketball",
            "cricket",
            "football",
            "ice_hockey",
            "motorsport",
            "tennis",
        ]

        records = [
            {
                "id": (
                    "record-"
                    + sport
                ),
                "origin_type": (
                    "external_dataset"
                ),
                "data_family": (
                    "structured_sports_data"
                ),
                "dataset_name": (
                    sport
                    + "-validation"
                ),
                "external_record_id": (
                    "one"
                ),
                "sport_key": sport,
                "payload_hash": (
                    "hash-"
                    + sport
                ),
                "ingested_at": (
                    "2026-08-15T06:00:00+00:00"
                ),
            }
            for sport in sports
        ]

        return (
            build_validation_corpus_expansion(
                records=records,
                target_records_per_sport=1,
            )
        )

    def complete_inputs(
        self,
    ):
        holdout = (
            self.holdout_cases()
        )

        return {
            "calibration": (
                self.calibration()
            ),
            "holdout_cases": (
                holdout
            ),
            "shadow_results": (
                self.shadow_results(
                    holdout_cases=(
                        holdout
                    )
                )
            ),
            "corpus_expansion": (
                self.corpus()
            ),
        }

    def test_version_and_automatic_policy(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                request_live=False,
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                MERIT_LIVE_RELEASE_GATE_VERSION
            ),
        )

        self.assertEqual(
            (
                MERIT_LIVE_RELEASE_GATE_VERSION
            ),
            "merit-live-release-gate-v4",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "automated_validation_only"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "human_review_required"
            ]
        )

    def test_shadow_safe_without_release_inputs(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                request_live=False,
            )
        )

        self.assertTrue(
            result[
                "release_authorized"
            ]
        )

        self.assertFalse(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertEqual(
            result[
                "status"
            ],
            "shadow_safe",
        )

    def test_live_request_requires_automatic_inputs(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                request_live=True,
            )
        )

        self.assertFalse(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertIn(
            "calibration_missing",
            result[
                "blockers"
            ],
        )

        self.assertIn(
            "holdout_validation_missing",
            result[
                "blockers"
            ],
        )

        self.assertIn(
            "shadow_results_missing",
            result[
                "blockers"
            ],
        )

        self.assertIn(
            "corpus_expansion_missing",
            result[
                "blockers"
            ],
        )

    def test_insufficient_calibration_support_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        inputs[
            "calibration"
        ][
            "profiles"
        ][0][
            "distinct_claim_count"
        ] = 4

        inputs[
            "calibration"
        ][
            "profiles"
        ][0][
            "supporting_claim_ids"
        ] = [
            "training-1",
            "training-2",
            "training-3",
            "training-4",
        ]

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "calibration_profile_support_insufficient",
            result[
                "blockers"
            ],
        )

    def test_holdout_cannot_reuse_calibration_claim(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        inputs[
            "holdout_cases"
        ][0][
            "claim_id"
        ] = "training-1"

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "holdout_claim_reused_for_calibration",
            result[
                "blockers"
            ],
        )

    def test_too_few_holdout_claims_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        for case in inputs[
            "holdout_cases"
        ]:
            case[
                "claim_id"
            ] = "holdout-1"

        inputs[
            "shadow_results"
        ] = (
            self.shadow_results(
                holdout_cases=(
                    inputs[
                        "holdout_cases"
                    ]
                )
            )
        )

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "insufficient_holdout_claims",
            result[
                "blockers"
            ],
        )

    def test_all_adjudication_fields_require_holdout_coverage(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        removed = inputs[
            "holdout_cases"
        ].pop()

        inputs[
            "shadow_results"
        ] = (
            self.shadow_results(
                holdout_cases=(
                    inputs[
                        "holdout_cases"
                    ]
                )
            )
        )

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "required_field_coverage_missing",
            result[
                "blockers"
            ],
        )

        self.assertIn(
            removed[
                "field"
            ],
            result[
                "missing_field_coverage"
            ],
        )

    def test_incomplete_corpus_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        first = inputs[
            "corpus_expansion"
        ][
            "coverage"
        ][0]

        first[
            "coverage_status"
        ] = "under_covered"

        first[
            "deficit"
        ] = 1

        inputs[
            "corpus_expansion"
        ][
            "expansion_queue"
        ] = [
            {
                "sport_key": (
                    first[
                        "sport_key"
                    ]
                )
            }
        ]

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "corpus_coverage_incomplete",
            result[
                "blockers"
            ],
        )

        self.assertIn(
            "corpus_expansion_still_pending",
            result[
                "blockers"
            ],
        )

    def test_invalid_shadow_version_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        inputs[
            "shadow_results"
        ][0][
            "version"
        ] = "wrong"

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "shadow_result_version_invalid",
            result[
                "blockers"
            ],
        )

    def test_shadow_decision_regression_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        comparison = inputs[
            "shadow_results"
        ][0][
            "comparisons"
        ][0]

        comparison[
            "shadow"
        ][
            "value"
        ] = "wrong-value"

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "shadow_decision_regression",
            result[
                "blockers"
            ],
        )

    def test_shadow_reference_promotion_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        comparison = inputs[
            "shadow_results"
        ][0][
            "comparisons"
        ][0]

        comparison[
            "shadow"
        ][
            "training_reference_allowed"
        ] = True

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "shadow_reference_gate_promotion",
            result[
                "blockers"
            ],
        )

    def test_untrusted_shadow_gold_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        comparison = inputs[
            "shadow_results"
        ][0][
            "comparisons"
        ][0]

        comparison[
            "shadow"
        ][
            "tier"
        ] = "auto_gold"

        comparison[
            "shadow"
        ][
            "training_reference_allowed"
        ] = False

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "shadow_untrusted_auto_gold",
            result[
                "blockers"
            ],
        )

    def test_no_measurable_shadow_improvement_blocks_live(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        for result in inputs[
            "shadow_results"
        ]:
            for adjustment in result[
                "adjustments"
            ]:
                adjustment[
                    "shadow_confidence"
                ] = adjustment[
                    "baseline_confidence"
                ]

                adjustment[
                    "delta"
                ] = 0.0

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertIn(
            "no_measurable_shadow_improvement",
            result[
                "blockers"
            ],
        )


    def test_unresolved_adjudication_does_not_fake_calibration_failure(
        self,
    ):
        inputs = (
            self.complete_inputs()
        )

        for result in inputs[
            "shadow_results"
        ]:
            for comparison in result[
                "comparisons"
            ]:
                comparison[
                    "baseline"
                ][
                    "tier"
                ] = "unresolved"

                comparison[
                    "baseline"
                ][
                    "value"
                ] = ""

                comparison[
                    "baseline"
                ][
                    "confidence"
                ] = 0.0

                comparison[
                    "shadow"
                ][
                    "tier"
                ] = "unresolved"

                comparison[
                    "shadow"
                ][
                    "value"
                ] = ""

                comparison[
                    "shadow"
                ][
                    "confidence"
                ] = 0.0

        result = (
            build_merit_live_release_gate(
                request_live=True,
                **inputs,
            )
        )

        self.assertEqual(
            result[
                "blockers"
            ],
            [],
        )

        self.assertTrue(
            result[
                "live_merit_authorized"
            ]
        )

        metrics = result[
            "shadow_metrics"
        ]

        self.assertEqual(
            metrics[
                "confidence_metric_scope"
            ],
            "adjusted_judgments",
        )

        self.assertEqual(
            metrics[
                "baseline_correct_count"
            ],
            len(
                inputs[
                    "holdout_cases"
                ]
            ),
        )

        self.assertEqual(
            metrics[
                "decision_regression_count"
            ],
            0,
        )

    def test_complete_automated_validation_can_authorize_gate(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                request_live=True,
                **self.complete_inputs(),
            )
        )

        self.assertEqual(
            result[
                "blockers"
            ],
            [],
        )

        self.assertTrue(
            result[
                "release_authorized"
            ]
        )

        self.assertTrue(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertEqual(
            result[
                "status"
            ],
            "live_authorized",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "gate_does_not_activate_product"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "production_wiring_required_separately"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_modify_merit_score"
            ]
        )

    def test_legacy_human_gate_inputs_cannot_authorize_live(
        self,
    ):
        result = (
            build_merit_live_release_gate(
                request_live=True,
                dataset={
                    "legacy": True
                },
                minimum_approved_cases=5,
                evaluator=lambda **kwargs: {
                    "status": "passed"
                },
            )
        )

        self.assertTrue(
            result[
                "legacy_input_detected"
            ]
        )

        self.assertFalse(
            result[
                "live_merit_authorized"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "legacy_human_curated_gate_is_not_authoritative"
            ]
        )


if __name__ == "__main__":
    unittest.main()
