from __future__ import annotations

import unittest
from unittest.mock import patch

from evals import claim_semantic_extraction_router_live as live


class TestClaimSemanticExtractionRouterLiveFixture(unittest.TestCase):
    def test_version_is_v1(self):
        self.assertEqual(
            live.CLAIM_SEMANTIC_EXTRACTION_ROUTER_LIVE_VERSION,
            "claim-semantic-extraction-router-live-v1",
        )

    def test_exact_provider_calls_is_one(self):
        self.assertEqual(live.EXACT_PROVIDER_CALLS, 1)

    def test_client_key_is_dedicated_to_35f_hard_negative(self):
        self.assertEqual(
            live.CLIENT_KEY,
            "eval35f:bellingham:hard-negative",
        )

    def test_live_input_is_frozen_bellingham_hard_negative(self):
        self.assertEqual(
            live.live_input(),
            "Jude Bellingham later scored in a league match, a different claim from his transfer.",
        )

    def test_deterministic_anchor_is_completed_real_madrid_transfer(self):
        anchor = live.deterministic_anchor()
        self.assertEqual(anchor["event_type"], "transfer")
        self.assertEqual(anchor["state"], "completed")
        self.assertEqual(
            anchor["roles"]["destination"],
            live.REAL_MADRID_KEY,
        )

    def test_allowed_entities_are_frozen_three_entity_set(self):
        self.assertEqual(
            set(live.ALLOWED_ENTITIES),
            {
                live.SUBJECT_KEY,
                live.REAL_MADRID_KEY,
                live.DORTMUND_KEY,
            },
        )


class TestClaimSemanticExtractionRouterLiveScoring(unittest.TestCase):
    def _partial_row(self):
        return {
            "label": live.SOURCE_LABEL,
            "status": "partial",
            "route": "partial_semantics",
            "reason": "match event known; exact match unknown",
            "candidate": {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "match_event",
                "state": "scored",
                "negated": False,
                "roles": {},
                "facets": {},
            },
            "identity_complete": False,
            "missing_identity_fields": ["facets.event_key"],
            "core_key": "",
            "core_fingerprint": "",
            "specific_fingerprint": "",
            "safe_acceptance": False,
            "safe_exclusion": False,
            "raw_provider_response_stored": False,
        }

    def test_invalid_output_safe_row_does_not_store_raw_response(self):
        row = live._safe_route_row(
            parsed=None,
            error=ValueError("bad"),
        )
        self.assertEqual(row["status"], "invalid_output")
        self.assertIsNone(row["candidate"])
        self.assertFalse(row["raw_provider_response_stored"])

    def test_safe_route_row_preserves_partial_without_fingerprints(self):
        parsed = {
            "status": "partial",
            "route": "partial_semantics",
            "candidate": self._partial_row()["candidate"],
            "identity_complete": False,
            "missing_identity_fields": ["facets.event_key"],
            "core_key": "",
            "core_fingerprint": "",
            "specific_fingerprint": "",
            "safe_acceptance": False,
            "safe_exclusion": False,
        }
        row = live._safe_route_row(parsed=parsed)
        self.assertEqual(row["status"], "partial")
        self.assertEqual(row["core_fingerprint"], "")
        self.assertEqual(row["specific_fingerprint"], "")

    def test_partial_comparison_is_structurally_incompatible(self):
        result = live._comparison(self._partial_row())
        self.assertEqual(result["kind"], "full_vs_partial")
        self.assertEqual(result["status"], "structurally_incompatible")
        self.assertEqual(result["structural_conflicts"], ["event_type"])
        self.assertTrue(result["safe_exclusion"])
        self.assertFalse(result["safe_acceptance"])

    def test_full_hard_negative_comparison_is_different_core(self):
        row = {
            "route": "full_identity",
            "candidate": {
                "subject_key": live.SUBJECT_KEY,
                "event_type": "match_event",
                "state": "scored",
                "roles": {},
                "facets": {"event_key": "football|match|known-match"},
            },
        }
        result = live._comparison(row)
        self.assertEqual(result["kind"], "full_vs_full")
        self.assertEqual(result["status"], "different_core")
        self.assertFalse(result["same_core"])

    def test_insufficient_route_is_not_comparable(self):
        result = live._comparison(
            {
                "route": "none",
                "candidate": None,
            }
        )
        self.assertEqual(result["status"], "not_comparable")
        self.assertFalse(result["safe_exclusion"])
        self.assertFalse(result["safe_acceptance"])

    def test_quality_passes_for_expected_partial_result(self):
        row = self._partial_row()
        quality = live._quality(row, live._comparison(row))
        self.assertEqual(quality, {"status": "pass", "failures": []})

    def test_quality_fails_when_hard_negative_is_not_partial(self):
        row = self._partial_row()
        row["status"] = "insufficient"
        quality = live._quality(row, live._comparison(row))
        self.assertIn("hard_negative_not_partial", quality["failures"])

    def test_quality_fails_for_wrong_event_type(self):
        row = self._partial_row()
        row["candidate"] = dict(row["candidate"])
        row["candidate"]["event_type"] = "transfer"
        comparison = {
            "status": "undetermined",
            "safe_exclusion": False,
            "safe_acceptance": False,
        }
        quality = live._quality(row, comparison)
        self.assertIn("hard_negative_event_type", quality["failures"])

    def test_quality_fails_for_wrong_state(self):
        row = self._partial_row()
        row["candidate"] = dict(row["candidate"])
        row["candidate"]["state"] = "assisted"
        quality = live._quality(row, live._comparison(row))
        self.assertIn("hard_negative_state", quality["failures"])

    def test_quality_fails_for_wrong_missing_identity_fields(self):
        row = self._partial_row()
        row["missing_identity_fields"] = ["state"]
        quality = live._quality(row, live._comparison(row))
        self.assertIn(
            "hard_negative_missing_identity_fields",
            quality["failures"],
        )

    def test_quality_fails_if_partial_received_fingerprint(self):
        row = self._partial_row()
        row["core_fingerprint"] = "forbidden"
        quality = live._quality(row, live._comparison(row))
        self.assertIn("partial_received_fingerprint", quality["failures"])

    def test_hard_safety_passes_for_expected_partial_exclusion(self):
        row = self._partial_row()
        safety = live._hard_safety(row, live._comparison(row))
        self.assertEqual(safety["status"], "pass")
        self.assertFalse(safety["affects_live_merit"])

    def test_hard_safety_fails_if_partial_receives_fingerprint(self):
        row = self._partial_row()
        row["specific_fingerprint"] = "forbidden"
        safety = live._hard_safety(row, live._comparison(row))
        self.assertEqual(safety["status"], "fail")
        self.assertIn("partial_received_fingerprint", safety["failures"])

    def test_hard_safety_fails_if_partial_safe_acceptance_is_enabled(self):
        row = self._partial_row()
        comparison = live._comparison(row)
        comparison["safe_acceptance"] = True
        safety = live._hard_safety(row, comparison)
        self.assertEqual(safety["status"], "fail")
        self.assertIn("partial_safe_acceptance_enabled", safety["failures"])

    def test_hard_safety_fails_if_full_hard_negative_merges_with_anchor(self):
        row = {
            "route": "full_identity",
            "candidate": live.deterministic_anchor(),
            "raw_provider_response_stored": False,
        }
        comparison = live._comparison(row)
        self.assertTrue(comparison["same_core"])
        safety = live._hard_safety(row, comparison)
        self.assertEqual(safety["status"], "fail")
        self.assertIn(
            "hard_negative_merged_with_transfer_anchor",
            safety["failures"],
        )

    def test_hard_safety_never_establishes_semantic_authorities(self):
        row = self._partial_row()
        safety = live._hard_safety(row, live._comparison(row))
        self.assertFalse(safety["establishes_truth"])
        self.assertFalse(safety["establishes_authority"])
        self.assertFalse(safety["establishes_reliability"])
        self.assertFalse(safety["establishes_independence"])
        self.assertFalse(safety["establishes_corroboration"])


