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
    LOCAL_CONFIDENCE_PROFILE_VERSION,
)

from app.analysis.shadow_calibration import (
    SHADOW_CALIBRATION_VERSION,
    build_shadow_calibrated_adjudication,
)


class ShadowCalibrationTests(
    unittest.TestCase
):
    def judgment(
        self,
        *,
        judgment_id,
        field="authority_class",
        value="direct",
        confidence=0.75,
        evaluator_id="semantic-v1",
        evaluator_family="semantic_model",
        basis_class="model_inference",
        training_eligible=False,
    ):
        return {
            "id": judgment_id,
            "field": field,
            "value": value,
            "confidence": confidence,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "basis_class": (
                basis_class
            ),
            "evidence_ids": [
                (
                    f"{judgment_id}-evidence"
                )
            ],
            "training_eligible": (
                training_eligible
            ),
        }

    def evaluator_run(
        self,
        *,
        run_id,
        evaluator_id,
        evaluator_family,
        confidence,
        value="direct",
        derivation_mode="model_assisted",
        basis_class="model_inference",
        training_eligible=False,
    ):
        return {
            "run_id": run_id,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "derivation_mode": (
                derivation_mode
            ),
            "judgments": [
                self.judgment(
                    judgment_id=(
                        f"{run_id}-judgment"
                    ),
                    value=value,
                    confidence=confidence,
                    evaluator_id=(
                        evaluator_id
                    ),
                    evaluator_family=(
                        evaluator_family
                    ),
                    basis_class=(
                        basis_class
                    ),
                    training_eligible=(
                        training_eligible
                    ),
                )
            ],
        }

    def profile(
        self,
        *,
        profile_id="profile-1",
        family="semantic_model",
        bucket="0.60-0.79",
        target=0.90,
        eligible=True,
        live=False,
        field="authority_class",
    ):
        claims = [
            "claim-a",
            "claim-b",
            "claim-c",
            "claim-d",
            "claim-e",
        ]

        return {
            "version": (
                LOCAL_CONFIDENCE_PROFILE_VERSION
            ),
            "id": profile_id,
            "scope_id": (
                f"scope-{profile_id}"
            ),
            "field": field,
            "evaluator_family": (
                family
            ),
            "confidence_bucket": (
                bucket
            ),
            "distinct_claim_count": 5,
            "supporting_claim_ids": (
                claims
            ),
            "status": (
                "shadow_ready"
                if eligible
                else "insufficient_data"
            ),
            "eligible_for_shadow_adjustment": (
                eligible
            ),
            "shadow_target_confidence": (
                target
                if eligible
                else None
            ),
            "eligible_for_live_use": (
                live
            ),
        }

    def calibration(
        self,
        profiles,
    ):
        return {
            "version": (
                LOCAL_CONFIDENCE_CALIBRATION_VERSION
            ),
            "profiles": profiles,
        }

    def test_version_and_shadow_guards(
        self,
    ):
        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[],
                calibration=(
                    self.calibration([])
                ),
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            SHADOW_CALIBRATION_VERSION,
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "shadow_only"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_change_live_merit"
            ]
        )

    def test_no_profile_leaves_baseline_unchanged(
        self,
    ):
        runs = [
            self.evaluator_run(
                run_id="model",
                evaluator_id="semantic-v1",
                evaluator_family=(
                    "semantic_model"
                ),
                confidence=0.75,
            )
        ]

        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=runs,
                calibration=(
                    self.calibration([])
                ),
            )
        )

        self.assertEqual(
            result[
                "baseline_adjudication"
            ],
            result[
                "shadow_adjudication"
            ],
        )

        self.assertEqual(
            result[
                "adjustments"
            ],
            [],
        )

    def test_matching_shadow_profile_adjusts_confidence(
        self,
    ):
        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    self.evaluator_run(
                        run_id="model",
                        evaluator_id=(
                            "semantic-v1"
                        ),
                        evaluator_family=(
                            "semantic_model"
                        ),
                        confidence=0.75,
                    )
                ],
                calibration=(
                    self.calibration(
                        [
                            self.profile()
                        ]
                    )
                ),
            )
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "adjusted_judgment_count"
            ],
            1,
        )

        adjustment = (
            result[
                "adjustments"
            ][0]
        )

        self.assertEqual(
            adjustment[
                "baseline_confidence"
            ],
            0.75,
        )

        self.assertEqual(
            adjustment[
                "shadow_confidence"
            ],
            0.90,
        )

        self.assertEqual(
            adjustment[
                "baseline_value"
            ],
            "direct",
        )

        self.assertEqual(
            adjustment[
                "shadow_value"
            ],
            "direct",
        )

    def test_insufficient_profile_is_ignored(
        self,
    ):
        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    self.evaluator_run(
                        run_id="model",
                        evaluator_id=(
                            "semantic-v1"
                        ),
                        evaluator_family=(
                            "semantic_model"
                        ),
                        confidence=0.75,
                    )
                ],
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                eligible=False
                            )
                        ]
                    )
                ),
            )
        )

        self.assertEqual(
            result[
                "adjustments"
            ],
            [],
        )

    def test_trusted_reference_run_is_never_adjusted(
        self,
    ):
        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    self.evaluator_run(
                        run_id="trusted",
                        evaluator_id=(
                            "authority-record-v1"
                        ),
                        evaluator_family=(
                            "authority_record"
                        ),
                        confidence=0.99,
                        derivation_mode=(
                            "machine_verified"
                        ),
                        basis_class=(
                            "direct_authority_record"
                        ),
                        training_eligible=True,
                    )
                ],
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                family=(
                                    "authority_record"
                                ),
                                bucket=(
                                    "0.90-1.00"
                                ),
                                target=0.50,
                            )
                        ]
                    )
                ),
            )
        )

        self.assertEqual(
            result[
                "adjustments"
            ],
            [],
        )

        self.assertEqual(
            result[
                "baseline_adjudication"
            ],
            result[
                "shadow_adjudication"
            ],
        )

    def test_profile_bucket_is_local(
        self,
    ):
        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    self.evaluator_run(
                        run_id="model",
                        evaluator_id=(
                            "semantic-v1"
                        ),
                        evaluator_family=(
                            "semantic_model"
                        ),
                        confidence=0.82,
                    )
                ],
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                bucket=(
                                    "0.60-0.79"
                                )
                            )
                        ]
                    )
                ),
            )
        )

        self.assertEqual(
            result[
                "adjustments"
            ],
            [],
        )

    def test_shadow_calibration_can_change_unresolved_to_silver(
        self,
    ):
        runs = [
            self.evaluator_run(
                run_id="semantic",
                evaluator_id="semantic-v1",
                evaluator_family=(
                    "semantic_model"
                ),
                confidence=0.75,
            ),
            self.evaluator_run(
                run_id="heuristic",
                evaluator_id="heuristic-v1",
                evaluator_family=(
                    "heuristic_family"
                ),
                confidence=0.90,
                basis_class="heuristic",
            ),
        ]

        result = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=runs,
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                family=(
                                    "semantic_model"
                                ),
                                target=0.90,
                            )
                        ]
                    )
                ),
            )
        )

        baseline = (
            result[
                "baseline_adjudication"
            ][
                "fields"
            ][
                "authority_class"
            ][
                "automatic"
            ]
        )

        shadow = (
            result[
                "shadow_adjudication"
            ][
                "fields"
            ][
                "authority_class"
            ][
                "automatic"
            ]
        )

        self.assertEqual(
            baseline[
                "tier"
            ],
            "unresolved",
        )

        self.assertEqual(
            shadow[
                "tier"
            ],
            "auto_silver",
        )

        self.assertFalse(
            result[
                "shadow_adjudication"
            ][
                "fields"
            ][
                "authority_class"
            ][
                "reference_gate"
            ][
                "training_reference_allowed"
            ]
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "decision_changed_field_count"
            ],
            1,
        )

    def test_live_enabled_profile_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "forbidden",
        ):
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[],
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                live=True
                            )
                        ]
                    )
                ),
            )

    def test_duplicate_profile_scope_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "duplicate profile scope",
        ):
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=[],
                calibration=(
                    self.calibration(
                        [
                            self.profile(
                                profile_id="one"
                            ),
                            self.profile(
                                profile_id="two"
                            ),
                        ]
                    )
                ),
            )

    def test_input_runs_are_not_mutated(
        self,
    ):
        runs = [
            self.evaluator_run(
                run_id="model",
                evaluator_id="semantic-v1",
                evaluator_family=(
                    "semantic_model"
                ),
                confidence=0.75,
            )
        ]

        original = copy.deepcopy(
            runs
        )

        build_shadow_calibrated_adjudication(
            claim_id="claim-1",
            evaluator_runs=runs,
            calibration=(
                self.calibration(
                    [
                        self.profile()
                    ]
                )
            ),
        )

        self.assertEqual(
            runs,
            original,
        )

    def test_profile_order_is_deterministic(
        self,
    ):
        runs = [
            self.evaluator_run(
                run_id="one",
                evaluator_id="one-v1",
                evaluator_family="family_one",
                confidence=0.75,
            ),
            self.evaluator_run(
                run_id="two",
                evaluator_id="two-v1",
                evaluator_family="family_two",
                confidence=0.82,
            ),
        ]

        first = self.profile(
            profile_id="first",
            family="family_one",
            bucket="0.60-0.79",
            target=0.88,
        )

        second = self.profile(
            profile_id="second",
            family="family_two",
            bucket="0.80-0.89",
            target=0.91,
        )

        forward = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=runs,
                calibration=(
                    self.calibration(
                        [
                            first,
                            second,
                        ]
                    )
                ),
            )
        )

        reverse = (
            build_shadow_calibrated_adjudication(
                claim_id="claim-1",
                evaluator_runs=runs,
                calibration=(
                    self.calibration(
                        [
                            second,
                            first,
                        ]
                    )
                ),
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )


if __name__ == "__main__":
    unittest.main()
