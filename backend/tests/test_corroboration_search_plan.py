import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )

from app.services.corroboration_discovery import (
    CORROBORATION_SEARCH_PLAN_VERSION,
    build_claim_corroboration_search_plan,
)


class CorroborationSearchPlanTests(
    unittest.TestCase
):
    def claim(
        self,
        **overrides,
    ):
        row = {
            "id": "claim-1",
            "canonical_key": (
                "transfer|player-123|club-456|agreement"
            ),
            "subject_key": (
                "transfer|player-123|club-456"
            ),
            "canonical_text": (
                "Player Alpha has agreed to join "
                "Club Beta."
            ),
            "claim_type": "assertion",
        }

        row.update(
            overrides
        )

        return row

    def test_policy_version(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim()
            )
        )

        self.assertEqual(
            plan["version"],
            CORROBORATION_SEARCH_PLAN_VERSION,
        )

        self.assertEqual(
            plan["version"],
            "corroboration-search-plan-v1",
        )

    def test_claim_text_produces_searchable_plan(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim(),
                source_url=(
                    "https://source.example/story"
                ),
            )
        )

        self.assertEqual(
            plan["status"],
            "searchable",
        )

        self.assertGreaterEqual(
            len(plan["queries"]),
            1,
        )

        self.assertEqual(
            plan["queries"][0]["purpose"],
            "claim_text",
        )

    def test_internal_keys_are_not_provider_queries(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim()
            )
        )

        provider_queries = " ".join(
            row["query"]
            for row in plan["queries"]
        )

        self.assertNotIn(
            "player-123",
            provider_queries,
        )

        self.assertNotIn(
            "club-456",
            provider_queries,
        )

        self.assertNotIn(
            "transfer|",
            provider_queries,
        )

    def test_core_query_removes_filler_but_keeps_claim_terms(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim()
            )
        )

        core = next(
            row["query"]
            for row in plan["queries"]
            if row["purpose"]
            == "claim_core"
        )

        self.assertIn(
            "Player Alpha",
            core,
        )

        self.assertIn(
            "agreed",
            core,
        )

        self.assertIn(
            "Club Beta",
            core,
        )

        self.assertNotIn(
            " has ",
            f" {core} ",
        )

        self.assertNotIn(
            " to ",
            f" {core} ",
        )

    def test_negation_is_preserved(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim(
                    canonical_text=(
                        "Player Alpha has not agreed "
                        "to join Club Beta."
                    )
                )
            )
        )

        core = next(
            row["query"]
            for row in plan["queries"]
            if row["purpose"]
            == "claim_core"
        )

        self.assertIn(
            "not",
            core.lower(),
        )

    def test_missing_canonical_text_is_not_searchable(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim(
                    canonical_text=""
                )
            )
        )

        self.assertEqual(
            plan["status"],
            "not_searchable",
        )

        self.assertEqual(
            plan["reason"],
            "canonical_text_missing",
        )

        self.assertEqual(
            plan["queries"],
            [],
        )

    def test_whitespace_is_normalized(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim(
                    canonical_text=(
                        " Player Alpha   has agreed\n"
                        " to join   Club Beta. "
                    )
                )
            )
        )

        self.assertEqual(
            plan["canonical_text"],
            (
                "Player Alpha has agreed "
                "to join Club Beta."
            ),
        )

    def test_queries_respect_provider_limits(
        self,
    ):
        long_text = " ".join(
            f"word{i}"
            for i in range(100)
        )

        plan = (
            build_claim_corroboration_search_plan(
                self.claim(
                    canonical_text=long_text
                )
            )
        )

        for row in plan["queries"]:
            self.assertLessEqual(
                len(row["query"]),
                400,
            )

            self.assertLessEqual(
                len(
                    row["query"].split()
                ),
                50,
            )

    def test_duplicate_full_and_core_queries_collapse(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim(
                    canonical_text=(
                        "Alpha Beta Agreement"
                    )
                )
            )
        )

        self.assertEqual(
            len(plan["queries"]),
            1,
        )

        self.assertEqual(
            plan["queries"][0][
                "sequence"
            ],
            1,
        )

    def test_plan_is_deterministic(
        self,
    ):
        first = (
            build_claim_corroboration_search_plan(
                self.claim(),
                source_url=(
                    "https://source.example/story"
                ),
                freshness="PW",
            )
        )

        second = (
            build_claim_corroboration_search_plan(
                self.claim(),
                source_url=(
                    "https://source.example/story"
                ),
                freshness="pw",
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_discovery_has_no_semantic_corroboration_claim(
        self,
    ):
        plan = (
            build_claim_corroboration_search_plan(
                self.claim()
            )
        )

        policy = plan["policy"]

        self.assertTrue(
            policy[
                "search_discovery_does_not_"
                "establish_support"
            ]
        )

        self.assertTrue(
            policy[
                "search_discovery_does_not_"
                "establish_independence"
            ]
        )

        self.assertTrue(
            policy[
                "search_discovery_does_not_"
                "establish_corroboration"
            ]
        )


if __name__ == "__main__":
    unittest.main()
