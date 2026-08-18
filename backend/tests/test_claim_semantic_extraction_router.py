from __future__ import annotations

import json
import unittest

from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import partial_claim_semantics


BELLINGHAM = "football|player|jude-bellingham"
REAL_MADRID = "football|club|real-madrid"
DORTMUND = "football|club|borussia-dortmund"

ALLOWED_KEYS = [
    BELLINGHAM,
    REAL_MADRID,
    DORTMUND,
]

ALLOWED_ENTITIES = {
    BELLINGHAM: {
        "canonical_name": "Jude Bellingham",
        "entity_type": "player",
    },
    REAL_MADRID: {
        "canonical_name": "Real Madrid",
        "entity_type": "club",
    },
    DORTMUND: {
        "canonical_name": "Borussia Dortmund",
        "entity_type": "club",
    },
}


def envelope(status, candidate, reason=""):
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": status,
        "candidate": candidate,
        "reason": reason,
    }


def parse(status, candidate, reason=""):
    return router.parse_claim_semantic_extraction_router_output(
        envelope(status, candidate, reason),
        expected_subject_key=BELLINGHAM,
        allowed_entity_keys=ALLOWED_KEYS,
    )


def full_transfer(**overrides):
    value = {
        "subject_key": BELLINGHAM,
        "event_type": "transfer",
        "state": "completed",
        "negated": False,
        "roles": {
            "destination": REAL_MADRID,
        },
        "facets": {
            "effective_period": "2023",
        },
    }
    value.update(overrides)
    return value


