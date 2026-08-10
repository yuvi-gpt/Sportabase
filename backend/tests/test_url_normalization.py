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


class UrlNormalizationTests(
    unittest.TestCase
):
    def test_preserves_www_for_article_urls(
        self,
    ):
        result = main.normalized_analysis_url(
            (
                "https://www.espn.in/football/story/"
                "_/id/49566333/test-story"
                "?utm_source=test"
            )
        )

        self.assertEqual(
            result,
            (
                "https://www.espn.in/football/story/"
                "_/id/49566333/test-story"
            ),
        )

    def test_youtube_still_uses_canonical_host(
        self,
    ):
        result = main.normalized_analysis_url(
            (
                "https://www.youtube.com/watch"
                "?v=1590RBk06L8"
                "&utm_source=test"
            )
        )

        self.assertEqual(
            result,
            (
                "https://youtube.com/watch"
                "?v=1590RBk06L8"
            ),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
