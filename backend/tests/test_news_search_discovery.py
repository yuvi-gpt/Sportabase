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
from app.services.news_search import (
    BRAVE_NEWS_SEARCH_URL,
    normalize_brave_news_candidates,
    normalize_brave_news_freshness,
    normalize_brave_news_query,
    search_brave_news,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        payload=None,
    ):
        self.status_code = status_code
        self._payload = (
            payload
            if payload is not None
            else {}
        )

    def json(self):
        return self._payload


class NewsSearchDiscoveryTests(
    unittest.TestCase
):
    def test_query_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            normalize_brave_news_query(
                "   "
            )

    def test_query_limits_are_enforced(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            normalize_brave_news_query(
                "x" * 401
            )

        with self.assertRaises(
            ValueError
        ):
            normalize_brave_news_query(
                " ".join(
                    ["word"] * 51
                )
            )

        self.assertEqual(
            normalize_brave_news_query(
                "  player   transfer  "
            ),
            "player transfer",
        )

    def test_pagination_limits_are_enforced(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            search_brave_news(
                query="transfer",
                api_key="test-key",
                count=51,
                request_get=lambda *a, **k: (
                    FakeResponse()
                ),
            )

        with self.assertRaises(
            ValueError
        ):
            search_brave_news(
                query="transfer",
                api_key="test-key",
                offset=10,
                request_get=lambda *a, **k: (
                    FakeResponse()
                ),
            )

    def test_freshness_validation(
        self,
    ):
        self.assertEqual(
            normalize_brave_news_freshness(
                " PW "
            ),
            "pw",
        )

        self.assertEqual(
            normalize_brave_news_freshness(
                "2026-08-01to2026-08-13"
            ),
            "2026-08-01to2026-08-13",
        )

        with self.assertRaises(
            ValueError
        ):
            normalize_brave_news_freshness(
                "2026-08-13to2026-08-01"
            )

    def test_search_uses_brave_contract_without_real_network(
        self,
    ):
        captured = {}

        def fake_get(
            url,
            *,
            params,
            headers,
            timeout,
        ):
            captured["url"] = url
            captured["params"] = params
            captured["headers"] = headers
            captured["timeout"] = timeout

            return FakeResponse(
                payload={
                    "type": "news",
                    "query": {
                        "original": (
                            "player transfer"
                        )
                    },
                    "results": [
                        {
                            "title": "Report",
                            "url": (
                                "https://example.com/"
                                "report"
                            ),
                        }
                    ],
                }
            )

        result = search_brave_news(
            query="  player   transfer ",
            api_key="secret-key",
            count=12,
            offset=1,
            freshness="pw",
            country="ALL",
            search_lang="en",
            request_get=fake_get,
        )

        self.assertEqual(
            captured["url"],
            BRAVE_NEWS_SEARCH_URL,
        )

        self.assertEqual(
            captured["params"]["q"],
            "player transfer",
        )

        self.assertEqual(
            captured["params"]["count"],
            12,
        )

        self.assertEqual(
            captured["params"]["offset"],
            1,
        )

        self.assertEqual(
            captured["params"][
                "freshness"
            ],
            "pw",
        )

        self.assertEqual(
            captured["headers"][
                "X-Subscription-Token"
            ],
            "secret-key",
        )

        self.assertEqual(
            result["provider"],
            "brave_news",
        )

        self.assertEqual(
            len(result["results"]),
            1,
        )

    def test_search_rejects_provider_http_error(
        self,
    ):
        with self.assertRaisesRegex(
            RuntimeError,
            "HTTP 429",
        ):
            search_brave_news(
                query="transfer",
                api_key="test-key",
                request_get=(
                    lambda *a, **k: (
                        FakeResponse(
                            status_code=429
                        )
                    )
                ),
            )

    def test_candidate_normalization_excludes_current_and_deduplicates(
        self,
    ):
        payload = {
            "results": [
                {
                    "title": "Current",
                    "url": (
                        "https://example.com/story"
                        "?utm_source=test"
                    ),
                },
                {
                    "title": "Candidate",
                    "url": (
                        "https://other.com/report"
                        "?utm_source=feed"
                    ),
                },
                {
                    "title": "Duplicate",
                    "url": (
                        "https://other.com/report"
                    ),
                },
            ]
        }

        candidates = (
            normalize_brave_news_candidates(
                payload,
                source_url=(
                    "https://example.com/story"
                ),
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        self.assertEqual(
            candidates[0][
                "normalized_url"
            ],
            "https://other.com/report",
        )

    def test_same_domain_candidate_is_retained_but_flagged(
        self,
    ):
        payload = {
            "results": [
                {
                    "title": (
                        "Follow-up report"
                    ),
                    "url": (
                        "https://example.com/"
                        "second-story"
                    ),
                }
            ]
        }

        candidates = (
            normalize_brave_news_candidates(
                payload,
                source_url=(
                    "https://example.com/"
                    "first-story"
                ),
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        self.assertTrue(
            candidates[0][
                "same_source_domain"
            ]
        )

        self.assertEqual(
            candidates[0][
                "source_domain"
            ],
            "example.com",
        )

    def test_malformed_candidate_rows_are_ignored(
        self,
    ):
        payload = {
            "results": [
                None,
                "bad-row",
                {},
                {
                    "url": "",
                },
                {
                    "title": "Valid",
                    "url": (
                        "https://valid.example/"
                        "story"
                    ),
                    "extra_snippets": [
                        " One ",
                        "",
                        "Two",
                    ],
                },
            ]
        }

        candidates = (
            normalize_brave_news_candidates(
                payload,
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

        self.assertEqual(
            len(candidates),
            1,
        )

        self.assertEqual(
            candidates[0][
                "extra_snippets"
            ],
            [
                "One",
                "Two",
            ],
        )

    def test_candidate_order_is_stable(
        self,
    ):
        payload = {
            "results": [
                {
                    "title": "First",
                    "url": (
                        "https://one.example/a"
                    ),
                },
                {
                    "title": "Second",
                    "url": (
                        "https://two.example/b"
                    ),
                },
            ]
        }

        first = (
            normalize_brave_news_candidates(
                payload,
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

        second = (
            normalize_brave_news_candidates(
                payload,
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            [
                row["provider_rank"]
                for row in first
            ],
            [1, 2],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
