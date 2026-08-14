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


class ClaimSupportProvenanceTests(
    unittest.TestCase
):
    def claim(self):
        return {
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
            "claim_type": "assertion",
        }

    def support_link(
        self,
        *,
        link_id,
        target_type=(
            "source_observation"
        ),
        target_id="obs-1",
        relationship_type="supports",
    ):
        return {
            "id": link_id,
            "claim_id": "claim-1",
            "target_type": target_type,
            "target_id": target_id,
            "relationship_type": (
                relationship_type
            ),
            "confidence": 0.9,
            "observed_at": (
                "2026-08-13"
                "T15:00:00+00:00"
            ),
        }

    def bundle(self):
        return {
            "claims": [
                self.claim()
            ],
            "claim_links": [],
            "source_observations": [],
            "reporter_observations": [],
            "observation_dependencies": [],
        }

    def test_dictionary_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.build_claim_support_provenance(
                []
            )

    def test_neutral_alignment_is_not_support(
        self,
    ):
        bundle = self.bundle()

        bundle["claim_links"] = [
            self.support_link(
                link_id="neutral-1",
                relationship_type=(
                    "aligned_to"
                ),
            )
        ]

        result = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            "no_explicit_support",
        )

        self.assertEqual(
            claim["counts"][
                "supporting_observations"
            ],
            0,
        )

    def test_evidence_only_support_is_separate(
        self,
    ):
        bundle = self.bundle()

        bundle["claim_links"] = [
            self.support_link(
                link_id="evidence-support",
                target_type="evidence",
                target_id="evidence-1",
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            "evidence_only_support",
        )

        self.assertEqual(
            claim[
                "supporting_evidence_ids"
            ],
            ["evidence-1"],
        )

        self.assertEqual(
            claim[
                "supporting_source_ids"
            ],
            [],
        )

    def test_single_support_observation(
        self,
    ):
        bundle = self.bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            }
        ]

        bundle["claim_links"] = [
            self.support_link(
                link_id="support-1",
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            "single_support_observation",
        )

        self.assertEqual(
            claim[
                "supporting_source_ids"
            ],
            ["source-1"],
        )

    def test_same_source_does_not_establish_diversity(
        self,
    ):
        bundle = self.bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": "source-1",
            },
        ]

        bundle["claim_links"] = [
            self.support_link(
                link_id="support-1",
                target_id="obs-1",
            ),
            self.support_link(
                link_id="support-2",
                target_id="obs-2",
            ),
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            (
                "support_source_diversity_"
                "not_established"
            ),
        )

    def test_multi_source_without_dependency_is_unknown(
        self,
    ):
        bundle = self.bundle()

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
            self.support_link(
                link_id="support-1",
                target_id="obs-1",
            ),
            self.support_link(
                link_id="support-2",
                target_id="obs-2",
            ),
        ]

        result = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        claim = result["claims"][0]

        self.assertEqual(
            claim["status"],
            (
                "multi_source_support_"
                "independence_unknown"
            ),
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim[
                "corroboration_status"
            ],
            "not_assessed",
        )

    def test_dependency_is_support_specific(
        self,
    ):
        bundle = self.bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": "source-2",
            },
            {
                "id": "neutral-obs",
                "source_id": "source-3",
            },
        ]

        bundle["claim_links"] = [
            self.support_link(
                link_id="support-1",
                target_id="obs-1",
            ),
            self.support_link(
                link_id="support-2",
                target_id="obs-2",
            ),
            self.support_link(
                link_id="neutral-link",
                target_id="neutral-obs",
                relationship_type=(
                    "aligned_to"
                ),
            ),
        ]

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "irrelevant-dependency",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": (
                    "neutral-obs"
                ),
                "upstream_type": "source",
                "upstream_id": "source-1",
                "relationship_type": (
                    "derived_from"
                ),
                "confidence": 0.9,
                "observed_at": (
                    "2026-08-13"
                    "T15:01:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            (
                "multi_source_support_"
                "independence_unknown"
            ),
        )

        self.assertEqual(
            claim[
                "recorded_support_dependencies"
            ],
            [],
        )

    def test_recorded_support_dependency_is_detected(
        self,
    ):
        bundle = self.bundle()

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
            self.support_link(
                link_id="support-1",
                target_id="obs-1",
            ),
            self.support_link(
                link_id="support-2",
                target_id="obs-2",
            ),
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
                "confidence": 0.95,
                "observed_at": (
                    "2026-08-13"
                    "T15:02:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            (
                "recorded_support_dependency_"
                "present"
            ),
        )

        self.assertEqual(
            claim["counts"][
                (
                    "supporter_to_supporter_"
                    "dependencies"
                )
            ],
            1,
        )

    def test_contradiction_does_not_count_as_support(
        self,
    ):
        bundle = self.bundle()

        bundle["source_observations"] = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            }
        ]

        bundle["claim_links"] = [
            self.support_link(
                link_id="contradiction-1",
                relationship_type=(
                    "contradicts"
                ),
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim["status"],
            "no_explicit_support",
        )

    def test_reporter_support_preserves_actor_identity(
        self,
    ):
        bundle = self.bundle()

        bundle[
            "reporter_observations"
        ] = [
            {
                "id": "reporter-obs-1",
                "source_id": "source-1",
                "reporter_id": "reporter-1",
            }
        ]

        bundle["claim_links"] = [
            self.support_link(
                link_id="reporter-support",
                target_type=(
                    "reporter_observation"
                ),
                target_id=(
                    "reporter-obs-1"
                ),
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertEqual(
            claim[
                "supporting_source_ids"
            ],
            ["source-1"],
        )

        self.assertEqual(
            claim[
                "supporting_reporter_ids"
            ],
            ["reporter-1"],
        )

    def test_input_order_is_stable(
        self,
    ):
        bundle = self.bundle()

        observations = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": "source-2",
            },
        ]

        links = [
            self.support_link(
                link_id="support-1",
                target_id="obs-1",
            ),
            self.support_link(
                link_id="support-2",
                target_id="obs-2",
            ),
        ]

        bundle[
            "source_observations"
        ] = observations

        bundle["claim_links"] = links

        first = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        bundle[
            "source_observations"
        ] = list(
            reversed(observations)
        )

        bundle["claim_links"] = list(
            reversed(links)
        )

        second = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        self.assertEqual(
            first,
            second,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
