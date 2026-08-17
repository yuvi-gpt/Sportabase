from __future__ import annotations

import unittest

from app.intelligence import canonical_claims
from app.intelligence import partial_claim_semantics as partial


class TestPartialClaimSemanticsContract(unittest.TestCase):
    def test_01_policy_marks_partial_as_non_identity(self):
        self.assertTrue(
            partial.PARTIAL_SEMANTICS_POLICY[
                "partial_semantics_are_not_claim_identity"
            ]
        )

    def test_02_policy_forbids_partial_fingerprints(self):
        self.assertTrue(
            partial.PARTIAL_SEMANTICS_POLICY[
                "partial_semantics_never_mint_fingerprints"
            ]
        )

    def test_03_policy_forbids_same_claim_establishment(self):
        self.assertFalse(
            partial.PARTIAL_SEMANTICS_POLICY[
                "partial_semantics_can_establish_same_claim"
            ]
        )

    def test_04_policy_requires_full_identity_for_acceptance(self):
        self.assertTrue(
            partial.PARTIAL_SEMANTICS_POLICY[
                "full_identity_required_for_acceptance"
            ]
        )

    def test_05_policy_requires_structural_conflict_for_exclusion(self):
        self.assertTrue(
            partial.PARTIAL_SEMANTICS_POLICY[
                "structural_conflict_required_for_exclusion"
            ]
        )

    def test_06_absence_of_conflict_is_not_equivalence(self):
        self.assertTrue(
            partial.PARTIAL_SEMANTICS_POLICY[
                "absence_of_conflict_is_not_equivalence"
            ]
        )

    def test_07_no_fuzzy_similarity(self):
        self.assertFalse(
            partial.PARTIAL_SEMANTICS_POLICY[
                "fuzzy_similarity_used"
            ]
        )

    def test_08_no_model_equivalence_authority(self):
        self.assertFalse(
            partial.PARTIAL_SEMANTICS_POLICY[
                "model_equivalence_decision_used"
            ]
        )

    def test_09_no_truth_authority_or_merit(self):
        policy = partial.PARTIAL_SEMANTICS_POLICY
        self.assertFalse(policy["establishes_truth"])
        self.assertFalse(policy["establishes_authority"])
        self.assertFalse(policy["affects_live_merit"])

    def test_10_no_independence_or_corroboration(self):
        policy = partial.PARTIAL_SEMANTICS_POLICY
        self.assertFalse(policy["establishes_independence"])
        self.assertFalse(policy["establishes_corroboration"])

    def test_11_schema_derives_all_locked_event_types(self):
        schema = partial.partial_semantic_candidate_schema()
        self.assertEqual(
            set(schema["events"]),
            set(canonical_claims.EVENT_RULES),
        )

    def test_12_schema_reuses_locked_forbidden_fields(self):
        schema = partial.partial_semantic_candidate_schema()
        self.assertEqual(
            set(schema["forbidden_identity_fields"]),
            set(canonical_claims.FORBIDDEN_IDENTITY_FIELDS),
        )


if __name__ == "__main__":
    unittest.main()
