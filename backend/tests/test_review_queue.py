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


from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)

from app.analysis.review_queue import (
    REVIEW_QUEUE_ITEM_VERSION,
    REVIEW_QUEUE_PACKET_VERSION,
    build_adjudication_review_queue,
)


class AdjudicationReviewQueueTests(
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
        training_eligible=False,
    ):
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
            "evidence_ids": [
                "observation-1",
            ],
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

    def adjudicate(
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

    def queue(
        self,
        result,
    ):
        return (
            build_adjudication_review_queue(
                adjudication=result,
                evidence_id="evidence-1",
            )
        )

    def test_versions_and_missing_coverage(
        self,
    ):
        packet = self.queue(
            self.adjudicate(
                []
            )
        )

        self.assertEqual(
            packet[
                "version"
            ],
            REVIEW_QUEUE_PACKET_VERSION,
        )

        self.assertEqual(
            packet[
                "items"
            ],
            [],
        )

        self.assertEqual(
            set(
                packet[
                    "summary"
                ][
                    "missing_evaluation_fields"
                ]
            ),
            {
                "source_role",
                "authority_class",
                "reliability_class",
                "provenance_class",
                "stance",
                "independence_status",
            },
        )

    def test_contested_is_highest_priority_review(
        self,
    ):
        support = self.evaluator_run(
            run_id="support",
            evaluator_id="model",
            evaluator_family="semantic_model",
            judgments=[
                self.judgment(
                    row_id="support",
                    evaluator_id="model",
                    evaluator_family="semantic_model",
                )
            ],
        )

        contradict = self.evaluator_run(
            run_id="contradict",
            evaluator_id="graph",
            evaluator_family="provenance_graph",
            derivation_mode="machine_verified",
            judgments=[
                self.judgment(
                    row_id="contradict",
                    value="contradicts",
                    confidence=0.96,
                    evaluator_id="graph",
                    evaluator_family="provenance_graph",
                    basis_class="provenance_graph",
                )
            ],
        )

        packet = self.queue(
            self.adjudicate(
                [
                    support,
                    contradict,
                ]
            )
        )

        item = packet[
            "items"
        ][0]

        self.assertEqual(
            item[
                "queue_reason"
            ],
            "contested",
        )

        self.assertEqual(
            item[
                "priority"
            ],
            400,
        )

        self.assertEqual(
            item[
                "conflicting_values"
            ],
            [
                "contradicts",
                "supports",
            ],
        )

    def test_auto_silver_is_reviewable(
        self,
    ):
        model = self.evaluator_run(
            run_id="model",
            evaluator_id="model",
            evaluator_family="semantic_model",
            judgments=[
                self.judgment(
                    row_id="model",
                    evaluator_id="model",
                    evaluator_family="semantic_model",
                )
            ],
        )

        rule = self.evaluator_run(
            run_id="rule",
            evaluator_id="rule",
            evaluator_family="claim_rule",
            derivation_mode="machine_verified",
            judgments=[
                self.judgment(
                    row_id="rule",
                    confidence=0.92,
                    evaluator_id="rule",
                    evaluator_family="claim_rule",
                    basis_class="deterministic_rule",
                )
            ],
        )

        packet = self.queue(
            self.adjudicate(
                [
                    model,
                    rule,
                ]
            )
        )

        stance = [
            row
            for row
            in packet[
                "items"
            ]
            if row[
                "field"
            ]
            == "stance"
        ][0]

        self.assertEqual(
            stance[
                "queue_reason"
            ],
            "auto_silver",
        )

        self.assertEqual(
            stance[
                "priority"
            ],
            200,
        )

    def test_unresolved_with_judgment_is_reviewable(
        self,
    ):
        packet = self.queue(
            self.adjudicate(
                [
                    self.evaluator_run()
                ]
            )
        )

        stance = [
            row
            for row
            in packet[
                "items"
            ]
            if row[
                "field"
            ]
            == "stance"
        ][0]

        self.assertEqual(
            stance[
                "queue_reason"
            ],
            "unresolved",
        )

        self.assertEqual(
            stance[
                "priority"
            ],
            300,
        )

    def test_missing_judgments_are_not_human_review(
        self,
    ):
        packet = self.queue(
            self.adjudicate(
                [
                    self.evaluator_run()
                ]
            )
        )

        self.assertNotIn(
            "source_role",
            packet[
                "summary"
            ][
                "queued_fields"
            ],
        )

        self.assertIn(
            "source_role",
            packet[
                "summary"
            ][
                "missing_evaluation_fields"
            ],
        )

    def test_untrusted_auto_gold_is_queued(
        self,
    ):
        model = self.evaluator_run(
            judgments=[
                self.judgment(
                    row_id="authority",
                    field="authority_class",
                    value="direct",
                    confidence=0.99,
                    basis_class="direct_authority_record",
                )
            ]
        )

        packet = self.queue(
            self.adjudicate(
                [
                    model
                ]
            )
        )

        authority = [
            row
            for row
            in packet[
                "items"
            ]
            if row[
                "field"
            ]
            == "authority_class"
        ][0]

        self.assertEqual(
            authority[
                "automatic_tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            authority[
                "queue_reason"
            ],
            (
                "blocked_auto_gold_reference"
            ),
        )

    def test_trusted_auto_gold_is_not_queued(
        self,
    ):
        verified = self.evaluator_run(
            run_id="verified",
            evaluator_id="official",
            evaluator_family="authority_record",
            derivation_mode="machine_verified",
            judgments=[
                self.judgment(
                    row_id="authority",
                    field="authority_class",
                    value="direct",
                    confidence=0.99,
                    evaluator_id="official",
                    evaluator_family="authority_record",
                    basis_class="direct_authority_record",
                    training_eligible=True,
                )
            ],
        )

        packet = self.queue(
            self.adjudicate(
                [
                    verified
                ]
            )
        )

        self.assertNotIn(
            "authority_class",
            packet[
                "summary"
            ][
                "queued_fields"
            ],
        )

        self.assertIn(
            "authority_class",
            packet[
                "summary"
            ][
                "trusted_auto_gold_fields"
            ],
        )

    def test_corrected_field_is_not_requeued(
        self,
    ):
        model = self.evaluator_run(
            run_id="model",
            evaluator_id="model",
            evaluator_family="semantic_model",
            judgments=[
                self.judgment(
                    row_id="model",
                    evaluator_id="model",
                    evaluator_family="semantic_model",
                )
            ],
        )

        rule = self.evaluator_run(
            run_id="rule",
            evaluator_id="rule",
            evaluator_family="claim_rule",
            derivation_mode="machine_verified",
            judgments=[
                self.judgment(
                    row_id="rule",
                    evaluator_id="rule",
                    evaluator_family="claim_rule",
                    basis_class="deterministic_rule",
                )
            ],
        )

        result = self.adjudicate(
            [
                model,
                rule,
            ],
            corrections={
                "stance": {
                    "value": "supports",
                    "reason": (
                        "Human reviewed source."
                    ),
                    "corrected_by": (
                        "Reviewer"
                    ),
                    "corrected_at": (
                        "2026-08-15T10:00:00+05:30"
                    ),
                    "scope": "case_only",
                }
            },
        )

        packet = self.queue(
            result
        )

        self.assertNotIn(
            "stance",
            packet[
                "summary"
            ][
                "queued_fields"
            ],
        )

        self.assertIn(
            "stance",
            packet[
                "summary"
            ][
                "corrected_fields"
            ],
        )

    def test_changed_adjudication_content_creates_new_review_identity(
        self,
    ):
        first_result = (
            self.adjudicate(
                [
                    self.evaluator_run(
                        judgments=[
                            self.judgment(
                                confidence=0.90,
                            )
                        ]
                    )
                ]
            )
        )

        second_result = (
            self.adjudicate(
                [
                    self.evaluator_run(
                        judgments=[
                            self.judgment(
                                confidence=0.91,
                            )
                        ]
                    )
                ]
            )
        )

        first = self.queue(
            first_result
        )[
            "items"
        ][0]

        second = self.queue(
            second_result
        )[
            "items"
        ][0]

        self.assertEqual(
            first[
                "version"
            ],
            REVIEW_QUEUE_ITEM_VERSION,
        )

        self.assertNotEqual(
            first[
                "content_sha256"
            ],
            second[
                "content_sha256"
            ],
        )

        self.assertNotEqual(
            first[
                "review_key"
            ],
            second[
                "review_key"
            ],
        )


if __name__ == "__main__":
    unittest.main()
