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
from app.services.corroboration_independence import (
    CORROBORATION_INDEPENDENCE_PLAN_VERSION,
    build_corroboration_independence_plan,
)


class CorroborationIndependencePlanTests(
    unittest.TestCase
):
    def observation(
        self,
        observation_id,
        source_id,
        url,
    ):
        return {
            "id": observation_id,
            "source_id": source_id,
            "subject_key": (
                "transfer|alpha|beta"
            ),
            "observation_type": "report",
            "status": "unresolved",
            "claim_summary": (
                "Player Alpha joins Club Beta."
            ),
            "provenance_url": url,
            "observed_at": (
                "2026-08-14T08:00:00+00:00"
            ),
        }

    def support_link(
        self,
        observation_id,
        *,
        relationship="supports",
        claim_id="claim-1",
    ):
        return {
            "id": (
                "link-"
                + observation_id
                + "-"
                + relationship
            ),
            "claim_id": claim_id,
            "target_type": (
                "source_observation"
            ),
            "target_id": observation_id,
            "relationship_type": (
                relationship
            ),
            "confidence": 0.9,
            "observed_at": (
                "2026-08-14T08:00:00+00:00"
            ),
        }

    def bundle(
        self,
        *,
        observations=None,
        links=None,
        dependencies=None,
        assertions=None,
        version=None,
    ):
        return {
            "version": (
                EVIDENCE_ANALYSIS_BUNDLE_VERSION
                if version is None
                else version
            ),
            "scope": {
                "media_item_id": "media-1",
            },
            "claims": [
                {
                    "id": "claim-1",
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
                    "claim_type": "assertion",
                },
            ],
            "source_observations": (
                observations or []
            ),
            "reporter_observations": [],
            "evidence_records": [],
            "evidence_links": [],
            "claim_links": links or [],
            "observation_dependencies": (
                dependencies or []
            ),
            (
                "observation_independence_"
                "assertions"
            ): assertions or [],
        }

    def eligible_bundle(self):
        first = self.observation(
            "obs-a",
            "source-a",
            "https://a.example/story",
        )

        second = self.observation(
            "obs-b",
            "source-b",
            "https://b.example/story",
        )

        return self.bundle(
            observations=[
                first,
                second,
            ],
            links=[
                self.support_link(
                    "obs-a"
                ),
                self.support_link(
                    "obs-b"
                ),
            ],
        )

    def test_builds_distinct_source_support_pair(
        self,
    ):
        result = (
            build_corroboration_independence_plan(
                evidence_bundle=(
                    self.eligible_bundle()
                ),
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["version"],
            CORROBORATION_INDEPENDENCE_PLAN_VERSION,
        )

        self.assertEqual(
            result["status"],
            "verification_pairs_available",
        )

        self.assertEqual(
            result["counts"][
                "verification_pairs"
            ],
            1,
        )

        pair = result["pairs"][0]

        self.assertEqual(
            pair[
                "observation_a_id"
            ],
            "obs-a",
        )

        self.assertEqual(
            pair[
                "observation_b_id"
            ],
            "obs-b",
        )

        self.assertEqual(
            pair["status"],
            "verification_required",
        )

    def test_pair_identity_is_deterministic(
        self,
    ):
        first = (
            build_corroboration_independence_plan(
                evidence_bundle=(
                    self.eligible_bundle()
                ),
                claim_id="claim-1",
            )
        )

        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "source_observations"
        ].reverse()

        bundle[
            "claim_links"
        ].reverse()

        second = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            first["pairs"][0][
                "pair_id"
            ],
            second["pairs"][0][
                "pair_id"
            ],
        )

    def test_same_source_pair_is_skipped(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "source_observations"
        ][1][
            "source_id"
        ] = "source-a"

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["skipped"][0][
                "reason"
            ],
            "same_source",
        )

    def test_direct_observation_dependency_blocks_pair(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dep-1",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": "obs-b",
                "upstream_type": (
                    "source_observation"
                ),
                "upstream_id": "obs-a",
                "relationship_type": (
                    "attributed_to"
                ),
            },
        ]

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["skipped"][0][
                "reason"
            ],
            "recorded_pair_dependency",
        )

        self.assertEqual(
            result["skipped"][0][
                "dependency_conflict_ids"
            ],
            ["dep-1"],
        )

    def test_supporter_source_dependency_blocks_pair(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dep-source",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": "obs-b",
                "upstream_type": "source",
                "upstream_id": "source-a",
                "relationship_type": (
                    "derived_from"
                ),
            },
        ]

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["skipped"][0][
                "reason"
            ],
            "recorded_pair_dependency",
        )

    def test_unrelated_dependency_does_not_block_pair(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "observation_dependencies"
        ] = [
            {
                "id": "dep-third-party",
                "downstream_type": (
                    "source_observation"
                ),
                "downstream_id": "obs-b",
                "upstream_type": "source",
                "upstream_id": (
                    "unrelated-source"
                ),
                "relationship_type": (
                    "attributed_to"
                ),
            },
        ]

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            len(
                result["pairs"]
            ),
            1,
        )

    def test_same_subject_without_support_does_not_enter(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "source_observations"
        ].append(
            self.observation(
                "obs-c",
                "source-c",
                "https://c.example/story",
            )
        )

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["counts"][
                "supporting_source_observations"
            ],
            2,
        )

        self.assertEqual(
            len(
                result["pairs"]
            ),
            1,
        )

    def test_non_support_relationship_does_not_enter(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "claim_links"
        ][1] = (
            self.support_link(
                "obs-b",
                relationship=(
                    "contradicts"
                ),
            )
        )

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["counts"][
                "supporting_source_observations"
            ],
            1,
        )

    def test_verified_assertion_prevents_reverification(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            {
                "id": "assertion-verified",
                "observation_a_type": (
                    "source_observation"
                ),
                "observation_a_id": "obs-a",
                "observation_b_type": (
                    "source_observation"
                ),
                "observation_b_id": "obs-b",
                "provenance_evidence_id": (
                    "evidence-1"
                ),
                "verification_status": (
                    "verified"
                ),
                "confidence": 0.95,
                "observed_at": (
                    "2026-08-14T09:00:00+00:00"
                ),
            },
        ]

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["skipped"][0][
                "reason"
            ],
            "verified_assertion_exists",
        )

    def test_unverified_assertion_can_be_reassessed(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "observation_independence_assertions"
        ] = [
            {
                "id": "assertion-unverified",
                "observation_a_type": (
                    "source_observation"
                ),
                "observation_a_id": "obs-b",
                "observation_b_type": (
                    "source_observation"
                ),
                "observation_b_id": "obs-a",
                "provenance_evidence_id": (
                    "evidence-old"
                ),
                "verification_status": (
                    "unverified"
                ),
                "confidence": 0.7,
                "observed_at": (
                    "2026-08-14T08:30:00+00:00"
                ),
            },
        ]

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            len(
                result["pairs"]
            ),
            1,
        )

        self.assertEqual(
            result["pairs"][0][
                "existing_unverified_"
                "assertion_ids"
            ],
            [
                "assertion-unverified",
            ],
        )

    def test_missing_provenance_url_is_skipped(
        self,
    ):
        bundle = (
            self.eligible_bundle()
        )

        bundle[
            "source_observations"
        ][1][
            "provenance_url"
        ] = ""

        result = (
            build_corroboration_independence_plan(
                evidence_bundle=bundle,
                claim_id="claim-1",
            )
        )

        self.assertEqual(
            result["pairs"],
            [],
        )

        self.assertEqual(
            result["skipped"][0][
                "reason"
            ],
            "provenance_url_missing",
        )

    def test_rejects_wrong_bundle_version(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported evidence analysis",
        ):
            (
                build_corroboration_independence_plan(
                    evidence_bundle=(
                        self.bundle(
                            version=(
                                "evidence-analysis-v999"
                            )
                        )
                    ),
                    claim_id="claim-1",
                )
            )


if __name__ == "__main__":
    unittest.main()
