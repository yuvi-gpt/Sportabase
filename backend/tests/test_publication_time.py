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

from app.services.publication_time import (
    PUBLICATION_TIME_VERSION,
    extract_publication_time,
    normalize_publication_timestamp,
    resolve_publication_time,
)


class PublicationTimeTests(
    unittest.TestCase
):
    def test_explicit_meta_timestamp_is_normalized_to_utc(
        self,
    ):
        html = """
        <html>
          <head>
            <meta
              property="article:published_time"
              content="2026-08-13T18:30:00+05:30"
            >
          </head>
        </html>
        """

        result = extract_publication_time(
            html
        )

        self.assertEqual(
            result["version"],
            PUBLICATION_TIME_VERSION,
        )

        self.assertEqual(
            result["status"],
            "found",
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-13T13:00:00+00:00",
        )

        self.assertTrue(
            result["timezone_known"]
        )

        self.assertEqual(
            result["source_key"],
            "article:published_time",
        )

    def test_json_ld_date_published_is_supported(
        self,
    ):
        html = """
        <html>
          <head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "NewsArticle",
                  "datePublished": "2026-08-12T20:15:00Z"
                }
              ]
            }
            </script>
          </head>
        </html>
        """

        result = extract_publication_time(
            html
        )

        self.assertEqual(
            result["status"],
            "found",
        )

        self.assertEqual(
            result["source_type"],
            "json_ld",
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-12T20:15:00+00:00",
        )

    def test_invalid_first_meta_falls_through(
        self,
    ):
        html = """
        <html>
          <head>
            <meta
              property="article:published_time"
              content="not-a-date"
            >
            <meta
              name="pubdate"
              content="2026-08-11T09:00:00Z"
            >
          </head>
        </html>
        """

        result = extract_publication_time(
            html
        )

        self.assertEqual(
            result["status"],
            "found",
        )

        self.assertEqual(
            result["source_key"],
            "pubdate",
        )

    def test_date_only_preserves_date_precision(
        self,
    ):
        result = (
            normalize_publication_timestamp(
                "2026-08-10"
            )
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-10",
        )

        self.assertEqual(
            result["precision"],
            "date",
        )

        self.assertFalse(
            result["timezone_known"]
        )

    def test_naive_datetime_does_not_invent_timezone(
        self,
    ):
        result = (
            normalize_publication_timestamp(
                "2026-08-10T14:30:00"
            )
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-10T14:30:00",
        )

        self.assertFalse(
            result["timezone_known"]
        )

    def test_relative_provider_age_is_rejected(
        self,
    ):
        result = resolve_publication_time(
            "<html></html>",
            provider_page_age="2 hours ago",
        )

        self.assertEqual(
            result["status"],
            "not_found",
        )

        self.assertEqual(
            result["published_at"],
            "",
        )

    def test_absolute_provider_time_is_allowed_as_fallback(
        self,
    ):
        result = resolve_publication_time(
            "<html></html>",
            provider_page_age=(
                "2026-08-13T10:00:00Z"
            ),
        )

        self.assertEqual(
            result["status"],
            "found",
        )

        self.assertEqual(
            result["source_type"],
            "provider",
        )

        self.assertEqual(
            result["source_key"],
            "page_age",
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-13T10:00:00+00:00",
        )

    def test_html_metadata_beats_provider_fallback(
        self,
    ):
        html = """
        <html>
          <head>
            <meta
              property="article:published_time"
              content="2026-08-13T12:00:00Z"
            >
          </head>
        </html>
        """

        result = resolve_publication_time(
            html,
            provider_page_age=(
                "2026-08-12T12:00:00Z"
            ),
        )

        self.assertEqual(
            result["source_type"],
            "meta",
        )

        self.assertEqual(
            result["published_at"],
            "2026-08-13T12:00:00+00:00",
        )


if __name__ == "__main__":
    unittest.main()
