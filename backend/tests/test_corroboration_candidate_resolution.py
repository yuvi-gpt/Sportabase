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

from app import main

from app.services.corroboration_discovery import (
    CORROBORATION_CANDIDATE_COLLECTION_VERSION,
    build_claim_corroboration_search_plan,
    collect_corroboration_candidates,
)


class CorroborationCandidateResolutionTests(
    unittest.TestCase
):
    def claim(self):
        return {
            "id": "claim-1",
            "canonical_key": (
                "transfer|alpha|beta|agreement"
            ),
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "canonical_text": (
                "Player Alpha has agreed to join "
                "Club Beta."
            ),
            "claim_type": "assertion",
        }

    def plan(self):
        return (
            build_claim_corroboration_search_plan(
                self.claim(),
                source_url=(
                    "https://origin.example/story"
                ),
            )
        )

    def html(
        self,
        title="Candidate report",
        body=(
            "Player Alpha has agreed to join "
            "Club Beta according to the report. "
            "The article provides additional "
            "details about the proposed move "
            "and the negotiations between the "
            "parties involved."
        ),
    ):
        return (
            "<html><head>"
            f"<title>{title}</title>"
            "</head><body><article>"
            f"<p>{body}</p>"
            "</article></body></html>"
        )

    def searcher_from_results(
        self,
        result_map,
        calls=None,
    ):
        def fake_searcher(
            *,
            query,
            api_key,
            count,
            offset,
            freshness,
        ):
            if calls is not None:
                calls.append(
                    {
                        "query": query,
                        "api_key": api_key,
                        "count": count,
                        "offset": offset,
                        "freshness": (
                            freshness
                        ),
                    }
                )

            value = result_map.get(
                query,
                [],
            )

            if isinstance(
                value,
                Exception,
            ):
                raise value

            return {
                "results": value
            }

        return fake_searcher

    def fake_fetch(
        self,
        url,
    ):
        return {
            "html": self.html(),
            "final_url": url,
            "redirect_count": 0,
            "content_type": "text/html",
            "byte_count": 250,
        }

    def collect(
        self,
        *,
        plan=None,
        searcher,
        fetch_article=None,
        extract_article=None,
        max_candidates=8,
    ):
        return collect_corroboration_candidates(
            plan=(
                plan
                if plan is not None
                else self.plan()
            ),
            api_key="test-key",
            normalize_url=(
                main.normalized_analysis_url
            ),
            domain_resolver=(
                main.source_domain_for_url
            ),
            fetch_article=(
                fetch_article
                or self.fake_fetch
            ),
            extract_article=(
                extract_article
                or main.extract_article_content
            ),
            searcher=searcher,
            max_candidates=max_candidates,
        )

    def test_version_and_real_extraction(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": (
                                    "Candidate"
                                ),
                                "url": (
                                    "https://news.example/"
                                    "candidate"
                                ),
                            }
                        ]
                    }
                )
            )
        )

        self.assertEqual(
            result["version"],
            (
                CORROBORATION_CANDIDATE_COLLECTION_VERSION
            ),
        )

        self.assertEqual(
            result["status"],
            "resolved_candidates_available",
        )

        self.assertEqual(
            result["counts"]["resolved"],
            1,
        )

        resolved = (
            result[
                "resolved_candidates"
            ][0]
        )

        self.assertEqual(
            resolved[
                "resolution_status"
            ],
            "resolved",
        )

        self.assertIn(
            "Player Alpha",
            resolved["text"],
        )

        self.assertGreater(
            resolved[
                "character_count"
            ],
            80,
        )

    def test_non_searchable_plan_makes_no_calls(
        self,
    ):
        calls = []

        result = self.collect(
            plan={
                "status": (
                    "not_searchable"
                ),
                "reason": (
                    "canonical_text_missing"
                ),
                "claim_id": "claim-1",
                "source_url": "",
                "queries": [],
            },
            searcher=(
                self.searcher_from_results(
                    {},
                    calls,
                )
            ),
        )

        self.assertEqual(
            result["status"],
            "not_searchable",
        )

        self.assertEqual(
            calls,
            [],
        )

    def test_search_queries_execute_in_plan_order(
        self,
    ):
        plan = self.plan()
        calls = []

        self.collect(
            searcher=(
                self.searcher_from_results(
                    {},
                    calls,
                )
            ),
        )

        self.assertEqual(
            [
                call["query"]
                for call in calls
            ],
            [
                row["query"]
                for row in plan["queries"]
            ],
        )

    def test_duplicate_candidate_merges_query_provenance(
        self,
    ):
        plan = self.plan()

        results = {
            row["query"]: [
                {
                    "title": "Candidate",
                    "url": (
                        "https://news.example/"
                        "candidate"
                    ),
                }
            ]
            for row in plan["queries"]
        }

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    results
                )
            )
        )

        self.assertEqual(
            result["counts"]["discovered"],
            1,
        )

        self.assertEqual(
            len(
                result["candidates"][0][
                    "discovery_queries"
                ]
            ),
            len(plan["queries"]),
        )

    def test_search_failure_is_best_effort(
        self,
    ):
        plan = self.plan()

        first = plan["queries"][0][
            "query"
        ]

        second = plan["queries"][-1][
            "query"
        ]

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first: RuntimeError(
                            "provider down"
                        ),
                        second: [
                            {
                                "title": (
                                    "Candidate"
                                ),
                                "url": (
                                    "https://news.example/"
                                    "candidate"
                                ),
                            }
                        ],
                    }
                )
            )
        )

        self.assertEqual(
            result["counts"][
                "search_failures"
            ],
            1,
        )

        self.assertEqual(
            result["counts"]["resolved"],
            1,
        )

    def test_fetch_failure_does_not_abort_other_candidate(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        def fetch(url):
            if "broken" in url:
                raise ValueError(
                    "blocked article"
                )

            return self.fake_fetch(
                url
            )

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": "Broken",
                                "url": (
                                    "https://broken.example/"
                                    "story"
                                ),
                            },
                            {
                                "title": "Good",
                                "url": (
                                    "https://good.example/"
                                    "story"
                                ),
                            },
                        ]
                    }
                )
            ),
            fetch_article=fetch,
        )

        self.assertEqual(
            result["counts"]["failed"],
            1,
        )

        self.assertEqual(
            result["counts"]["resolved"],
            1,
        )

    def test_extraction_failure_does_not_abort_other_candidate(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        def fetch(url):
            return {
                "html": (
                    ""
                    if "empty" in url
                    else self.html()
                ),
                "final_url": url,
                "redirect_count": 0,
                "content_type": (
                    "text/html"
                ),
                "byte_count": 200,
            }

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": "Empty",
                                "url": (
                                    "https://empty.example/"
                                    "story"
                                ),
                            },
                            {
                                "title": "Good",
                                "url": (
                                    "https://good.example/"
                                    "story"
                                ),
                            },
                        ]
                    }
                )
            ),
            fetch_article=fetch,
        )

        statuses = [
            row["resolution_status"]
            for row in result[
                "candidates"
            ]
        ]

        self.assertIn(
            "extraction_failed",
            statuses,
        )

        self.assertIn(
            "resolved",
            statuses,
        )

    def test_redirect_back_to_current_article_is_excluded(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        def fetch(url):
            return {
                "html": self.html(),
                "final_url": (
                    "https://origin.example/"
                    "story?utm_source=redirect"
                ),
                "redirect_count": 1,
                "content_type": (
                    "text/html"
                ),
                "byte_count": 200,
            }

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": "Redirect",
                                "url": (
                                    "https://redirect.example/"
                                    "story"
                                ),
                            }
                        ]
                    }
                )
            ),
            fetch_article=fetch,
        )

        self.assertEqual(
            result["counts"]["resolved"],
            0,
        )

        self.assertEqual(
            result["counts"]["excluded"],
            1,
        )

        self.assertEqual(
            result["candidates"][0][
                "resolution_status"
            ],
            (
                "excluded_current_"
                "after_redirect"
            ),
        )

    def test_duplicate_final_redirect_url_is_not_double_resolved(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        def fetch(url):
            return {
                "html": self.html(),
                "final_url": (
                    "https://final.example/story"
                ),
                "redirect_count": 1,
                "content_type": (
                    "text/html"
                ),
                "byte_count": 200,
            }

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": "One",
                                "url": (
                                    "https://one.example/"
                                    "story"
                                ),
                            },
                            {
                                "title": "Two",
                                "url": (
                                    "https://two.example/"
                                    "story"
                                ),
                            },
                        ]
                    }
                )
            ),
            fetch_article=fetch,
        )

        self.assertEqual(
            result["counts"]["resolved"],
            1,
        )

        self.assertEqual(
            result["counts"]["excluded"],
            1,
        )

        self.assertEqual(
            result["candidates"][1][
                "resolution_status"
            ],
            "duplicate_final_url",
        )

    def test_candidate_limit_prevents_extra_fetches(
        self,
    ):
        first_query = (
            self.plan()["queries"][0][
                "query"
            ]
        )

        fetch_calls = []

        def fetch(url):
            fetch_calls.append(
                url
            )

            return self.fake_fetch(
                url
            )

        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {
                        first_query: [
                            {
                                "title": "One",
                                "url": (
                                    "https://one.example/a"
                                ),
                            },
                            {
                                "title": "Two",
                                "url": (
                                    "https://two.example/b"
                                ),
                            },
                            {
                                "title": "Three",
                                "url": (
                                    "https://three.example/c"
                                ),
                            },
                        ]
                    }
                )
            ),
            fetch_article=fetch,
            max_candidates=2,
        )

        self.assertEqual(
            len(fetch_calls),
            2,
        )

        self.assertEqual(
            result["counts"][
                "not_attempted"
            ],
            1,
        )

        self.assertEqual(
            result["candidates"][2][
                "resolution_status"
            ],
            "not_attempted_limit",
        )

    def test_missing_api_key_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            collect_corroboration_candidates(
                plan=self.plan(),
                api_key="",
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
                fetch_article=(
                    self.fake_fetch
                ),
                extract_article=(
                    main.extract_article_content
                ),
                searcher=(
                    self.searcher_from_results(
                        {}
                    )
                ),
            )

    def test_collection_has_no_semantic_corroboration_claim(
        self,
    ):
        result = self.collect(
            searcher=(
                self.searcher_from_results(
                    {}
                )
            )
        )

        policy = result["policy"]

        self.assertTrue(
            policy[
                "discovery_does_not_"
                "establish_support"
            ]
        )

        self.assertTrue(
            policy[
                "discovery_does_not_"
                "establish_independence"
            ]
        )

        self.assertTrue(
            policy[
                "discovery_does_not_"
                "establish_corroboration"
            ]
        )

        self.assertTrue(
            policy[
                "candidate_content_must_be_"
                "evaluated_before_semantic_use"
            ]
        )


if __name__ == "__main__":
    unittest.main()
