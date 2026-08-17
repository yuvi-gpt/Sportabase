from __future__ import annotations

import unittest

from app.intelligence import canonical_claim_extraction


class TestCanonicalClaimExtractionContract(unittest.TestCase):
    def setUp(self):
        self.schema = (
            canonical_claim_extraction
            .canonical_claim_extraction_schema()
        )

    def test_schema_version_is_locked(self):
        self.assertEqual(
            self.schema["version"],
            "canonical-claim-extraction-contract-v1",
        )

    def test_output_version_is_locked(self):
        self.assertEqual(
            self.schema["output_version"],
            "canonical-claim-extraction-output-v1",
        )

    def test_event_taxonomy_is_exact_initial_set(self):
        self.assertEqual(
            set(self.schema["events"]),
            {
                "transfer",
                "contract",
                "tenure",
                "retirement",
                "injury",
                "availability",
                "lineup",
                "match_result",
                "match_event",
                "championship",
                "disciplinary",
            },
        )

    def test_transfer_contract_requires_destination(self):
        transfer = self.schema["events"]["transfer"]
        self.assertEqual(
            transfer["required_roles"],
            ["destination"],
        )
        self.assertEqual(
            transfer["core_roles"],
            ["destination"],
        )

    def test_transfer_completed_is_allowed_state(self):
        self.assertIn(
            "completed",
            self.schema["events"]["transfer"]["states"],
        )

    def test_match_event_requires_event_key(self):
        event = self.schema["events"]["match_event"]
        self.assertEqual(
            event["required_facets"],
            ["event_key"],
        )
        self.assertEqual(
            event["core_facets"],
            ["event_key"],
        )

    def test_championship_requires_competition_and_period(self):
        event = self.schema["events"]["championship"]
        self.assertEqual(
            event["required_facets"],
            ["competition_key", "effective_period"],
        )

    def test_forbidden_identity_fields_include_safety_concepts(self):
        forbidden = set(
            self.schema["forbidden_identity_fields"]
        )
        self.assertTrue(
            {
                "truth",
                "authority",
                "reliability",
                "independence",
                "corroboration",
                "merit",
                "training_eligible",
                "confidence",
                "source_url",
                "provider",
                "model",
            }.issubset(forbidden)
        )

    def test_policy_is_non_authoritative(self):
        policy = self.schema["policy"]
        self.assertFalse(policy["establishes_truth"])
        self.assertFalse(policy["establishes_authority"])
        self.assertFalse(policy["establishes_independence"])
        self.assertFalse(policy["establishes_corroboration"])
        self.assertFalse(policy["affects_live_merit"])

    def test_policy_disallows_fuzzy_identity(self):
        policy = self.schema["policy"]
        self.assertFalse(
            policy["fuzzy_similarity_used"]
        )
        self.assertFalse(
            policy["model_equivalence_decision_used"]
        )

    def test_policy_requires_entity_allowlist(self):
        policy = self.schema["policy"]
        self.assertTrue(
            policy["entity_values_must_come_from_allowlist"]
        )
        self.assertTrue(
            policy["unknown_entity_fails_closed"]
        )

    def test_schema_generation_is_deterministic(self):
        again = (
            canonical_claim_extraction
            .canonical_claim_extraction_schema()
        )
        self.assertEqual(
            self.schema,
            again,
        )


if __name__ == "__main__":
    unittest.main()
