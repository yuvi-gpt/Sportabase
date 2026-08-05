import sys
import json
import unittest

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.main import (
    gemini_article_single_pass,
    normalize_ai_article_classification,
    run_article_ai_strategy,
)


class ArticleSinglePassContractTests(
    unittest.TestCase
):
    def test_weak_english_uses_single_pass(
        self,
    ):
        single_pass_payload = {
            "classification": {
                "enabled": True,
                "article_type":
                    "transfer_rumor",
                "article_type_label":
                    "Transfer Rumor",
                "article_subtype":
                    "unconfirmed_transfer_claim",
                "confidence": 0.91,
                "reason":
                    "Rumor wording detected.",
            },
            "bullets": [
                "A possible transfer has "
                "been reported."
            ],
            "ui_labels": {},
        }

        with patch(
            "app.main."
            "gemini_article_single_pass",
            return_value=(
                single_pass_payload
            ),
        ) as mock_single_pass, patch(
            "app.main."
            "ai_detect_article_type",
        ) as mock_classifier:
            result = (
                run_article_ai_strategy(
                    title=(
                        "Player linked with move"
                    ),
                    text=(
                        "Reports suggest a "
                        "possible summer move."
                    ),
                    url=(
                        "https://example.com/"
                        "transfer"
                    ),
                    max_bullets=3,
                    language_info={
                        "detected_language":
                            "English",
                    },
                    is_non_english_or_mixed=(
                        False
                    ),
                    rule_is_weak_generic=(
                        True
                    ),
                    client_key="test",
                )
            )

        mock_single_pass.assert_called_once()
        mock_classifier.assert_not_called()

        self.assertTrue(
            result["used_single_pass"]
        )

        self.assertEqual(
            result[
                "ai_type_info"
            ][
                "article_type"
            ],
            "transfer_rumor",
        )


    def test_multilingual_keeps_old_path(
        self,
    ):
        classifier_payload = {
            "enabled": True,
            "article_type":
                "match_report",
            "article_type_label":
                "Match Report / Result",
            "article_subtype":
                "final_score",
            "confidence": 0.92,
            "reason":
                "The article reports a result.",
        }

        with patch(
            "app.main."
            "gemini_article_single_pass",
        ) as mock_single_pass, patch(
            "app.main."
            "ai_detect_article_type",
            return_value=(
                classifier_payload
            ),
        ) as mock_classifier:
            result = (
                run_article_ai_strategy(
                    title="Equipo gana 3-1",
                    text=(
                        "El equipo gan? el "
                        "partido por 3-1."
                    ),
                    url=(
                        "https://example.com/"
                        "resultado"
                    ),
                    max_bullets=3,
                    language_info={
                        "detected_language":
                            "Spanish",
                    },
                    is_non_english_or_mixed=(
                        True
                    ),
                    rule_is_weak_generic=(
                        False
                    ),
                    client_key="test",
                )
            )

        mock_single_pass.assert_not_called()
        mock_classifier.assert_called_once()

        self.assertFalse(
            result["used_single_pass"]
        )

        self.assertIsNone(
            result[
                "single_pass_result"
            ]
        )


    def test_confident_english_skips_classifier(
        self,
    ):
        with patch(
            "app.main."
            "gemini_article_single_pass",
        ) as mock_single_pass, patch(
            "app.main."
            "ai_detect_article_type",
        ) as mock_classifier:
            result = (
                run_article_ai_strategy(
                    title=(
                        "Club officially "
                        "announces signing"
                    ),
                    text=(
                        "The club officially "
                        "confirmed the signing."
                    ),
                    url=(
                        "https://example.com/"
                        "official"
                    ),
                    max_bullets=3,
                    language_info={
                        "detected_language":
                            "English",
                    },
                    is_non_english_or_mixed=(
                        False
                    ),
                    rule_is_weak_generic=(
                        False
                    ),
                    client_key="test",
                )
            )

        mock_single_pass.assert_not_called()
        mock_classifier.assert_not_called()

        self.assertFalse(
            result["used_single_pass"]
        )


    @patch(
        "app.main.generate_gemini_content"
    )
    @patch(
        "app.main.gemini_client"
    )
    def test_combined_call_uses_one_request(
        self,
        mock_client,
        mock_generate,
    ):
        mock_client.return_value = object()

        mock_generate.return_value = (
            SimpleNamespace(
                text=json.dumps(
                    {
                        "article_type":
                            "transfer_rumor",
                        "article_subtype":
                            "unconfirmed_transfer_claim",
                        "confidence": 0.93,
                        "reason":
                            "Rumor language is used.",
                        "bullets": [
                            "The player has been linked "
                            "with a possible move.",
                            "No completed agreement has "
                            "been officially announced.",
                            "No completed agreement has "
                            "been officially announced.",
                        ],
                        "ui_labels": {
                            "summary": "Summary",
                        },
                    }
                )
            )
        )

        result = (
            gemini_article_single_pass(
                title=(
                    "Player linked with move"
                ),
                text=(
                    "Reports suggest the player "
                    "could move this summer."
                ),
                url=(
                    "https://example.com/rumor"
                ),
                max_bullets=3,
                language_info={
                    "detected_language":
                        "English",
                },
            )
        )

        self.assertEqual(
            mock_generate.call_count,
            1,
        )

        self.assertEqual(
            result[
                "classification"
            ][
                "article_type"
            ],
            "transfer_rumor",
        )

        self.assertEqual(
            len(result["bullets"]),
            2,
        )


    @patch(
        "app.main.generate_gemini_content"
    )
    @patch(
        "app.main.gemini_client"
    )
    def test_missing_client_uses_fallback(
        self,
        mock_client,
        mock_generate,
    ):
        mock_client.return_value = None

        result = (
            gemini_article_single_pass(
                title="Match report",
                text=(
                    "The team won the match "
                    "3-1 after scoring twice."
                ),
                max_bullets=2,
            )
        )

        mock_generate.assert_not_called()

        self.assertFalse(
            result[
                "classification"
            ][
                "enabled"
            ]
        )

        self.assertIsInstance(
            result["bullets"],
            list,
        )


    def test_supported_classification_survives(
        self,
    ):
        result = (
            normalize_ai_article_classification(
                {
                    "article_type":
                        "transfer_rumor",
                    "article_subtype":
                        "unconfirmed_transfer_claim",
                    "confidence": 0.914,
                    "reason":
                        "The report uses rumor language.",
                }
            )
        )

        self.assertEqual(
            result["article_type"],
            "transfer_rumor",
        )

        self.assertEqual(
            result["article_type_label"],
            "Transfer Rumor",
        )

        self.assertEqual(
            result["confidence"],
            0.91,
        )


    def test_unsupported_type_is_safe(
        self,
    ):
        result = (
            normalize_ai_article_classification(
                {
                    "article_type":
                        "certain_transfer",
                    "article_subtype":
                        "completed",
                    "confidence": 0.98,
                    "reason":
                        "Unsupported classification.",
                }
            )
        )

        self.assertEqual(
            result["article_type"],
            "generic_news",
        )

        self.assertEqual(
            result["article_subtype"],
            "general",
        )

        self.assertLessEqual(
            result["confidence"],
            0.35,
        )


    def test_confidence_is_bounded(
        self,
    ):
        result = (
            normalize_ai_article_classification(
                {
                    "article_type":
                        "match_report",
                    "confidence": 7,
                }
            )
        )

        self.assertEqual(
            result["confidence"],
            0.99,
        )


    def test_invalid_payload_is_safe(
        self,
    ):
        result = (
            normalize_ai_article_classification(
                ["not", "an", "object"]
            )
        )

        self.assertEqual(
            result["article_type"],
            "generic_news",
        )

        self.assertEqual(
            result["confidence"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
