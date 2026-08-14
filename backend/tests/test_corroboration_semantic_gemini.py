import json
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
from app.services.corroboration_semantics import (
    CORROBORATION_SEMANTIC_GEMINI_MODEL,
    CORROBORATION_SEMANTIC_GEMINI_MODE,
    CORROBORATION_SEMANTIC_GEMINI_VERSION,
)


class FakeResponse:
    def __init__(self, payload):
        self.text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload)
        )


class CorroborationSemanticGeminiTests(
    unittest.TestCase
):
    def claim(self, **overrides):
        row = {
            "id": "claim-1",
            "canonical_text": (
                "Player Alpha has agreed to join "
                "Club Beta."
            ),
        }
        row.update(overrides)
        return row

    def candidate(self, **overrides):
        row = {
            "resolution_status": "resolved",
            "extracted_title": (
                "Player Alpha transfer update"
            ),
            "final_url": (
                "https://news.example/story"
            ),
            "text": (
                "Player Alpha has agreed to join "
                "Club Beta. The clubs expect to "
                "complete the remaining formalities."
            ),
        }
        row.update(overrides)
        return row

    def payload(self, **overrides):
        row = {
            "claim_relevance": "same_claim",
            "claim_stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_relationship": "",
            "dependency_targets": [],
            "claim_evidence": [
                (
                    "Player Alpha has agreed to "
                    "join Club Beta."
                )
            ],
            "dependency_evidence": [],
            "relevance_confidence": 0.94,
            "stance_confidence": 0.91,
            "dependency_confidence": 0.72,
        }
        row.update(overrides)
        return row

    def test_no_client_is_conservatively_unavailable(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=None,
        ), patch.object(
            main,
            "generate_gemini_content",
        ) as generator:
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        self.assertEqual(
            result["status"],
            "unavailable",
        )
        self.assertEqual(
            result["reason"],
            "gemini_unavailable",
        )
        self.assertIsNone(
            result["assessment"]
        )
        generator.assert_not_called()

    def test_existing_centralized_generator_is_used(
        self,
    ):
        client = object()

        with patch.object(
            main,
            "gemini_client",
            return_value=client,
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                self.payload()
            ),
        ) as generator:
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                    client_key="client-123",
                )
            )

        call = generator.call_args.kwargs

        self.assertIs(
            call["client"],
            client,
        )
        self.assertEqual(
            call["client_key"],
            "client-123",
        )
        self.assertEqual(
            call["mode"],
            CORROBORATION_SEMANTIC_GEMINI_MODE,
        )
        self.assertEqual(
            call["model"],
            CORROBORATION_SEMANTIC_GEMINI_MODEL,
        )
        self.assertIn(
            "<UNTRUSTED_CANDIDATE_REPORT>",
            call["contents"],
        )
        self.assertEqual(
            result["status"],
            "assessed",
        )

    def test_provider_wrapper_version(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                self.payload()
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        self.assertEqual(
            result["version"],
            CORROBORATION_SEMANTIC_GEMINI_VERSION,
        )

    def test_support_is_normalized_but_not_independence(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                self.payload()
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        assessment = result["assessment"]

        self.assertTrue(
            assessment["support_present"]
        )
        self.assertFalse(
            assessment[
                "independence_established"
            ]
        )
        self.assertFalse(
            assessment[
                "corroboration_established"
            ]
        )

    def test_support_and_dependency_remain_separate(
        self,
    ):
        payload = self.payload(
            dependency_status=(
                "explicit_dependency"
            ),
            dependency_relationship=(
                "attributed_to"
            ),
            dependency_targets=[
                "ESPN",
            ],
            dependency_evidence=[
                "According to ESPN, the deal is agreed."
            ],
        )

        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                payload
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        assessment = result["assessment"]

        self.assertTrue(
            assessment["support_present"]
        )
        self.assertTrue(
            assessment[
                "explicit_dependency_present"
            ]
        )
        self.assertEqual(
            assessment[
                "dependency_relationship"
            ],
            "attributed_to",
        )
        self.assertFalse(
            assessment[
                "independence_established"
            ]
        )

    def test_contradiction_is_normalized(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                self.payload(
                    claim_stance="contradicts"
                )
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        assessment = result["assessment"]

        self.assertTrue(
            assessment[
                "contradiction_present"
            ]
        )
        self.assertEqual(
            assessment[
                "claim_relationship_type"
            ],
            "contradicts",
        )

    def test_malformed_json_fails_closed(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                "not-json"
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        self.assertEqual(
            result["status"],
            "assessment_failed",
        )
        self.assertIsNone(
            result["assessment"]
        )

    def test_provider_failure_is_best_effort(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            side_effect=RuntimeError(
                "provider unavailable"
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        self.assertEqual(
            result["status"],
            "assessment_failed",
        )
        self.assertEqual(
            result["error_type"],
            "RuntimeError",
        )
        self.assertIsNone(
            result["assessment"]
        )

    def test_unresolved_candidate_never_reaches_generator(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
        ) as generator:
            with self.assertRaises(
                ValueError
            ):
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(
                        resolution_status=(
                            "fetch_failed"
                        )
                    ),
                )

        generator.assert_not_called()

    def test_claim_and_candidate_provenance_are_retained(
        self,
    ):
        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            return_value=FakeResponse(
                self.payload()
            ),
        ):
            result = (
                main.gemini_candidate_semantics(
                    claim=self.claim(),
                    candidate=self.candidate(),
                )
            )

        self.assertEqual(
            result["claim_id"],
            "claim-1",
        )
        self.assertEqual(
            result["candidate_url"],
            "https://news.example/story",
        )
        self.assertEqual(
            result["assessment"]["claim_id"],
            "claim-1",
        )
        self.assertEqual(
            result["assessment"][
                "candidate_url"
            ],
            "https://news.example/story",
        )


if __name__ == "__main__":
    unittest.main()
