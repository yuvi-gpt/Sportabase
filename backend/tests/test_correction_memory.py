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


from app.analysis.adjudication_state import (
    build_adjudication_state_revision,
)

from app.analysis.correction_memory import (
    AUTOMATIC_CORRECTION_MEMORY_VERSION,
    build_automatic_correction_memory,
)

from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)


class AutomaticCorrectionMemoryTests(
    unittest.TestCase
):
    def judgment(
        self,
        *,
        row_id,
        value,
        evaluator_id,
        evaluator_family,
        basis_class,
        confidence=0.99,
        training_eligible=False,
    ):
        return {
            "id": row_id,
            "field": "authority_class",
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
                row_id
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

    def untrusted_gold(
        self,
        claim_id,
        *,
        value,
    ):
        run = self.evaluator_run(
            run_id=(
                f"{claim_id}-model-run"
            ),
            evaluator_id="semantic-v1",
            evaluator_family=(
                "semantic_model"
            ),
            derivation_mode=(
                "model_assisted"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        f"{claim_id}-model"
                    ),
                    value=value,
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

        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    run
                ],
            )
        )

    def trusted_gold(
        self,
        claim_id,
        *,
        value,
    ):
        run = self.evaluator_run(
            run_id=(
                f"{claim_id}-trusted-run"
            ),
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
                        f"{claim_id}-trusted"
                    ),
                    value=value,
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

        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    run
                ],
            )
        )

    def silver(
        self,
        claim_id,
        *,
        value,
    ):
        model = self.evaluator_run(
            run_id=(
                f"{claim_id}-model"
            ),
            evaluator_id="semantic-v1",
            evaluator_family=(
                "semantic_model"
            ),
            derivation_mode=(
                "model_assisted"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        f"{claim_id}-silver-model"
                    ),
                    value=value,
                    evaluator_id=(
                        "semantic-v1"
                    ),
                    evaluator_family=(
                        "semantic_model"
                    ),
                    basis_class=(
                        "model_inference"
                    ),
                    confidence=0.94,
                )
            ],
        )

        rule = self.evaluator_run(
            run_id=(
                f"{claim_id}-rule"
            ),
            evaluator_id="rule-v1",
            evaluator_family=(
                "claim_rule"
            ),
            derivation_mode=(
                "machine_verified"
            ),
            judgments=[
                self.judgment(
                    row_id=(
                        f"{claim_id}-silver-rule"
                    ),
                    value=value,
                    evaluator_id="rule-v1",
                    evaluator_family=(
                        "claim_rule"
                    ),
                    basis_class=(
                        "deterministic_rule"
                    ),
                    confidence=0.94,
                )
            ],
        )

        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[
                    model,
                    rule,
                ],
            )
        )

    def unresolved(
        self,
        claim_id,
    ):
        return (
            build_multi_evaluator_adjudication(
                claim_id=claim_id,
                evaluator_runs=[],
            )
        )

    def revision_pair(
        self,
        *,
        claim_id="claim-1",
        previous_adjudication,
        current_adjudication,
    ):
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
                    "evidence_verified"
                ),
                trigger_evidence_ids=[
                    (
                        f"{claim_id}-"
                        "official-evidence"
                    )
                ],
                previous_revision=(
                    previous
                ),
            )
        )

        return (
            previous,
            current,
        )

    def build_wrong_to_correct(
        self,
        claim_id="claim-1",
    ):
        previous, current = (
            self.revision_pair(
                claim_id=claim_id,
                previous_adjudication=(
                    self.untrusted_gold(
                        claim_id,
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        claim_id,
                        value="direct",
                    )
                ),
            )
        )

        return (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
            )
        )

    def test_version_and_policy(
        self,
    ):
        result = (
            self.build_wrong_to_correct()
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                AUTOMATIC_CORRECTION_MEMORY_VERSION
            ),
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "only_trusted_auto_gold_can_correct"
            ]
        )

        self.assertFalse(
            result[
                "policy"
            ][
                "human_review_required"
            ]
        )

    def test_untrusted_wrong_gold_to_trusted_gold_is_correction(
        self,
    ):
        result = (
            self.build_wrong_to_correct()
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "correction_count"
            ],
            1,
        )

        event = result[
            "corrections"
        ][0]

        self.assertEqual(
            event[
                "previous_state"
            ][
                "value"
            ],
            "indirect",
        )

        self.assertEqual(
            event[
                "corrected_state"
            ][
                "value"
            ],
            "direct",
        )

        self.assertTrue(
            event[
                "corrected_state"
            ][
                "training_reference_allowed"
            ]
        )

    def test_unresolved_to_gold_is_resolution_not_correction(
        self,
    ):
        previous, current = (
            self.revision_pair(
                previous_adjudication=(
                    self.unresolved(
                        "claim-1"
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        result = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
            )
        )

        self.assertEqual(
            result[
                "corrections"
            ],
            [],
        )

    def test_same_value_trust_upgrade_is_not_correction(
        self,
    ):
        previous, current = (
            self.revision_pair(
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        result = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
            )
        )

        self.assertEqual(
            result[
                "corrections"
            ],
            [],
        )

    def test_silver_wrong_value_to_trusted_gold_is_correction(
        self,
    ):
        previous, current = (
            self.revision_pair(
                previous_adjudication=(
                    self.silver(
                        "claim-1",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        result = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
            )
        )

        self.assertEqual(
            result[
                "summary"
            ][
                "correction_count"
            ],
            1,
        )

    def test_untrusted_new_value_cannot_correct(
        self,
    ):
        previous, current = (
            self.revision_pair(
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-1",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.silver(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        result = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
            )
        )

        self.assertEqual(
            result[
                "corrections"
            ],
            [],
        )

    def test_one_correction_remains_case_memory(
        self,
    ):
        result = (
            self.build_wrong_to_correct()
        )

        candidate = result[
            "memory_candidates"
        ][0]

        self.assertEqual(
            candidate[
                "status"
            ],
            "case_memory",
        )

        self.assertEqual(
            candidate[
                "support_count"
            ],
            1,
        )

        self.assertFalse(
            candidate[
                "eligible_for_automatic_global_rule"
            ]
        )

    def test_matching_corrections_across_two_claims_create_pattern_candidate(
        self,
    ):
        first = (
            self.build_wrong_to_correct(
                "claim-1"
            )
        )

        second_previous, second_current = (
            self.revision_pair(
                claim_id="claim-2",
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-2",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-2",
                        value="direct",
                    )
                ),
            )
        )

        second = (
            build_automatic_correction_memory(
                previous_revision=(
                    second_previous
                ),
                current_revision=(
                    second_current
                ),
                prior_correction_events=(
                    first[
                        "corrections"
                    ]
                ),
            )
        )

        candidate = (
            second[
                "memory_candidates"
            ][0]
        )

        self.assertEqual(
            candidate[
                "status"
            ],
            "pattern_candidate",
        )

        self.assertEqual(
            candidate[
                "support_count"
            ],
            2,
        )

        self.assertEqual(
            candidate[
                "supporting_claim_ids"
            ],
            [
                "claim-1",
                "claim-2",
            ],
        )

    def test_duplicate_same_claim_does_not_promote_pattern(
        self,
    ):
        first = (
            self.build_wrong_to_correct(
                "claim-1"
            )
        )

        event = copy.deepcopy(
            first[
                "corrections"
            ][0]
        )

        previous, current = (
            self.revision_pair(
                claim_id="claim-1",
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-1",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        result = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
                prior_correction_events=[
                    event
                ],
            )
        )

        candidate = (
            result[
                "memory_candidates"
            ][0]
        )

        self.assertEqual(
            candidate[
                "status"
            ],
            "case_memory",
        )

        self.assertEqual(
            candidate[
                "support_count"
            ],
            1,
        )

    def test_revision_chain_must_be_direct(
        self,
    ):
        previous, current = (
            self.revision_pair(
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-1",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-1",
                        value="direct",
                    )
                ),
            )
        )

        broken = copy.deepcopy(
            current
        )

        broken[
            "previous_revision_id"
        ] = "wrong-parent"

        with self.assertRaisesRegex(
            ValueError,
            "direct consecutive revisions",
        ):
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=broken,
            )

    def test_prior_event_order_is_deterministic(
        self,
    ):
        first = (
            self.build_wrong_to_correct(
                "claim-1"
            )
        )

        second = (
            self.build_wrong_to_correct(
                "claim-2"
            )
        )

        previous, current = (
            self.revision_pair(
                claim_id="claim-3",
                previous_adjudication=(
                    self.untrusted_gold(
                        "claim-3",
                        value="indirect",
                    )
                ),
                current_adjudication=(
                    self.trusted_gold(
                        "claim-3",
                        value="direct",
                    )
                ),
            )
        )

        forward = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
                prior_correction_events=[
                    first[
                        "corrections"
                    ][0],
                    second[
                        "corrections"
                    ][0],
                ],
            )
        )

        reverse = (
            build_automatic_correction_memory(
                previous_revision=previous,
                current_revision=current,
                prior_correction_events=[
                    second[
                        "corrections"
                    ][0],
                    first[
                        "corrections"
                    ][0],
                ],
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )


if __name__ == "__main__":
    unittest.main()
