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
    CORROBORATION_SEMANTIC_BATCH_VERSION,
)


class FakeResponse:
    def __init__(
        self,
        payload,
    ):
        self.text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload)
        )


class CorroborationSemanticBatchTests(
    unittest.TestCase
):
    def claim(self):
        return {
            "id": "claim-1",
            "canonical_text": (
                "Player Alpha has agreed to join "
                "Club Beta."
            ),
        }

    def candidate(
        self,
        domain,
        *,
        rank=1,
    ):
        return {
            "resolution_status": "resolved",
            "final_url": (
                f"https://{domain}/story"
            ),
            "final_source_domain": domain,
            "provider": "brave_news",
            "provider_rank": rank,
            "text": (
                "Player Alpha has agreed to join "
                "Club Beta. Further details about "
                "the transfer are included here."
            ),
            "extracted_title": (
                "Player Alpha transfer"
            ),
        }

    def collection(
        self,
        candidates,
    ):
        return {
            "version": (
                "corroboration-candidate-"
                "collection-v1"
            ),
            "resolved_candidates": (
                candidates
            ),
        }

    def payload(
        self,
        *,
        stance="supports",
        dependency=False,
    ):
        return {
            "claim_relevance": "same_claim",
            "claim_stance": stance,
            "dependency_status": (
                "explicit_dependency"
                if dependency
                else (
                    "no_explicit_dependency_detected"
                )
            ),
            "dependency_relationship": (
                "attributed_to"
                if dependency
                else ""
            ),
            "dependency_targets": (
                ["ESPN"]
                if dependency
                else []
            ),
            "claim_evidence": [
                (
                    "Player Alpha has agreed to "
                    "join Club Beta."
                )
            ],
            "dependency_evidence": (
                ["According to ESPN."]
                if dependency
                else []
            ),
            "relevance_confidence": 0.9,
            "stance_confidence": 0.9,
            "dependency_confidence": 0.8,
        }

    def test_batch_version_and_success(
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
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "one.example"
                            )
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["version"],
            CORROBORATION_SEMANTIC_BATCH_VERSION,
        )

        self.assertEqual(
            result["status"],
            "assessed_candidates_available",
        )

        self.assertEqual(
            result["counts"]["assessed"],
            1,
        )

    def test_empty_collection_makes_no_provider_call(
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
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        []
                    ),
                )
            )

        self.assertEqual(
            result["status"],
            "no_resolved_candidates",
        )

        generator.assert_not_called()

    def test_candidates_are_assessed_in_order(
        self,
    ):
        calls = []

        def generator(**kwargs):
            calls.append(
                kwargs["contents"]
            )

            return FakeResponse(
                self.payload()
            )

        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            side_effect=generator,
        ):
            main.gemini_candidate_collection_semantics(
                claim=self.claim(),
                collection=self.collection(
                    [
                        self.candidate(
                            "one.example",
                            rank=1,
                        ),
                        self.candidate(
                            "two.example",
                            rank=2,
                        ),
                    ]
                ),
            )

        self.assertEqual(
            len(calls),
            2,
        )

        self.assertIn(
            "https://one.example/story",
            calls[0],
        )

        self.assertIn(
            "https://two.example/story",
            calls[1],
        )

    def test_one_bad_response_does_not_abort_next(
        self,
    ):
        responses = [
            FakeResponse(
                "not-json"
            ),
            FakeResponse(
                self.payload()
            ),
        ]

        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            side_effect=responses,
        ):
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "bad.example",
                                rank=1,
                            ),
                            self.candidate(
                                "good.example",
                                rank=2,
                            ),
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["counts"]["failed"],
            1,
        )

        self.assertEqual(
            result["counts"]["assessed"],
            1,
        )

        self.assertEqual(
            result["status"],
            "assessed_candidates_available",
        )

    def test_provider_failure_does_not_abort_next(
        self,
    ):
        responses = [
            RuntimeError(
                "provider failure"
            ),
            FakeResponse(
                self.payload()
            ),
        ]

        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            side_effect=responses,
        ):
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "bad.example"
                            ),
                            self.candidate(
                                "good.example"
                            ),
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["counts"]["failed"],
            1,
        )

        self.assertEqual(
            result["counts"]["assessed"],
            1,
        )

    def test_support_and_contradiction_are_counted_separately(
        self,
    ):
        responses = [
            FakeResponse(
                self.payload(
                    stance="supports"
                )
            ),
            FakeResponse(
                self.payload(
                    stance="contradicts"
                )
            ),
        ]

        with patch.object(
            main,
            "gemini_client",
            return_value=object(),
        ), patch.object(
            main,
            "generate_gemini_content",
            side_effect=responses,
        ):
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "support.example"
                            ),
                            self.candidate(
                                "contradict.example"
                            ),
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["counts"]["supports"],
            1,
        )

        self.assertEqual(
            result["counts"][
                "contradictions"
            ],
            1,
        )

    def test_dependency_is_separate_from_support(
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
                    stance="supports",
                    dependency=True,
                )
            ),
        ):
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "copy.example"
                            )
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["counts"]["supports"],
            1,
        )

        self.assertEqual(
            result["counts"][
                "explicit_dependencies"
            ],
            1,
        )

        self.assertEqual(
            result["counts"][
                "independence_established"
            ],
            0,
        )

    def test_unavailable_client_is_conservative(
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
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "one.example"
                            ),
                            self.candidate(
                                "two.example"
                            ),
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["status"],
            "semantic_provider_unavailable",
        )

        self.assertEqual(
            result["counts"]["unavailable"],
            2,
        )

        self.assertEqual(
            result["counts"]["assessed"],
            0,
        )

        generator.assert_not_called()

    def test_assessment_limit_prevents_extra_calls(
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
        ) as generator:
            result = (
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "one.example"
                            ),
                            self.candidate(
                                "two.example"
                            ),
                            self.candidate(
                                "three.example"
                            ),
                        ]
                    ),
                    max_assessments=2,
                )
            )

        self.assertEqual(
            generator.call_count,
            2,
        )

        self.assertEqual(
            result["counts"][
                "not_attempted"
            ],
            1,
        )

        self.assertEqual(
            result[
                "candidate_assessments"
            ][2]["status"],
            "not_assessed_limit",
        )

    def test_batch_cannot_establish_corroboration_or_merit(
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
                main.gemini_candidate_collection_semantics(
                    claim=self.claim(),
                    collection=self.collection(
                        [
                            self.candidate(
                                "one.example"
                            )
                        ]
                    ),
                )
            )

        self.assertEqual(
            result["counts"][
                "corroboration_established"
            ],
            0,
        )

        self.assertTrue(
            result["policy"][
                "semantic_support_does_not_"
                "establish_independence"
            ]
        )

        self.assertTrue(
            result["policy"][
                "semantic_batch_does_not_"
                "establish_corroboration"
            ]
        )

        self.assertTrue(
            result["policy"][
                "semantic_batch_has_no_"
                "merit_effect"
            ]
        )


if __name__ == "__main__":
    unittest.main()
