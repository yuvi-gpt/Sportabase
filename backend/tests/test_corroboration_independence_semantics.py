import json
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


from app.analysis.independence_verification import (
    CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
    build_independence_verification_prompt,
    normalize_independence_verification_assessment,
)
from app.services.corroboration_independence_semantics import (
    CORROBORATION_INDEPENDENCE_GEMINI_MODE,
    CORROBORATION_INDEPENDENCE_GEMINI_MODEL,
    CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
    assess_independence_pair_with_gemini,
)


class CorroborationIndependenceSemanticTests(
    unittest.TestCase
):
    def setUp(self):
        self.claim = {
            "id": "claim-1",
            "canonical_text": (
                "Player Alpha has agreed "
                "to join Club Beta."
            ),
        }

        self.pair = {
            "pair_id": "pair-1",
            "claim_id": "claim-1",
            "status": (
                "verification_required"
            ),
            "observation_a_id": (
                "obs-a"
            ),
            "observation_b_id": (
                "obs-b"
            ),
            "source_a_id": (
                "source-a"
            ),
            "source_b_id": (
                "source-b"
            ),
            "provenance_url_a": (
                "https://a.example/story"
            ),
            "provenance_url_b": (
                "https://b.example/story"
            ),
        }

        self.article_a = (
            "Sources close to Player Alpha "
            "have told A Sports that an "
            "agreement with Club Beta is done."
        )

        self.article_b = (
            "B Sports understands from club "
            "sources that Player Alpha has "
            "agreed terms with Club Beta."
        )

    def raw(
        self,
        **overrides,
    ):
        payload = {
            (
                "source_a_reporting_basis"
            ): "original_reporting",
            (
                "source_b_reporting_basis"
            ): "original_reporting",
            (
                "cross_source_dependency"
            ): "not_detected",
            "source_a_evidence": [
                (
                    "Sources close to Player "
                    "Alpha have told A Sports"
                ),
            ],
            "source_b_evidence": [
                (
                    "B Sports understands from "
                    "club sources"
                ),
            ],
            "dependency_evidence": [],
            "confidence": 0.92,
        }

        payload.update(
            overrides
        )

        return json.dumps(
            payload
        )

    def normalize(
        self,
        raw=None,
    ):
        return (
            normalize_independence_verification_assessment(
                (
                    self.raw()
                    if raw is None
                    else raw
                ),
                claim_id="claim-1",
                pair_id="pair-1",
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
            )
        )

    def test_prompt_contains_pair_and_reports(
        self,
    ):
        prompt = (
            build_independence_verification_prompt(
                claim=self.claim,
                pair=self.pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
            )
        )

        self.assertIn(
            "pair-1",
            prompt,
        )

        self.assertIn(
            self.claim[
                "canonical_text"
            ],
            prompt,
        )

        self.assertIn(
            self.article_a,
            prompt,
        )

        self.assertIn(
            self.article_b,
            prompt,
        )

        self.assertIn(
            (
                "Absence of attribution does "
                "NOT establish independence"
            ),
            prompt,
        )

    def test_positive_evidence_requires_both_reports(
        self,
    ):
        result = self.normalize()

        self.assertEqual(
            result["version"],
            CORROBORATION_INDEPENDENCE_EVIDENCE_VERSION,
        )

        self.assertEqual(
            result["status"],
            (
                "positive_independence_"
                "evidence"
            ),
        )

        self.assertTrue(
            result[
                "positive_independence_"
                "evidence_present"
            ]
        )

        self.assertFalse(
            result[
                "independence_established"
            ]
        )

        self.assertFalse(
            result[
                "independence_assertion_created"
            ]
        )

    def test_different_sources_without_positive_evidence_is_insufficient(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_a_reporting_basis=(
                    "unclear"
                ),
                source_b_reporting_basis=(
                    "unclear"
                ),
                source_a_evidence=[],
                source_b_evidence=[],
            )
        )

        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )

    def test_hallucinated_excerpt_is_rejected(
        self,
    ):
        result = self.normalize(
            self.raw(
                source_a_evidence=[
                    (
                        "A Sports exclusively "
                        "interviewed the player"
                    ),
                ],
            )
        )

        self.assertEqual(
            result[
                "source_a_evidence"
            ],
            [],
        )

        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )

    def test_grounded_dependency_blocks_positive_result(
        self,
    ):
        dependent_b = (
            self.article_b
            + " According to A Sports, "
            + "the agreement is complete."
        )

        raw = self.raw(
            cross_source_dependency=(
                "present"
            ),
            dependency_evidence=[
                (
                    "According to A Sports, "
                    "the agreement is complete."
                ),
            ],
        )

        result = (
            normalize_independence_verification_assessment(
                raw,
                claim_id="claim-1",
                pair_id="pair-1",
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    dependent_b
                ),
            )
        )

        self.assertEqual(
            result["status"],
            "dependency_present",
        )

        self.assertTrue(
            result[
                "explicit_dependency_present"
            ]
        )

        self.assertFalse(
            result[
                "positive_independence_"
                "evidence_present"
            ]
        )

    def test_ungrounded_dependency_claim_is_not_accepted(
        self,
    ):
        result = self.normalize(
            self.raw(
                cross_source_dependency=(
                    "present"
                ),
                dependency_evidence=[
                    (
                        "According to A Sports"
                    ),
                ],
            )
        )

        self.assertEqual(
            result[
                "dependency_evidence"
            ],
            [],
        )

        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )

    def test_uncertain_dependency_blocks_positive_result(
        self,
    ):
        result = self.normalize(
            self.raw(
                cross_source_dependency=(
                    "uncertain"
                ),
            )
        )

        self.assertEqual(
            result["status"],
            "insufficient_evidence",
        )

    def test_prompt_rejects_non_verification_pair(
        self,
    ):
        pair = {
            **self.pair,
            "status": "skipped",
        }

        with self.assertRaisesRegex(
            ValueError,
            "must require verification",
        ):
            build_independence_verification_prompt(
                claim=self.claim,
                pair=pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
            )

    def test_prompt_requires_both_article_texts(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Article B text is required",
        ):
            build_independence_verification_prompt(
                claim=self.claim,
                pair=self.pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text="",
            )

    def test_adapter_unavailable_does_not_call_generator(
        self,
    ):
        called = []

        def generator(
            **kwargs,
        ):
            called.append(
                kwargs
            )

            raise AssertionError(
                "generator should not run"
            )

        result = (
            assess_independence_pair_with_gemini(
                claim=self.claim,
                pair=self.pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
                client=None,
                client_key="test",
                generator=generator,
            )
        )

        self.assertEqual(
            result["status"],
            "unavailable",
        )

        self.assertEqual(
            called,
            [],
        )

    def test_adapter_uses_expected_mode_and_model(
        self,
    ):
        captured = {}

        def generator(
            **kwargs,
        ):
            captured.update(
                kwargs
            )

            return type(
                "Response",
                (),
                {
                    "text": self.raw(),
                },
            )()

        result = (
            assess_independence_pair_with_gemini(
                claim=self.claim,
                pair=self.pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
                client=object(),
                client_key=(
                    "client-key"
                ),
                generator=generator,
            )
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_INDEPENDENCE_GEMINI_VERSION,
        )

        self.assertEqual(
            result["status"],
            "assessed",
        )

        self.assertEqual(
            captured["mode"],
            CORROBORATION_INDEPENDENCE_GEMINI_MODE,
        )

        self.assertEqual(
            captured["model"],
            CORROBORATION_INDEPENDENCE_GEMINI_MODEL,
        )

        self.assertTrue(
            result[
                "assessment"
            ][
                "positive_independence_"
                "evidence_present"
            ]
        )

        self.assertFalse(
            result[
                "assessment"
            ][
                "independence_established"
            ]
        )

    def test_adapter_parse_failure_is_best_effort(
        self,
    ):
        def generator(
            **kwargs,
        ):
            return type(
                "Response",
                (),
                {
                    "text": (
                        "definitely not json"
                    ),
                },
            )()

        result = (
            assess_independence_pair_with_gemini(
                claim=self.claim,
                pair=self.pair,
                article_a_text=(
                    self.article_a
                ),
                article_b_text=(
                    self.article_b
                ),
                client=object(),
                client_key="test",
                generator=generator,
            )
        )

        self.assertEqual(
            result["status"],
            "assessment_failed",
        )

        self.assertIsNone(
            result["assessment"]
        )


if __name__ == "__main__":
    unittest.main()
