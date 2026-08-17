from __future__ import annotations

import unittest

from app.intelligence import partial_claim_semantics as partial


BELLINGHAM = "football|player|jude-bellingham"
REAL_MADRID = "football|club|real-madrid"
DORTMUND = "football|club|borussia-dortmund"
BARCELONA = "football|club|barcelona"


class TestPartialClaimSemantics(unittest.TestCase):
    def setUp(self):
        self.allowed = [
            BELLINGHAM,
            REAL_MADRID,
            DORTMUND,
            BARCELONA,
        ]
        self.anchor = {
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
        self.partial_goal = {
            "subject_key": BELLINGHAM,
            "event_type": "match_event",
            "state": "scored",
            "negated": False,
            "roles": {},
            "facets": {},
        }

    def test_01_contract_version(self):
        self.assertEqual(
            partial.PARTIAL_CLAIM_SEMANTICS_CONTRACT_VERSION,
            "partial-claim-semantics-contract-v1",
        )

    def test_02_comparison_version(self):
        self.assertEqual(
            partial.PARTIAL_CLAIM_COMPARISON_VERSION,
            "partial-claim-comparison-v1",
        )

    def test_03_schema_contains_transfer(self):
        self.assertIn(
            "transfer",
            partial.partial_semantic_candidate_schema()["events"],
        )

    def test_04_schema_contains_match_event(self):
        self.assertIn(
            "match_event",
            partial.partial_semantic_candidate_schema()["events"],
        )

    def test_05_match_goal_without_event_key_is_incomplete(self):
        value = partial.normalize_partial_semantic_candidate(
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertFalse(value["identity_complete"])

    def test_06_match_goal_reports_missing_event_key(self):
        value = partial.normalize_partial_semantic_candidate(
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(
            value["missing_identity_fields"],
            ["facets.event_key"],
        )

    def test_07_partial_never_has_core_key(self):
        value = partial.normalize_partial_semantic_candidate(
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(value["core_key"], "")

    def test_08_partial_never_has_core_fingerprint(self):
        value = partial.normalize_partial_semantic_candidate(
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(value["core_fingerprint"], "")

    def test_09_partial_never_has_specific_fingerprint(self):
        value = partial.normalize_partial_semantic_candidate(
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(value["specific_fingerprint"], "")

    def test_10_goal_alias_normalizes_to_scored(self):
        candidate = dict(self.partial_goal)
        candidate["state"] = "goal"
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(value["state"], "scored")

    def test_11_race_event_alias_normalizes_to_match_event(self):
        candidate = dict(self.partial_goal)
        candidate["event_type"] = "race_event"
        candidate["state"] = "podium"
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(value["event_type"], "match_event")

    def test_12_transfer_role_alias_normalizes(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "",
            "roles": {"to": REAL_MADRID},
            "facets": {},
        }
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(
            value["roles"],
            {"destination": REAL_MADRID},
        )

    def test_13_invented_role_entity_is_rejected(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "",
            "roles": {"destination": "football|club|invented"},
            "facets": {},
        }
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_14_subject_outside_allowlist_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["subject_key"] = "football|player|invented"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_15_unknown_event_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["event_type"] = "transfer_vibes"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_16_unknown_state_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["state"] = "did_something"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_17_unknown_role_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["roles"] = {"mystery": REAL_MADRID}
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_18_unknown_facet_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["facets"] = {"mystery": "x"}
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_19_truth_field_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["truth"] = True
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_20_nonboolean_negated_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["negated"] = "false"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_21_unknown_top_level_field_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["extra"] = "x"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_22_wrong_contract_version_is_rejected(self):
        candidate = dict(self.partial_goal)
        candidate["version"] = "partial-claim-semantics-contract-v999"
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.normalize_partial_semantic_candidate(
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_23_complete_transfer_is_detected(self):
        value = partial.normalize_partial_semantic_candidate(
            self.anchor,
            allowed_entity_keys=self.allowed,
        )
        self.assertTrue(value["identity_complete"])

    def test_24_complete_transfer_is_rejected_from_partial_path(self):
        with self.assertRaises(partial.PartialClaimSemanticsCompleteError):
            partial.require_incomplete_partial_semantics(
                self.anchor,
                allowed_entity_keys=self.allowed,
            )

    def test_25_bellingham_goal_is_structurally_incompatible_with_transfer(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(
            result["status"],
            partial.STATUS_STRUCTURALLY_INCOMPATIBLE,
        )

    def test_26_bellingham_goal_conflict_is_event_type(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(result["structural_conflicts"], ["event_type"])

    def test_27_structural_incompatibility_allows_safe_exclusion(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertTrue(result["safe_exclusion"])

    def test_28_partial_semantics_never_allow_safe_acceptance(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertFalse(result["safe_acceptance"])

    def test_29_same_transfer_missing_destination_is_undetermined(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(result["status"], partial.STATUS_UNDETERMINED)

    def test_30_undetermined_does_not_allow_exclusion(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "completed",
            "roles": {},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertFalse(result["safe_exclusion"])

    def test_31_transfer_interest_conflicts_with_completed(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "interest",
            "roles": {},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertIn("state", result["structural_conflicts"])

    def test_32_different_destination_conflicts_when_provided(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "completed",
            "roles": {"destination": BARCELONA},
            "facets": {},
        }
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertTrue(value["identity_complete"])
        with self.assertRaises(partial.PartialClaimSemanticsCompleteError):
            partial.compare_full_claim_to_partial_semantics(
                self.anchor,
                candidate,
                allowed_entity_keys=self.allowed,
            )

    def test_33_conflicting_origin_can_exclude_incomplete_transfer(self):
        full = dict(self.anchor)
        full["roles"] = {
            "destination": REAL_MADRID,
            "origin": DORTMUND,
        }
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "",
            "roles": {"origin": BARCELONA},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            full,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertIn("roles.origin", result["structural_conflicts"])

    def test_34_nonconflicting_origin_without_destination_is_undetermined(self):
        full = dict(self.anchor)
        full["roles"] = {
            "destination": REAL_MADRID,
            "origin": DORTMUND,
        }
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "completed",
            "roles": {"origin": DORTMUND},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            full,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(result["status"], partial.STATUS_UNDETERMINED)

    def test_35_negation_conflict_can_exclude(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "",
            "negated": True,
            "roles": {},
            "facets": {},
        }
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertIn("negated", result["structural_conflicts"])

    def test_36_missing_state_is_reported(self):
        candidate = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "roles": {"destination": REAL_MADRID},
            "facets": {},
        }
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertIn("state", value["missing_identity_fields"])

    def test_37_match_event_with_event_key_is_full_identity(self):
        candidate = dict(self.partial_goal)
        candidate["facets"] = {
            "event_key": "football|match|known-match",
        }
        value = partial.normalize_partial_semantic_candidate(
            candidate,
            allowed_entity_keys=self.allowed,
        )
        self.assertTrue(value["identity_complete"])

    def test_38_same_claim_is_never_established(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertFalse(result["same_claim_established"])

    def test_39_comparison_partial_fingerprints_are_empty(self):
        result = partial.compare_full_claim_to_partial_semantics(
            self.anchor,
            self.partial_goal,
            allowed_entity_keys=self.allowed,
        )
        self.assertEqual(result["partial_core_fingerprint"], "")
        self.assertEqual(result["partial_specific_fingerprint"], "")

    def test_40_invalid_full_claim_is_rejected(self):
        bad_full = dict(self.anchor)
        bad_full["roles"] = {}
        with self.assertRaises(partial.PartialClaimSemanticsInputError):
            partial.compare_full_claim_to_partial_semantics(
                bad_full,
                self.partial_goal,
                allowed_entity_keys=self.allowed,
            )


if __name__ == "__main__":
    unittest.main()
