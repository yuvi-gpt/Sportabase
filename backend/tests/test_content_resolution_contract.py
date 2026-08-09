import sys
import unittest

from pathlib import Path

from pydantic import ValidationError


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


class ContentResolutionContractTests(
    unittest.TestCase
):
    def test_request_accepts_shared_url(
        self,
    ):
        request = main.ContentResolveRequest(
            url=(
                "https://youtube.com/"
                "watch?v=contract-test"
            )
        )

        self.assertEqual(
            request.url,
            (
                "https://youtube.com/"
                "watch?v=contract-test"
            ),
        )


    def test_request_rejects_short_url(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            main.ContentResolveRequest(
                url="bad"
            )


    def test_youtube_response_contract(
        self,
    ):
        response = main.ContentResolveResponse(
            url=(
                "https://youtu.be/contract-test"
            ),
            normalized_url=(
                "https://youtube.com/"
                "watch?v=contract-test"
            ),
            source="youtube",
            mode="video",
            title="Test video",
            content=(
                "This is an extracted transcript."
            ),
            content_characters=32,
            metadata={
                "segment_count": 4,
            },
        )

        self.assertEqual(
            response.source,
            "youtube",
        )

        self.assertEqual(
            response.mode,
            "video",
        )

        self.assertEqual(
            response.metadata[
                "segment_count"
            ],
            4,
        )


    def test_article_response_contract(
        self,
    ):
        response = main.ContentResolveResponse(
            url=(
                "https://example.com/"
                "sports/story"
            ),
            normalized_url=(
                "https://example.com/"
                "sports/story"
            ),
            source="article",
            mode="article",
            title="Test article",
            content=(
                "This is extracted article text."
            ),
            content_characters=31,
        )

        self.assertEqual(
            response.source,
            "article",
        )

        self.assertEqual(
            response.mode,
            "article",
        )

        self.assertEqual(
            response.metadata,
            {},
        )


    def test_unsupported_source_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            main.ContentResolveResponse(
                url="https://example.com/post",
                normalized_url=(
                    "https://example.com/post"
                ),
                source="social",
                mode="article",
                title="Post",
                content="Some extracted content.",
                content_characters=23,
            )


    def test_empty_content_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValidationError
        ):
            main.ContentResolveResponse(
                url="https://example.com/story",
                normalized_url=(
                    "https://example.com/story"
                ),
                source="article",
                mode="article",
                title="Story",
                content="",
                content_characters=0,
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