class TestClaimSemanticExtractionRouter(unittest.TestCase):
    def test_01_schema_has_three_statuses(self):
        schema = router.claim_semantic_extraction_router_schema()
        self.assertEqual(
            schema["output_statuses"],
            ["extracted", "partial", "insufficient"],
        )

    def test_02_extracted_routes_to_full_identity(self):
        result = parse("extracted", full_transfer())
        self.assertEqual(result["route"], "full_identity")
        self.assertTrue(result["identity_complete"])

    def test_03_extracted_mints_locked_full_fingerprints(self):
        result = parse("extracted", full_transfer())
        self.assertTrue(result["core_key"])
        self.assertTrue(result["core_fingerprint"])
        self.assertTrue(result["specific_fingerprint"])

    def test_04_extracted_normalizes_aliases(self):
        result = parse(
            "extracted",
            {
                "subject_key": BELLINGHAM,
                "event_type": "move",
                "state": "signed",
                "negated": False,
                "roles": {"to": REAL_MADRID},
                "facets": {},
            },
        )
        self.assertEqual(result["candidate"]["event_type"], "transfer")
        self.assertEqual(result["candidate"]["state"], "completed")

    def test_05_partial_routes_to_partial_semantics(self):
        result = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "match_event",
                "state": "goal",
                "negated": False,
                "roles": {},
                "facets": {},
            },
        )
        self.assertEqual(result["route"], "partial_semantics")
        self.assertFalse(result["identity_complete"])

    def test_06_partial_normalizes_goal_to_scored(self):
        result = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "match_event",
                "state": "goal",
                "roles": {},
                "facets": {},
            },
        )
        self.assertEqual(result["candidate"]["state"], "scored")

    def test_07_partial_reports_missing_identity_fields(self):
        result = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "match_event",
                "state": "scored",
                "roles": {},
                "facets": {},
            },
        )
        self.assertEqual(
            result["missing_identity_fields"],
            ["facets.event_key"],
        )

    def test_08_partial_never_mints_fingerprints(self):
        result = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "transfer",
                "state": "completed",
                "roles": {},
                "facets": {},
            },
        )
        self.assertEqual(result["core_key"], "")
        self.assertEqual(result["core_fingerprint"], "")
        self.assertEqual(result["specific_fingerprint"], "")

    def test_09_insufficient_routes_nowhere(self):
        result = parse(
            "insufficient",
            None,
            "No supported structured event can be established.",
        )
        self.assertEqual(result["route"], "none")
        self.assertIsNone(result["candidate"])

    def test_10_insufficient_requires_reason(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("insufficient", None, "")

    def test_11_insufficient_rejects_candidate(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("insufficient", {"event_type": "transfer"}, "vague")

    def test_12_extracted_rejects_incomplete_candidate(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse(
                "extracted",
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "transfer",
                    "state": "completed",
                    "roles": {},
                    "facets": {},
                },
            )

    def test_13_partial_rejects_complete_candidate(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("partial", full_transfer())

    def test_14_partial_rejects_wrong_subject(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse(
                "partial",
                {
                    "subject_key": REAL_MADRID,
                    "event_type": "match_event",
                    "state": "scored",
                    "roles": {},
                    "facets": {},
                },
            )

    def test_15_extracted_rejects_wrong_subject(self):
        candidate = full_transfer(subject_key=REAL_MADRID)
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("extracted", candidate)

    def test_16_partial_rejects_invented_entity(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse(
                "partial",
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "transfer",
                    "state": "completed",
                    "roles": {
                        "destination": "football|club|invented",
                    },
                    "facets": {},
                },
            )

    def test_17_extracted_rejects_invented_entity(self):
        candidate = full_transfer(
            roles={"destination": "football|club|invented"}
        )
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("extracted", candidate)

    def test_18_partial_rejects_unknown_event(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse(
                "partial",
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "transfer_vibes",
                    "state": "completed",
                    "roles": {},
                    "facets": {},
                },
            )

    def test_19_extracted_rejects_unknown_event(self):
        candidate = full_transfer(event_type="transfer_vibes")
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("extracted", candidate)

    def test_20_partial_rejects_forbidden_truth_field(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse(
                "partial",
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "match_event",
                    "state": "scored",
                    "roles": {},
                    "facets": {},
                    "truth": True,
                },
            )

    def test_21_extracted_rejects_forbidden_truth_field(self):
        candidate = full_transfer()
        candidate["truth"] = True
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("extracted", candidate)

    def test_22_rejects_unknown_envelope_field(self):
        payload = envelope("insufficient", None, "vague")
        payload["confidence"] = 0.9
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            router.parse_claim_semantic_extraction_router_output(
                payload,
                expected_subject_key=BELLINGHAM,
                allowed_entity_keys=ALLOWED_KEYS,
            )

    def test_23_rejects_bad_version(self):
        payload = envelope("insufficient", None, "vague")
        payload["version"] = "bad-version"
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            router.parse_claim_semantic_extraction_router_output(
                payload,
                expected_subject_key=BELLINGHAM,
                allowed_entity_keys=ALLOWED_KEYS,
            )

    def test_24_rejects_unknown_status(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            parse("maybe", None, "unknown")

    def test_25_accepts_fenced_json(self):
        payload = envelope(
            "insufficient",
            None,
            "No supported event.",
        )
        raw = "```json\n" + json.dumps(payload) + "\n```"
        result = router.parse_claim_semantic_extraction_router_output(
            raw,
            expected_subject_key=BELLINGHAM,
            allowed_entity_keys=ALLOWED_KEYS,
        )
        self.assertEqual(result["status"], "insufficient")

    def test_26_rejects_malformed_json(self):
        with self.assertRaises(router.ClaimSemanticExtractionRouterOutputError):
            router.parse_claim_semantic_extraction_router_output(
                "{bad",
                expected_subject_key=BELLINGHAM,
                allowed_entity_keys=ALLOWED_KEYS,
            )

    def test_27_bellingham_hard_negative_is_partial_and_safely_excludable(self):
        anchor = parse("extracted", full_transfer())
        negative = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "match_event",
                "state": "scored",
                "roles": {},
                "facets": {},
            },
        )
        comparison = partial_claim_semantics.compare_full_claim_to_partial_semantics(
            anchor["candidate"],
            negative["candidate"],
            allowed_entity_keys=ALLOWED_KEYS,
        )
        self.assertEqual(comparison["status"], "structurally_incompatible")
        self.assertTrue(comparison["safe_exclusion"])
        self.assertFalse(comparison["safe_acceptance"])

    def test_28_incomplete_matching_transfer_remains_undetermined(self):
        anchor = parse("extracted", full_transfer())
        partial = parse(
            "partial",
            {
                "subject_key": BELLINGHAM,
                "event_type": "transfer",
                "state": "completed",
                "roles": {},
                "facets": {},
            },
        )
        comparison = partial_claim_semantics.compare_full_claim_to_partial_semantics(
            anchor["candidate"],
            partial["candidate"],
            allowed_entity_keys=ALLOWED_KEYS,
        )
        self.assertEqual(comparison["status"], "undetermined")
        self.assertFalse(comparison["safe_exclusion"])
        self.assertFalse(comparison["safe_acceptance"])

    def test_29_prompt_contains_three_way_rules(self):
        prompt = router.build_claim_semantic_extraction_router_prompt(
            claim_text="Jude Bellingham later scored in a league match.",
            subject_key=BELLINGHAM,
            allowed_entities=ALLOWED_ENTITIES,
        )
        self.assertIn("extracted —", prompt)
        self.assertIn("partial —", prompt)
        self.assertIn("insufficient —", prompt)
        self.assertIn("Do not invent", prompt)
        self.assertIn("NEVER establish same-claim membership", prompt)

    def test_30_request_descriptor_is_zero_provider(self):
        descriptor = router.extraction_router_request_descriptor(
            claim_text="Jude Bellingham signed for Real Madrid.",
            subject_key=BELLINGHAM,
            allowed_entities=ALLOWED_ENTITIES,
        )
        self.assertFalse(descriptor["provider_call_performed"])
        self.assertFalse(descriptor["provider_required"])
        self.assertEqual(
            descriptor["output_statuses"],
            ["extracted", "partial", "insufficient"],
        )


if __name__ == "__main__":
    unittest.main()
