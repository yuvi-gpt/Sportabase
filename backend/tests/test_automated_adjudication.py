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


from app.analysis.adjudication import (
    ADJUDICATION_FIELDS,
    ADJUDICATION_TIERS,
    AUTOMATED_ADJUDICATION_VERSION,
    build_automated_adjudication,
)


class AutomatedAdjudicationTests(
    unittest.TestCase
):
    def judgment(
        self,
        *,
        row_id="judgment-1",
        value="stakeholder_confirmed",
        confidence=0.90,
        evaluator_id="authority-rule-v1",
        evaluator_family="authority_rule",
        basis_class="deterministic_rule",
        evidence_ids=None,
    ):
        if evidence_ids is None:
            evidence_ids = [
                "observation-1",
            ]

        return {
            "id": row_id,
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
            "evidence_ids": (
                evidence_ids
            ),
        }

    def build(
        self,
        judgments,
        *,
        field="authority_state",
        correction=None,
    ):
        return (
            build_automated_adjudication(
                claim_id="claim-1",
                field=field,
                judgments=judgments,
                correction=correction,
            )
        )

    def test_version_and_vocabularies(
        self,
    ):
        self.assertEqual(
            AUTOMATED_ADJUDICATION_VERSION,
            "automated-adjudication-v1",
        )

        self.assertEqual(
            set(
                ADJUDICATION_TIERS
            ),
            {
                "auto_gold",
                "auto_silver",
                "contested",
                "unresolved",
            },
        )

        self.assertIn(
            "authority_state",
            ADJUDICATION_FIELDS,
        )

        self.assertIn(
            "outcome_status",
            ADJUDICATION_FIELDS,
        )

    def test_direct_authority_record_can_create_auto_gold_authority(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

    def test_canonical_resolution_can_create_auto_gold_outcome(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    value="eventually_true",
                    confidence=0.99,
                    evaluator_id=(
                        "official-result-v1"
                    ),
                    evaluator_family=(
                        "official_result"
                    ),
                    basis_class=(
                        "canonical_resolution"
                    ),
                )
            ],
            field="outcome_status",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            result[
                "effective"
            ][
                "value"
            ],
            "eventually_true",
        )

    def test_two_distinct_evaluator_families_can_create_auto_silver(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    row_id="rule",
                    confidence=0.91,
                    evaluator_id="rule-v1",
                    evaluator_family=(
                        "authority_rule"
                    ),
                ),
                self.judgment(
                    row_id="graph",
                    confidence=0.93,
                    evaluator_id="graph-v1",
                    evaluator_family=(
                        "provenance_graph"
                    ),
                    basis_class=(
                        "provenance_graph"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "auto_silver",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "supporting_evaluator_families"
            ],
            [
                "authority_rule",
                "provenance_graph",
            ],
        )

    def test_same_family_votes_do_not_create_silver_consensus(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    row_id="rule-a",
                    confidence=0.94,
                    evaluator_id="rule-a",
                    evaluator_family=(
                        "authority_rule"
                    ),
                ),
                self.judgment(
                    row_id="rule-b",
                    confidence=0.93,
                    evaluator_id="rule-b",
                    evaluator_family=(
                        "authority_rule"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

    def test_high_confidence_conflict_is_contested(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    row_id="support",
                    value=(
                        "stakeholder_confirmed"
                    ),
                    confidence=0.94,
                    evaluator_id="rule",
                    evaluator_family=(
                        "authority_rule"
                    ),
                ),
                self.judgment(
                    row_id="contradict",
                    value=(
                        "stakeholder_contested"
                    ),
                    confidence=0.92,
                    evaluator_id="graph",
                    evaluator_family=(
                        "provenance_graph"
                    ),
                    basis_class=(
                        "provenance_graph"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "contested",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "conflicting_values"
            ],
            [
                "stakeholder_confirmed",
                "stakeholder_contested",
            ],
        )

    def test_conflict_blocks_auto_gold(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    row_id="official",
                    value=(
                        "stakeholder_confirmed"
                    ),
                    confidence=0.99,
                    evaluator_id=(
                        "official-record"
                    ),
                    evaluator_family=(
                        "authority_record"
                    ),
                    basis_class=(
                        "direct_authority_record"
                    ),
                ),
                self.judgment(
                    row_id="conflict",
                    value=(
                        "stakeholder_contested"
                    ),
                    confidence=0.90,
                    evaluator_id="other",
                    evaluator_family=(
                        "provenance_graph"
                    ),
                    basis_class=(
                        "provenance_graph"
                    ),
                ),
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "contested",
        )

    def test_weak_evidence_remains_unresolved(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.60,
                )
            ]
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

        self.assertEqual(
            result[
                "effective"
            ][
                "value"
            ],
            "",
        )

    def test_gold_basis_is_field_specific(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    value="supports",
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ],
            field="stance",
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

    def test_input_order_is_stable(
        self,
    ):
        rows = [
            self.judgment(
                row_id="a",
                evaluator_id="a",
                evaluator_family="family_a",
            ),
            self.judgment(
                row_id="b",
                evaluator_id="b",
                evaluator_family="family_b",
            ),
        ]

        first = self.build(
            rows
        )

        second = self.build(
            list(
                reversed(
                    rows
                )
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_conflicting_duplicate_judgment_is_rejected(
        self,
    ):
        first = self.judgment(
            row_id="same"
        )

        second = {
            **first,
            "value": (
                "stakeholder_contested"
            ),
        }

        with self.assertRaisesRegex(
            ValueError,
            "conflicting duplicate",
        ):
            self.build(
                [
                    first,
                    second,
                ]
            )

    def test_confidence_must_be_bounded(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "between 0 and 1",
        ):
            self.build(
                [
                    self.judgment(
                        confidence=1.5,
                    )
                ]
            )

    def test_manual_override_preserves_automatic_history(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ],
            correction={
                "value": (
                    "stakeholder_contested"
                ),
                "reason": (
                    "A conflicting primary "
                    "stakeholder statement was "
                    "missed by automation."
                ),
                "corrected_by": (
                    "Human Reviewer"
                ),
                "corrected_at": (
                    "2026-08-15T08:30:00+05:30"
                ),
                "scope": (
                    "pattern_candidate"
                ),
            },
        )

        self.assertEqual(
            result[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            result[
                "effective"
            ],
            {
                "value": (
                    "stakeholder_contested"
                ),
                "source": (
                    "manual_override"
                ),
            },
        )

        self.assertEqual(
            result[
                "correction"
            ][
                "value"
            ],
            "stakeholder_contested",
        )

    def test_manual_override_creates_pending_learning_signal(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ],
            correction={
                "value": (
                    "stakeholder_contested"
                ),
                "reason": (
                    "Missed conflicting "
                    "stakeholder evidence."
                ),
                "corrected_by": (
                    "Human Reviewer"
                ),
                "corrected_at": (
                    "2026-08-15T08:30:00+05:30"
                ),
                "scope": (
                    "pattern_candidate"
                ),
            },
        )

        signal = result[
            "learning_signal"
        ]

        self.assertEqual(
            signal[
                "status"
            ],
            "pending_validation",
        )

        self.assertEqual(
            signal[
                "original_value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            signal[
                "corrected_value"
            ],
            "stakeholder_contested",
        )

        self.assertFalse(
            signal[
                "training_eligible"
            ]
        )

    def test_manual_correction_requires_audit_metadata(
        self,
    ):
        incomplete = [
            {
                "value": "other",
                "reason": "",
                "corrected_by": "Reviewer",
                "corrected_at": (
                    "2026-08-15T08:30:00+05:30"
                ),
            },
            {
                "value": "other",
                "reason": "Reason.",
                "corrected_by": "",
                "corrected_at": (
                    "2026-08-15T08:30:00+05:30"
                ),
            },
            {
                "value": "other",
                "reason": "Reason.",
                "corrected_by": "Reviewer",
                "corrected_at": "",
            },
        ]

        for correction in incomplete:
            with self.subTest(
                correction=correction
            ):
                with self.assertRaises(
                    ValueError
                ):
                    self.build(
                        [
                            self.judgment()
                        ],
                        correction=(
                            correction
                        ),
                    )

    def test_auto_gold_is_reference_training_eligible(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ]
        )

        signal = result[
            "learning_signal"
        ]

        self.assertEqual(
            signal[
                "status"
            ],
            "reference_ready",
        )

        self.assertEqual(
            signal[
                "source"
            ],
            "auto_gold",
        )

        self.assertTrue(
            signal[
                "training_eligible"
            ]
        )

    def test_auto_silver_is_not_gold_training_data(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    row_id="a",
                    evaluator_id="a",
                    evaluator_family="family_a",
                    confidence=0.90,
                ),
                self.judgment(
                    row_id="b",
                    evaluator_id="b",
                    evaluator_family="family_b",
                    confidence=0.91,
                ),
            ]
        )

        signal = result[
            "learning_signal"
        ]

        self.assertEqual(
            signal[
                "status"
            ],
            "calibration_candidate",
        )

        self.assertFalse(
            signal[
                "training_eligible"
            ]
        )

    def test_adjudication_does_not_touch_merit(
        self,
    ):
        result = self.build(
            [
                self.judgment(
                    confidence=0.99,
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ]
        )

        forbidden = {
            "merit",
            "merit_score",
            "live_total",
            "shadow_total",
            "score_adjustment",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "adjudication_does_not_change_live_merit"
            ]
        )


if __name__ == "__main__":
    unittest.main()
