import copy
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


from app.analysis.adjudication_state import (
    build_adjudication_state_revision,
)

from app.analysis.confidence_calibration import (
    LOCAL_CONFIDENCE_CALIBRATION_VERSION,
    build_local_confidence_calibration,
    build_local_confidence_cases,
)

from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)


class LocalConfidenceCalibrationTests(
    unittest.TestCase
):
    def evaluator_run(
        self,
        *,
        claim_id,
        value,
        confidence=0.95,
        trusted=False,
        family="semantic_model",
    ):
        if trusted:
            evaluator_id = (
                "authority-record-v1"
            )
            family = (
                "authority_record"
            )
            derivation_mode = (
                "machine_verified"
            )
            basis = (
                "direct_authority_record"
            )
            training = True
            suffix = "trusted"
        else:
            evaluator_id = (
                f"{family}-v1"
            )
            derivation_mode = (
                "model_assisted"
            )
            basis = (
                "direct_authority_record"
            )
            training = False
            suffix = family

        return {
            "run_id": (
                f"{claim_id}-{suffix}-run"
            ),
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": family,
            "derivation_mode": (
                derivation_mode
            ),
            "judgments": [
                {
                    "id": (
                        f"{claim_id}-{suffix}-judgment"
                    ),
                    "field": (
                        "authority_class"
                    ),
                    "value": value,
                    "confidence": confidence,
                    "evaluator_id": (
                        evaluator_id
                    ),
                    "evaluator_family": (
                        family
                    ),
                    "basis_class": basis,
                    "evidence_ids": [
                        (
                            f"{claim_id}-{suffix}-evidence"
                        )
                    ],
                    "training_eligible": (
                        training
                    ),
                }
            ],
        }

    def adjudication(
        self,
        *,
        claim_id,
        value=None,
        confidence=0.95,
        trusted=False,
        family="semantic_model",
    ):
        runs = []

        if value is not None:
            runs = [
                self.evaluator_run(
                    claim_id=claim_id,
                    value=value,
                    confidence=confidence,
                    trusted=trusted,
                    family=family,
                )
            ]

        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=runs,
            )
        )

    def pair(
        self,
        *,
        claim_id="claim-1",
        previous_value="direct",
        verified_value="direct",
        confidence=0.95,
        previous_empty=False,
        trusted_current=True,
        family="semantic_model",
    ):
        previous_adjudication = (
            self.adjudication(
                claim_id=claim_id,
            )
            if previous_empty
            else self.adjudication(
                claim_id=claim_id,
                value=previous_value,
                confidence=confidence,
                trusted=False,
                family=family,
            )
        )

        current_adjudication = (
            self.adjudication(
                claim_id=claim_id,
                value=verified_value,
                confidence=0.99,
                trusted=trusted_current,
                family=family,
            )
        )

        previous = (
            build_adjudication_state_revision(
                adjudication=(
                    previous_adjudication
                ),
                as_of=(
                    "2026-08-15T05:00:00Z"
                ),
                trigger_type=(
                    "initial_evaluation"
                ),
            )
        )

        current = (
            build_adjudication_state_revision(
                adjudication=(
                    current_adjudication
                ),
                as_of=(
                    "2026-08-15T06:00:00Z"
                ),
                trigger_type=(
                    "evaluator_refresh"
                ),
                previous_revision=previous,
            )
        )

        return (
            previous,
            current,
        )

    def cases(self, **kwargs):
        previous, current = self.pair(
            **kwargs
        )

        return (
            build_local_confidence_cases(
                previous_revision=previous,
                current_revision=current,
            )
        )

    def test_confirmed_case_is_extracted(
        self,
    ):
        cases = self.cases(
            previous_value="direct",
            verified_value="direct",
        )

        self.assertEqual(
            len(cases),
            1,
        )

        self.assertEqual(
            cases[0]["outcome"],
            "confirmed",
        )

    def test_corrected_case_is_extracted(
        self,
    ):
        cases = self.cases(
            previous_value="indirect",
            verified_value="direct",
        )

        self.assertEqual(
            len(cases),
            1,
        )

        self.assertEqual(
            cases[0]["outcome"],
            "corrected",
        )

    def test_unresolved_previous_state_is_not_calibration_case(
        self,
    ):
        cases = self.cases(
            previous_empty=True,
        )

        self.assertEqual(
            cases,
            [],
        )

    def test_untrusted_current_state_cannot_calibrate(
        self,
    ):
        cases = self.cases(
            previous_value="indirect",
            verified_value="direct",
            trusted_current=False,
        )

        self.assertEqual(
            cases,
            [],
        )

    def test_profile_measures_accuracy_gap_and_brier(
        self,
    ):
        cases = []

        cases += self.cases(
            claim_id="claim-1",
            previous_value="direct",
            verified_value="direct",
            confidence=0.90,
        )

        cases += self.cases(
            claim_id="claim-2",
            previous_value="indirect",
            verified_value="direct",
            confidence=0.90,
        )

        result = (
            build_local_confidence_calibration(
                cases=cases
            )
        )

        profile = result[
            "profiles"
        ][0]

        self.assertEqual(
            profile[
                "observed_accuracy"
            ],
            0.5,
        )

        self.assertEqual(
            profile[
                "mean_reported_confidence"
            ],
            0.9,
        )

        self.assertEqual(
            profile[
                "calibration_gap"
            ],
            -0.4,
        )

        self.assertEqual(
            profile[
                "brier_score"
            ],
            0.41,
        )

    def test_confidence_buckets_are_local(
        self,
    ):
        cases = []

        cases += self.cases(
            claim_id="claim-1",
            confidence=0.75,
        )

        cases += self.cases(
            claim_id="claim-2",
            confidence=0.95,
        )

        result = (
            build_local_confidence_calibration(
                cases=cases
            )
        )

        buckets = {
            profile[
                "confidence_bucket"
            ]
            for profile
            in result[
                "profiles"
            ]
        }

        self.assertEqual(
            buckets,
            {
                "0.60-0.79",
                "0.90-1.00",
            },
        )

    def test_small_sample_is_not_shadow_ready(
        self,
    ):
        result = (
            build_local_confidence_calibration(
                cases=self.cases()
            )
        )

        profile = result[
            "profiles"
        ][0]

        self.assertEqual(
            profile["status"],
            "insufficient_data",
        )

        self.assertFalse(
            profile[
                "eligible_for_shadow_adjustment"
            ]
        )

        self.assertIsNone(
            profile[
                "shadow_target_confidence"
            ]
        )

    def test_five_distinct_claims_unlock_shadow_profile(
        self,
    ):
        cases = []

        for number in range(
            1,
            6,
        ):
            cases += self.cases(
                claim_id=(
                    f"claim-{number}"
                ),
                previous_value="direct",
                verified_value="direct",
                confidence=0.95,
            )

        result = (
            build_local_confidence_calibration(
                cases=cases
            )
        )

        profile = result[
            "profiles"
        ][0]

        self.assertEqual(
            profile[
                "distinct_claim_count"
            ],
            5,
        )

        self.assertEqual(
            profile["status"],
            "shadow_ready",
        )

        self.assertTrue(
            profile[
                "eligible_for_shadow_adjustment"
            ]
        )

        self.assertFalse(
            profile[
                "eligible_for_live_use"
            ]
        )

        self.assertEqual(
            profile[
                "smoothing_prior_mean"
            ],
            0.95,
        )

        self.assertEqual(
            profile[
                "smoothing_prior_strength"
            ],
            2.0,
        )

        self.assertEqual(
            profile[
                "shadow_target_confidence"
            ],
            0.985714,
        )

        self.assertEqual(
            profile[
                "shadow_target_brier_score"
            ],
            0.000204,
        )

        self.assertTrue(
            profile[
                "shadow_target_improves_calibration_brier"
            ]
        )

    def test_same_claim_does_not_satisfy_distinct_claim_threshold(
        self,
    ):
        original = self.cases(
            claim_id="claim-1"
        )[0]

        cases = []

        for number in range(
            5
        ):
            case = copy.deepcopy(
                original
            )

            case[
                "previous_revision_id"
            ] = (
                f"previous-{number}"
            )

            case[
                "current_revision_id"
            ] = (
                f"current-{number}"
            )

            payload = {
                key: value
                for key, value
                in case.items()
                if key != "id"
            }

            import hashlib
            import json

            case["id"] = hashlib.sha256(
                (
                    "local-confidence-case|"
                    + json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                ).encode(
                    "utf-8"
                )
            ).hexdigest()

            cases.append(case)

        result = (
            build_local_confidence_calibration(
                cases=cases
            )
        )

        profile = result[
            "profiles"
        ][0]

        self.assertEqual(
            profile[
                "sample_count"
            ],
            5,
        )

        self.assertEqual(
            profile[
                "distinct_claim_count"
            ],
            1,
        )

        self.assertFalse(
            profile[
                "eligible_for_shadow_adjustment"
            ]
        )

    def test_tampered_case_is_rejected(
        self,
    ):
        case = self.cases()[0]

        tampered = copy.deepcopy(
            case
        )

        tampered[
            "verified_value"
        ] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "deterministic identity",
        ):
            build_local_confidence_calibration(
                cases=[
                    tampered
                ]
            )

    def test_version_and_live_guards(
        self,
    ):
        result = (
            build_local_confidence_calibration(
                cases=self.cases()
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                LOCAL_CONFIDENCE_CALIBRATION_VERSION
            ),
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "eligible_for_live_use"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_change_live_merit"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "human_review_required"
            ]
        )


if __name__ == "__main__":
    unittest.main()
