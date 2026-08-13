import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import main

from app.services.corroboration_graph import (
    CORROBORATION_GRAPH_PLAN_VERSION,
    build_corroboration_graph_plan,
)


class CorroborationGraphPlanTests(unittest.TestCase):
    def claim(self):
        return {
            "id": "claim-1",
            "subject_key": "transfer|alpha|beta",
            "canonical_text": (
                "Player Alpha has agreed to join Club Beta."
            ),
        }

    def candidate(
        self,
        url="https://news.example/story",
        **overrides,
    ):
        row = {
            "resolution_status": "resolved",
            "final_url": url,
            "final_source_domain": "news.example",
            "final_same_source_domain": False,
            "published_at": "2026-08-13T12:00:00+00:00",
            "publication_time_status": "found",
            "publication_time_version": "publication-time-v1",
            "publication_time_source_type": "meta",
            "publication_time_source_key": (
                "article:published_time"
            ),
            "provider": "brave_news",
            "provider_rank": 1,
        }
        row.update(overrides)
        return row

    def assessment(
        self,
        relationship="supports",
        **overrides,
    ):
        row = {
            "claim_relationship_type": relationship,
            "stance_confidence": 0.91,
            "explicit_dependency_present": False,
            "dependency_relationship": "",
            "dependency_targets": [],
            "dependency_evidence": [],
            "dependency_confidence": 0.7,
        }
        row.update(overrides)
        return row

    def semantic_row(
        self,
        url="https://news.example/story",
        status="assessed",
        assessment=None,
    ):
        return {
            "candidate_url": url,
            "source_domain": "news.example",
            "provider": "brave_news",
            "provider_rank": 1,
            "status": status,
            "semantic_result": {
                "status": status,
                "assessment": (
                    self.assessment()
                    if assessment is None
                    else assessment
                ),
            },
        }

    def build(
        self,
        *,
        candidates=None,
        rows=None,
        claim=None,
    ):
        return build_corroboration_graph_plan(
            claim=claim or self.claim(),
            collection={
                "resolved_candidates": (
                    candidates
                    if candidates is not None
                    else [self.candidate()]
                )
            },
            semantic_batch={
                "candidate_assessments": (
                    rows
                    if rows is not None
                    else [self.semantic_row()]
                )
            },
            normalize_url=main.normalized_analysis_url,
            domain_resolver=main.source_domain_for_url,
        )

    def test_version_and_support_action(self):
        result = self.build()
        action = result["actions"][0]

        self.assertEqual(
            result["version"],
            CORROBORATION_GRAPH_PLAN_VERSION,
        )
        self.assertEqual(
            result["status"],
            "materializable_actions_available",
        )
        self.assertEqual(
            action["claim_link"]["relationship_type"],
            "supports",
        )
        self.assertEqual(
            action["observation"]["status"],
            "unresolved",
        )
        self.assertEqual(
            action["observation"]["observation_type"],
            "report",
        )

    def test_contradiction_materializes(self):
        row = self.semantic_row(
            assessment=self.assessment(
                "contradicts"
            )
        )

        result = self.build(rows=[row])

        self.assertEqual(
            result["actions"][0][
                "claim_link"
            ]["relationship_type"],
            "contradicts",
        )

    def test_neutral_alignment_materializes(self):
        row = self.semantic_row(
            assessment=self.assessment(
                "aligned_to"
            )
        )

        result = self.build(rows=[row])

        self.assertEqual(
            result["actions"][0][
                "claim_link"
            ]["relationship_type"],
            "aligned_to",
        )

    def test_uncertain_relationship_is_not_materialized(self):
        row = self.semantic_row(
            assessment=self.assessment("")
        )

        result = self.build(rows=[row])

        self.assertEqual(
            result["counts"]["materializable"],
            0,
        )
        self.assertEqual(
            result["skipped"][0]["reason"],
            "no_materializable_claim_relationship",
        )

    def test_missing_publication_time_blocks_materialization(self):
        candidate = self.candidate(
            published_at="",
            publication_time_status="not_found",
        )

        result = self.build(
            candidates=[candidate]
        )

        self.assertEqual(
            result["counts"]["materializable"],
            0,
        )
        self.assertEqual(
            result["skipped"][0]["reason"],
            "deterministic_publication_time_missing",
        )

    def test_failed_semantic_row_is_not_materialized(self):
        row = self.semantic_row(
            status="assessment_failed",
        )

        result = self.build(rows=[row])

        self.assertEqual(
            result["counts"]["materializable"],
            0,
        )
        self.assertEqual(
            result["skipped"][0]["reason"],
            "semantic_not_assessed",
        )

    def test_explicit_url_dependency_creates_intent(self):
        row = self.semantic_row(
            assessment=self.assessment(
                explicit_dependency_present=True,
                dependency_relationship="attributed_to",
                dependency_targets=[
                    "https://espn.com/source-story"
                ],
                dependency_evidence=[
                    "According to ESPN."
                ],
            )
        )

        result = self.build(rows=[row])
        action = result["actions"][0]

        self.assertEqual(
            result["counts"]["dependency_intents"],
            1,
        )
        self.assertEqual(
            action["dependency_intents"][0][
                "upstream_source_domain"
            ],
            "espn.com",
        )
        self.assertEqual(
            action["dependency_intents"][0][
                "relationship_type"
            ],
            "attributed_to",
        )

    def test_named_dependency_target_is_not_guessed(self):
        row = self.semantic_row(
            assessment=self.assessment(
                explicit_dependency_present=True,
                dependency_relationship="attributed_to",
                dependency_targets=["ESPN"],
            )
        )

        result = self.build(rows=[row])
        action = result["actions"][0]

        self.assertEqual(
            result["counts"]["dependency_intents"],
            0,
        )
        self.assertEqual(
            len(
                action[
                    "unresolved_dependency_targets"
                ]
            ),
            1,
        )

    def test_no_dependency_never_establishes_independence(self):
        result = self.build()

        self.assertEqual(
            result["counts"]["independence_assertions"],
            0,
        )
        self.assertTrue(
            result["policy"][
                "absence_of_dependency_does_not_"
                "establish_independence"
            ]
        )

    def test_same_source_candidate_is_still_recordable(self):
        candidate = self.candidate(
            final_same_source_domain=True,
        )

        result = self.build(
            candidates=[candidate]
        )

        self.assertEqual(
            result["counts"]["materializable"],
            1,
        )
        self.assertTrue(
            result["actions"][0][
                "same_source_domain"
            ]
        )
        self.assertEqual(
            result["counts"]["independence_assertions"],
            0,
        )

    def test_duplicate_semantic_candidate_is_deduplicated(self):
        row = self.semantic_row()

        result = self.build(
            rows=[row, row]
        )

        self.assertEqual(
            result["counts"]["materializable"],
            1,
        )
        self.assertEqual(
            result["skipped"][0]["reason"],
            "duplicate_semantic_candidate",
        )

    def test_semantic_candidate_without_resolved_article_is_skipped(self):
        row = self.semantic_row(
            url="https://missing.example/story"
        )

        result = self.build(rows=[row])

        self.assertEqual(
            result["counts"]["materializable"],
            0,
        )
        self.assertEqual(
            result["skipped"][0]["reason"],
            "resolved_candidate_missing",
        )


if __name__ == "__main__":
    unittest.main()
