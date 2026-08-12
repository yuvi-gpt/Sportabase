import unittest

from app import main


class AnalysisCacheKeyTests(unittest.TestCase):
    def test_article_cache_key_changes_with_scoring_version(
        self,
    ):
        original_version = main.SCORING_VERSION

        try:
            main.SCORING_VERSION = "merit-test-v1"

            first_key = main.make_analysis_cache_key(
                mode="article",
                url="https://example.com/story",
                content="Example article content.",
                variant="max_bullets:4",
            )

            main.SCORING_VERSION = "merit-test-v2"

            second_key = main.make_analysis_cache_key(
                mode="article",
                url="https://example.com/story",
                content="Example article content.",
                variant="max_bullets:4",
            )
        finally:
            main.SCORING_VERSION = original_version

        self.assertNotEqual(
            first_key,
            second_key,
        )

    def test_article_cache_key_changes_with_context_hash(
        self,
    ):
        first_key = main.make_analysis_cache_key(
            mode="article",
            url="https://example.com/story",
            content="Example article content.",
            variant="max_bullets:4",
            context_hash="evidence-context-a",
        )

        second_key = main.make_analysis_cache_key(
            mode="article",
            url="https://example.com/story",
            content="Example article content.",
            variant="max_bullets:4",
            context_hash="evidence-context-b",
        )

        self.assertNotEqual(
            first_key,
            second_key,
        )

    def test_same_article_context_reuses_cache_key(
        self,
    ):
        first_key = main.make_analysis_cache_key(
            mode="article",
            url="https://example.com/story",
            content="Example article content.",
            variant="max_bullets:4",
            context_hash="evidence-context-a",
        )

        second_key = main.make_analysis_cache_key(
            mode="article",
            url="https://example.com/story",
            content="Example article content.",
            variant="max_bullets:4",
            context_hash="evidence-context-a",
        )

        self.assertEqual(
            first_key,
            second_key,
        )

    def test_video_cache_key_ignores_context_hash(
        self,
    ):
        first_key = main.make_analysis_cache_key(
            mode="video",
            url=(
                "https://www.youtube.com/"
                "watch?v=abc123xyz"
            ),
            content="Example transcript content.",
            context_hash="evidence-context-a",
        )

        second_key = main.make_analysis_cache_key(
            mode="video",
            url=(
                "https://www.youtube.com/"
                "watch?v=abc123xyz"
            ),
            content="Example transcript content.",
            context_hash="evidence-context-b",
        )

        self.assertEqual(
            first_key,
            second_key,
        )

    def test_video_cache_key_ignores_article_scoring_version(
        self,
    ):
        original_version = main.SCORING_VERSION

        try:
            main.SCORING_VERSION = "merit-test-v1"

            first_key = main.make_analysis_cache_key(
                mode="video",
                url=(
                    "https://www.youtube.com/"
                    "watch?v=abc123xyz"
                ),
                content="Example transcript content.",
            )

            main.SCORING_VERSION = "merit-test-v2"

            second_key = main.make_analysis_cache_key(
                mode="video",
                url=(
                    "https://www.youtube.com/"
                    "watch?v=abc123xyz"
                ),
                content="Example transcript content.",
            )
        finally:
            main.SCORING_VERSION = original_version

        self.assertEqual(
            first_key,
            second_key,
        )


if __name__ == "__main__":
    unittest.main()