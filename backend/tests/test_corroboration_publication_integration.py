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
    build_claim_corroboration_search_plan,
    collect_corroboration_candidates,
)

from app.services.publication_time import (
    PUBLICATION_TIME_VERSION,
)


class CorroborationPublicationIntegrationTests(
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
        *,
        published_meta="",
    ):
        meta = ""

        if published_meta:
            meta = (
                '<meta property="article:published_time" '
                f'content="{published_meta}">'
            )

        return (
            "<html><head>"
            + meta
            + "<title>Transfer report</title>"
            "</head><body><article>"
            "<p>"
            "Player Alpha has agreed to join "
            "Club Beta after negotiations between "
            "the clubs continued this week."
            "</p>"
            "<p>"
            "Further contractual formalities are "
            "expected to be completed soon."
            "</p>"
            "</article></body></html>"
        )

    def searcher(
        self,
        results,
    ):
        def fake_searcher(
            *,
            query,
            api_key,
            count,
            offset,
            freshness,
        ):
            return {
                "results": results
            }

        return fake_searcher

    def collect(
        self,
        *,
        results,
        html_by_url,
    ):
        def fetch_article(url):
            return {
                "html": html_by_url[url],
                "final_url": url,
                "redirect_count": 0,
                "content_type": "text/html",
                "byte_count": 500,
            }

        return (
            collect_corroboration_candidates(
                plan=self.plan(),
                api_key="test-key",
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
                fetch_article=fetch_article,
                extract_article=(
                    main.extract_article_content
                ),
                searcher=self.searcher(
                    results
                ),
            )
        )

    def test_html_publication_time_is_carried_with_provenance(
        self,
    ):
        url = (
            "https://news.example/report"
        )

        result = self.collect(
            results=[
                {
                    "title": "Candidate",
                    "url": url,
                    "page_age": (
                        "2026-08-12T10:00:00Z"
                    ),
                }
            ],
            html_by_url={
                url: self.html(
                    published_meta=(
                        "2026-08-13T16:00:00Z"
                    )
                ),
            },
        )

        candidate = (
            result[
                "resolved_candidates"
            ][0]
        )

        self.assertEqual(
            candidate[
                "resolution_status"
            ],
            "resolved",
        )

        self.assertEqual(
            candidate["published_at"],
            "2026-08-13T16:00:00+00:00",
        )

        self.assertEqual(
            candidate[
                "publication_time_version"
            ],
            PUBLICATION_TIME_VERSION,
        )

        self.assertEqual(
            candidate[
                "publication_time_status"
            ],
            "found",
        )

        self.assertEqual(
            candidate[
                "publication_time_source_type"
            ],
            "meta",
        )

        self.assertEqual(
            candidate[
                "publication_time_source_key"
            ],
            "article:published_time",
        )

    def test_missing_deterministic_time_does_not_fail_resolution(
        self,
    ):
        url = (
            "https://news.example/report"
        )

        result = self.collect(
            results=[
                {
                    "title": "Candidate",
                    "url": url,
                    "page_age": "2 hours ago",
                }
            ],
            html_by_url={
                url: self.html(),
            },
        )

        candidate = (
            result[
                "resolved_candidates"
            ][0]
        )

        self.assertEqual(
            result["counts"]["resolved"],
            1,
        )

        self.assertEqual(
            candidate[
                "resolution_status"
            ],
            "resolved",
        )

        self.assertEqual(
            candidate["published_at"],
            "",
        )

        self.assertEqual(
            candidate[
                "publication_time_status"
            ],
            "not_found",
        )

        self.assertEqual(
            candidate[
                "publication_time_version"
            ],
            PUBLICATION_TIME_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
