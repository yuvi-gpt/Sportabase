from __future__ import annotations

import copy
import unittest

from app.intelligence import canonical_claims


BELLINGHAM = "football|player|jude-bellingham"
REAL_MADRID = "football|club|real-madrid"
DORTMUND = "football|club|borussia-dortmund"
BIRMINGHAM = "football|club|birmingham-city"


def transfer_claim(
    *,
    state="completed",
    subject=BELLINGHAM,
    destination=REAL_MADRID,
    origin="",
    effective_period="",
    transfer_kind="",
    negated=False,
):
    roles = {
        "destination": destination,
    }

    if origin:
        roles["origin"] = origin

    facets = {}

    if effective_period:
        facets["effective_period"] = effective_period

    if transfer_kind:
        facets["transfer_kind"] = transfer_kind

    return {
        "subject_key": subject,
        "event_type": "transfer",
        "state": state,
        "negated": negated,
        "roles": roles,
        "facets": facets,
    }


class CanonicalClaimNormalizationTests(
    unittest.TestCase
):
    def test_transfer_aliases_normalize(self):
        normalized = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": "  Football|Player|Jude-Bellingham  ",
                "event_type": "move",
                "state": "signed",
                "roles": {
                    "to": " Football|Club|Real-Madrid ",
                    "from": "Football|Club|Borussia-Dortmund",
                },
                "facets": {
                    "year": " 2023 ",
                    "type": " Permanent ",
                },
            }
        )

        self.assertEqual(
            normalized["subject_key"],
            BELLINGHAM,
        )
        self.assertEqual(
            normalized["event_type"],
            "transfer",
        )
        self.assertEqual(
            normalized["state"],
            "completed",
        )
        self.assertEqual(
            normalized["roles"]["destination"],
            REAL_MADRID,
        )
        self.assertEqual(
            normalized["roles"]["origin"],
            DORTMUND,
        )
        self.assertEqual(
            normalized["facets"]["effective_period"],
            "2023",
        )
        self.assertEqual(
            normalized["facets"]["transfer_kind"],
            "permanent",
        )

    def test_completed_transfer_state_synonyms_converge(self):
        values = [
            "completed",
            "signed",
            "joined",
            "transferred",
            "presented",
            "announced_as_player",
        ]

        states = {
            canonical_claims.normalize_canonical_claim(
                transfer_claim(state=value)
            )["state"]
            for value in values
        }

        self.assertEqual(states, {"completed"})

    def test_role_alias_collision_same_value_is_allowed(self):
        normalized = canonical_claims.normalize_canonical_claim(
            {
                "subject_key": BELLINGHAM,
                "event_type": "transfer",
                "state": "completed",
                "roles": {
                    "to": REAL_MADRID,
                    "destination": REAL_MADRID.upper(),
                },
            }
        )

        self.assertEqual(
            normalized["roles"],
            {"destination": REAL_MADRID},
        )

    def test_role_alias_collision_conflict_is_rejected(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimConflictError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "transfer",
                    "state": "completed",
                    "roles": {
                        "to": REAL_MADRID,
                        "destination": "football|club|barcelona",
                    },
                }
            )

    def test_unsupported_event_type_is_rejected(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "vibes",
                    "state": "good",
                }
            )

    def test_unsupported_state_is_rejected(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                transfer_claim(state="maybe_sort_of_signed")
            )

    def test_transfer_requires_destination(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "transfer",
                    "state": "completed",
                    "roles": {},
                }
            )

    def test_retirement_requires_scope(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": "football|player|toni-kroos",
                    "event_type": "retirement",
                    "state": "announced",
                }
            )

    def test_availability_requires_event_key(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "availability",
                    "state": "available",
                }
            )

    def test_lineup_requires_event_key(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "lineup",
                    "state": "starting",
                }
            )

    def test_championship_requires_competition_and_period(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": "f1|person|max-verstappen",
                    "event_type": "championship",
                    "state": "won",
                    "facets": {
                        "competition": "f1|competition|drivers-world-championship",
                    },
                }
            )

    def test_injury_requires_episode_or_body_region(self):
        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(
                {
                    "subject_key": BELLINGHAM,
                    "event_type": "injury",
                    "state": "injured",
                }
            )

    def test_forbidden_truth_field_is_rejected(self):
        claim = transfer_claim()
        claim["truth"] = True

        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(claim)

    def test_forbidden_reliability_nested_field_is_rejected(self):
        claim = transfer_claim()
        claim["facets"] = {
            "reliability": "high",
        }

        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(claim)

    def test_unknown_top_level_field_is_rejected(self):
        claim = transfer_claim()
        claim["summary"] = "Bellingham joined Real Madrid."

        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(claim)

    def test_unknown_role_is_rejected(self):
        claim = transfer_claim()
        claim["roles"]["best_friend"] = "someone"

        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(claim)

    def test_version_mismatch_is_rejected(self):
        claim = transfer_claim()
        claim["version"] = "canonical-claim-contract-v999"

        with self.assertRaises(
            canonical_claims.CanonicalClaimInputError
        ):
            canonical_claims.normalize_canonical_claim(claim)

    def test_input_is_not_mutated(self):
        claim = transfer_claim(
            origin=DORTMUND,
            effective_period="2023",
        )
        before = copy.deepcopy(claim)

        canonical_claims.normalize_canonical_claim(claim)

        self.assertEqual(claim, before)


