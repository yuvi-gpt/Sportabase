import sys
import unittest

from pathlib import Path
from unittest.mock import patch

import requests


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app import main


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        headers=None,
        chunks=None,
        url="https://example.com/story",
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks or []
        self.url = url
        self.encoding = "utf-8"
        self.closed = False

    def iter_content(self, chunk_size=65536):
        del chunk_size

        for chunk in self._chunks:
            yield chunk

    def close(self):
        self.closed = True


class SafeArticleFetchTests(unittest.TestCase):
    def test_fetches_public_html_page(self):
        response = FakeResponse(
            headers={
                "Content-Type": (
                    "text/html; charset=utf-8"
                ),
            },
            chunks=[
                b"<html><body>",
                b"Sports article",
                b"</body></html>",
            ],
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/story"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=response,
            ) as request:
                result = (
                    main.fetch_safe_article_html(
                        "https://example.com/story"
                    )
                )

        self.assertEqual(
            result["final_url"],
            "https://example.com/story",
        )

        self.assertIn(
            "Sports article",
            result["html"],
        )

        self.assertEqual(
            result["redirect_count"],
            0,
        )

        self.assertTrue(response.closed)

        request.assert_called_once()

        call_options = request.call_args.kwargs

        self.assertFalse(
            call_options["allow_redirects"]
        )

        self.assertTrue(
            call_options["stream"]
        )

    def test_rejects_non_html_content_type(self):
        response = FakeResponse(
            headers={
                "Content-Type": "application/pdf",
            },
            chunks=[b"%PDF"],
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/file.pdf"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=response,
            ):
                with self.assertRaises(
                    ValueError
                ):
                    main.fetch_safe_article_html(
                        "https://example.com/file.pdf"
                    )

        self.assertTrue(response.closed)

    def test_rejects_declared_oversized_response(self):
        response = FakeResponse(
            headers={
                "Content-Type": "text/html",
                "Content-Length": "2000",
            },
            chunks=[b"<html></html>"],
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/large"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=response,
            ):
                with self.assertRaises(
                    ValueError
                ):
                    main.fetch_safe_article_html(
                        "https://example.com/large",
                        max_bytes=1000,
                    )

        self.assertTrue(response.closed)

    def test_rejects_stream_that_exceeds_limit(self):
        response = FakeResponse(
            headers={
                "Content-Type": "text/html",
            },
            chunks=[
                b"a" * 700,
                b"b" * 700,
            ],
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/large"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=response,
            ):
                with self.assertRaises(
                    ValueError
                ):
                    main.fetch_safe_article_html(
                        "https://example.com/large",
                        max_bytes=1000,
                    )

        self.assertTrue(response.closed)

    def test_validates_redirect_destination(self):
        redirect = FakeResponse(
            status_code=302,
            headers={
                "Location": (
                    "http://127.0.0.1/private"
                ),
            },
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            side_effect=[
                "https://example.com/story",
                ValueError(
                    "Private address blocked."
                ),
            ],
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=redirect,
            ) as request:
                with self.assertRaises(
                    ValueError
                ):
                    main.fetch_safe_article_html(
                        "https://example.com/story"
                    )

        self.assertEqual(
            request.call_count,
            1,
        )

        self.assertTrue(redirect.closed)

    def test_follows_safe_redirect(self):
        redirect = FakeResponse(
            status_code=301,
            headers={
                "Location": "/final-story",
            },
        )

        final_response = FakeResponse(
            headers={
                "Content-Type": "text/html",
            },
            chunks=[
                b"<html>Final story</html>",
            ],
            url=(
                "https://example.com/final-story"
            ),
        )

        with patch.object(
            main,
            "validate_safe_remote_url",
            side_effect=[
                "https://example.com/story",
                (
                    "https://example.com/"
                    "final-story"
                ),
            ],
        ):
            with patch.object(
                main.requests,
                "get",
                side_effect=[
                    redirect,
                    final_response,
                ],
            ):
                result = (
                    main.fetch_safe_article_html(
                        "https://example.com/story"
                    )
                )

        self.assertEqual(
            result["final_url"],
            "https://example.com/final-story",
        )

        self.assertEqual(
            result["redirect_count"],
            1,
        )

        self.assertTrue(redirect.closed)
        self.assertTrue(final_response.closed)

    def test_converts_timeout_to_value_error(self):
        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/story"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                side_effect=requests.Timeout(
                    "Request timed out."
                ),
            ):
                with self.assertRaises(
                    ValueError
                ):
                    main.fetch_safe_article_html(
                        "https://example.com/story"
                    )


    def test_prefers_utf8_when_html_has_no_declared_charset(
        self,
    ):
        expected_text = (
            "Atl\u00e9tico "
            "Bar\u00e7a "
            "Ara\u00fajo "
            "\u20ac "
            "\u00a3"
        )

        response = FakeResponse(
            headers={
                "Content-Type": "text/html",
            },
            chunks=[
                (
                    "<html><body>"
                    + expected_text
                    + "</body></html>"
                ).encode("utf-8"),
            ],
        )

        response.encoding = "ISO-8859-1"

        with patch.object(
            main,
            "validate_safe_remote_url",
            return_value=(
                "https://example.com/story"
            ),
        ):
            with patch.object(
                main.requests,
                "get",
                return_value=response,
            ):
                result = (
                    main.fetch_safe_article_html(
                        "https://example.com/story"
                    )
                )

        self.assertIn(
            expected_text,
            result["html"],
        )

        self.assertNotIn(
            "Atl\u00c3\u00a9tico",
            result["html"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
