from __future__ import annotations

import json
import unittest

from app.intelligence import canonical_claims
from app.intelligence import claim_semantic_extraction_router as router
from app.intelligence import claim_semantic_protocol_ownership as ownership
from app.intelligence import partial_claim_semantics


SUBJECT = "football|player|jude-bellingham"
REAL_MADRID = "football|club|real-madrid"
DORTMUND = "football|club|borussia-dortmund"
ALLOWED = [SUBJECT, REAL_MADRID, DORTMUND]


def envelope(status, candidate, reason=""):
    return {
        "version": router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
        "status": status,
        "candidate": candidate,
        "reason": reason,
    }


def partial_candidate(version=None):
    value = {
        "subject_key": SUBJECT,
        "event_type": "match_event",
        "state": "goal",
        "negated": False,
        "roles": {},
        "facets": {},
    }
    if version is not None:
        value["version"] = version
    return value


def full_candidate(version=None):
    value = {
        "subject_key": SUBJECT,
        "event_type": "transfer",
        "state": "completed",
        "negated": False,
        "roles": {"destination": REAL_MADRID},
        "facets": {"effective_period": "2023"},
    }
    if version is not None:
        value["version"] = version
    return value


class TestClaimSemanticProtocolOwnershipSanitizer(unittest.TestCase):
    def test_01_contract_version(self):
        self.assertEqual(
            ownership.CLAIM_SEMANTIC_PROTOCOL_OWNERSHIP_CONTRACT_VERSION,
            "claim-semantic-protocol-ownership-contract-v1",
        )

    def test_02_mapping_input_is_accepted(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", partial_candidate())
        )
        self.assertEqual(
            result["sanitized_envelope"]["status"],
            "partial",
        )

    def test_03_json_string_is_accepted(self):
        raw = json.dumps(envelope("partial", partial_candidate()))
        result = ownership.sanitize_model_protocol_metadata(raw)
        self.assertEqual(result["sanitized_envelope"]["status"], "partial")

    def test_04_fenced_json_is_accepted(self):
        raw = "```json\n" + json.dumps(envelope("partial", partial_candidate())) + "\n```"
        result = ownership.sanitize_model_protocol_metadata(raw)
        self.assertEqual(result["sanitized_envelope"]["status"], "partial")

    def test_05_canonical_candidate_version_is_removed(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope(
                "partial",
                partial_candidate(canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION),
            )
        )
        self.assertNotIn("version", result["sanitized_envelope"]["candidate"])
        self.assertTrue(result["candidate_contract_version_removed_before_validation"])

    def test_06_partial_candidate_version_is_removed(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope(
                "partial",
                partial_candidate(
                    partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION
                ),
            )
        )
        self.assertNotIn("version", result["sanitized_envelope"]["candidate"])

    def test_07_arbitrary_candidate_version_is_removed(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", partial_candidate("model-invented-version"))
        )
        self.assertNotIn("version", result["sanitized_envelope"]["candidate"])

    def test_08_case_variant_candidate_version_is_removed(self):
        candidate = partial_candidate()
        candidate["Version"] = "anything"
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", candidate)
        )
        self.assertNotIn("Version", result["sanitized_envelope"]["candidate"])

    def test_09_duplicate_normalized_candidate_versions_fail_closed(self):
        candidate = partial_candidate()
        candidate["version"] = "a"
        candidate["Version"] = "b"
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            ownership.sanitize_model_protocol_metadata(
                envelope("partial", candidate)
            )

    def test_10_wrong_outer_version_fails_closed(self):
        value = envelope("partial", partial_candidate())
        value["version"] = "wrong-outer-version"
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            ownership.sanitize_model_protocol_metadata(value)

    def test_11_missing_outer_version_fails_closed(self):
        value = envelope("partial", partial_candidate())
        value.pop("version")
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            ownership.sanitize_model_protocol_metadata(value)

    def test_12_malformed_json_fails_closed(self):
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            ownership.sanitize_model_protocol_metadata("{not json")

    def test_13_non_object_json_fails_closed(self):
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            ownership.sanitize_model_protocol_metadata("[]")

    def test_14_semantic_fields_are_preserved_by_sanitizer(self):
        candidate = partial_candidate("wrong")
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", candidate, "keep this reason")
        )["sanitized_envelope"]
        self.assertEqual(result["candidate"]["subject_key"], SUBJECT)
        self.assertEqual(result["candidate"]["event_type"], "match_event")
        self.assertEqual(result["candidate"]["state"], "goal")
        self.assertEqual(result["candidate"]["roles"], {})
        self.assertEqual(result["candidate"]["facets"], {})

    def test_15_status_is_not_rewritten_by_sanitizer(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", partial_candidate("wrong"))
        )
        self.assertEqual(result["sanitized_envelope"]["status"], "partial")

    def test_16_reason_is_not_rewritten_by_sanitizer(self):
        result = ownership.sanitize_model_protocol_metadata(
            envelope("partial", partial_candidate("wrong"), "exact reason")
        )
        self.assertEqual(result["sanitized_envelope"]["reason"], "exact reason")