class CanonicalClaimFingerprintTests(
    unittest.TestCase
):
    def test_bellingham_anchor_and_web_positive_share_core(self):
        anchor = transfer_claim(
            state="completed",
            effective_period="2023",
        )

        web = {
            "subject_key": BELLINGHAM,
            "event_type": "move",
            "state": "signed",
            "roles": {
                "to": REAL_MADRID,
                "from": DORTMUND,
            },
        }

        comparison = canonical_claims.compare_canonical_claims(
            anchor,
            web,
        )

        self.assertTrue(comparison["same_core"])
        self.assertFalse(comparison["same_specific"])
        self.assertEqual(
            comparison["status"],
            "same_core_no_material_conflict",
        )
        self.assertEqual(
            comparison["material_conflicts"],
            [],
        )

    def test_bellingham_anchor_and_youtube_positive_share_core(self):
        anchor = transfer_claim(
            effective_period="2023",
        )

        youtube = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "presented",
            "roles": {
                "new_club": REAL_MADRID,
            },
        }

        comparison = canonical_claims.compare_canonical_claims(
            anchor,
            youtube,
        )

        self.assertEqual(
            comparison["status"],
            "same_core_no_material_conflict",
        )

    def test_bellingham_hard_negative_is_different_core(self):
        transfer = transfer_claim()

        later_goal = {
            "subject_key": BELLINGHAM,
            "event_type": "match_event",
            "state": "goal",
            "facets": {
                "match_key": "football|match|later-league-match",
            },
        }

        comparison = canonical_claims.compare_canonical_claims(
            transfer,
            later_goal,
        )

        self.assertFalse(comparison["same_core"])
        self.assertEqual(
            comparison["status"],
            "different_core",
        )

    def test_interest_and_completed_transfer_are_different_core(self):
        completed = transfer_claim(state="completed")
        interest = transfer_claim(state="interest")

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(completed),
            canonical_claims.canonical_claim_core_fingerprint(interest),
        )

    def test_agreed_and_completed_transfer_are_different_core(self):
        agreed = transfer_claim(state="agreed")
        completed = transfer_claim(state="completed")

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(agreed),
            canonical_claims.canonical_claim_core_fingerprint(completed),
        )

    def test_negation_changes_core_identity(self):
        positive = transfer_claim(negated=False)
        negative = transfer_claim(negated=True)

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(positive),
            canonical_claims.canonical_claim_core_fingerprint(negative),
        )

    def test_subject_changes_core_identity(self):
        first = transfer_claim(subject=BELLINGHAM)
        second = transfer_claim(subject="football|player|kylian-mbappe")

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(first),
            canonical_claims.canonical_claim_core_fingerprint(second),
        )

    def test_destination_changes_core_identity(self):
        first = transfer_claim(destination=REAL_MADRID)
        second = transfer_claim(destination="football|club|barcelona")

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(first),
            canonical_claims.canonical_claim_core_fingerprint(second),
        )

    def test_optional_origin_does_not_change_core_fingerprint(self):
        sparse = transfer_claim()
        specific = transfer_claim(origin=DORTMUND)

        self.assertEqual(
            canonical_claims.canonical_claim_core_fingerprint(sparse),
            canonical_claims.canonical_claim_core_fingerprint(specific),
        )
        self.assertNotEqual(
            canonical_claims.canonical_claim_specific_fingerprint(sparse),
            canonical_claims.canonical_claim_specific_fingerprint(specific),
        )

    def test_optional_period_does_not_change_transfer_core_fingerprint(self):
        without_period = transfer_claim()
        with_period = transfer_claim(effective_period="2023")

        self.assertEqual(
            canonical_claims.canonical_claim_core_fingerprint(without_period),
            canonical_claims.canonical_claim_core_fingerprint(with_period),
        )

    def test_conflicting_origins_are_material_conflict(self):
        dortmund = transfer_claim(origin=DORTMUND)
        birmingham = transfer_claim(origin=BIRMINGHAM)

        comparison = canonical_claims.compare_canonical_claims(
            dortmund,
            birmingham,
        )

        self.assertTrue(comparison["same_core"])
        self.assertEqual(
            comparison["status"],
            "material_conflict",
        )
        self.assertEqual(
            comparison["material_conflicts"],
            ["roles.origin"],
        )

    def test_conflicting_periods_are_material_conflict(self):
        first = transfer_claim(effective_period="2023")
        second = transfer_claim(effective_period="2024")

        comparison = canonical_claims.compare_canonical_claims(
            first,
            second,
        )

        self.assertEqual(
            comparison["status"],
            "material_conflict",
        )
        self.assertEqual(
            comparison["material_conflicts"],
            ["facets.effective_period"],
        )

    def test_identical_specific_claim_is_exact_specific_match(self):
        first = transfer_claim(
            origin=DORTMUND,
            effective_period="2023",
            transfer_kind="permanent",
        )

        second = {
            "subject_key": BELLINGHAM.upper(),
            "event_type": "move",
            "state": "joined",
            "roles": {
                "from": DORTMUND.upper(),
                "to": REAL_MADRID.upper(),
            },
            "facets": {
                "year": "2023",
                "deal_type": "PERMANENT",
            },
        }

        comparison = canonical_claims.compare_canonical_claims(
            first,
            second,
        )

        self.assertEqual(
            comparison["status"],
            "exact_specific_match",
        )
        self.assertTrue(comparison["same_specific"])

    def test_map_order_does_not_change_specific_fingerprint(self):
        first = transfer_claim(
            origin=DORTMUND,
            effective_period="2023",
            transfer_kind="permanent",
        )

        second = {
            "subject_key": BELLINGHAM,
            "event_type": "transfer",
            "state": "completed",
            "facets": {
                "transfer_kind": "permanent",
                "effective_period": "2023",
            },
            "roles": {
                "origin": DORTMUND,
                "destination": REAL_MADRID,
            },
        }

        self.assertEqual(
            canonical_claims.canonical_claim_specific_fingerprint(first),
            canonical_claims.canonical_claim_specific_fingerprint(second),
        )

    def test_core_key_is_deterministic(self):
        claim = transfer_claim(
            effective_period="2023",
        )

        first = canonical_claims.canonical_claim_core_key(claim)
        second = canonical_claims.canonical_claim_core_key(copy.deepcopy(claim))

        self.assertEqual(first, second)
        self.assertTrue(
            first.startswith(
                "structured-claim|canonical-claim-contract-v1|"
            )
        )

    def test_contract_extension_synonyms_converge(self):
        first = {
            "subject_key": "f1|person|fernando-alonso",
            "event_type": "contract",
            "state": "renewed",
            "roles": {
                "team": "f1|team|aston-martin",
            },
            "facets": {
                "through": "2026",
            },
        }
        second = {
            "subject_key": "F1|Person|Fernando-Alonso",
            "event_type": "contract_status",
            "state": "extended",
            "roles": {
                "organization": "F1|Team|Aston-Martin",
            },
        }

        self.assertEqual(
            canonical_claims.canonical_claim_core_fingerprint(first),
            canonical_claims.canonical_claim_core_fingerprint(second),
        )

    def test_championship_season_changes_core(self):
        first = {
            "subject_key": "f1|person|max-verstappen",
            "event_type": "championship",
            "state": "clinched",
            "facets": {
                "competition": "f1|competition|drivers-world-championship",
                "season": "2023",
            },
        }
        second = copy.deepcopy(first)
        second["facets"]["season"] = "2024"

        self.assertNotEqual(
            canonical_claims.canonical_claim_core_fingerprint(first),
            canonical_claims.canonical_claim_core_fingerprint(second),
        )

    def test_policy_explicitly_excludes_truth_and_merit(self):
        comparison = canonical_claims.compare_canonical_claims(
            transfer_claim(),
            transfer_claim(),
        )

        policy = comparison["policy"]

        self.assertTrue(policy["deterministic_only"])
        self.assertFalse(policy["fuzzy_similarity_used"])
        self.assertFalse(policy["model_equivalence_decision_used"])
        self.assertFalse(policy["establishes_truth"])
        self.assertFalse(policy["establishes_authority"])
        self.assertFalse(policy["establishes_independence"])
        self.assertFalse(policy["establishes_corroboration"])
        self.assertFalse(policy["affects_live_merit"])


if __name__ == "__main__":
    unittest.main()
