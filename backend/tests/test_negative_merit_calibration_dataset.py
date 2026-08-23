import copy
import json
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


from app.analysis.negative_merit import (
    build_negative_merit_shadow,
)

from app.analysis.negative_merit_calibration_dataset import (
    NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION,
    NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION,
    build_negative_merit_calibration_dataset,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)


class NegativeMeritCalibrationDatasetTests(
    unittest.TestCase
):
    @staticmethod
    def authority(
        claim_id,
    ):
        return {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_direct_stakeholder_"
                "contradiction_lineage"
            ),
            "persisted": True,
            "evidence": {
                "id": (
                    "authority-"
                    + claim_id
                ),
                "evidence_type": (
                    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE
                ),
                "verification_status": (
                    "verified"
                ),
                "subject_key": (
                    "merit-negative-evidence|"
                    + claim_id
                ),
                "metadata_json": json.dumps(
                    {
                        "verifier_version": (
                            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
                        ),
                        "machine_verified_authority": True,
                        "recorded_contradiction_relationship": True,
                        "contradiction_semantics_verified": False,
                        "claim_truth_established": False,
                        "live_merit_changed": False,
                    }
                ),
            },
        }

    @staticmethod
    def semantics(
        claim_id,
    ):
        return {
            "version": (
                MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_machine_"
                "contradiction_semantics"
            ),
            "persisted": True,
            "evidence": {
                "id": (
                    "semantic-"
                    + claim_id
                ),
                "evidence_type": (
                    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE
                ),
                "verification_status": (
                    "verified"
                ),
                "subject_key": (
                    "merit-negative-semantic-evidence|"
                    + claim_id
                ),
                "metadata_json": json.dumps(
                    {
                        "verifier_version": (
                            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION
                        ),
                        "claim_id": (
                            claim_id
                        ),
                        "stance": (
                            "contradicts"
                        ),
                        "contradiction_semantics_verified": True,
                        "contradiction_semantics_are_source_semantics": True,
                        "claim_truth_established": False,
                        "live_merit_changed": False,
                    }
                ),
            },
        }

    @staticmethod
    def capture(
        *,
        source_id,
        letter,
    ):
        return {
            "url": (
                "https://"
                + source_id
                + ".example/"
                + letter
            ),
            "source_id": (
                source_id
            ),
            "content_sha256": (
                letter
                * 64
            ),
            "captured_at": (
                "2026-08-23T09:00:00Z"
            ),
        }

    def case(
        self,
        *,
        case_id,
        observation_class,
        score,
        authority=False,
        semantics=False,
        letter="a",
    ):
        claim_id = (
            "claim-"
            + case_id
        )

        return {
            "version": (
                NEGATIVE_MERIT_CALIBRATION_OBSERVATION_VERSION
            ),
            "origin": (
                "real_world"
            ),
            "machine_verified": True,
            "id": (
                case_id
            ),
            "claim_id": (
                claim_id
            ),
            "observation_class": (
                observation_class
            ),
            "observed_at": (
                "2026-08-23T09:05:00Z"
            ),
            "resolution_status": (
                "unresolved"
            ),
            "source_captures": [
                self.capture(
                    source_id=(
                        "source-"
                        + case_id
                    ),
                    letter=(
                        letter
                    ),
                )
            ],
            "legacy_score": {
                "total": (
                    score
                ),
                "badge": "Measured",
                "components": {},
                "calculation": {},
                "reasons": [],
            },
            "contradiction_verification": (
                self.authority(
                    claim_id
                )
                if authority
                else None
            ),
            "semantic_verification": (
                self.semantics(
                    claim_id
                )
                if semantics
                else None
            ),
        }

    def complete_cases(
        self,
    ):
        return [
            self.case(
                case_id=(
                    "two-gate"
                ),
                observation_class=(
                    "two_gate_observation"
                ),
                score=82,
                authority=True,
                semantics=True,
                letter="a",
            ),
            self.case(
                case_id=(
                    "authority-only"
                ),
                observation_class=(
                    "authority_only_control"
                ),
                score=78,
                authority=True,
                semantics=False,
                letter="b",
            ),
            self.case(
                case_id=(
                    "semantic-only"
                ),
                observation_class=(
                    "semantic_only_control"
                ),
                score=70,
                authority=False,
                semantics=True,
                letter="c",
            ),
            self.case(
                case_id=(
                    "no-evidence"
                ),
                observation_class=(
                    "no_negative_evidence_control"
                ),
                score=64,
                authority=False,
                semantics=False,
                letter="d",
            ),
            self.case(
                case_id=(
                    "exclusive"
                ),
                observation_class=(
                    "exclusive_no_corroboration_control"
                ),
                score=88,
                authority=False,
                semantics=False,
                letter="e",
            ),
        ]

    def test_measurement_dataset_builds_without_selecting_penalty(
        self,
    ):
        result = (
            build_negative_merit_calibration_dataset(
                cases=(
                    self.complete_cases()
                )
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            NEGATIVE_MERIT_CALIBRATION_DATASET_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "measurement_ready",
        )

        self.assertEqual(
            result[
                "case_count"
            ],
            5,
        )

        overall = (
            result[
                "score_distribution"
            ][
                "overall"
            ]
        )

        self.assertEqual(
            overall[
                "count"
            ],
            5,
        )

        self.assertAlmostEqual(
            overall[
                "mean"
            ],
            76.4,
        )

        self.assertEqual(
            overall[
                "median"
            ],
            78.0,
        )

        candidate = (
            result[
                "score_distribution"
            ][
                "two_gate_observations"
            ]
        )

        self.assertEqual(
            candidate[
                "count"
            ],
            1,
        )

        self.assertEqual(
            candidate[
                "mean"
            ],
            82.0,
        )

        controls = (
            result[
                "score_distribution"
            ][
                "controls"
            ]
        )

        self.assertEqual(
            controls[
                "count"
            ],
            4,
        )

        calibration = result[
            "calibration"
        ]

        self.assertFalse(
            calibration[
                "penalty_weight_selected"
            ]
        )

        self.assertFalse(
            calibration[
                "numeric_penalty_authorized"
            ]
        )

        self.assertFalse(
            calibration[
                "live_negative_merit_authorized"
            ]
        )

        self.assertFalse(
            calibration[
                "canonical_outcome_labels_available"
            ]
        )

        self.assertIn(
            (
                "canonical_outcome_verifier_"
                "not_implemented"
            ),
            calibration[
                "blockers"
            ],
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "two_gate_observation_is_not_a_falsehood_label"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "early_exclusives_are_controls_not_falsehoods"
            ]
        )

    def test_resolved_outcome_label_is_rejected_until_verifier_exists(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "resolution_status"
        ] = (
            "resolved_against_claim"
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "dedicated .*canonical-outcome "
                "verifier"
            ),
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_non_https_capture_is_rejected(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "source_captures"
        ][
            0
        ][
            "url"
        ] = (
            "http://unsafe.example/story"
        )

        with self.assertRaisesRegex(
            ValueError,
            "must use HTTPS",
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_two_gate_class_requires_both_real_gates(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "semantic_verification"
        ] = None

        with self.assertRaisesRegex(
            ValueError,
            (
                "must satisfy both evidence gates"
            ),
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_numeric_shadow_change_is_rejected(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        def unsafe_builder(
            **kwargs,
        ):
            result = copy.deepcopy(
                build_negative_merit_shadow(
                    **kwargs
                )
            )

            result[
                "proposed"
            ][
                "adjustment"
            ] = -20.0

            result[
                "proposed"
            ][
                "shadow_total"
            ] = 62.0

            return result

        with self.assertRaisesRegex(
            ValueError,
            (
                "cannot contain a numeric "
                "negative Merit adjustment"
            ),
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ],
                shadow_builder=(
                    unsafe_builder
                ),
            )

    def test_synthetic_origin_is_rejected(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "origin"
        ] = (
            "synthetic_policy_fixture"
        )

        with self.assertRaisesRegex(
            ValueError,
            "must be marked real_world",
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )


if __name__ == "__main__":
    unittest.main()
