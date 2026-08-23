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

from app.services.canonical_outcome_resolution_verifier import (
    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
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

    @staticmethod
    def resolution_verification(
        case,
    ):
        claim_id = case[
            "claim_id"
        ]

        capture = case[
            "source_captures"
        ][
            0
        ]

        source_id = capture[
            "source_id"
        ]

        evidence_id = (
            "resolution-evidence-"
            + claim_id
        )

        proof_evidence_id = (
            "outcome-proof-"
            + claim_id
        )

        rule_id = (
            "transfer_completed_then_failed"
        )

        evidence_metadata = {
            "canonical_outcome_resolution_verifier_version": (
                CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
            ),
            "canonical_outcome_resolution_verified": True,
            "resolved_against_claim": True,
            "claim_truth_established": False,
            "live_merit_changed": False,
        }

        return {
            "version": (
                CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_"
                "canonical_outcome_resolution"
            ),
            "persisted": True,
            "candidate": {
                "version": (
                    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION
                ),
                "status": (
                    "verified_canonical_outcome_"
                    "against_claim"
                ),
                "claim_id": (
                    claim_id
                ),
                "source_id": (
                    source_id
                ),
                "proof_evidence_id": (
                    proof_evidence_id
                ),
                "candidate": {
                    "canonical_url": (
                        capture[
                            "url"
                        ]
                    ),
                    "content_sha256": (
                        capture[
                            "content_sha256"
                        ]
                    ),
                    "rule_id": (
                        rule_id
                    ),
                    "canonical_resolution": {
                        "status": (
                            "resolution_against_claim_candidate"
                        ),
                        "direction": (
                            "against_claim"
                        ),
                        "rule_id": (
                            rule_id
                        ),
                    },
                },
            },
            "revision_runtime": {
                "version": (
                    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION
                ),
                "status": (
                    "persisted"
                ),
                "evidence": {
                    "id": (
                        evidence_id
                    ),
                    "verification_status": (
                        "verified"
                    ),
                    "canonical_url": (
                        capture[
                            "url"
                        ]
                    ),
                    "metadata_json": json.dumps(
                        evidence_metadata
                    ),
                },
                "machine_evaluator_runs": [
                    {
                        "derivation_mode": (
                            "machine_verified"
                        ),
                        "judgments": [
                            {
                                "field": (
                                    "stance"
                                ),
                                "value": (
                                    "contradicts"
                                ),
                                "basis_class": (
                                    "canonical_resolution"
                                ),
                            }
                        ],
                    }
                ],
            },
            "resolution_evidence_id": (
                evidence_id
            ),
            "policy": {
                "canonical_resolution_machine_verified": True,
                "machine_stance": (
                    "contradicts"
                ),
                "machine_basis_class": (
                    "canonical_resolution"
                ),
                "resolved_against_claim": True,
                "claim_truth_established": False,
                "numeric_negative_penalty_authorized": False,
                "live_negative_merit_authorized": False,
                "does_not_change_live_merit": True,
            },
        }

    def resolved_case(
        self,
    ):
        case = self.case(
            case_id=(
                "resolved-two-gate"
            ),
            observation_class=(
                "resolved_against_claim_observation"
            ),
            score=84,
            authority=True,
            semantics=True,
            letter="f",
        )

        case[
            "resolution_status"
        ] = (
            "resolved_against_claim"
        )

        case[
            "resolution_verification"
        ] = (
            self.resolution_verification(
                case
            )
        )

        return case

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

        self.assertTrue(
            calibration[
                "canonical_outcome_verifier_available"
            ]
        )

        self.assertFalse(
            calibration[
                "canonical_outcome_labels_available"
            ]
        )

        self.assertEqual(
            calibration[
                "resolved_against_claim_case_count"
            ],
            0,
        )

        self.assertIn(
            (
                "resolved_outcome_labels_"
                "not_present"
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

        self.assertTrue(
            result[
                "policy"
            ][
                "resolved_labels_require_exact_verified_canonical_outcome_result"
            ]
        )

    def test_resolved_label_requires_exact_verifier_result(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "observation_class"
        ] = (
            "resolved_against_claim_observation"
        )

        case[
            "resolution_status"
        ] = (
            "resolved_against_claim"
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "requires the persisted "
                "canonical outcome verifier result"
            ),
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_verified_resolved_label_enters_separate_distribution(
        self,
    ):
        case = (
            self.resolved_case()
        )

        result = (
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "measurement_ready",
        )

        calibration = (
            result[
                "calibration"
            ]
        )

        self.assertTrue(
            calibration[
                "canonical_outcome_verifier_available"
            ]
        )

        self.assertTrue(
            calibration[
                "canonical_outcome_labels_available"
            ]
        )

        self.assertEqual(
            calibration[
                "resolved_against_claim_case_count"
            ],
            1,
        )

        self.assertNotIn(
            (
                "resolved_outcome_labels_"
                "not_present"
            ),
            calibration[
                "blockers"
            ],
        )

        self.assertIn(
            (
                "numeric_penalty_not_calibrated"
            ),
            calibration[
                "blockers"
            ],
        )

        distribution = (
            result[
                "score_distribution"
            ][
                "resolved_against_claim"
            ]
        )

        self.assertEqual(
            distribution[
                "count"
            ],
            1,
        )

        self.assertEqual(
            distribution[
                "mean"
            ],
            84.0,
        )

        observation = (
            result[
                "observations"
            ][
                0
            ]
        )

        self.assertEqual(
            observation[
                "resolution_status"
            ],
            "resolved_against_claim",
        )

        verification = (
            observation[
                "resolution_verification"
            ]
        )

        self.assertEqual(
            verification[
                "status"
            ],
            "resolved_against_claim",
        )

        self.assertTrue(
            verification[
                "machine_verified"
            ]
        )

        self.assertFalse(
            verification[
                "claim_truth_established"
            ]
        )

        self.assertFalse(
            verification[
                "live_merit_effect_enabled"
            ]
        )

        self.assertEqual(
            observation[
                "negative_merit"
            ][
                "adjustment"
            ],
            0.0,
        )

    def test_resolved_verification_must_match_case_claim(
        self,
    ):
        case = (
            self.resolved_case()
        )

        case[
            "resolution_verification"
        ][
            "candidate"
        ][
            "claim_id"
        ] = (
            "claim-other"
        )

        with self.assertRaisesRegex(
            ValueError,
            "belongs to another claim",
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_resolved_verification_must_match_immutable_capture(
        self,
    ):
        case = (
            self.resolved_case()
        )

        case[
            "source_captures"
        ][
            0
        ][
            "content_sha256"
        ] = (
            "9" * 64
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "not bound to an immutable "
                "source capture"
            ),
        ):
            build_negative_merit_calibration_dataset(
                cases=[
                    case
                ]
            )

    def test_unresolved_case_cannot_carry_resolution_verification(
        self,
    ):
        case = (
            self.complete_cases()[
                0
            ]
        )

        case[
            "resolution_verification"
        ] = (
            self.resolution_verification(
                case
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "must not carry "
                "resolved-outcome verification"
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
