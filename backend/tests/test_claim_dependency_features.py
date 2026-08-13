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


class ClaimDependencyFeatureTests(
    unittest.TestCase
):
    def base_bundle(self):
        return {
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
            "claim_links": [],
            "source_observations": [],
            "reporter_observations": [],
            "observation_dependencies": [],
        }

    def test_dictionary_is_required(self):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_dependency_features(
                []
            )

    def test_absence_of_dependency_is_not_independence(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "source_observations"
        ] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": "source-2",
            },
        ]

        bundle["claim_links"] = [
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
        ]

        features = (
            main.build_claim_dependency_features(
                bundle
            )
        )

        self.assertTrue(
            features["policy"][
                (
                    "absence_of_dependency_does_not_"
                    "imply_independence"
                )
            ]
        )

        claim = features["claims"][0]

        self.assertEqual(
            claim["counts"][
                "aligned_observations"
            ],
            2,
        )

        self.assertEqual(
            claim["counts"][
                "recorded_dependencies"
            ],
            0,
        )

        self.assertEqual(
            len(
                claim[
                    "observations_without_"
                    "recorded_dependency"
                ]
            ),
            2,
        )

    def test_recorded_dependency_is_attached_to_claim(
        self,
    ):
        bundle = self.base_bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": "source-2",
            },
        ]

        bundle["claim_links"] = [
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
        ]

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dep-1",
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
                    "2026-08-13T12:00:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_dependency_features(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["counts"][
                "recorded_dependencies"
            ],
            1,
        )

        self.assertEqual(
            claim[
                "observations_with_"
                "recorded_dependency"
            ],
            [
                {
                    "target_type": (
                        "source_observation"
                    ),
                    "target_id": "obs-2",
                }
            ],
        )

    def test_unaligned_dependency_is_excluded(
        self,
    ):
        bundle = self.base_bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-other",
                "source_id": "source-2",
            },
        ]

        bundle["claim_links"] = [
            {
                "claim_id": "claim-1",
                "target_type": (
                    "source_observation"
                ),
                "target_id": "obs-1",
            }
        ]

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dep-other",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": (
                    "obs-other"
                ),
                "upstream_type": "source",
                "upstream_id": "source-3",
                "relationship_type": (
                    "attributed_to"
                ),
                "confidence": 0.8,
                "observed_at": (
                    "2026-08-13T12:00:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_dependency_features(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim[
                "recorded_dependencies"
            ],
            [],
        )

    def test_evidence_alignment_is_separate(
        self,
    ):
        bundle = self.base_bundle()

        bundle["claim_links"] = [
            {
                "claim_id": "claim-1",
                "target_type": "evidence",
                "target_id": "evidence-1",
            }
        ]

        claim = (
            main.build_claim_dependency_features(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim[
                "aligned_evidence_ids"
            ],
            ["evidence-1"],
        )

        self.assertEqual(
            claim["counts"][
                "aligned_observations"
            ],
            0,
        )

    def test_claim_specific_actors_are_exposed(
        self,
    ):
        bundle = self.base_bundle()

        bundle["source_observations"] = [
            {
                "id": "source-obs",
                "source_id": "source-a",
            }
        ]

        bundle[
            "reporter_observations"
        ] = [
            {
                "id": "reporter-obs",
                "source_id": "source-b",
                "reporter_id": "reporter-b",
            }
        ]

        bundle["claim_links"] = [
            {
                "claim_id": "claim-1",
                "target_type": (
                    "source_observation"
                ),
                "target_id": "source-obs",
            },
            {
                "claim_id": "claim-1",
                "target_type": (
                    "reporter_observation"
                ),
                "target_id": "reporter-obs",
            },
        ]

        claim = (
            main.build_claim_dependency_features(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["aligned_source_ids"],
            [
                "source-a",
                "source-b",
            ],
        )

        self.assertEqual(
            claim["aligned_reporter_ids"],
            ["reporter-b"],
        )

        self.assertTrue(
            main.build_claim_dependency_features(
                bundle
            )["policy"][
                (
                    "distinct_sources_do_not_imply_"
                    "independence"
                )
            ]
        )

    def test_claims_remain_isolated_and_stable(
        self,
    ):
        bundle = self.base_bundle()

        bundle["claims"].append(
            {
                "id": "claim-2",
                "canonical_key": (
                    "transfer|a|b|terms"
                ),
                "subject_key": (
                    "transfer|a|b"
                ),
            }
        )

        links = [
            {
                "claim_id": "claim-2",
                "target_type": (
                    "source_observation"
                ),
                "target_id": "obs-2",
            },
            {
                "claim_id": "claim-1",
                "target_type": (
                    "source_observation"
                ),
                "target_id": "obs-1",
            },
        ]

        bundle["claim_links"] = links

        first = (
            main.build_claim_dependency_features(
                bundle
            )
        )

        bundle["claim_links"] = list(
            reversed(links)
        )

        second = (
            main.build_claim_dependency_features(
                bundle
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
