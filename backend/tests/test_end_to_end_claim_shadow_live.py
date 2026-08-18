from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.intelligence import claim_semantic_extraction_router as router
from evals import end_to_end_claim_shadow_live as live


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeGenerator:
    def __init__(self, payload=None):
        self.payload = (
            payload
            if payload is not None
            else fusion_payload()
        )
        self.calls = []
        self.event_sink = None

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return FakeResponse(
            json.dumps(self.payload)
        )

    def summary(self):
        return {
            "max_calls": 1,
            "call_count": len(self.calls),
            "remaining_calls": max(
                0,
                1 - len(self.calls),
            ),
            "prompt_tokens": 300,
            "output_tokens": 80,
            "thought_tokens": 120,
            "cached_tokens": 0,
            "total_tokens": 500,
            "calls_by_mode": {
                live.LIVE_MODE: len(
                    self.calls
                )
            },
            "calls_by_model": {
                live.LIVE_MODEL: len(
                    self.calls
                )
            },
            "calls_by_eval_client": {
                live.CLIENT_KEY: len(
                    self.calls
                )
            },
            "call_log": [
                {
                    "call_index": index + 1,
                    "usage_id": 999 + index,
                    "mode": call["mode"],
                    "model": call["model"],
                    "status": "completed",
                    "prompt_tokens": 300,
                    "output_tokens": 80,
                    "thought_tokens": 120,
                    "cached_tokens": 0,
                    "total_tokens": 500,
                }
                for index, call in enumerate(
                    self.calls
                )
            ],
        }


def structured_output():
    return {
        "version": (
            router
            .CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION
        ),
        "status": "partial",
        "candidate": {
            "subject_key": live.SUBJECT_KEY,
            "event_type": "match_event",
            "state": "scored",
            "negated": False,
            "roles": {},
            "facets": {},
        },
        "reason": (
            "The exact league match is not identified."
        ),
    }


def fusion_payload():
    return {
        "alignment_assessments": [],
        "claim_candidates": [
            {
                "text": live.SOURCE_TEXT,
                "confidence": 0.92,
                "source_artifact_ids": [
                    "source:text"
                ],
                "modality_sources": [
                    "text"
                ],
                "uncertainty": (
                    "The exact match is not specified."
                ),
                "structured_claim_output": (
                    structured_output()
                ),
            }
        ],
    }


