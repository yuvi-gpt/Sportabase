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


from app.analysis.adjudication_state import (
    AUTOMATED_ADJUDICATION_STATE_VERSION,
    build_adjudication_state_revision,
)

from app.analysis.multi_evaluator_adjudication import (
    MULTI_EVALUATOR_FIELDS,
    build_multi_evaluator_adjudication,
)


class AutomatedAdjudicationStateTests(
    unittest.TestCase
):
    def judgment(
        self,
        *,
        row_id,
        field,
        value,
        confidence,
        evaluator_id,
        evaluator_family,
        basis_class,
        evidence_ids=None,
        training_eligible=False,
    ):
        if evidence_ids is None:
            evidence_ids = [
                "evidence-1"
            ]

        return {
            "id": row_id,
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
        run_id,
        evaluator_id,
        evaluator_family,
        derivation_mode,
        judgments,
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
            "judgments": judgments,
        }

    def empty_adjudication(
        self,
        *,
        claim_id="claim-1",
    ):
        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[],
            )
        )

    def contested_authority(
        self,
    ):
        model = self.evaluator_run(
            run_id="model",
            evaluator_id=(
                "semantic-v1"
            ),
            evaluator_family=(
                "semantic_model"
            ),
            derivation_mode=(
                "model_assisted"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        "model-authority"
                    ),
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
                        "model_inference"
                    ),
                )
            ],
        )

        graph = self.evaluator_run(
            run_id="graph",
            evaluator_id=(
                "graph-v1"
            ),
            evaluator_family=(
                "provenance_graph"
            ),
            derivation_mode=(
                "machine_verified"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        "graph-authority"
                    ),
                    field=(
                        "authority_class"
                    ),
                    value="indirect",
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

        return (
            build_multi_evaluator_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    model,
                    graph,
                ],
            )
        )

    def verified_authority(
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
                    evidence_ids=[
                        "official-evidence"
                    ],
                    training_eligible=True,
                )
            ],
        )

        return (
            build_multi_evaluator_adjudication(
                claim_id="claim-1",
                evaluator_runs=[
                    verified
                ],
            )
        )

    def revision(
        self,
        adjudication=None,
        *,
        as_of=(
            "2026-08-15T05:00:00Z"
        ),
        trigger_type=(
            "initial_evaluation"
        ),
        trigger_evidence_ids=None,
        previous_revision=None,
    ):
        if adjudication is None:
            adjudication = (
                self.empty_adjudication()
            )

        return (
            build_adjudication_state_revision(
                adjudication=(
                    adjudication
                ),
                as_of=as_of,
                trigger_type=(
                    trigger_type
                ),
                trigger_evidence_ids=(
                    trigger_evidence_ids
                ),
                previous_revision=(
                    previous_revision
                ),
            )
        )

    def test_initial_revision_has_full_machine_state(
        self,
    ):
        result = self.revision()

        self.assertEqual(
            result[
                "version"
            ],
            (
                AUTOMATED_ADJUDICATION_STATE_VERSION
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
            len(
                result[
                    "transitions"
                ]
            ),
            len(
                MULTI_EVALUATOR_FIELDS
            ),
        )

        self.assertTrue(
            all(
                row[
                    "kind"
                ]
                == "initialized"
                for row
                in result[
                    "transitions"
                ]
            )
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "manual_corrections_are_rejected"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "state_transition_does_not_change_live_merit"
            ]
            is False
        )

    def test_manual_correction_is_rejected(
        self,
    ):
        corrected = (
            build_multi_evaluator_adjudication(
                claim_id="claim-1",
                evaluator_runs=[],
                corrections={
                    "stance": {
                        "value": "supports",
                        "reason": (
                            "manual override"
                        ),
                        "corrected_by": (
                            "reviewer"
                        ),
                        "corrected_at": (
                            "2026-08-15T05:00:00Z"
                        ),
                        "scope": (
                            "case_only"
                        ),
                    }
                },
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot contain corrected fields",
        ):
            self.revision(
                corrected
            )

    def test_trigger_evidence_ids_are_normalized(
        self,
    ):
        result = self.revision(
            trigger_type="evidence_added",
            trigger_evidence_ids=[
                "evidence-b",
                "evidence-a",
                "evidence-b",
                " evidence-a ",
            ],
        )

        self.assertEqual(
            result[
                "trigger"
            ][
                "evidence_ids"
            ],
            [
                "evidence-a",
                "evidence-b",
            ],
        )

    def test_evidence_trigger_requires_evidence_id(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "requires at least one evidence ID",
        ):
            self.revision(
                trigger_type=(
                    "evidence_verified"
                ),
            )

    def test_same_decision_state_has_no_transition(
        self,
    ):
        adjudication = (
            self.empty_adjudication()
        )

        first = self.revision(
            adjudication,
            trigger_type=(
                "initial_evaluation"
            ),
        )

        second = self.revision(
            adjudication,
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
            trigger_type=(
                "evidence_added"
            ),
            trigger_evidence_ids=[
                "new-evidence"
            ],
            previous_revision=first,
        )

        self.assertEqual(
            second[
                "transitions"
            ],
            [],
        )

        self.assertNotEqual(
            first[
                "revision_id"
            ],
            second[
                "revision_id"
            ],
        )

    def test_contested_can_become_machine_verified_gold(
        self,
    ):
        first = self.revision(
            self.contested_authority(),
        )

        second = self.revision(
            self.verified_authority(),
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
            trigger_type=(
                "evidence_verified"
            ),
            trigger_evidence_ids=[
                "official-evidence"
            ],
            previous_revision=first,
        )

        authority = second[
            "fields"
        ][
            "authority_class"
        ][
            "state"
        ]

        self.assertEqual(
            authority[
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            authority[
                "value"
            ],
            "direct",
        )

        self.assertTrue(
            authority[
                "training_reference_allowed"
            ]
        )

        transitions = {
            row[
                "field"
            ]: row
            for row
            in second[
                "transitions"
            ]
        }

        self.assertIn(
            "authority_class",
            transitions,
        )

        self.assertEqual(
            transitions[
                "authority_class"
            ][
                "from_state"
            ][
                "tier"
            ],
            "contested",
        )

        self.assertEqual(
            transitions[
                "authority_class"
            ][
                "to_state"
            ][
                "tier"
            ],
            "auto_gold",
        )

    def test_backdated_revision_is_rejected(
        self,
    ):
        first = self.revision(
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "cannot move backward in time",
        ):
            self.revision(
                as_of=(
                    "2026-08-15T05:00:00Z"
                ),
                previous_revision=first,
            )

    def test_previous_revision_claim_must_match(
        self,
    ):
        previous = self.revision(
            self.empty_adjudication(
                claim_id="claim-other"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "different claim",
        ):
            self.revision(
                previous_revision=(
                    previous
                )
            )

    def test_revision_identity_is_deterministic(
        self,
    ):
        adjudication = (
            self.verified_authority()
        )

        first = self.revision(
            adjudication,
            trigger_type=(
                "evidence_verified"
            ),
            trigger_evidence_ids=[
                "evidence-b",
                "evidence-a",
            ],
        )

        second = self.revision(
            adjudication,
            trigger_type=(
                "evidence_verified"
            ),
            trigger_evidence_ids=[
                "evidence-a",
                "evidence-b",
                "evidence-a",
            ],
        )

        self.assertEqual(
            first[
                "revision_id"
            ],
            second[
                "revision_id"
            ],
        )

        self.assertEqual(
            first[
                "adjudication_sha256"
            ],
            second[
                "adjudication_sha256"
            ],
        )


if __name__ == "__main__":
    unittest.main()
