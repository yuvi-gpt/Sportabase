import hashlib
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
    analysis_cache,
)


class AnalysisCacheModuleTests(
    unittest.TestCase
):
    def test_content_hash_normalizes_cleaned_text(
        self,
    ):
        cleaner = lambda value: (
            " Example   sports article "
        )

        result = (
            analysis_cache
            .analysis_content_hash(
                "<p>ignored</p>",
                clean_html=cleaner,
            )
        )

        expected = hashlib.sha256(
            (
                "Example sports article"
            ).encode(
                "utf-8"
            )
        ).hexdigest()

        self.assertEqual(
            result,
            expected,
        )

    def test_main_content_hash_injects_current_cleaner(
        self,
    ):
        with patch.object(
            main,
            "clean_html",
            return_value="canonical content",
        ) as cleaner:
            result = (
                main.analysis_content_hash(
                    "<b>raw</b>"
                )
            )

        cleaner.assert_called_once_with(
            "<b>raw</b>"
        )

        self.assertEqual(
            result,
            hashlib.sha256(
                b"canonical content"
            ).hexdigest(),
        )

    def test_article_cache_key_uses_runtime_versions(
        self,
    ):
        original_analysis = (
            main.ANALYSIS_VERSION
        )

        original_scoring = (
            main.SCORING_VERSION
        )

        try:
            main.ANALYSIS_VERSION = (
                "analysis-test-v1"
            )

            main.SCORING_VERSION = (
                "score-test-v1"
            )

            first = (
                main.make_analysis_cache_key(
                    mode="article",
                    url=(
                        "https://example.com/story"
                    ),
                    content="Article body",
                )
            )

            main.SCORING_VERSION = (
                "score-test-v2"
            )

            second = (
                main.make_analysis_cache_key(
                    mode="article",
                    url=(
                        "https://example.com/story"
                    ),
                    content="Article body",
                )
            )

        finally:
            main.ANALYSIS_VERSION = (
                original_analysis
            )

            main.SCORING_VERSION = (
                original_scoring
            )

        self.assertNotEqual(
            first,
            second,
        )

    def test_live_ttl_uses_runtime_configuration(
        self,
    ):
        original_normal = (
            main.ANALYSIS_CACHE_TTL_SECONDS
        )

        original_live = (
            main.LIVE_CACHE_TTL_SECONDS
        )

        try:
            main.ANALYSIS_CACHE_TTL_SECONDS = 999
            main.LIVE_CACHE_TTL_SECONDS = 123

            self.assertEqual(
                main.cache_ttl_for_analysis(
                    "article",
                    "live_commentary",
                ),
                123,
            )

            self.assertEqual(
                main.cache_ttl_for_analysis(
                    "article",
                    "transfer_report",
                ),
                999,
            )

        finally:
            main.ANALYSIS_CACHE_TTL_SECONDS = (
                original_normal
            )

            main.LIVE_CACHE_TTL_SECONDS = (
                original_live
            )

    def test_cache_read_wrapper_injects_database(
        self,
    ):
        sentinel = {
            "merit_score": 70
        }

        with patch.object(
            main,
            "_get_cached_analysis_cache_impl",
            return_value=sentinel,
        ) as impl:
            result = (
                main.get_cached_analysis(
                    "cache-key"
                )
            )

        self.assertIs(
            result,
            sentinel,
        )

        self.assertIs(
            (
                impl.call_args.kwargs[
                    "connection_factory"
                ]
            ),
            main.db_conn,
        )

    def test_cache_write_wrapper_injects_runtime_dependencies(
        self,
    ):
        with patch.object(
            main,
            "_set_cached_analysis_cache_impl",
        ) as impl:
            main.set_cached_analysis(
                "cache-key",
                "article",
                "https://example.com/story",
                "Article body",
                {
                    "merit_score": 70
                },
                "transfer_report",
            )

        kwargs = (
            impl.call_args.kwargs
        )

        self.assertIs(
            kwargs[
                "connection_factory"
            ],
            main.db_conn,
        )

        self.assertIs(
            kwargs[
                "ttl_resolver"
            ],
            main.cache_ttl_for_analysis,
        )

        self.assertIs(
            kwargs[
                "normalize_url"
            ],
            main.normalized_analysis_url,
        )

        self.assertIs(
            kwargs[
                "content_hash_resolver"
            ],
            main.analysis_content_hash,
        )

        self.assertEqual(
            kwargs[
                "analysis_version"
            ],
            main.ANALYSIS_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
