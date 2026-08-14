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


class ClaimCorroborationAnalysisTests(
    unittest.TestCase
):
    def support_claim(
        self,
        *,
        status,
        observations=0,
        evidence=0,
        sources=0,
        dependencies=0,
        independent=False,
    ):
        source_ids = [
            f"source-{index}"
            for index in range(
                sources
            )
        ]

        dependency_rows = [
            {
                "id": (
                    f"dependency-{index}"
                )
            }
            for index in range(
                dependencies
            )
        ]

        return {
            "claim_id": "claim-1",
            "canonical_key": (
                "transfer|a|b|agreement"
            ),
            "subject_key": (
                "transfer|a|b"
            ),
            "status": status,
            "independent_support_established": (
                independent
            ),
            "supporting_source_ids": (
                source_ids
            ),
            "recorded_support_dependencies": (
                dependency_rows
            ),
            "counts": {
                "supporting_observations": (
                    observations
                ),
                "supporting_evidence": (
                    evidence
                ),
                "distinct_supporting_sources": (
                    sources
                ),
                "recorded_support_dependencies": (
                    dependencies
                ),
            },
        }

    def stance_claim(
        self,
        *,
        contradictions=0,
    ):
        return {
            "claim_id": "claim-1",
            "canonical_key": (
                "transfer|a|b|agreement"
            ),
            "subject_key": (
                "transfer|a|b"
            ),
            "status": (
                "explicit_contradiction"
                if contradictions
                else "no_explicit_stance"
            ),
            "counts": {
                "contradiction_links": (
                    contradictions
                ),
            },
        }

    def assess(
        self,
        support_claim,
        stance_claim=None,
    ):
        return (
            main.build_claim_corroboration_assessment(
                support_state={
                    "claims": [
                        support_claim
                    ]
                },
                stance_state={
                    "claims": [
                        stance_claim
                        or self.stance_claim()
                    ]
                },
            )
        )

    def test_support_state_dictionary_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_corroboration_assessment(
                support_state=[],
                stance_state={},
            )

    def test_stance_state_dictionary_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_corroboration_assessment(
                support_state={},
                stance_state=[],
            )

    def test_no_explicit_support_is_not_corroboration(
        self,
    ):
        result = self.assess(
            self.support_claim(
                status="no_explicit_support",
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "no_explicit_support",
        )

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

    def test_evidence_only_support_is_not_corroboration(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status="evidence_only_support",
                evidence=1,
            )
        )["claims"][0]

        self.assertEqual(
            claim["status"],
            "evidence_only_support",
        )

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

    def test_single_support_is_not_corroboration(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "single_support_observation"
                ),
                observations=1,
                sources=1,
            )
        )["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "single_support_observation"
            ),
        )

    def test_recorded_dependency_blocks_corroboration(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "recorded_support_"
                    "dependency_present"
                ),
                observations=2,
                sources=2,
                dependencies=1,
            )
        )["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "recorded_support_"
                "dependency_present"
            ),
        )

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

    def test_source_diversity_is_not_enough(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "multi_source_support_"
                    "independence_unknown"
                ),
                observations=2,
                sources=2,
            )
        )["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "support_independence_unknown"
            ),
        )

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

    def test_independent_support_can_establish_corroboration(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "multi_source_support_"
                    "independence_unknown"
                ),
                observations=2,
                sources=2,
                independent=True,
            )
        )["claims"][0]

        self.assertEqual(
            claim["status"],
            "corroboration_established",
        )

        self.assertTrue(
            claim[
                "corroboration_established"
            ]
        )

    def test_independence_flag_still_requires_two_sources(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "single_support_observation"
                ),
                observations=1,
                sources=1,
                independent=True,
            )
        )["claims"][0]

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            "single_support_observation",
        )

    def test_contradiction_marks_corroboration_as_contested(
        self,
    ):
        claim = self.assess(
            self.support_claim(
                status=(
                    "multi_source_support_"
                    "independence_unknown"
                ),
                observations=2,
                sources=2,
                independent=True,
            ),
            self.stance_claim(
                contradictions=1,
            ),
        )["claims"][0]

        self.assertTrue(
            claim[
                "corroboration_established"
            ]
        )

        self.assertTrue(
            claim["contested"]
        )

        self.assertTrue(
            claim[
                "contradiction_present"
            ]
        )

    def test_current_pipeline_does_not_infer_corroboration(
        self,
    ):
        bundle = {
            "claims": [
                {
                    "id": "claim-1",
                    "canonical_key": (
                        "transfer|a|b|agreement"
                    ),
                    "subject_key": (
                        "transfer|a|b"
                    ),
                    "canonical_text": (
                        "Agreement reached."
                    ),
                    "claim_type": (
                        "assertion"
                    ),
                }
            ],
            "claim_links": [
                {
                    "id": "support-1",
                    "claim_id": "claim-1",
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": "obs-1",
                    "relationship_type": (
                        "supports"
                    ),
                    "confidence": 0.9,
                    "observed_at": (
                        "2026-08-13"
                        "T16:00:00+00:00"
                    ),
                },
                {
                    "id": "support-2",
                    "claim_id": "claim-1",
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": "obs-2",
                    "relationship_type": (
                        "supports"
                    ),
                    "confidence": 0.9,
                    "observed_at": (
                        "2026-08-13"
                        "T16:01:00+00:00"
                    ),
                },
            ],
            "source_observations": [
                {
                    "id": "obs-1",
                    "source_id": "source-1",
                },
                {
                    "id": "obs-2",
                    "source_id": "source-2",
                },
            ],
            "reporter_observations": [],
            "observation_dependencies": [],
        }

        support = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        stance = (
            main.build_claim_stance_analysis(
                bundle
            )
        )

        assessment = (
            main.build_claim_corroboration_assessment(
                support_state=support,
                stance_state=stance,
            )
        )

        claim = assessment["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "support_independence_unknown"
            ),
        )

        self.assertFalse(
            claim[
                "corroboration_established"
            ]
        )

    def test_claim_order_is_stable(
        self,
    ):
        first_support = self.support_claim(
            status="no_explicit_support"
        )

        second_support = {
            **first_support,
            "claim_id": "claim-2",
            "canonical_key": "claim-two",
        }

        first_stance = self.stance_claim()

        second_stance = {
            **first_stance,
            "claim_id": "claim-2",
            "canonical_key": "claim-two",
        }

        first = (
            main.build_claim_corroboration_assessment(
                support_state={
                    "claims": [
                        second_support,
                        first_support,
                    ]
                },
                stance_state={
                    "claims": [
                        second_stance,
                        first_stance,
                    ]
                },
            )
        )

        second = (
            main.build_claim_corroboration_assessment(
                support_state={
                    "claims": [
                        first_support,
                        second_support,
                    ]
                },
                stance_state={
                    "claims": [
                        first_stance,
                        second_stance,
                    ]
                },
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            [
                row["claim_id"]
                for row in first["claims"]
            ],
            [
                "claim-1",
                "claim-2",
            ],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
