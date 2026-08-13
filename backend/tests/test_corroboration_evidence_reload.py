import tempfile
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

from app.services.corroboration_graph import (
    build_corroboration_graph_plan,
)

from app.services.corroboration_materialization import (
    materialize_corroboration_graph_plan,
)


class CorroborationEvidenceReloadTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = (
            main.DB_PATH
        )

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "corroboration-reload.db"
        )

        main.init_db()

        self.origin_source = (
            main.upsert_intelligence_source(
                url=(
                    "https://origin.example/"
                ),
                display_name="Origin Sports",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.media = main.upsert_media_item(
            url=(
                "https://origin.example/"
                "alpha-beta"
            ),
            mode="article",
            title=(
                "Player Alpha agrees "
                "to join Club Beta"
            ),
            content_hash=(
                "origin-alpha-beta"
            ),
            source_id=(
                self.origin_source["id"]
            ),
            seen_at=(
                "2026-08-13T10:00:00+00:00"
            ),
        )

        self.claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|alpha|beta|agreement"
                ),
                subject_key=(
                    "transfer|alpha|beta"
                ),
                canonical_text=(
                    "Player Alpha has agreed "
                    "to join Club Beta."
                ),
                claim_type="assertion",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.origin_observation = (
            main.record_source_observation(
                source_id=(
                    self.origin_source["id"]
                ),
                media_item_id=(
                    self.media["id"]
                ),
                subject_key=(
                    self.claim["subject_key"]
                ),
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    self.claim[
                        "canonical_text"
                    ]
                ),
                provenance_url=(
                    "https://origin.example/"
                    "alpha-beta"
                ),
                confidence=0.80,
                observed_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )["observation"]
        )

        main.record_claim_link(
            claim_id=self.claim["id"],
            relationship_type="supports",
            observed_at=(
                "2026-08-13T10:00:00+00:00"
            ),
            confidence=0.80,
            source_observation_id=(
                self.origin_observation["id"]
            ),
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def graph_plan(
        self,
        *,
        dependency=False,
    ):
        candidate_url = (
            "https://news.example/"
            "alpha-beta"
        )

        assessment = {
            "claim_relationship_type": (
                "supports"
            ),
            "stance_confidence": 0.91,
            "explicit_dependency_present": (
                dependency
            ),
            "dependency_relationship": (
                "attributed_to"
                if dependency
                else ""
            ),
            "dependency_targets": (
                [
                    "https://espn.com/"
                    "source-story"
                ]
                if dependency
                else []
            ),
            "dependency_evidence": (
                [
                    "According to ESPN."
                ]
                if dependency
                else []
            ),
            "dependency_confidence": 0.82,
        }

        return (
            build_corroboration_graph_plan(
                claim={
                    "id": self.claim["id"],
                    "subject_key": (
                        self.claim[
                            "subject_key"
                        ]
                    ),
                    "canonical_text": (
                        self.claim[
                            "canonical_text"
                        ]
                    ),
                },
                collection={
                    "resolved_candidates": [
                        {
                            "resolution_status": (
                                "resolved"
                            ),
                            "final_url": (
                                candidate_url
                            ),
                            "final_source_domain": (
                                "news.example"
                            ),
                            (
                                "final_same_"
                                "source_domain"
                            ): False,
                            "published_at": (
                                "2026-08-13"
                                "T11:00:00+00:00"
                            ),
                            (
                                "publication_time_"
                                "status"
                            ): "found",
                            (
                                "publication_time_"
                                "version"
                            ): (
                                "publication-time-v1"
                            ),
                            (
                                "publication_time_"
                                "source_type"
                            ): "meta",
                            (
                                "publication_time_"
                                "source_key"
                            ): (
                                "article:"
                                "published_time"
                            ),
                            "provider": (
                                "brave_news"
                            ),
                            "provider_rank": 1,
                        }
                    ],
                },
                semantic_batch={
                    "candidate_assessments": [
                        {
                            "candidate_url": (
                                candidate_url
                            ),
                            "provider": (
                                "brave_news"
                            ),
                            "provider_rank": 1,
                            "status": "assessed",
                            "semantic_result": {
                                "status": (
                                    "assessed"
                                ),
                                "assessment": (
                                    assessment
                                ),
                            },
                        }
                    ],
                },
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
            )
        )

    def materialize(
        self,
        *,
        dependency=False,
    ):
        return (
            materialize_corroboration_graph_plan(
                plan=self.graph_plan(
                    dependency=dependency
                ),
                normalize_url=(
                    main.normalized_analysis_url
                ),
                domain_resolver=(
                    main.source_domain_for_url
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

    def bundle(self):
        return (
            main.load_evidence_analysis_bundle_for_media_item(
                media_item_id=(
                    self.media["id"]
                ),
            )
        )

    def test_materialized_same_claim_observation_reloads(
        self,
    ):
        materialized = self.materialize()

        candidate_observation_id = (
            materialized["results"][0][
                "source_observation_id"
            ]
        )

        bundle = self.bundle()

        observation_ids = {
            row["id"]
            for row in bundle[
                "source_observations"
            ]
        }

        self.assertEqual(
            observation_ids,
            {
                self.origin_observation[
                    "id"
                ],
                candidate_observation_id,
            },
        )

        self.assertEqual(
            {
                row["claim_id"]
                for row in bundle[
                    "claim_links"
                ]
            },
            {
                self.claim["id"]
            },
        )

    def test_materialized_dependency_reloads(
        self,
    ):
        materialized = self.materialize(
            dependency=True
        )

        candidate_observation_id = (
            materialized["results"][0][
                "source_observation_id"
            ]
        )

        bundle = self.bundle()

        self.assertEqual(
            len(
                bundle[
                    "observation_dependencies"
                ]
            ),
            1,
        )

        dependency = bundle[
            "observation_dependencies"
        ][0]

        self.assertEqual(
            dependency[
                "downstream_type"
            ],
            "source_observation",
        )

        self.assertEqual(
            dependency[
                "downstream_id"
            ],
            candidate_observation_id,
        )

        self.assertEqual(
            dependency[
                "upstream_type"
            ],
            "source",
        )

    def test_unlinked_same_subject_observation_does_not_leak(
        self,
    ):
        unrelated_source = (
            main.upsert_intelligence_source(
                url=(
                    "https://unlinked.example/"
                ),
                display_name=(
                    "Unlinked Sports"
                ),
                seen_at=(
                    "2026-08-13T11:15:00+00:00"
                ),
            )
        )

        unrelated = (
            main.record_source_observation(
                source_id=(
                    unrelated_source["id"]
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    "Same subject but no "
                    "explicit claim link."
                ),
                provenance_url=(
                    "https://unlinked.example/"
                    "story"
                ),
                observed_at=(
                    "2026-08-13T11:15:00+00:00"
                ),
            )["observation"]
        )

        bundle = self.bundle()

        self.assertNotIn(
            unrelated["id"],
            {
                row["id"]
                for row in bundle[
                    "source_observations"
                ]
            },
        )

    def test_different_claim_same_subject_does_not_leak(
        self,
    ):
        other_claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|alpha|beta|"
                    "interest-only"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                canonical_text=(
                    "Club Beta is only "
                    "interested in Player Alpha."
                ),
                claim_type="assertion",
                seen_at=(
                    "2026-08-13T11:20:00+00:00"
                ),
            )
        )

        other_source = (
            main.upsert_intelligence_source(
                url=(
                    "https://other.example/"
                ),
                display_name="Other Sports",
                seen_at=(
                    "2026-08-13T11:20:00+00:00"
                ),
            )
        )

        other_observation = (
            main.record_source_observation(
                source_id=(
                    other_source["id"]
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    other_claim[
                        "canonical_text"
                    ]
                ),
                provenance_url=(
                    "https://other.example/"
                    "interest"
                ),
                observed_at=(
                    "2026-08-13T11:20:00+00:00"
                ),
            )["observation"]
        )

        main.record_claim_link(
            claim_id=other_claim["id"],
            relationship_type="supports",
            observed_at=(
                "2026-08-13T11:20:00+00:00"
            ),
            confidence=0.75,
            source_observation_id=(
                other_observation["id"]
            ),
        )

        bundle = self.bundle()

        self.assertNotIn(
            other_observation["id"],
            {
                row["id"]
                for row in bundle[
                    "source_observations"
                ]
            },
        )

        self.assertEqual(
            {
                row["id"]
                for row in bundle[
                    "claims"
                ]
            },
            {
                self.claim["id"]
            },
        )

    def test_two_supporting_sources_remain_independence_unknown(
        self,
    ):
        self.materialize()

        bundle = self.bundle()

        self.assertEqual(
            bundle[
                "observation_independence_assertions"
            ],
            [],
        )

        support = (
            main.build_claim_support_provenance(
                bundle
            )
        )

        claim_state = next(
            row
            for row in support["claims"]
            if row["claim_id"]
            == self.claim["id"]
        )

        self.assertEqual(
            claim_state["status"],
            (
                "multi_source_support_"
                "independence_unknown"
            ),
        )

        self.assertFalse(
            claim_state[
                "independent_support_established"
            ]
        )

    def test_bundle_version_marks_claim_scoped_reload(
        self,
    ):
        bundle = self.bundle()

        self.assertEqual(
            bundle["version"],
            "evidence-analysis-v5",
        )

        self.assertEqual(
            main.EVIDENCE_ANALYSIS_BUNDLE_VERSION,
            "evidence-analysis-v5",
        )


if __name__ == "__main__":
    unittest.main()