class EndToEndClaimShadowLiveTests(unittest.TestCase):
    def test_01_version(self):
        self.assertEqual(
            live.END_TO_END_CLAIM_SHADOW_LIVE_VERSION,
            "end-to-end-claim-shadow-live-v1",
        )

    def test_02_exact_one_call(self):
        self.assertEqual(
            live.EXACT_PROVIDER_CALLS,
            1,
        )

    def test_03_reuses_multimodal_fusion_mode(self):
        self.assertEqual(
            live.LIVE_MODE,
            "multimodal_fusion",
        )

    def test_04_uses_fresh_named_client_bucket(self):
        self.assertEqual(
            live.CLIENT_KEY,
            "eval-claim-shadow-e2e:bellingham:partial-match-event",
        )

    def test_05_live_source_is_frozen(self):
        self.assertEqual(
            live.live_input(),
            "Jude Bellingham scored in a league match.",
        )

    def test_06_subject_is_bellingham(self):
        self.assertEqual(
            live.SUBJECT_KEY,
            "player|jude_bellingham",
        )

    def test_07_context_contains_subject(self):
        value = live.structured_context()
        self.assertEqual(
            value["subject_key"],
            live.SUBJECT_KEY,
        )

    def test_08_context_allowlist_contains_subject(self):
        value = live.structured_context()
        self.assertIn(
            live.SUBJECT_KEY,
            value["allowed_entity_keys"],
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.capacity_snapshot"
    )
    def test_09_preflight_requires_one_call(self, mocked):
        mocked.return_value = {"ready": True}
        value = live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertEqual(
            mocked.call_args.kwargs[
                "required_calls"
            ],
            1,
        )
        self.assertEqual(
            value["exact_provider_calls"],
            1,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.capacity_snapshot"
    )
    def test_10_preflight_caps_client_at_one(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertEqual(
            mocked.call_args.kwargs[
                "max_calls_per_client"
            ],
            1,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.capacity_snapshot"
    )
    def test_11_preflight_uses_fresh_client(self, mocked):
        mocked.return_value = {"ready": True}
        live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertEqual(
            mocked.call_args.kwargs[
                "client_keys"
            ],
            (live.CLIENT_KEY,),
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.capacity_snapshot"
    )
    def test_12_preflight_declares_no_second_call(self, mocked):
        mocked.return_value = {"ready": True}
        value = live.live_capacity_preflight(
            usage_connection_factory=object()
        )
        self.assertTrue(
            value["call_two_forbidden"]
        )
        self.assertFalse(
            value["additional_structured_call"]
        )

    def test_13_rejects_two_call_budget(self):
        with self.assertRaises(
            live.EndToEndClaimShadowLiveInputError
        ):
            live.evaluate_live_end_to_end_claim_shadow(
                api_key="x",
                usage_connection_factory=object(),
                max_calls=2,
                client=object(),
            )

    def test_14_requires_key_or_client(self):
        with self.assertRaises(
            live.EndToEndClaimShadowLiveInputError
        ):
            live.evaluate_live_end_to_end_claim_shadow(
                api_key="",
                usage_connection_factory=object(),
                client=None,
            )

    def test_15_requires_usage_db_or_factory(self):
        with self.assertRaises(
            live.EndToEndClaimShadowLiveInputError
        ):
            live.evaluate_live_end_to_end_claim_shadow(
                api_key="x",
                usage_db_path=None,
                usage_connection_factory=None,
                client=object(),
            )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_16_fake_live_path_uses_exactly_one_call(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator()
        live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=generator,
        )
        self.assertEqual(
            len(generator.calls),
            1,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_17_fake_live_path_reuses_fusion_mode(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator()
        live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=generator,
        )
        self.assertEqual(
            generator.calls[0]["mode"],
            "multimodal_fusion",
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_18_fake_live_path_uses_fresh_client(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator()
        live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=generator,
        )
        self.assertEqual(
            generator.calls[0]["client_key"],
            live.CLIENT_KEY,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_19_structured_prompt_is_larger_than_base(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        measurement = report["prompt_measurement"]
        self.assertGreater(
            measurement["structured_prompt_chars"],
            measurement["base_prompt_chars"],
        )
        self.assertGreater(
            measurement["prompt_char_delta"],
            0,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_20_prompt_measurement_stores_no_raw_prompt(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertFalse(
            report["prompt_measurement"]["raw_prompt_stored"]
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_21_fake_live_quality_passes(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertEqual(
            report["quality"],
            {"status": "pass", "failures": []},
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_22_fake_live_hard_safety_passes(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertEqual(
            report["hard_safety"]["status"],
            "pass",
        )
        self.assertTrue(
            report["hard_safety"]["production_plan_unchanged"]
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_23_fake_live_sidecar_is_auto_collected(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        summary = report["shadow"]["structured_input"]
        self.assertEqual(
            summary["source"],
            "semantic_manifest_sidecar",
        )
        self.assertEqual(
            summary["provided_count"],
            1,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_24_fake_live_routes_partial_match_event(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        row = report["shadow"]["candidate_rows"][0]
        self.assertEqual(row["router_status"], "partial")
        self.assertEqual(row["route"], "partial_semantics")
        self.assertEqual(row["candidate"]["event_type"], "match_event")
        self.assertEqual(row["candidate"]["state"], "scored")

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_25_partial_receives_no_fingerprint(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        row = report["shadow"]["candidate_rows"][0]
        self.assertEqual(row["core_fingerprint"], "")
        self.assertEqual(row["specific_fingerprint"], "")
        self.assertIn(
            "facets.event_key",
            row["missing_identity_fields"],
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_26_shadow_has_no_authority(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        shadow = report["shadow"]
        for field in (
            "persistence_allowed",
            "replaces_production_identity",
            "story_membership_allowed",
            "corroboration_allowed",
            "live_merit_effect",
            "raw_model_outputs_stored",
        ):
            self.assertFalse(shadow[field], field)

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_27_report_stores_no_raw_provider_response(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertFalse(
            report["policy"]["raw_provider_response_stored"]
        )
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn(
            "alignment_assessments",
            serialized,
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_28_malformed_model_output_is_measured_not_authority(self, preflight):
        preflight.return_value = {"ready": True}
        generator = FakeGenerator(
            payload={
                "alignment_assessments": [],
                "claim_candidates": [
                    {
                        "text": live.SOURCE_TEXT,
                        "confidence": 0.8,
                        "source_artifact_ids": ["source:text"],
                        "modality_sources": ["text"],
                        "uncertainty": "",
                        "structured_claim_output": {
                            "version": "wrong",
                            "status": "partial",
                            "candidate": {},
                            "reason": "bad",
                        },
                    }
                ],
            }
        )
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=generator,
        )
        self.assertEqual(report["quality"]["status"], "fail")
        self.assertEqual(report["hard_safety"]["status"], "pass")
        self.assertFalse(report["policy"]["affects_live_merit"])

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_29_report_has_digest(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertRegex(
            report["report_digest"],
            r"^[0-9a-f]{64}$",
        )

    @patch(
        "evals.end_to_end_claim_shadow_live.live_capacity_preflight"
    )
    def test_30_policy_forbids_call_two(self, preflight):
        preflight.return_value = {"ready": True}
        report = live.evaluate_live_end_to_end_claim_shadow(
            api_key="x",
            usage_connection_factory=object(),
            client=object(),
            generator=FakeGenerator(),
        )
        self.assertTrue(
            report["policy"]["call_two_forbidden"]
        )
        self.assertFalse(
            report["policy"]["additional_structured_provider_call"]
        )


if __name__ == "__main__":
    unittest.main()
