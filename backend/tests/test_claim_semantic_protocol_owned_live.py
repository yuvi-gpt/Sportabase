from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.intelligence import canonical_claims
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import partial_claim_semantics
from evals import claim_semantic_protocol_owned_live as live


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeGenerator:
    def __init__(self, text):
        self.text = text
        self.calls = []
        self.event_sink = None

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return FakeResponse(self.text)

    def summary(self):
        return {
            "max_calls": 1,
            "call_count": 1,
            "remaining_calls": 0,
            "prompt_tokens": 100,
            "output_tokens": 20,
            "thought_tokens": 30,
            "cached_tokens": 0,
            "total_tokens": 150,
            "calls_by_mode": {live.LIVE_MODE: 1},
            "calls_by_model": {live.LIVE_MODEL: 1},
            "calls_by_eval_client": {live.CLIENT_KEY: 1},
            "call_log": [
                {
                    "call_index": 1,
                    "usage_id": 999,
                    "mode": live.LIVE_MODE,
                    "model": live.LIVE_MODEL,
                    "status": "completed",
                    "prompt_tokens": 100,
                    "output_tokens": 20,
                    "thought_tokens": 30,
                    "cached_tokens": 0,
                    "total_tokens": 150,
                }
            ],
        }


def partial_payload(candidate_version=None):
    candidate = {
        "subject_key": live.SUBJECT_KEY,
        "event_type": "match_event",
        "state": "goal",
        "negated": False,
        "roles": {},
        "facets": {},
    }
    if candidate_version is not None:
        candidate["version"] = candidate_version
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": "partial",
        "candidate": candidate,
        "reason": "The exact match is not identified.",
    }


class Test35HFixture(unittest.TestCase):
    def test_01_version(self):
        self.assertEqual(
            live.CLAIM_SEMANTIC_PROTOCOL_OWNED_LIVE_VERSION,
            "claim-semantic-protocol-owned-live-v1",
        )

    def test_02_exact_provider_calls(self):
        self.assertEqual(live.EXACT_PROVIDER_CALLS, 1)

    def test_03_fresh_client_bucket(self):
        self.assertEqual(
            live.CLIENT_KEY,
            "eval35h:bellingham:hard-negative",
        )

    def test_04_mode(self):
        self.assertEqual(
            live.LIVE_MODE,
            "claim_semantic_protocol_owned_router",
        )

    def test_05_model(self):
        self.assertEqual(live.LIVE_MODEL, "gemini-3.5-flash")

    def test_06_source_label(self):
        self.assertEqual(live.SOURCE_LABEL, "hard_negative")

    def test_07_frozen_source(self):
        self.assertEqual(
            live.live_input(),
            "Jude Bellingham later scored in a league match, a different claim from his transfer.",
        )

    def test_08_anchor_is_full_transfer(self):
        anchor = live.deterministic_anchor()
        self.assertEqual(anchor["event_type"], "transfer")
        self.assertEqual(anchor["state"], "completed")
        self.assertEqual(
            anchor["roles"]["destination"],
            live.REAL_MADRID_KEY,
        )


class Test35HScoring(unittest.TestCase):
    def _partial_row(self):
        return {
            "label": "hard_negative",
            "status": "partial",
            "route": "partial_semantics",
            "reason": "",
            "candidate": {
                "version": partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
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
            "protocol_ownership": {
                "candidate_contract_version_supplied_by_model": True,
                "candidate_contract_version_removed_before_validation": True,
                "validator_assigned_candidate_contract_version": (
                    partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION
                ),
                "semantic_fields_rewritten": False,
                "status_rewritten": False,
                "reason_rewritten": False,
            },
            "raw_provider_response_stored": False,
        }

    def test_09_comparison_is_structurally_incompatible(self):
        result = live._comparison(self._partial_row())
        self.assertEqual(result["status"], "structurally_incompatible")

    def test_10_comparison_safe_exclusion(self):
        result = live._comparison(self._partial_row())
        self.assertTrue(result["safe_exclusion"])
        self.assertFalse(result["safe_acceptance"])

    def test_11_quality_passes_expected_partial(self):
        row = self._partial_row()
        result = live._quality(row, live._comparison(row))
        self.assertEqual(result, {"status": "pass", "failures": []})

    def test_12_quality_requires_protocol_metadata(self):
        row = self._partial_row()
        row["protocol_ownership"] = None
        result = live._quality(row, live._comparison(row))
        self.assertIn("protocol_ownership_missing", result["failures"])

    def test_13_quality_requires_no_semantic_rewrite(self):
        row = self._partial_row()
        row["protocol_ownership"]["semantic_fields_rewritten"] = True
        result = live._quality(row, live._comparison(row))
        self.assertIn("semantic_fields_rewritten", result["failures"])

    def test_14_quality_requires_no_status_rewrite(self):
        row = self._partial_row()
        row["protocol_ownership"]["status_rewritten"] = True
        result = live._quality(row, live._comparison(row))
        self.assertIn("status_rewritten", result["failures"])

    def test_15_quality_requires_partial_validator_version(self):
        row = self._partial_row()
        row["protocol_ownership"][
            "validator_assigned_candidate_contract_version"
        ] = "wrong"
        result = live._quality(row, live._comparison(row))
        self.assertIn("partial_validator_version_wrong", result["failures"])

    def test_16_hard_safety_passes_expected_partial(self):
        row = self._partial_row()
        result = live._hard_safety(row, live._comparison(row))
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["affects_live_merit"])

    def test_17_hard_safety_blocks_unremoved_model_version(self):
        row = self._partial_row()
        row["protocol_ownership"][
            "candidate_contract_version_removed_before_validation"
        ] = False
        result = live._hard_safety(row, live._comparison(row))
        self.assertEqual(result["status"], "fail")
        self.assertIn("model_candidate_version_not_removed", result["failures"])

    def test_18_safe_error_row_stores_no_raw_response(self):
        row = live._safe_route_row(parsed=None, error=ValueError("bad"))
        self.assertEqual(row["status"], "invalid_output")
        self.assertFalse(row["raw_provider_response_stored"])
        self.assertIsNone(row["candidate"])


