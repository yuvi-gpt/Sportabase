import sys
import unittest

from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app import main


class ContentResolutionEndpointTests(
    unittest.TestCase
):
    def test_youtube_dispatches_to_video_resolver(
        self,
    ):
        resolved_payload = {
            "title": "Test sports video",
            "content": (
                "This is a mocked transcript "
                "for a sports video."
            ),
            "metadata": {
                "segment_count": 7,
            },
        }

        with patch.object(
            main,
            "resolve_youtube_content",
            return_value=resolved_payload,
        ) as resolver:
            response = main.resolve_content(
                main.ContentResolveRequest(
                    url=(
                        "https://youtu.be/"
                        "1590RBk06L8"
                    )
                )
            )

        resolver.assert_called_once_with(
            (
                "https://youtube.com/"
                "watch?v=1590RBk06L8"
            )
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
            response.title,
            "Test sports video",
        )

        self.assertEqual(
            response.content_characters,
            len(response.content),
        )

        self.assertEqual(
            response.metadata[
                "segment_count"
            ],
            7,
        )


    def test_article_dispatches_to_article_resolver(
        self,
    ):
        resolved_payload = {
            "title": "Test sports article",
            "content": (
                "This is mocked article content "
                "for the resolver endpoint."
            ),
            "metadata": {
                "author": "Test Reporter",
            },
        }

        with patch.object(
            main,
            "resolve_article_content",
            return_value=resolved_payload,
        ) as resolver:
            response = main.resolve_content(
                main.ContentResolveRequest(
                    url=(
                        "https://example.com/"
                        "sports/story"
                        "?utm_source=test"
                    )
                )
            )

        resolver.assert_called_once_with(
            (
                "https://example.com/"
                "sports/story"
            )
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
            response.metadata["author"],
            "Test Reporter",
        )


    def test_invalid_url_returns_400(
        self,
    ):
        with self.assertRaises(
            HTTPException
        ) as context:
            main.resolve_content(
                main.ContentResolveRequest(
                    url="ftp://example.com/story"
                )
            )

        self.assertEqual(
            context.exception.status_code,
            400,
        )


    def test_invalid_resolver_payload_returns_502(
        self,
    ):
        with patch.object(
            main,
            "resolve_article_content",
            return_value=["invalid"],
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                main.resolve_content(
                    main.ContentResolveRequest(
                        url=(
                            "https://example.com/"
                            "sports/story"
                        )
                    )
                )

        self.assertEqual(
            context.exception.status_code,
            502,
        )


    def test_empty_content_returns_502(
        self,
    ):
        with patch.object(
            main,
            "resolve_article_content",
            return_value={
                "title": "Empty article",
                "content": "   ",
                "metadata": {},
            },
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                main.resolve_content(
                    main.ContentResolveRequest(
                        url=(
                            "https://example.com/"
                            "sports/story"
                        )
                    )
                )

        self.assertEqual(
            context.exception.status_code,
            502,
        )


    def test_placeholder_resolver_returns_501(
        self,
    ):
        with self.assertRaises(
            HTTPException
        ) as context:
            main.resolve_content(
                main.ContentResolveRequest(
                    url=(
                        "https://youtu.be/"
                        "1590RBk06L8"
                    )
                )
            )

        self.assertEqual(
            context.exception.status_code,
            501,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
