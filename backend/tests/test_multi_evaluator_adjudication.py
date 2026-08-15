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


from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_ADJUDICATION_VERSION,
    MULTI_EVALUATOR_FIELDS,
    build_multi_evaluator_adjudication,
)


class MultiEvaluatorAdjudicationTests(
    unittest.TestCase
):
    def judgment(
        self,
        *,
        row_id="judgment-1",
        field="stance",
        value="supports",
        confidence=0.95,
        evaluator_id="semantic-v1",
        evaluator_family="semantic_model",
        basis_class="model_inference",
        evidence_ids=None,
        training_eligible=False,
    ):
        if evidence_ids is None:
            evidence_ids = [
                "observation-1",
            ]

        return {
            "id": row_id,
            "field": field,
            "value": value,
            "confidence": (
                confidence
            ),
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
            "training_eligible": (
                training_eligible
            ),
        }

    def evaluator_run(
        self,
        *,
        run_id="run-1",
        evaluator_id="semantic-v1",
        evaluator_family="semantic_model",
        derivation_mode="model_assisted",
        judgments=None,
    ):
        if judgments is None:
            judgments = [
                self.judgment(
                    evaluator_id=(
                        evaluator_id
                    ),
                    evaluator_family=(
                        evaluator_family
                    ),
                )
            ]

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
            "judgments": (
                judgments
            ),
        }

    def build(
        self,
        runs,
        *,
        corrections=None,
    ):
        return (
            build_multi_evaluator_adjudication(
                claim_id="claim-1",
                evaluator_runs=runs,
                corrections=corrections,
            )
        )

    def test_version_and_full_field_coverage(
        self,
    ):
        result = self.build(
            []
        )

        self.assertEqual(
            MULTI_EVALUATOR_ADJUDICATION_VERSION,
            (
                "multi-evaluator-"
                "adjudication-v1"
            ),
        )

        self.assertEqual(
            set(
                result[
                    "fields"
                ].keys()
            ),
            set(
                MULTI_EVALUATOR_FIELDS
            ),
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "unresolved_fields"
            ],
            sorted(
                MULTI_EVALUATOR_FIELDS
            ),
        )

    def test_single_model_vote_does_not_create_consensus(
        self,
    ):
        result = self.build(
            [
                self.evaluator_run()
            ]
        )

        self.assertEqual(
            result[
                "fields"
            ][
                "stance"
            ][
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

    def test_distinct_families_can_create_auto_silver(
        self,
    ):
        model = self.evaluator_run(
            run_id="model",
            evaluator_id="semantic-v1",
            evaluator_family="semantic_model",
            judgments=[
                self.judgment(
                    row_id="model-stance",
                    evaluator_id=(
                        "semantic-v1"
                    ),
                    evaluator_family=(
                        "semantic_model"
                    ),
                )
            ],
        )

        rule = self.evaluator_run(
            run_id="rule",
            evaluator_id="claim-rule-v1",
            evaluator_family="claim_rule",
            derivation_mode=(
                "machine_verified"
            ),
            judgments=[
                self.judgment(
                    row_id="rule-stance",
                    evaluator_id=(
                        "claim-rule-v1"
                    ),
                    evaluator_family=(
                        "claim_rule"
                    ),
                    basis_class=(
                        "deterministic_rule"
                    ),
                )
            ],
        )

        result = self.build(
            [
                model,
                rule,
            ]
        )

        stance = result[
            "fields"
        ][
            "stance"
        ]

        self.assertEqual(
            stance[
                "automatic"
            ][
                "tier"
            ],
            "auto_silver",
        )

        self.assertEqual(
            stance[
                "automatic"
            ][
                "supporting_evaluator_families"
            ],
            [
                "claim_rule",
                "semantic_model",
            ],
        )

        self.assertFalse(
            stance[
                "reference_gate"
            ][
                "training_reference_allowed"
            ]
        )

    def test_same_family_multiple_runs_do_not_create_silver(
        self,
    ):
        first = self.evaluator_run(
            run_id="first",
            evaluator_id="model-a",
            evaluator_family=(
                "semantic_model"
            ),
            judgments=[
                self.judgment(
                    row_id="first-stance",
                    evaluator_id="model-a",
                    evaluator_family=(
                        "semantic_model"
                    ),
                )
            ],
        )

        second = self.evaluator_run(
            run_id="second",
            evaluator_id="model-b",
            evaluator_family=(
                "semantic_model"
            ),
            judgments=[
                self.judgment(
                    row_id="second-stance",
                    evaluator_id="model-b",
                    evaluator_family=(
                        "semantic_model"
                    ),
                )
            ],
        )

        result = self.build(
            [
                first,
                second,
            ]
        )

        self.assertEqual(
            result[
                "fields"
            ][
                "stance"
            ][
                "automatic"
            ][
                "tier"
            ],
            "unresolved",
        )

    def test_high_confidence_disagreement_is_contested(
        self,
    ):
        support = self.evaluator_run(
            run_id="support",
            evaluator_id="semantic-v1",
            evaluator_family=(
                "semantic_model"
            ),
            judgments=[
                self.judgment(
                    row_id="support",
                    value="supports",
                    evaluator_id=(
                        "semantic-v1"
                    ),
                    evaluator_family=(
                        "semantic_model"
                    ),
                )
            ],
        )

        contradict = self.evaluator_run(
            run_id="contradict",
            evaluator_id="graph-v1",
            evaluator_family=(
                "provenance_graph"
            ),
            derivation_mode=(
                "machine_verified"
            ),
            judgments=[
                self.judgment(
                    row_id="contradict",
                    value="contradicts",
                    confidence=0.96,
                    evaluator_id=(
                        "graph-v1"
                    ),
                    evaluator_family=(
                        "provenance_graph"
                    ),
                    basis_class=(
                        "provenance_graph"
                    ),
                )
            ],
        )

        result = self.build(
            [
                support,
                contradict,
            ]
        )

        stance = result[
            "fields"
        ][
            "stance"
        ]

        self.assertEqual(
            stance[
                "automatic"
            ][
                "tier"
            ],
            "contested",
        )

        self.assertEqual(
            stance[
                "automatic"
            ][
                "conflicting_values"
            ],
            [
                "contradicts",
                "supports",
            ],
        )

    def test_untrusted_model_cannot_self_train_from_auto_gold(
        self,
    ):
        model = self.evaluator_run(
            run_id="model",
            evaluator_id="semantic-v1",
            evaluator_family=(
                "semantic_model"
            ),
            judgments=[
                self.judgment(
                    row_id="model-authority",
                    field=(
                        "authority_class"
                    ),
                    value="direct",
                    confidence=0.99,
                    evaluator_id=(
                        "semantic-v1"
                    ),
                    evaluator_family=(
                        "semantic_model"
                    ),
                    basis_class=(
                        "direct_authority_record"
                    ),
                )
            ],
        )

        result = self.build(
            [
                model
            ]
        )

        authority = result[
            "fields"
        ][
            "authority_class"
        ]

        self.assertEqual(
            authority[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            authority[
                "learning_signal"
            ][
                "status"
            ],
            (
                "reference_blocked_"
                "untrusted_evaluators"
            ),
        )

        self.assertFalse(
            authority[
                "learning_signal"
            ][
                "training_eligible"
            ]
        )

        self.assertFalse(
            authority[
                "reference_gate"
            ][
                "training_reference_allowed"
            ]
        )

    def test_machine_verified_hard_reference_can_train(
        self,
    ):
        verified = self.evaluator_run(
            run_id="verified",
            evaluator_id=(
                "authority-record-v1"
            ),
            evaluator_family=(
                "authority_record"
            ),
            derivation_mode=(
                "machine_verified"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        "verified-authority"
                    ),
                    field=(
                        "authority_class"
                    ),
                    value="direct",
                    confidence=0.99,
                    evaluator_id=(
                        "authority-record-v1"
                    ),
                    evaluator_family=(
                        "authority_record"
                    ),
                    basis_class=(
                        "direct_authority_record"
                    ),
                    training_eligible=True,
                )
            ],
        )

        result = self.build(
            [
                verified
            ]
        )

        authority = result[
            "fields"
        ][
            "authority_class"
        ]

        self.assertEqual(
            authority[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertTrue(
            authority[
                "learning_signal"
            ][
                "training_eligible"
            ]
        )

        self.assertTrue(
            authority[
                "learning_signal"
            ][
                "reference_input_trusted"
            ]
        )

        self.assertEqual(
            authority[
                "reference_gate"
            ][
                "trusted_hard_reference_judgment_ids"
            ],
            [
                "verified-authority",
            ],
        )

    def test_untrusted_run_cannot_mark_training_eligible(
        self,
    ):
        run = self.evaluator_run(
            judgments=[
                self.judgment(
                    training_eligible=True,
                )
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot mark a judgment training eligible",
        ):
            self.build(
                [
                    run
                ]
            )

    def test_evaluator_family_laundering_is_rejected(
        self,
    ):
        run = self.evaluator_run(
            evaluator_id="semantic-v1",
            evaluator_family=(
                "semantic_model"
            ),
            judgments=[
                self.judgment(
                    evaluator_id=(
                        "semantic-v1"
                    ),
                    evaluator_family=(
                        "provenance_graph"
                    ),
                )
            ],
        )

        with self.assertRaisesRegex(
            ValueError,
            "family does not match",
        ):
            self.build(
                [
                    run
                ]
            )

    def test_one_run_cannot_stuff_multiple_votes_into_same_field(
        self,
    ):
        run = self.evaluator_run(
            judgments=[
                self.judgment(
                    row_id="vote-a",
                ),
                self.judgment(
                    row_id="vote-b",
                ),
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "at most one judgment per field",
        ):
            self.build(
                [
                    run
                ]
            )

    def test_input_order_is_deterministic(
        self,
    ):
        first = self.evaluator_run(
            run_id="a",
            evaluator_id="model-a",
            evaluator_family="family_a",
            judgments=[
                self.judgment(
                    row_id="a",
                    evaluator_id="model-a",
                    evaluator_family="family_a",
                )
            ],
        )

        second = self.evaluator_run(
            run_id="b",
            evaluator_id="model-b",
            evaluator_family="family_b",
            judgments=[
                self.judgment(
                    row_id="b",
                    evaluator_id="model-b",
                    evaluator_family="family_b",
                )
            ],
        )

        forward = self.build(
            [
                first,
                second,
            ]
        )

        reverse = self.build(
            [
                second,
                first,
            ]
        )

        self.assertEqual(
            forward,
            reverse,
        )


if __name__ == "__main__":
    unittest.main()