class TestClaimSemanticProtocolOwnershipRouting(unittest.TestCase):
    def parse(self, value):
        return ownership.parse_protocol_owned_claim_semantic_output(
            value,
            expected_subject_key=SUBJECT,
            allowed_entity_keys=ALLOWED,
        )

    def test_17_exact_35f_failure_shape_now_routes_partial(self):
        result = self.parse(
            envelope(
                "partial",
                partial_candidate(canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION),
            )
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["route"], "partial_semantics")

    def test_18_exact_35f_failure_shape_normalizes_match_event(self):
        result = self.parse(
            envelope(
                "partial",
                partial_candidate(canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION),
            )
        )
        self.assertEqual(result["candidate"]["event_type"], "match_event")
        self.assertEqual(result["candidate"]["state"], "scored")

    def test_19_exact_35f_failure_shape_reports_missing_event_key(self):
        result = self.parse(
            envelope(
                "partial",
                partial_candidate(canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION),
            )
        )
        self.assertEqual(
            result["missing_identity_fields"],
            ["facets.event_key"],
        )

    def test_20_partial_validator_assigns_35d_version(self):
        result = self.parse(
            envelope("partial", partial_candidate("anything"))
        )
        self.assertEqual(
            result["candidate"]["version"],
            partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        )
        self.assertEqual(
            result["protocol_ownership"]["validator_assigned_candidate_contract_version"],
            partial_claim_semantics.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
        )

    def test_21_partial_never_receives_fingerprints(self):
        result = self.parse(
            envelope("partial", partial_candidate("anything"))
        )
        self.assertEqual(result["core_key"], "")
        self.assertEqual(result["core_fingerprint"], "")
        self.assertEqual(result["specific_fingerprint"], "")

    def test_22_extracted_wrong_nested_version_still_uses_full_validator(self):
        result = self.parse(
            envelope("extracted", full_candidate("model-version"))
        )
        self.assertEqual(result["status"], "extracted")
        self.assertEqual(result["route"], "full_identity")

    def test_23_extracted_validator_assigns_canonical_version(self):
        result = self.parse(
            envelope("extracted", full_candidate("model-version"))
        )
        self.assertEqual(
            result["candidate"]["version"],
            canonical_claims.CANONICAL_CLAIM_CONTRACT_VERSION,
        )

    def test_24_extracted_full_path_mints_deterministic_fingerprints(self):
        result = self.parse(
            envelope("extracted", full_candidate("model-version"))
        )
        self.assertTrue(result["core_fingerprint"])
        self.assertTrue(result["specific_fingerprint"])

    def test_25_candidate_without_version_still_parses(self):
        result = self.parse(
            envelope("partial", partial_candidate())
        )
        self.assertEqual(result["route"], "partial_semantics")
        self.assertFalse(
            result["protocol_ownership"]["candidate_contract_version_supplied_by_model"]
        )

    def test_26_insufficient_null_candidate_still_routes_none(self):
        result = self.parse(
            envelope("insufficient", None, "No structured event.")
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["route"], "none")


class TestClaimSemanticProtocolOwnershipFailClosed(unittest.TestCase):
    def parse(self, value):
        return ownership.parse_protocol_owned_claim_semantic_output(
            value,
            expected_subject_key=SUBJECT,
            allowed_entity_keys=ALLOWED,
        )

    def assertBlocked(self, value):
        with self.assertRaises(ownership.ClaimSemanticProtocolOwnershipOutputError):
            self.parse(value)

    def test_27_complete_candidate_plus_partial_still_blocked(self):
        self.assertBlocked(envelope("partial", full_candidate("wrong")))

    def test_28_incomplete_candidate_plus_extracted_still_blocked(self):
        candidate = full_candidate("wrong")
        candidate["roles"] = {}
        self.assertBlocked(envelope("extracted", candidate))

    def test_29_candidate_plus_insufficient_still_blocked(self):
        self.assertBlocked(
            envelope("insufficient", partial_candidate("wrong"), "reason")
        )

    def test_30_forbidden_truth_field_still_blocked(self):
        candidate = partial_candidate("wrong")
        candidate["truth"] = True
        self.assertBlocked(envelope("partial", candidate))

    def test_31_forbidden_authority_field_still_blocked(self):
        candidate = full_candidate("wrong")
        candidate["authority"] = "official"
        self.assertBlocked(envelope("extracted", candidate))

    def test_32_unknown_partial_semantic_field_still_blocked(self):
        candidate = partial_candidate("wrong")
        candidate["made_up_field"] = "x"
        self.assertBlocked(envelope("partial", candidate))

    def test_33_unknown_extracted_semantic_field_still_blocked(self):
        candidate = full_candidate("wrong")
        candidate["made_up_field"] = "x"
        self.assertBlocked(envelope("extracted", candidate))

    def test_34_invented_entity_still_blocked(self):
        candidate = full_candidate("wrong")
        candidate["roles"]["destination"] = "football|club|invented"
        self.assertBlocked(envelope("extracted", candidate))

    def test_35_wrong_subject_still_blocked(self):
        candidate = partial_candidate("wrong")
        candidate["subject_key"] = REAL_MADRID
        self.assertBlocked(envelope("partial", candidate))

    def test_36_unknown_event_still_blocked(self):
        candidate = partial_candidate("wrong")
        candidate["event_type"] = "made_up_event"
        self.assertBlocked(envelope("partial", candidate))

    def test_37_unknown_state_still_blocked(self):
        candidate = partial_candidate("wrong")
        candidate["state"] = "made_up_state"
        self.assertBlocked(envelope("partial", candidate))

    def test_38_unknown_outer_field_still_blocked(self):
        value = envelope("partial", partial_candidate("wrong"))
        value["surprise"] = True
        self.assertBlocked(value)

    def test_39_non_mapping_candidate_still_blocked(self):
        self.assertBlocked(envelope("partial", "not-an-object"))

    def test_40_partial_safe_acceptance_is_never_enabled(self):
        result = self.parse(envelope("partial", partial_candidate("wrong")))
        self.assertFalse(result["safe_acceptance"])
        self.assertFalse(
            result["policy"]["partial_semantics_can_establish_same_claim"]
        )


if __name__ == "__main__":
    unittest.main()
