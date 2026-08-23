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

from app.analysis.negative_merit_evaluation import (
    NEGATIVE_MERIT_EVALUATION_CASE_VERSION,
    NEGATIVE_MERIT_EVALUATION_ORIGIN,
    NEGATIVE_MERIT_EVALUATION_VERSION,
    evaluate_negative_merit_cases,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_EVIDENCE_TYPE,
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
)


class NegativeMeritEvaluationTests(
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
                    "authority-evidence-"
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
                    "semantic-evidence-"
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
    def legacy():
        return {
            "total": 70,
            "badge": "Good",
            "components": {},
            "calculation": {},
            "reasons": [],
        }

    def case(
        self,
        *,
        case_id,
        control_class,
        authority=False,
        semantics=False,
        signal,
        severity_class,
        eligible,
    ):
        claim_id = (
            "claim-"
            + case_id
        )

        return {
            "version": (
                NEGATIVE_MERIT_EVALUATION_CASE_VERSION
            ),
            "origin": (
                NEGATIVE_MERIT_EVALUATION_ORIGIN
            ),
            "id": (
                case_id
            ),
            "claim_id": (
                claim_id
            ),
            "control_class": (
                control_class
            ),
            "legacy_score": (
                self.legacy()
            ),
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
            "expectations": {
                "signal": (
                    signal
                ),
                "severity_class": (
                    severity_class
                ),
                "calibration_eligible": (
                    eligible
                ),
                "adjustment": 0.0,
                "live_total": 70.0,
                "shadow_total": 70.0,
                "authority_gate": (
                    authority
                ),
                "semantic_gate": (
                    semantics
                ),
            },
        }

    def complete_cases(
        self,
    ):
        return [
            self.case(
                case_id=(
                    "verified-two-gate"
                ),
                control_class=(
                    "two_gate_candidate"
                ),
                authority=True,
                semantics=True,
                signal=(
                    "verified_authority_machine_"
                    "semantic_contradiction"
                ),
                severity_class=(
                    "two_gate_negative_"
                    "evidence_candidate"
                ),
                eligible=True,
            ),
            self.case(
                case_id=(
                    "authority-only"
                ),
                control_class=(
                    "authority_only_control"
                ),
                authority=True,
                semantics=False,
                signal=(
                    "verified_authority_"
                    "contradiction_semantics_"
                    "unverified"
                ),
                severity_class=(
                    "authority_only_negative_"
                    "evidence_candidate"
                ),
                eligible=False,
            ),
            self.case(
                case_id=(
                    "semantics-only"
                ),
                control_class=(
                    "semantic_only_control"
                ),
                authority=False,
                semantics=True,
                signal=(
                    "machine_semantic_"
                    "contradiction_without_"
                    "verified_direct_authority"
                ),
                severity_class=(
                    "semantic_only_negative_"
                    "evidence_candidate"
                ),
                eligible=False,
            ),
            self.case(
                case_id=(
                    "no-negative-evidence"
                ),
                control_class=(
                    "no_negative_evidence_control"
                ),
                authority=False,
                semantics=False,
                signal=(
                    "no_certified_negative_evidence"
                ),
                severity_class="none",
                eligible=False,
            ),
            self.case(
                case_id=(
                    "early-exclusive"
                ),
                control_class=(
                    "exclusive_no_corroboration_control"
                ),
                authority=False,
                semantics=False,
                signal=(
                    "no_certified_negative_evidence"
                ),
                severity_class="none",
                eligible=False,
            ),
        ]

    def test_complete_policy_matrix_passes(
        self,
    ):
        result = (
            evaluate_negative_merit_cases(
                cases=(
                    self.complete_cases()
                )
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            NEGATIVE_MERIT_EVALUATION_VERSION,
        )

        self.assertEqual(
            result[
                "status"
            ],
            "passed",
        )

        metrics = result[
            "metrics"
        ]

        self.assertEqual(
            metrics[
                "cases"
            ],
            5,
        )

        self.assertEqual(
            metrics[
                "expectations_failed"
            ],
            0,
        )

        self.assertEqual(
            metrics[
                "safety_violations"
            ],
            0,
        )

        self.assertEqual(
            metrics[
                "two_gate_candidates"
            ],
            1,
        )

        self.assertEqual(
            metrics[
                "calibration_candidates"
            ],
            1,
        )

        self.assertEqual(
            metrics[
                "false_positive_calibration_candidates"
            ],
            0,
        )

        self.assertFalse(
            result[
                "enablement"
            ][
                "live_negative_merit_authorized"
            ]
        )

        self.assertFalse(
            result[
                "enablement"
            ][
                "numeric_penalty_authorized"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "exclusive_reporting_is_not_negative_evidence"
            ]
        )

    def test_empty_case_set_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "requires at least one case",
        ):
            evaluate_negative_merit_cases(
                cases=[]
            )

    def test_single_gate_false_positive_is_safety_failure(
        self,
    ):
        case = self.complete_cases()[
            1
        ]

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
                "eligible_for_penalty_calibration"
            ] = True

            return result

        result = (
            evaluate_negative_merit_cases(
                cases=[
                    case
                ],
                shadow_builder=(
                    unsafe_builder
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "failed",
        )

        self.assertGreater(
            result[
                "metrics"
            ][
                "false_positive_calibration_candidates"
            ],
            0,
        )

        violations = result[
            "cases"
        ][
            0
        ][
            "safety_violations"
        ]

        self.assertIn(
            (
                "calibration_eligible_"
                "without_both_gates"
            ),
            violations,
        )

        self.assertIn(
            (
                "negative_control_became_"
                "calibration_eligible"
            ),
            violations,
        )

    def test_numeric_penalty_before_calibration_is_safety_failure(
        self,
    ):
        case = self.complete_cases()[
            0
        ]

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
            ] = -15.0

            result[
                "proposed"
            ][
                "shadow_total"
            ] = 55.0

            return result

        result = (
            evaluate_negative_merit_cases(
                cases=[
                    case
                ],
                shadow_builder=(
                    unsafe_builder
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "failed",
        )

        self.assertEqual(
            result[
                "metrics"
            ][
                "numeric_adjustments_before_calibration"
            ],
            1,
        )

        violations = result[
            "cases"
        ][
            0
        ][
            "safety_violations"
        ]

        self.assertIn(
            (
                "numeric_adjustment_"
                "before_calibration"
            ),
            violations,
        )

        self.assertIn(
            (
                "shadow_total_changed_"
                "before_calibration"
            ),
            violations,
        )

    def test_live_score_change_is_safety_failure(
        self,
    ):
        case = self.complete_cases()[
            0
        ]

        def unsafe_builder(
            **kwargs,
        ):
            result = copy.deepcopy(
                build_negative_merit_shadow(
                    **kwargs
                )
            )

            result[
                "live"
            ][
                "score_effect_enabled"
            ] = True

            result[
                "live"
            ][
                "total"
            ] = 55.0

            return result

        result = (
            evaluate_negative_merit_cases(
                cases=[
                    case
                ],
                shadow_builder=(
                    unsafe_builder
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            "failed",
        )

        self.assertEqual(
            result[
                "metrics"
            ][
                "live_score_changes"
            ],
            1,
        )

        violations = result[
            "cases"
        ][
            0
        ][
            "safety_violations"
        ]

        self.assertIn(
            "live_score_changed",
            violations,
        )

        self.assertIn(
            "live_negative_merit_enabled",
            violations,
        )


if __name__ == "__main__":
    unittest.main()
