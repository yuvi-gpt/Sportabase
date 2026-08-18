from __future__ import annotations

import unittest

from app.intelligence import canonical_claim_extraction
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import partial_claim_semantics


class TestClaimSemanticExtractionRouterContract(unittest.TestCase):
    def test_01_contract_version(self):
        self.assertEqual(
            router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_CONTRACT_VERSION,
            "claim-semantic-extraction-router-contract-v1",
        )

    def test_02_output_version(self):
        self.assertEqual(
            router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
            "claim-semantic-extraction-router-output-v1",
        )

    def test_03_statuses_are_exactly_three(self):
        schema = router.claim_semantic_extraction_router_schema()
        self.assertEqual(
            schema["output_statuses"],
            ["extracted", "partial", "insufficient"],
        )

    def test_04_full_contract_is_locked_35b_contract(self):
        schema = router.claim_semantic_extraction_router_schema()
        self.assertEqual(
            schema["full_extraction_contract"]["version"],
            canonical_claim_extraction.CANONICAL_CLAIM_EXTRACTION_CONTRACT_VERSION,
        )

    def test_05_partial_contract_is_locked_35d_contract(self):
        schema = router.claim_semantic_extraction_router_schema()
        self.assertEqual(
            schema["partial_semantics_contract"]["version"],
            partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        )

    def test_06_partial_never_mints_fingerprints(self):
        self.assertTrue(
            router.ROUTER_POLICY["partial_semantics_never_mint_fingerprints"]
        )
        self.assertTrue(router.ROUTER_POLICY["router_never_mints_identity"])

    def test_07_partial_never_establishes_same_claim(self):
        self.assertFalse(
            router.ROUTER_POLICY["partial_semantics_can_establish_same_claim"]
        )

    def test_08_status_mismatch_fails_closed(self):
        self.assertTrue(router.ROUTER_POLICY["status_mismatch_fails_closed"])
        self.assertTrue(
            router.ROUTER_POLICY["router_does_not_auto_upgrade_partial_to_full"]
        )
        self.assertTrue(
            router.ROUTER_POLICY["router_does_not_auto_downgrade_extracted_to_partial"]
        )

    def test_09_no_fuzzy_or_model_equivalence_authority(self):
        self.assertFalse(router.ROUTER_POLICY["fuzzy_similarity_used"])
        self.assertFalse(
            router.ROUTER_POLICY["model_equivalence_decision_used"]
        )

    def test_10_no_truth_authority_or_reliability(self):
        self.assertFalse(router.ROUTER_POLICY["establishes_truth"])
        self.assertFalse(router.ROUTER_POLICY["establishes_authority"])
        self.assertFalse(router.ROUTER_POLICY["establishes_reliability"])

    def test_11_no_independence_corroboration_or_merit(self):
        self.assertFalse(router.ROUTER_POLICY["establishes_independence"])
        self.assertFalse(router.ROUTER_POLICY["establishes_corroboration"])
        self.assertFalse(router.ROUTER_POLICY["affects_live_merit"])

    def test_12_not_training_eligible(self):
        self.assertFalse(router.ROUTER_POLICY["training_eligible"])


if __name__ == "__main__":
    unittest.main()
