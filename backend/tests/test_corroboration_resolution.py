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


from app.analysis.evidence import (
    EVIDENCE_ANALYSIS_BUNDLE_VERSION,
)
from app.services.corroboration_independence_pipeline import (
    CORROBORATION_INDEPENDENCE_PIPELINE_VERSION,
)
from app.services.corroboration_resolution import (
    CORROBORATION_RESOLUTION_VERSION,
    resolve_corroboration_from_independence_batch,
)


class CorroborationResolutionTests(
    unittest.TestCase
):
    def observation(
        self,
        observation_id,
        source_id,
    ):
        return {
            "id": observation_id,
            "source_id": source_id,
            "media_item_id": "",
            "story_id": "",
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "observation_type": (
                "report"
            ),
            "status": (
                "unresolved"
            ),
            "claim_summary": (
                "Player Alpha has agreed "
                "to join Club Beta."
            ),
            "provenance_url": (
                "https://"
                + source_id
                + ".example/story"
            ),
            "confidence": 0.90,
            "observed_at": (
                "2026-08-14T08:00:00+00:00"
            ),
        }

    def claim_link(
        self,
        link_id,
        observation_id,
        relationship,
    ):
        return {
            "id": link_id,
            "claim_id": (
                "claim-1"
            ),
            "target_type": (
                "source_observation"
            ),
            "target_id": (
                observation_id
            ),
            "relationship_type": (
                relationship
            ),
            "confidence": 0.90,
            "observed_at": (
                "2026-08-14T08:00:00+00:00"
            ),
        }

    def bundle(
        self,
        *,
        verified=False,
        dependency=False,
        contradiction=False,
        media_item_id="media-1",
        claim_id="claim-1",
    ):
        observations = [
            self.observation(
                "obs-a",
                "source-a",
            ),
            self.observation(
                "obs-b",
                "source-b",
            ),
        ]

        links = [
            self.claim_link(
                "link-a",
                "obs-a",
                "supports",
            ),
            self.claim_link(
                "link-b",
                "obs-b",
                "supports",
            ),
        ]

        if claim_id != "claim-1":
            for link in links:
                link[
                    "claim_id"
                ] = claim_id

        if contradiction:
            observations.append(
                self.observation(
                    "obs-c",
                    "source-c",
                )
            )

            contradiction_link = (
                self.claim_link(
                    "link-c",
                    "obs-c",
                    "contradicts",
                )
            )

            contradiction_link[
                "claim_id"
            ] = claim_id

            links.append(
                contradiction_link
            )

        dependencies = []

        if dependency:
            dependencies.append(
                {
                    "id": "dep-1",
                    "downstream_type": (
                        "source_observation"
                    ),
                    "downstream_id": (
                        "obs-b"
                    ),
                    "upstream_type": (
                        "source"
                    ),
                    "upstream_id": (
                        "source-a"
                    ),
                    "relationship_type": (
                        "attributed_to"
                    ),
                    "confidence": 0.95,
                    "observed_at": (
                        "2026-08-14T08:05:00+00:00"
                    ),
                }
            )

        assertions = []
        evidence_records = []
        evidence_links = []

        if verified:
            evidence_records.append(
                {
                    "id": (
                        "evidence-independent-1"
                    ),
                    "evidence_key": (
                        "evidence-key-1"
                    ),
                    "evidence_type": (
                        "independence_verification"
                    ),
                    "subject_key": (
                        "transfer|alpha|beta"
                    ),
                    "claim_summary": (
                        "Independent reporting "
                        "evidence"
                    ),
                    "canonical_url": "",
                    "reference_key": (
                        "independence:pair-1"
                    ),
                    "verification_status": (
                        "verified"
                    ),
                    "observed_at": (
                        "2026-08-14T08:05:00+00:00"
                    ),
                }
            )

            evidence_links.append(
                {
                    "id": (
                        "evidence-link-1"
                    ),
                    "evidence_id": (
                        "evidence-independent-1"
                    ),
                    "target_type": (
                        "media_item"
                    ),
                    "target_id": (
                        media_item_id
                    ),
                    "relationship_type": (
                        "provenance"
                    ),
                    "confidence": 0.93,
                }
            )

            assertions.append(
                {
                    "id": (
                        "assertion-1"
                    ),
                    "observation_a_type": (
                        "source_observation"
                    ),
                    "observation_a_id": (
                        "obs-a"
                    ),
                    "observation_b_type": (
                        "source_observation"
                    ),
                    "observation_b_id": (
                        "obs-b"
                    ),
                    "provenance_evidence_id": (
                        "evidence-independent-1"
                    ),
                    "verification_status": (
                        "verified"
                    ),
                    "confidence": 0.93,
                    "observed_at": (
                        "2026-08-14T08:05:00+00:00"
                    ),
                }
            )

        return {
            "version": (
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
            ),
            "scope": {
                "media_item_id": (
                    media_item_id
                ),
            },
            "story_links": [],
            "source_observations": (
                observations
            ),
            "reporter_observations": [],
            "evidence_records": (
                evidence_records
            ),
            "evidence_links": (
                evidence_links
            ),
            "claims": [
                {
                    "id": (
                        claim_id
                    ),
                    "canonical_key": (
                        "transfer|alpha|beta|agreement"
                    ),
                    "subject_key": (
                        "transfer|alpha|beta"
                    ),
                    "canonical_text": (
                        "Player Alpha has agreed "
                        "to join Club Beta."
                    ),
                    "claim_type": (
                        "assertion"
                    ),
                },
            ],
            "claim_links": (
                links
            ),
            "observation_dependencies": (
                dependencies
            ),
            (
                "observation_independence_"
                "assertions"
            ): (
                assertions
            ),
        }

    def batch(
        self,
        *,
        bundle=None,
        status="completed",
        claim_id="claim-1",
        media_item_id="media-1",
        version=None,
    ):
        return {
            "version": (
                CORROBORATION_INDEPENDENCE_PIPELINE_VERSION
                if version is None
                else version
            ),
            "status": (
                status
            ),
            "claim_id": (
                claim_id
            ),
            "media_item_id": (
                media_item_id
            ),
            "evidence_bundle": (
                self.bundle()
                if bundle is None
                else bundle
            ),
        }

    def test_verified_independent_support_establishes_corroboration(
        self,
    ):
        result = (
            resolve_corroboration_from_independence_batch(
                batch_result=(
                    self.batch(
                        bundle=(
                            self.bundle(
                                verified=True
                            )
                        )
                    )
                )
            )
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_RESOLUTION_VERSION,
        )

        self.assertEqual(
            result["status"],
            "assessed",
        )

        self.assertEqual(
            result[
                "corroboration_status"
            ],
            "corroboration_established",
        )

        self.assertTrue(
            result[
                "corroboration_established"
            ]
        )

        self.assertFalse(
            result[
                "contested"
            ]
        )

        self.assertEqual(
            result[
                "target_claim"
            ][
                "support_status"
            ],
            "verified_independent_support",
        )

    def test_distinct_sources_without_assertion_remain_unknown(
        self,
    ):
        result = (
            resolve_corroboration_from_independence_batch(
                batch_result=(
                    self.batch()
                )
            )
        )

        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )

        self.assertEqual(
            result[
                "corroboration_status"
            ],
            "support_independence_unknown",
        )

    def test_recorded_pair_dependency_blocks_corroboration(
        self,
    ):
        result = (
            resolve_corroboration_from_independence_batch(
                batch_result=(
                    self.batch(
                        bundle=(
                            self.bundle(
                                verified=True,
                                dependency=True,
                            )
                        )
                    )
                )
            )
        )

        self.assertFalse(
            result[
                "corroboration_established"
            ]
        )

        self.assertEqual(
            result[
                "corroboration_status"
            ],
            (
                "recorded_support_"
                "dependency_present"
            ),
        )

    def test_contradiction_marks_established_corroboration_contested(
        self,
    ):
        result = (
            resolve_corroboration_from_independence_batch(
                batch_result=(
                    self.batch(
                        bundle=(
                            self.bundle(
                                verified=True,
                                contradiction=True,
                            )
                        )
                    )
                )
            )
        )

        self.assertTrue(
            result[
                "corroboration_established"
            ]
        )

        self.assertTrue(
            result[
                "contested"
            ]
        )

        self.assertEqual(
            result[
                "target_claim"
            ][
                "counts"
            ][
                "contradictions"
            ],
            1,
        )

    def test_no_verification_pairs_can_resolve_existing_verified_state(
        self,
    ):
        result = (
            resolve_corroboration_from_independence_batch(
                batch_result=(
                    self.batch(
                        status=(
                            "no_verification_pairs"
                        ),
                        bundle=(
                            self.bundle(
                                verified=True
                            )
                        ),
                    )
                )
            )
        )

        self.assertTrue(
            result[
                "corroboration_established"
            ]
        )

    def test_rejects_wrong_batch_version(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported independence batch",
        ):
            (
                resolve_corroboration_from_independence_batch(
                    batch_result=(
                        self.batch(
                            version=(
                                "independence-batch-v999"
                            )
                        )
                    )
                )
            )

    def test_rejects_evidence_scope_mismatch(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "media scope does not match",
        ):
            (
                resolve_corroboration_from_independence_batch(
                    batch_result=(
                        self.batch(
                            bundle=(
                                self.bundle(
                                    media_item_id=(
                                        "different-media"
                                    )
                                )
                            )
                        )
                    )
                )
            )

    def test_requires_target_claim_in_final_analysis(
        self,
    ):
        bundle = self.bundle(
            claim_id=(
                "other-claim"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly one target claim",
        ):
            (
                resolve_corroboration_from_independence_batch(
                    batch_result=(
                        self.batch(
                            claim_id=(
                                "claim-1"
                            ),
                            bundle=bundle,
                        )
                    )
                )
            )

    def test_rejects_stage_version_mismatch(
        self,
    ):
        def bad_stance(
            bundle,
        ):
            return {
                "version": (
                    "claim-stance-v999"
                ),
                "claims": [],
            }

        with self.assertRaisesRegex(
            ValueError,
            "unsupported version",
        ):
            (
                resolve_corroboration_from_independence_batch(
                    batch_result=(
                        self.batch()
                    ),
                    stance_builder=(
                        bad_stance
                    ),
                )
            )


if __name__ == "__main__":
    unittest.main()