class TestClaimSemanticExtractionRouterLiveCapacity(unittest.TestCase):
    @patch("evals.claim_semantic_extraction_router_live.capacity_snapshot")
    def test_preflight_requires_exactly_one_call(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertEqual(result["exact_provider_calls"], 1)
        self.assertEqual(mocked.call_args.kwargs["required_calls"], 1)

    @patch("evals.claim_semantic_extraction_router_live.capacity_snapshot")
    def test_preflight_uses_one_call_per_client(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertEqual(
            mocked.call_args.kwargs["max_calls_per_client"],
            1,
        )
        self.assertEqual(
            mocked.call_args.kwargs["client_keys"],
            (live.CLIENT_KEY,),
        )

    @patch("evals.claim_semantic_extraction_router_live.capacity_snapshot")
    def test_preflight_declares_call_two_forbidden(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertTrue(result["hard_negative_only"])
        self.assertFalse(result["positive_sources_recalled"])
        self.assertTrue(result["deterministic_anchor_only"])
        self.assertTrue(result["call_two_forbidden"])


class TestClaimSemanticExtractionRouterLiveValidation(unittest.TestCase):
    def test_evaluator_rejects_nonone_budget(self):
        with self.assertRaises(
            live.ClaimSemanticExtractionRouterLiveInputError
        ):
            live.evaluate_live_router_hard_negative(
                api_key="x",
                usage_connection_factory=object(),
                max_calls=2,
                client=object(),
            )

    def test_evaluator_requires_key_or_client(self):
        with self.assertRaises(
            live.ClaimSemanticExtractionRouterLiveInputError
        ):
            live.evaluate_live_router_hard_negative(
                api_key="",
                usage_connection_factory=object(),
                max_calls=1,
                client=None,
            )

    def test_evaluator_requires_usage_database_when_factory_absent(self):
        with self.assertRaises(
            live.ClaimSemanticExtractionRouterLiveInputError
        ):
            live.evaluate_live_router_hard_negative(
                api_key="x",
                usage_db_path=None,
                usage_connection_factory=None,
                max_calls=1,
                client=object(),
            )


if __name__ == "__main__":
    unittest.main()
