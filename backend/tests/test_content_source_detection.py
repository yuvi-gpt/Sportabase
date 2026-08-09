import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


class ContentSourceDetectionTests(
    unittest.TestCase
):
    def test_youtube_watch_url(
        self,
    ):
        result = main.detect_content_source(
            "https://www.youtube.com/"
            "watch?v=1590RBk06L8"
            "&si=tracking-value"
        )

        self.assertEqual(
            result["source"],
            "youtube",
        )

        self.assertEqual(
            result["mode"],
            "video",
        )

        self.assertEqual(
            result["normalized_url"],
            (
                "https://youtube.com/"
                "watch?v=1590RBk06L8"
            ),
        )


    def test_youtube_short_url(
        self,
    ):
        result = main.detect_content_source(
            "https://youtu.be/1590RBk06L8"
        )

        self.assertEqual(
            result["source"],
            "youtube",
        )

        self.assertEqual(
            result["mode"],
            "video",
        )

        self.assertEqual(
            result["normalized_url"],
            (
                "https://youtube.com/"
                "watch?v=1590RBk06L8"
            ),
        )


    def test_article_url(
        self,
    ):
        result = main.detect_content_source(
            "https://example.com/"
            "sports/story?utm_source=test"
            "&page=2"
        )

        self.assertEqual(
            result["source"],
            "article",
        )

        self.assertEqual(
            result["mode"],
            "article",
        )

        self.assertEqual(
            result["normalized_url"],
            (
                "https://example.com/"
                "sports/story?page=2"
            ),
        )


    def test_invalid_scheme_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "HTTP or HTTPS",
        ):
            main.detect_content_source(
                "ftp://example.com/story"
            )


    def test_invalid_youtube_url_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "valid video ID",
        ):
            main.detect_content_source(
                "https://youtube.com/watch"
            )


    def test_empty_url_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "required",
        ):
            main.detect_content_source("")


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
