from __future__ import annotations

import unittest

from app.intelligence import canonical_claims


class CanonicalClaimTaxonomyTests(unittest.TestCase):
    def assert_normalizes(self, value, *, event_type, state):
        result = canonical_claims.normalize_canonical_claim(value)
        self.assertEqual(result["event_type"], event_type)
        self.assertEqual(result["state"], state)
        return result

    def test_contract(self):
        result = self.assert_normalizes(
            {
                "subject_key": "f1|person|fernando-alonso",
                "event_type": "contract",
                "state": "renewed",
                "roles": {"team": "f1|team|aston-martin"},
                "facets": {"through": "2026"},
            },
            event_type="contract",
            state="extended",
        )
        self.assertEqual(result["roles"]["organization"], "f1|team|aston-martin")

    def test_tenure(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|person|arne-slot",
                "event_type": "manager_appointment",
                "state": "hired",
                "roles": {"club": "football|club|liverpool"},
                "facets": {"title": "head coach", "year": "2024"},
            },
            event_type="tenure",
            state="appointed",
        )
        self.assertEqual(result["facets"]["role"], "head coach")

    def test_retirement(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|player|toni-kroos",
                "event_type": "retirement",
                "state": "will_retire",
                "facets": {
                    "scope": "professional football",
                    "after": "euro 2024",
                },
            },
            event_type="retirement",
            state="announced",
        )
        self.assertEqual(result["facets"]["scope"], "professional football")

    def test_injury(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|player|example",
                "event_type": "injury",
                "state": "diagnosed",
                "facets": {
                    "body_part": "right knee",
                    "diagnosis": "meniscus tear",
                },
            },
            event_type="injury",
            state="diagnosed",
        )
        self.assertEqual(result["facets"]["body_region"], "right knee")

    def test_availability(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|player|example",
                "event_type": "availability",
                "state": "fit",
                "facets": {"match_key": "football|match|abc"},
            },
            event_type="availability",
            state="available",
        )
        self.assertEqual(result["facets"]["event_key"], "football|match|abc")

    def test_lineup(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|player|example",
                "event_type": "team_selection",
                "state": "starter",
                "facets": {"context_key": "football|match|abc"},
            },
            event_type="lineup",
            state="starting",
        )
        self.assertEqual(result["facets"]["event_key"], "football|match|abc")

    def test_match_result(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|club|manchester-city",
                "event_type": "match_result",
                "state": "victory",
                "facets": {"match_key": "football|match|ucl-final-2023"},
            },
            event_type="match_result",
            state="won",
        )
        self.assertEqual(result["facets"]["event_key"], "football|match|ucl-final-2023")

    def test_match_event(self):
        result = self.assert_normalizes(
            {
                "subject_key": "football|player|jude-bellingham",
                "event_type": "game_event",
                "state": "goal",
                "facets": {"game_key": "football|match|later-game"},
            },
            event_type="match_event",
            state="scored",
        )
        self.assertEqual(result["facets"]["event_key"], "football|match|later-game")

    def test_championship(self):
        result = self.assert_normalizes(
            {
                "subject_key": "f1|person|max-verstappen",
                "event_type": "title",
                "state": "clinched",
                "facets": {
                    "competition": "f1|competition|drivers-world-championship",
                    "season": "2023",
                },
            },
            event_type="championship",
            state="won",
        )
        self.assertEqual(result["facets"]["effective_period"], "2023")

    def test_disciplinary(self):
        result = self.assert_normalizes(
            {
                "subject_key": "f1|person|example",
                "event_type": "discipline",
                "state": "penalised",
                "facets": {"race_key": "f1|race|example"},
            },
            event_type="disciplinary",
            state="penalized",
        )
        self.assertEqual(result["facets"]["event_key"], "f1|race|example")


if __name__ == "__main__":
    unittest.main()
