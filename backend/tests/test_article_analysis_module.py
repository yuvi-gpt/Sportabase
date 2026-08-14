import sys
import unittest

from pathlib import Path
from unittest.mock import (
    Mock,
    patch,
)


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
    article_analysis,
)


class ArticleAnalysisModuleTests(
    unittest.TestCase
):
    def test_pure_helpers_are_reexported_directly(
        self,
    ):
        self.assertIs(
            main.extractive_fallback,
            article_analysis.extractive_fallback,
        )

        self.assertIs(
            main.normalize_article_bullets,
            article_analysis.normalize_article_bullets,
        )

    def test_candidate_semantics_injects_runtime(
        self,
    ):
        sentinel = {
            "status": "test"
        }

        with (
            patch.object(
                main,
                "_gemini_candidate_semantics_impl",
                return_value=sentinel,
            ) as implementation,
            patch.object(
                main,
                "gemini_client",
            ) as client_factory,
            patch.object(
                main,
                "generate_gemini_content",
            ) as generator,
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim={
                        "id": "claim-1"
                    },
                    candidate={
                        "id": "candidate-1"
                    },
                )
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
                "client_factory"
            ],
            client_factory,
        )

        self.assertIs(
            kwargs[
                "generator"
            ],
            generator,
        )

    def test_tldr_missing_client_uses_fallback(
        self,
    ):
        generator = Mock()

        result = (
            article_analysis
            .gemini_tldr_impl(
                title="Test",
                text=(
                    "The club officially confirmed "
                    "the result after the match and "
                    "published the final score."
                ),
                max_bullets=1,
                client_factory=(
                    lambda: None
                ),
                generator=generator,
                fallback_resolver=(
                    article_analysis
                    .extractive_fallback
                ),
                max_analyze_chars=6000,
            )
        )

        generator.assert_not_called()

        self.assertEqual(
            len(
                result[
                    "bullets"
                ]
            ),
            1,
        )

    def test_tldr_wrapper_injects_character_limit(
        self,
    ):
        original = (
            main.MAX_ANALYZE_CHARS
        )

        try:
            main.MAX_ANALYZE_CHARS = 4321

            with patch.object(
                main,
                "_gemini_tldr_impl",
                return_value={
                    "bullets": []
                },
            ) as implementation:
                main.gemini_tldr(
                    "Title",
                    "Body",
                )

        finally:
            main.MAX_ANALYZE_CHARS = original

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs[
                "max_analyze_chars"
            ],
            4321,
        )

        self.assertIs(
            kwargs[
                "fallback_resolver"
            ],
            main.extractive_fallback,
        )

    def test_single_pass_injects_current_dependencies(
        self,
    ):
        with (
            patch.object(
                main,
                "_gemini_article_single_pass_impl",
                return_value={
                    "classification": {}
                },
            ) as implementation,
            patch.object(
                main,
                "gemini_client",
            ) as client_factory,
            patch.object(
                main,
                "generate_gemini_content",
            ) as generator,
        ):
            main.gemini_article_single_pass(
                "Title",
                "Body",
            )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "client_factory"
            ],
            client_factory,
        )

        self.assertIs(
            kwargs[
                "generator"
            ],
            generator,
        )

        self.assertIs(
            kwargs[
                "classification_normalizer"
            ],
            (
                main
                .normalize_ai_article_classification
            ),
        )

        self.assertIs(
            kwargs[
                "bullet_normalizer"
            ],
            main.normalize_article_bullets,
        )

    def test_classifier_injects_runtime(
        self,
    ):
        with patch.object(
            main,
            "_ai_detect_article_type_impl",
            return_value={
                "enabled": False
            },
        ) as implementation:
            main.ai_detect_article_type(
                "Title",
                "Body",
            )

        kwargs = (
            implementation
            .call_args
            .kwargs
        )

        self.assertIs(
            kwargs[
                "client_factory"
            ],
            main.gemini_client,
        )

        self.assertIs(
            kwargs[
                "generator"
            ],
            main.generate_gemini_content,
        )

    def test_strategy_uses_current_single_pass(
        self,
    ):
        sentinel = {
            "classification": {
                "article_type":
                    "generic_news"
            },
            "bullets": [
                "Summary"
            ],
        }

        with patch.object(
            main,
            "gemini_article_single_pass",
            return_value=sentinel,
        ) as runner:
            result = (
                main.run_article_ai_strategy(
                    title="Title",
                    text="Body",
                    url=(
                        "https://example.com"
                    ),
                    max_bullets=3,
                    language_info={
                        "detected_language":
                            "English"
                    },
                    is_non_english_or_mixed=False,
                    rule_is_weak_generic=True,
                    client_key="client",
                )
            )

        runner.assert_called_once()

        self.assertTrue(
            result[
                "used_single_pass"
            ]
        )

        self.assertIs(
            result[
                "single_pass_result"
            ],
            sentinel,
        )

    def test_strategy_uses_current_classifier(
        self,
    ):
        classification = {
            "enabled": True,
            "article_type":
                "transfer_rumor",
        }

        with patch.object(
            main,
            "ai_detect_article_type",
            return_value=classification,
        ) as runner:
            result = (
                main.run_article_ai_strategy(
                    title="Title",
                    text="Body",
                    url=(
                        "https://example.com"
                    ),
                    max_bullets=3,
                    language_info={
                        "detected_language":
                            "Hindi-English mixed"
                    },
                    is_non_english_or_mixed=True,
                    rule_is_weak_generic=False,
                    client_key="client",
                )
            )

        runner.assert_called_once()

        self.assertFalse(
            result[
                "used_single_pass"
            ]
        )

        self.assertEqual(
            result[
                "ai_type_info"
            ],
            classification,
        )


if __name__ == "__main__":
    unittest.main()
