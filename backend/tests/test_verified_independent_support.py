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


class VerifiedIndependentSupportTests(
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
        target_id,
        relationship_type="supports",
    ):
        return {
            "id": link_id,
            "claim_id": "claim-1",
            "target_type": (
                "source_observation"
            ),
            "target_id": target_id,
            "relationship_type": (
                relationship_type
            ),
            "confidence": 0.9,
            "observed_at": (
                "2026-08-13T18:00:00+00:00"
            ),
        }

    def assertion(
        self,
        *,
        assertion_id="independence-1",
        first="obs-1",
        second="obs-2",
        verification_status="verified",
        confidence=0.9,
    ):
        return {
            "id": assertion_id,
            "observation_a_type": (
                "source_observation"
            ),
            "observation_a_id": first,
            "observation_b_type": (
                "source_observation"
            ),
            "observation_b_id": second,
            "provenance_evidence_id": (
                "evidence-proof"
            ),
            "verification_status": (
                verification_status
            ),
            "confidence": confidence,
            "observed_at": (
                "2026-08-13T18:05:00+00:00"
            ),
        }

    def base_bundle(
        self,
        *,
        same_source=False,
        include_third=False,
    ):
        observations = [
            {
                "id": "obs-1",
                "source_id": "source-1",
            },
            {
                "id": "obs-2",
                "source_id": (
                    "source-1"
                    if same_source
                    else "source-2"
                ),
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

        if include_third:
            observations.append(
                {
                    "id": "obs-3",
                    "source_id": "source-3",
                }
            )

            links.append(
                self.support_link(
                    link_id="support-3",
                    target_id="obs-3",
                )
            )

        return {
            "claims": [
                self.claim()
            ],
            "claim_links": links,
            "source_observations": (
                observations
            ),
            "reporter_observations": [],
            "observation_dependencies": [],
            (
                "observation_independence_"
                "assertions"
            ): [],
        }

    def test_support_policy_is_v2(
        self,
    ):
        result = (
            main.build_claim_support_provenance(
                self.base_bundle()
            )
        )

        self.assertEqual(
            result["version"],
            "claim-support-provenance-v2",
        )

    def test_unverified_assertion_does_not_establish_independence(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion(
                verification_status=(
                    "unverified"
                )
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            (
                "multi_source_support_"
                "independence_unknown"
            ),
        )

        self.assertEqual(
            claim["counts"][
                "blocked_independence_assertions"
            ],
            1,
        )

    def test_verified_distinct_source_pair_establishes_independence(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion()
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertTrue(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            "verified_independent_support",
        )

        self.assertEqual(
            claim["counts"][
                (
                    "qualifying_independence_"
                    "assertions"
                )
            ],
            1,
        )

        self.assertEqual(
            claim[
                "qualifying_independence_assertions"
            ][0][
                "provenance_evidence_id"
            ],
            "evidence-proof",
        )

    def test_same_source_pair_does_not_establish_independence(
        self,
    ):
        bundle = self.base_bundle(
            same_source=True
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion()
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            (
                "support_source_diversity_"
                "not_established"
            ),
        )

        self.assertIn(
            "same_source",
            claim[
                "blocked_independence_assertions"
            ][0][
                "block_reasons"
            ],
        )

    def test_assertion_with_non_support_endpoint_is_ignored(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "source_observations"
        ].append(
            {
                "id": "neutral-obs",
                "source_id": "source-3",
            }
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion(
                second="neutral-obs"
            )
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["counts"][
                (
                    "support_independence_"
                    "assertions"
                )
            ],
            0,
        )

    def test_direct_observation_dependency_blocks_pair(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion()
        ]

        bundle[
            "observation_dependencies"
        ] = [
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
                "confidence": 0.95,
                "observed_at": (
                    "2026-08-13T18:06:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            (
                "recorded_support_dependency_"
                "present"
            ),
        )

        self.assertIn(
            "recorded_dependency_conflict",
            claim[
                "blocked_independence_assertions"
            ][0][
                "block_reasons"
            ],
        )

    def test_actor_dependency_blocks_pair(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion()
        ]

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dependency-source",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": "obs-2",
                "upstream_type": "source",
                "upstream_id": "source-1",
                "relationship_type": (
                    "attributed_to"
                ),
                "confidence": 0.9,
                "observed_at": (
                    "2026-08-13T18:07:00+00:00"
                ),
            }
        ]

        claim = (
            main.build_claim_support_provenance(
                bundle
            )["claims"][0]
        )

        self.assertFalse(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["counts"][
                (
                    "qualifying_independence_"
                    "assertions"
                )
            ],
            0,
        )

    def test_unrelated_support_dependency_does_not_erase_clean_pair(
        self,
    ):
        bundle = self.base_bundle(
            include_third=True
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion(
                first="obs-1",
                second="obs-2",
            )
        ]

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "third-party-dependency",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": "obs-3",
                "upstream_type": "source",
                "upstream_id": (
                    "outside-source"
                ),
                "relationship_type": (
                    "derived_from"
                ),
                "confidence": 0.9,
                "observed_at": (
                    "2026-08-13T18:08:00+00:00"
                ),
            }
        ]

        support = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        claim = support["claims"][0]

        self.assertTrue(
            claim[
                "independent_support_established"
            ]
        )

        self.assertEqual(
            claim["status"],
            "verified_independent_support",
        )

        stance = (
            main.build_claim_stance_analysis(
                bundle
            )
        )

        corroboration = (
            main.build_claim_corroboration_assessment(
                support_state=support,
                stance_state=stance,
            )
        )

        corroboration_claim = (
            corroboration["claims"][0]
        )

        self.assertTrue(
            corroboration_claim[
                "corroboration_established"
            ]
        )

        self.assertEqual(
            corroboration_claim["status"],
            "corroboration_established",
        )

    def test_verified_independent_support_can_be_contested(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion()
        ]

        bundle[
            "source_observations"
        ].append(
            {
                "id": "contradiction-obs",
                "source_id": "source-3",
            }
        )

        bundle[
            "claim_links"
        ].append(
            self.support_link(
                link_id="contradiction-link",
                target_id="contradiction-obs",
                relationship_type=(
                    "contradicts"
                ),
            )
        )

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

        corroboration = (
            main.build_claim_corroboration_assessment(
                support_state=support,
                stance_state=stance,
            )
        )

        claim = corroboration["claims"][0]

        self.assertTrue(
            claim[
                "corroboration_established"
            ]
        )

        self.assertTrue(
            claim["contested"]
        )

    def test_verified_status_is_categorical_not_confidence_threshold(
        self,
    ):
        bundle = self.base_bundle()

        bundle[
            "observation_independence_assertions"
        ] = [
            self.assertion(
                confidence=0.1
            )
        ]

        result = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        claim = result["claims"][0]

        self.assertTrue(
            claim[
                "independent_support_established"
            ]
        )

        self.assertTrue(
            result["policy"][
                (
                    "independence_confidence_is_"
                    "recorded_but_not_thresholded"
                )
            ]
        )

    def test_assertion_input_order_is_stable(
        self,
    ):
        bundle = self.base_bundle(
            include_third=True
        )

        first_assertion = (
            self.assertion(
                assertion_id="independence-1",
                first="obs-1",
                second="obs-2",
            )
        )

        second_assertion = (
            self.assertion(
                assertion_id="independence-2",
                first="obs-1",
                second="obs-3",
                verification_status=(
                    "unverified"
                ),
            )
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            first_assertion,
            second_assertion,
        ]

        first = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            second_assertion,
            first_assertion,
        ]

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
