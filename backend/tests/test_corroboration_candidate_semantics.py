import json
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analysis.candidate_semantics import (
    CORROBORATION_CANDIDATE_SEMANTICS_VERSION,
    build_candidate_semantic_prompt,
    normalize_candidate_semantic_assessment,
)


class CandidateSemanticTests(unittest.TestCase):
    def claim(self, **overrides):
        value = {
            "id": "claim-1",
            "canonical_text": (
                "Player Alpha has agreed to join Club Beta."
            ),
        }
        value.update(overrides)
        return value

    def candidate(self, **overrides):
        value = {
            "resolution_status": "resolved",
            "extracted_title": "Player Alpha transfer update",
            "final_url": "https://news.example/story",
            "text": (
                "Player Alpha has agreed to join Club Beta. "
                "The clubs are expected to complete the "
                "remaining formalities."
            ),
        }
        value.update(overrides)
        return value

    def assessment(self, **overrides):
        value = {
            "claim_relevance": "same_claim",
            "claim_stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_relationship": "",
            "dependency_targets": [],
            "claim_evidence": [
                "Player Alpha has agreed to join Club Beta."
            ],
            "dependency_evidence": [],
            "relevance_confidence": 0.95,
            "stance_confidence": 0.92,
            "dependency_confidence": 0.75,
        }
        value.update(overrides)
        return value

    def test_policy_version(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment()
        )
        self.assertEqual(
            result["version"],
            CORROBORATION_CANDIDATE_SEMANTICS_VERSION,
        )
        self.assertEqual(
            result["version"],
            "corroboration-candidate-semantics-v1",
        )

    def test_prompt_contains_claim_candidate_and_url(self):
        prompt = build_candidate_semantic_prompt(
            claim=self.claim(),
            candidate=self.candidate(),
        )
        self.assertIn(
            "Player Alpha has agreed to join Club Beta.",
            prompt,
        )
        self.assertIn(
            "Player Alpha transfer update",
            prompt,
        )
        self.assertIn(
            "https://news.example/story",
            prompt,
        )

    def test_prompt_preserves_safety_contract(self):
        prompt = build_candidate_semantic_prompt(
            claim=self.claim(),
            candidate=self.candidate(),
        )
        self.assertIn(
            "<UNTRUSTED_CANDIDATE_REPORT>",
            prompt,
        )
        self.assertIn(
            "Do not browse the web.",
            prompt,
        )
        self.assertIn(
            "Supporting the claim does NOT mean",
            prompt,
        )
        self.assertIn(
            "does NOT establish independence",
            prompt,
        )

    def test_unresolved_candidate_is_rejected(self):
        with self.assertRaises(ValueError):
            build_candidate_semantic_prompt(
                claim=self.claim(),
                candidate=self.candidate(
                    resolution_status="fetch_failed"
                ),
            )

    def test_support_without_dependency_is_not_independence(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment()
        )
        self.assertTrue(
            result["support_present"]
        )
        self.assertEqual(
            result["claim_relationship_type"],
            "supports",
        )
        self.assertFalse(
            result["explicit_dependency_present"]
        )
        self.assertFalse(
            result["independence_established"]
        )

    def test_support_and_attribution_can_coexist(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                dependency_status="explicit_dependency",
                dependency_relationship="attributed_to",
                dependency_targets=["ESPN"],
                dependency_evidence=[
                    "According to ESPN, the deal is agreed."
                ],
            )
        )
        self.assertTrue(
            result["support_present"]
        )
        self.assertTrue(
            result["explicit_dependency_present"]
        )
        self.assertEqual(
            result["dependency_relationship"],
            "attributed_to",
        )
        self.assertFalse(
            result["independence_established"]
        )

    def test_derived_report_stays_separate_from_stance(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                dependency_status="explicit_dependency",
                dependency_relationship="derived_from",
                dependency_targets=["Original Outlet"],
            )
        )
        self.assertEqual(
            result["claim_stance"],
            "supports",
        )
        self.assertEqual(
            result["dependency_relationship"],
            "derived_from",
        )

    def test_contradiction_maps_to_existing_relationship(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                claim_stance="contradicts"
            )
        )
        self.assertTrue(
            result["contradiction_present"]
        )
        self.assertFalse(
            result["support_present"]
        )
        self.assertEqual(
            result["claim_relationship_type"],
            "contradicts",
        )

    def test_neutral_same_claim_maps_to_alignment(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                claim_stance="neutral"
            )
        )
        self.assertEqual(
            result["claim_relationship_type"],
            "aligned_to",
        )
        self.assertFalse(
            result["support_present"]
        )

    def test_related_claim_cannot_be_support(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                claim_relevance="related_claim",
                claim_stance="supports",
            )
        )
        self.assertEqual(
            result["claim_stance"],
            "not_applicable",
        )
        self.assertEqual(
            result["claim_relationship_type"],
            "",
        )
        self.assertFalse(
            result["support_present"]
        )
        self.assertEqual(
            result["claim_evidence"],
            [],
        )

    def test_unrelated_claim_cannot_be_contradiction(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                claim_relevance="unrelated",
                claim_stance="contradicts",
            )
        )
        self.assertEqual(
            result["claim_stance"],
            "not_applicable",
        )
        self.assertFalse(
            result["contradiction_present"]
        )

    def test_invalid_semantics_degrade_conservatively(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                claim_relevance="definitely",
                claim_stance="yes",
                dependency_status="independent",
                dependency_relationship="independent",
            )
        )
        self.assertEqual(
            result["claim_relevance"],
            "uncertain",
        )
        self.assertEqual(
            result["claim_stance"],
            "not_applicable",
        )
        self.assertEqual(
            result["dependency_status"],
            "uncertain",
        )
        self.assertFalse(
            result["independence_established"]
        )

    def test_invalid_dependency_relationship_degrades(self):
        result = normalize_candidate_semantic_assessment(
            self.assessment(
                dependency_status="explicit_dependency",
                dependency_relationship="copied_from",
                dependency_targets=["Outlet A"],
            )
        )
        self.assertEqual(
            result["dependency_status"],
            "uncertain",
        )
        self.assertEqual(
            result["dependency_relationship"],
            "",
        )
        self.assertEqual(
            result["dependency_targets"],
            [],
        )

    def test_json_wrapping_and_normalization(self):
        payload = {
            "claim_relevance": "SAME_CLAIM",
            "claim_stance": "SUPPORTS",
            "dependency_status": "EXPLICIT_DEPENDENCY",
            "dependency_relationship": "ATTRIBUTED_TO",
            "dependency_targets": [
                " ESPN ",
                "espn",
                "Reporter Alpha",
            ],
            "claim_evidence": [
                " Same evidence ",
                "same evidence",
            ],
            "dependency_evidence": [
                "According to ESPN."
            ],
            "relevance_confidence": "0.91",
            "stance_confidence": 0.88,
            "dependency_confidence": 5,
        }

        raw = (
            "Model response:\n```json\n"
            + json.dumps(payload)
            + "\n```"
        )

        result = normalize_candidate_semantic_assessment(
            raw,
            claim_id=" claim-1 ",
            candidate_url=" https://news.example/story ",
        )

        self.assertEqual(
            result["claim_id"],
            "claim-1",
        )
        self.assertEqual(
            result["dependency_targets"],
            ["ESPN", "Reporter Alpha"],
        )
        self.assertEqual(
            result["claim_evidence"],
            ["Same evidence"],
        )
        self.assertEqual(
            result["relevance_confidence"],
            0.91,
        )
        self.assertEqual(
            result["stance_confidence"],
            0.88,
        )
        self.assertIsNone(
            result["dependency_confidence"]
        )


if __name__ == "__main__":
    unittest.main()