class Test35HCapacity(unittest.TestCase):
    @patch("evals.claim_semantic_protocol_owned_live.capacity_snapshot")
    def test_19_preflight_requires_one_call(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(mocked.call_args.kwargs["required_calls"], 1)
        self.assertEqual(result["exact_provider_calls"], 1)

    @patch("evals.claim_semantic_protocol_owned_live.capacity_snapshot")
    def test_20_preflight_uses_fresh_client(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(
            mocked.call_args.kwargs["client_keys"],
            (live.CLIENT_KEY,),
        )

    @patch("evals.claim_semantic_protocol_owned_live.capacity_snapshot")
    def test_21_preflight_max_one_per_client(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(usage_connection_factory=object())
        self.assertEqual(mocked.call_args.kwargs["max_calls_per_client"], 1)

    @patch("evals.claim_semantic_protocol_owned_live.capacity_snapshot")
    def test_22_preflight_declares_same_prompt(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(usage_connection_factory=object())
        self.assertTrue(result["same_product35e_prompt"])
        self.assertTrue(result["protocol_ownership_is_product35g"])

    @patch("evals.claim_semantic_protocol_owned_live.capacity_snapshot")
    def test_23_preflight_forbids_call_two(self, mocked):
        mocked.return_value = {"ready": True}
        result = live.live_capacity_preflight(usage_connection_factory=object())
        self.assertTrue(result["call_two_forbidden"])


class Test35HEvaluator(unittest.TestCase):
    def test_24_rejects_nonone_budget(self):
        with self.assertRaises(live.ClaimSemanticProtocolOwnedLiveInputError):
            live.evaluate_live_protocol_owned_hard_negative(
                api_key="x",
                usage_connection_factory=object(),
                max_calls=2,
                client=object(),
            )

    def test_25_requires_key_or_client(self):
        with self.assertRaises(live.ClaimSemanticProtocolOwnedLiveInputError):
            live.evaluate_live_protocol_owned_hard_negative(
                api_key="",
                usage_connection_factory=object(),
                max_calls=1,
                client=None,
            )

    def test_26_requires_usage_db_or_factory(self):
        with self.assertRaises(live.ClaimSemanticProtocolOwnedLiveInputError):
            live.evaluate_live_protocol_owned_hard_negative(
                api_key="x",
                usage_db_path=None,
                usage_connection_factory=None,
                max_calls=1,
                client=object(),
            )

    @patch("evals.claim_semantic_protocol_owned_live.live_capacity_preflight")
    def test_27_protocol_owned_partial_passes_live_quality(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator(
            json.dumps(
                partial_payload(
                    canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION
                )
            )
        )
        report = live.evaluate_live_protocol_owned_hard_negative(
            api_key="x",
            usage_connection_factory=object(),
            max_calls=1,
            client=object(),
            generator=generator,
        )
        self.assertEqual(report["quality"]["status"], "pass")
        self.assertEqual(report["hard_safety"]["status"], "pass")
        self.assertEqual(report["extraction"]["status"], "partial")
        self.assertEqual(report["comparison"]["status"], "structurally_incompatible")

    @patch("evals.claim_semantic_protocol_owned_live.live_capacity_preflight")
    def test_28_provider_uses_exact_new_mode_and_client(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator(json.dumps(partial_payload()))
        live.evaluate_live_protocol_owned_hard_negative(
            api_key="x",
            usage_connection_factory=object(),
            max_calls=1,
            client=object(),
            generator=generator,
        )
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(generator.calls[0]["client_key"], live.CLIENT_KEY)
        self.assertEqual(generator.calls[0]["mode"], live.LIVE_MODE)
        self.assertEqual(generator.calls[0]["model"], live.LIVE_MODEL)

    @patch("evals.claim_semantic_protocol_owned_live.live_capacity_preflight")
    def test_29_report_declares_no_prompt_rewrite(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator(json.dumps(partial_payload()))
        report = live.evaluate_live_protocol_owned_hard_negative(
            api_key="x",
            usage_connection_factory=object(),
            max_calls=1,
            client=object(),
            generator=generator,
        )
        self.assertTrue(report["policy"]["same_product35e_prompt"])
        self.assertFalse(report["policy"]["prompt_rewritten_after_product35f"])
        self.assertTrue(report["policy"]["protocol_ownership_is_product35g"])

    @patch("evals.claim_semantic_protocol_owned_live.live_capacity_preflight")
    def test_30_quality_failure_is_measured_not_safety_authority(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator(
            json.dumps(
                {
                    "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
                    "status": "insufficient",
                    "candidate": None,
                    "reason": "No structured event.",
                }
            )
        )
        report = live.evaluate_live_protocol_owned_hard_negative(
            api_key="x",
            usage_connection_factory=object(),
            max_calls=1,
            client=object(),
            generator=generator,
        )
        self.assertEqual(report["quality"]["status"], "fail")
        self.assertEqual(report["hard_safety"]["status"], "pass")
        self.assertFalse(report["policy"]["affects_live_merit"])


if __name__ == "__main__":
    unittest.main()
