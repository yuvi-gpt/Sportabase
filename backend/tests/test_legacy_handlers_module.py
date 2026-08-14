import sys
import unittest

from pathlib import Path
from unittest.mock import patch


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
    legacy_handlers,
)


class LegacyHandlersModuleTests(
    unittest.TestCase
):
    def test_pure_helpers_are_reexported(
        self,
    ):
        self.assertIs(
            main.stable_id,
            legacy_handlers.stable_id,
        )

        self.assertIs(
            main.parse_published,
            legacy_handlers.parse_published,
        )

        self.assertIs(
            main.resolve_youtube_content,
            legacy_handlers.resolve_youtube_content,
        )

    def test_load_sources_uses_current_path(
        self,
    ):
        sentinel = []

        with patch.object(
            main,
            "_load_sources_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.load_sources()

        self.assertIs(
            result,
            sentinel,
        )

        self.assertEqual(
            implementation.call_args.kwargs[
                "SOURCES_PATH"
            ],
            main.SOURCES_PATH,
        )

    def test_ingest_wrapper_injects_runtime(
        self,
    ):
        sentinel = object()

        with patch.object(
            main,
            "_ingest_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.ingest()

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "db_conn"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "gemini_tldr"
            ],
            main.gemini_tldr,
        )

        self.assertIs(
            kwargs[
                "stable_id"
            ],
            main.stable_id,
        )

        self.assertIs(
            kwargs[
                "IngestResponse"
            ],
            main.IngestResponse,
        )

    def test_stories_wrapper_injects_runtime(
        self,
    ):
        sentinel = []

        with patch.object(
            main,
            "_stories_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.stories(
                sport="football",
                source="test",
                limit=5,
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs[
                "sport"
            ],
            "football",
        )

        self.assertEqual(
            kwargs[
                "source"
            ],
            "test",
        )

        self.assertEqual(
            kwargs[
                "limit"
            ],
            5,
        )

        self.assertIs(
            kwargs[
                "db_conn"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "Story"
            ],
            main.Story,
        )

    def test_article_resolver_preserves_patch_surface(
        self,
    ):
        fetched = {
            "html":
                "<html>article</html>",
            "final_url":
                "https://example.com/final",
            "redirect_count":
                1,
            "content_type":
                "text/html",
            "byte_count":
                100,
        }

        extracted = {
            "title":
                "Example title",
            "text":
                "Example article body.",
            "extraction_method":
                "test",
            "paragraph_count":
                1,
        }

        with (
            patch.object(
                main,
                "fetch_safe_article_html",
                return_value=fetched,
            ) as fetcher,
            patch.object(
                main,
                "extract_article_content",
                return_value=extracted,
            ) as extractor,
        ):
            result = (
                main.resolve_article_content(
                    "https://example.com/story"
                )
            )

        fetcher.assert_called_once_with(
            "https://example.com/story"
        )

        extractor.assert_called_once_with(
            "<html>article</html>"
        )

        self.assertEqual(
            result[
                "title"
            ],
            "Example title",
        )

        self.assertEqual(
            result[
                "content"
            ],
            "Example article body.",
        )

    def test_resolve_content_uses_current_resolvers(
        self,
    ):
        sentinel = object()

        with patch.object(
            main,
            "_resolve_content_handler_impl",
            return_value=sentinel,
        ) as implementation:
            result = main.resolve_content(
                object()
            )

        self.assertIs(
            result,
            sentinel,
        )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "detect_content_source"
            ],
            main.detect_content_source,
        )

        self.assertIs(
            kwargs[
                "resolve_article_content"
            ],
            main.resolve_article_content,
        )

        self.assertIs(
            kwargs[
                "resolve_youtube_content"
            ],
            main.resolve_youtube_content,
        )

        self.assertIs(
            kwargs[
                "ContentResolveResponse"
            ],
            main.ContentResolveResponse,
        )

    def test_legacy_routes_remain_registered(
        self,
    ):
        paths = (
            main.app.openapi()[
                "paths"
            ]
        )

        for path, method in (
            (
                "/ingest",
                "post",
            ),
            (
                "/stories",
                "get",
            ),
            (
                "/resolve-content",
                "post",
            ),
        ):
            with self.subTest(
                path=path
            ):
                self.assertIn(
                    path,
                    paths,
                )

                self.assertIn(
                    method,
                    paths[
                        path
                    ],
                )

    def test_service_has_no_route_registration(
        self,
    ):
        source = Path(
            legacy_handlers.__file__
        ).read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            "@app.",
            source,
        )

        self.assertNotIn(
            "from app.main",
            source,
        )

        self.assertNotIn(
            "from app import main",
            source,
        )


if __name__ == "__main__":
    unittest.main()
