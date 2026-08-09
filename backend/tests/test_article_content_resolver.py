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


class ArticleContentResolverTests(
    unittest.TestCase
):
    def setUp(self):
        self.normalized_url = (
            "https://example.com/sports/story"
        )

        self.fetched = {
            "html": (
                "<html><article>"
                "<p>Mock article body.</p>"
                "</article></html>"
            ),
            "final_url": (
                "https://example.com/final-story"
            ),
            "redirect_count": 1,
            "content_type": "text/html",
            "byte_count": 2400,
        }

        self.extracted = {
            "title": "Mock sports article",
            "text": (
                "This is the extracted article body "
                "containing enough useful sports "
                "reporting for analysis."
            ),
            "extraction_method": "article",
            "paragraph_count": 3,
            "character_count": 96,
        }

    def test_combines_fetch_and_extraction_results(
        self,
    ):
        with patch.object(
            main,
            "fetch_safe_article_html",
            return_value=self.fetched,
        ) as fetcher:
            with patch.object(
                main,
                "extract_article_content",
                return_value=self.extracted,
            ) as extractor:
                result = (
                    main.resolve_article_content(
                        self.normalized_url
                    )
                )

        fetcher.assert_called_once_with(
            self.normalized_url
        )

        extractor.assert_called_once_with(
            self.fetched["html"]
        )

        self.assertEqual(
            result["title"],
            "Mock sports article",
        )

        self.assertEqual(
            result["content"],
            self.extracted["text"],
        )

        self.assertEqual(
            result["metadata"]["final_url"],
            "https://example.com/final-story",
        )

        self.assertEqual(
            result["metadata"]["redirect_count"],
            1,
        )

        self.assertEqual(
            result["metadata"]["extraction_method"],
            "article",
        )

        self.assertEqual(
            result["metadata"]["paragraph_count"],
            3,
        )

        self.assertEqual(
            result["metadata"]["byte_count"],
            2400,
        )

    def test_endpoint_uses_connected_resolver(
        self,
    ):
        with patch.object(
            main,
            "fetch_safe_article_html",
            return_value=self.fetched,
        ):
            with patch.object(
                main,
                "extract_article_content",
                return_value=self.extracted,
            ):
                response = main.resolve_content(
                    main.ContentResolveRequest(
                        url=(
                            self.normalized_url
                            + "?utm_source=test"
                        )
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
            response.title,
            "Mock sports article",
        )

        self.assertEqual(
            response.content,
            self.extracted["text"],
        )

        self.assertEqual(
            response.content_characters,
            len(self.extracted["text"]),
        )

        self.assertEqual(
            response.metadata["final_url"],
            "https://example.com/final-story",
        )

    def test_fetch_failure_returns_502(
        self,
    ):
        with patch.object(
            main,
            "fetch_safe_article_html",
            side_effect=ValueError(
                "The article request timed out."
            ),
        ):
            with self.assertRaises(
                HTTPException
            ) as context:
                main.resolve_article_content(
                    self.normalized_url
                )

        self.assertEqual(
            context.exception.status_code,
            502,
        )

        self.assertIn(
            "timed out",
            str(context.exception.detail),
        )

    def test_extraction_failure_returns_422(
        self,
    ):
        with patch.object(
            main,
            "fetch_safe_article_html",
            return_value=self.fetched,
        ):
            with patch.object(
                main,
                "extract_article_content",
                side_effect=ValueError(
                    (
                        "The page does not contain "
                        "enough meaningful article text."
                    )
                ),
            ):
                with self.assertRaises(
                    HTTPException
                ) as context:
                    main.resolve_article_content(
                        self.normalized_url
                    )

        self.assertEqual(
            context.exception.status_code,
            422,
        )

        self.assertIn(
            "meaningful article text",
            str(context.exception.detail),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
