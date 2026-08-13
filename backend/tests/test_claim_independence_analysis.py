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


class ClaimIndependenceAnalysisTests(
    unittest.TestCase
):
    def feature_state(
        self,
        *,
        observations=1,
        source_ids=None,
        dependencies=None,
    ):
        return {
            "claims": [
                {
                    "claim_id": "claim-1",
                    "canonical_key": (
                        "transfer|a|b|agreement"
                    ),
                    "subject_key": (
                        "transfer|a|b"
                    ),
                    "aligned_observations": [
                        {
                            "target_type": (
                                "source_observation"
                            ),
                            "target_id": (
                                f"obs-{index}"
                            ),
                        }
                        for index in range(
                            observations
                        )
                    ],
                    "aligned_evidence_ids": [],
                    "aligned_source_ids": (
                        source_ids or []
                    ),
                    "aligned_reporter_ids": [],
                    "recorded_dependencies": (
                        dependencies or []
                    ),
                }
            ]
        }

    def test_dictionary_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_independence_assessment(
                []
            )

    def test_single_observation_is_insufficient(
        self,
    ):
        assessment = (
            main.build_claim_independence_assessment(
                self.feature_state(
                    observations=1,
                    source_ids=[
                        "source-1"
                    ],
                )
            )
        )

        claim = assessment["claims"][0]

        self.assertEqual(
            claim["status"],
            "insufficient_observations",
        )

        self.assertFalse(
            claim[
                "independence_established"
            ]
        )

    def test_recorded_dependency_takes_precedence(
        self,
    ):
        dependency = {
            "id": "dependency-1",
            "downstream_type": (
                "source_observation"
            ),
            "downstream_id": "obs-1",
            "upstream_type": (
                "source_observation"
            ),
            "upstream_id": "obs-0",
            "relationship_type": (
                "derived_from"
            ),
        }

        assessment = (
            main.build_claim_independence_assessment(
                self.feature_state(
                    observations=2,
                    source_ids=[
                        "source-1",
                        "source-2",
                    ],
                    dependencies=[
                        dependency
                    ],
                )
            )
        )

        claim = assessment["claims"][0]

        self.assertEqual(
            claim["status"],
            "recorded_dependency_present",
        )

        self.assertEqual(
            claim[
                "recorded_dependency_ids"
            ],
            ["dependency-1"],
        )

    def test_source_diversity_must_be_established(
        self,
    ):
        assessment = (
            main.build_claim_independence_assessment(
                self.feature_state(
                    observations=2,
                    source_ids=[
                        "source-1"
                    ],
                )
            )
        )

        self.assertEqual(
            assessment["claims"][0][
                "status"
            ],
            (
                "source_diversity_not_"
                "established"
            ),
        )

    def test_multi_source_without_dependency_is_unknown(
        self,
    ):
        assessment = (
            main.build_claim_independence_assessment(
                self.feature_state(
                    observations=2,
                    source_ids=[
                        "source-1",
                        "source-2",
                    ],
                )
            )
        )

        claim = assessment["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "multi_source_"
                "independence_unknown"
            ),
        )

        self.assertFalse(
            claim[
                "independence_established"
            ]
        )

        self.assertEqual(
            claim[
                "corroboration_status"
            ],
            "not_assessed",
        )

    def test_policy_never_equates_alignment_with_corroboration(
        self,
    ):
        assessment = (
            main.build_claim_independence_assessment(
                self.feature_state(
                    observations=2,
                    source_ids=[
                        "source-1",
                        "source-2",
                    ],
                )
            )
        )

        self.assertTrue(
            assessment["policy"][
                (
                    "claim_alignment_does_not_"
                    "imply_corroboration"
                )
            ]
        )

        self.assertTrue(
            assessment["policy"][
                (
                    "corroboration_requires_"
                    "explicit_support_semantics"
                )
            ]
        )

    def test_claim_order_is_stable(
        self,
    ):
        first_claim = {
            "claim_id": "claim-1",
            "canonical_key": "claim-one",
            "subject_key": "subject",
            "aligned_observations": [],
            "aligned_source_ids": [],
            "aligned_reporter_ids": [],
            "recorded_dependencies": [],
        }

        second_claim = {
            "claim_id": "claim-2",
            "canonical_key": "claim-two",
            "subject_key": "subject",
            "aligned_observations": [],
            "aligned_source_ids": [],
            "aligned_reporter_ids": [],
            "recorded_dependencies": [],
        }

        first = (
            main.build_claim_independence_assessment(
                {
                    "claims": [
                        second_claim,
                        first_claim,
                    ]
                }
            )
        )

        second = (
            main.build_claim_independence_assessment(
                {
                    "claims": [
                        first_claim,
                        second_claim,
                    ]
                }
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

    def test_feature_pipeline_preserves_dependency_state(
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
                }
            ],
            "claim_links": [
                {
                    "claim_id": "claim-1",
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": "obs-1",
                },
                {
                    "claim_id": "claim-1",
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": "obs-2",
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
            "observation_dependencies": [
                {
                    "id": "dependency-1",
                    "downstream_type": (
                        "source_observation"
                    ),
                    "downstream_id": "obs-2",
                    "upstream_type": (
                        "source_observation"
                    ),
                    "upstream_id": "obs-1",
                    "relationship_type": (
                        "derived_from"
                    ),
                    "confidence": 0.9,
                    "observed_at": (
                        "2026-08-13"
                        "T12:00:00+00:00"
                    ),
                }
            ],
        }

        features = (
            main.build_claim_dependency_features(
                bundle
            )
        )

        assessment = (
            main.build_claim_independence_assessment(
                features
            )
        )

        self.assertEqual(
            assessment["claims"][0][
                "status"
            ],
            "recorded_dependency_present",
        )

        self.assertFalse(
            assessment["claims"][0][
                "independence_established"
            ]
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
