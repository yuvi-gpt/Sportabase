import sys
import unittest

from pathlib import Path


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
    article_rules,
)


class ArticleRulesModuleTests(
    unittest.TestCase
):
    def test_main_reexports_moved_rule_symbols(
        self,
    ):
        names = (
            "clean_html",
            "_clamp",
            "_domain_from_url",
            "signal_hits",
            "ARTICLE_TYPE_LABELS",
            "AI_ARTICLE_TYPE_VALUES",
            "normalize_ai_article_classification",
            "detect_article_type",
            "_source_reputation",
            "badge",
            "merit_score",
        )

        for name in names:
            with self.subTest(
                name=name
            ):
                self.assertIs(
                    getattr(
                        main,
                        name,
                    ),
                    getattr(
                        article_rules,
                        name,
                    ),
                )

    def test_clean_html_contract_preserved(
        self,
    ):
        result = (
            article_rules
            .clean_html(
                "<p>Hello&nbsp;   world</p>"
            )
        )

        self.assertEqual(
            result,
            "Hello world",
        )

    def test_signal_hits_uses_phrase_boundaries(
        self,
    ):
        result = (
            article_rules
            .signal_hits(
                [
                    "interest",
                    "official offer",
                ],
                (
                    "Interesting stories are "
                    "different from interest. "
                    "There is no official offer."
                ).lower(),
            )
        )

        self.assertIn(
            "interest",
            result,
        )

        self.assertIn(
            "official offer",
            result,
        )

        self.assertEqual(
            result.count(
                "interest"
            ),
            1,
        )

    def test_invalid_ai_classification_falls_back_to_generic(
        self,
    ):
        result = (
            article_rules
            .normalize_ai_article_classification(
                {
                    "article_type":
                        "definitely_not_valid",
                    "article_subtype":
                        "made_up",
                    "confidence": 0.99,
                    "reason":
                        "Unsupported output",
                }
            )
        )

        self.assertEqual(
            result[
                "article_type"
            ],
            "generic_news",
        )

        self.assertEqual(
            result[
                "article_subtype"
            ],
            "general",
        )

        self.assertLessEqual(
            result[
                "confidence"
            ],
            0.35,
        )

    def test_badge_threshold_contract_preserved(
        self,
    ):
        cases = (
            (
                19,
                "Unverified Rumor",
            ),
            (
                20,
                "Speculative",
            ),
            (
                50,
                "Developing",
            ),
            (
                80,
                "Strong Evidence",
            ),
            (
                90,
                "High Credibility",
            ),
        )

        for score, expected in cases:
            with self.subTest(
                score=score
            ):
                self.assertEqual(
                    article_rules.badge(
                        score
                    ),
                    expected,
                )

    def test_transfer_rumor_classification_preserved(
        self,
    ):
        result = (
            article_rules
            .detect_article_type(
                (
                    "Arsenal linked with striker "
                    "as club monitors summer move"
                ),
                (
                    "Reports suggest Arsenal are "
                    "interested in the striker. "
                    "No official offer has been "
                    "made and no agreement has "
                    "been reached."
                ),
                (
                    "https://example.com/"
                    "transfer-rumour"
                ),
            )
        )

        self.assertEqual(
            result[
                "primary_type"
            ],
            "transfer_rumor",
        )

    def test_legacy_merit_is_deterministic_and_bounded(
        self,
    ):
        kwargs = {
            "title":
                "Club confirms player signing",
            "text": (
                "The club confirmed the signing "
                "in an official statement. "
                "The player has signed a "
                "four-year contract after "
                "completing a medical. "
                "The announcement included "
                "details of the agreement."
            ),
            "url":
                "https://example.com/signing",
        }

        first = (
            article_rules
            .merit_score(
                **kwargs
            )
        )

        second = (
            article_rules
            .merit_score(
                **kwargs
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertGreaterEqual(
            first[
                "total"
            ],
            0,
        )

        self.assertLessEqual(
            first[
                "total"
            ],
            100,
        )

        self.assertIn(
            "components",
            first,
        )

        self.assertIn(
            "calculation",
            first,
        )

    def test_extract_fallback_still_uses_moved_article_signals(
        self,
    ):
        result = (
            main.extractive_fallback(
                (
                    "The club confirmed the move "
                    "in an official statement and "
                    "said the player signed a "
                    "four-year contract today. "
                    "The agreement followed weeks "
                    "of negotiations and included "
                    "a completed medical."
                ),
                max_bullets=1,
            )
        )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertIsInstance(
            result[0],
            str,
        )


if __name__ == "__main__":
    unittest.main()
