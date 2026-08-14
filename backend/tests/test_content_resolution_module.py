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
from app.services import (
    content_resolution,
)


class ContentResolutionModuleTests(
    unittest.TestCase
):
    def test_main_reexports_extracted_functions(
        self,
    ):
        names = (
            "is_tracking_query_parameter",
            "youtube_video_id_from_url",
            "_validate_public_ip_address",
            "validate_safe_remote_url",
            "fetch_safe_article_html",
            "_normalize_extracted_text",
            "extract_article_content",
            "detect_content_source",
            "normalized_analysis_url",
        )

        for name in names:
            with self.subTest(
                name=name
            ):
                self.assertIs(
                    getattr(
                        main,
                        name,
                    ),
                    getattr(
                        content_resolution,
                        name,
                    ),
                )

    def test_main_reexports_content_constants(
        self,
    ):
        self.assertIs(
            main.TRACKING_QUERY_PARAMETERS,
            (
                content_resolution
                .TRACKING_QUERY_PARAMETERS
            ),
        )

        self.assertIs(
            main.YOUTUBE_HOSTS,
            content_resolution.YOUTUBE_HOSTS,
        )

    def test_tracking_parameters_remain_filtered(
        self,
    ):
        self.assertTrue(
            (
                content_resolution
                .is_tracking_query_parameter(
                    "utm_source"
                )
            )
        )

        self.assertTrue(
            (
                content_resolution
                .is_tracking_query_parameter(
                    "fbclid"
                )
            )
        )

        self.assertFalse(
            (
                content_resolution
                .is_tracking_query_parameter(
                    "season"
                )
            )
        )

    def test_article_url_normalization_preserved(
        self,
    ):
        result = (
            content_resolution
            .normalized_analysis_url(
                (
                    "HTTPS://Example.COM/"
                    "sports//story/"
                    "?utm_source=test"
                    "&b=2&a=1#comments"
                )
            )
        )

        self.assertEqual(
            result,
            (
                "https://example.com/"
                "sports/story?a=1&b=2"
            ),
        )

    def test_youtube_url_normalization_preserved(
        self,
    ):
        result = (
            content_resolution
            .normalized_analysis_url(
                (
                    "https://youtu.be/"
                    "abcDEF12345"
                    "?utm_source=test"
                )
            )
        )

        self.assertEqual(
            result,
            (
                "https://youtube.com/"
                "watch?v=abcDEF12345"
            ),
        )

    def test_content_source_detection_preserved(
        self,
    ):
        article = (
            content_resolution
            .detect_content_source(
                (
                    "https://example.com/"
                    "sports/story"
                )
            )
        )

        video = (
            content_resolution
            .detect_content_source(
                (
                    "https://youtube.com/"
                    "watch?v=abcDEF12345"
                )
            )
        )

        self.assertEqual(
            article["source"],
            "article",
        )

        self.assertEqual(
            article["mode"],
            "article",
        )

        self.assertEqual(
            video["source"],
            "youtube",
        )

        self.assertEqual(
            video["mode"],
            "video",
        )

    def test_article_extraction_preserved(
        self,
    ):
        html = """
        <html>
          <head>
            <meta
              property="og:title"
              content="Club confirms signing"
            >
          </head>
          <body>
            <nav>
              Navigation junk
            </nav>

            <article>
              <p>
                The club officially confirmed
                the signing after negotiations
                were completed earlier today.
              </p>

              <p>
                The player has signed a
                long-term contract and will
                join the squad immediately.
              </p>
            </article>
          </body>
        </html>
        """

        result = (
            content_resolution
            .extract_article_content(
                html
            )
        )

        self.assertEqual(
            result["title"],
            "Club confirms signing",
        )

        self.assertIn(
            "officially confirmed",
            result["text"],
        )

        self.assertNotIn(
            "Navigation junk",
            result["text"],
        )

    def test_localhost_remains_blocked(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            (
                content_resolution
                .validate_safe_remote_url(
                    (
                        "http://localhost/"
                        "private"
                    )
                )
            )


if __name__ == "__main__":
    unittest.main()
