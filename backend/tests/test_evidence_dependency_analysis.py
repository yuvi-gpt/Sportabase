import sys
import tempfile
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


class EvidenceDependencyAnalysisTests(
    unittest.TestCase
):
    def dependency_row(
        self,
        **overrides,
    ):
        row = {
            "id": "dependency-1",
            "downstream_source_observation_id":
                "source-observation-1",
            "downstream_reporter_observation_id":
                None,
            "upstream_source_observation_id":
                None,
            "upstream_reporter_observation_id":
                None,
            "upstream_source_id":
                "source-2",
            "upstream_reporter_id":
                None,
            "relationship_type":
                " ATTRIBUTED_TO ",
            "confidence": 0.8,
            "observed_at":
                "2026-08-12T12:00:00+00:00",
            "recorded_at":
                "2026-08-12T12:01:00+00:00",
            "metadata_json":
                '{"capture":"first"}',
        }

        row.update(overrides)

        return row

    def test_bundle_version_is_v3(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1"
            )
        )

        self.assertEqual(
            bundle["version"],
            "evidence-analysis-v3",
        )

        self.assertEqual(
            bundle[
                "observation_dependencies"
            ],
            [],
        )

    def test_dependency_is_normalized(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    self.dependency_row()
                ],
            )
        )

        self.assertEqual(
            bundle[
                "observation_dependencies"
            ],
            [
                {
                    "id":
                        "dependency-1",
                    "downstream_type":
                        "source_observation",
                    "downstream_id":
                        "source-observation-1",
                    "upstream_type":
                        "source",
                    "upstream_id":
                        "source-2",
                    "relationship_type":
                        "attributed_to",
                    "confidence": 0.8,
                    "observed_at":
                        "2026-08-12T12:00:00+00:00",
                }
            ],
        )

    def test_operational_fields_do_not_change_bundle(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    self.dependency_row()
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    self.dependency_row(
                        recorded_at=(
                            "2026-08-12T20:00:00+00:00"
                        ),
                        metadata_json=(
                            '{"capture":"different"}'
                        ),
                    )
                ],
            )
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )

    def test_dependency_semantics_change_hash(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    self.dependency_row(
                        relationship_type=(
                            "attributed_to"
                        )
                    )
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    self.dependency_row(
                        relationship_type=(
                            "derived_from"
                        )
                    )
                ],
            )
        )

        self.assertNotEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )

    def test_dependency_input_order_is_stable(
        self,
    ):
        first_row = self.dependency_row()

        second_row = self.dependency_row(
            id="dependency-2",
            upstream_source_id=None,
            upstream_reporter_id=(
                "reporter-2"
            ),
        )

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    first_row,
                    second_row,
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_dependencies=[
                    second_row,
                    first_row,
                ],
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_retrieval_is_scoped_by_downstream_observation(
        self,
    ):
        original_db_path = main.DB_PATH

        with tempfile.TemporaryDirectory() as temp_dir:
            main.DB_PATH = (
                Path(temp_dir)
                / "dependency-analysis.db"
            )

            try:
                main.init_db()

                source_a = (
                    main.upsert_intelligence_source(
                        url=(
                            "https://a.example/"
                        ),
                        display_name="Source A",
                        seen_at=(
                            "2026-08-12T09:00:00+00:00"
                        ),
                    )
                )

                source_b = (
                    main.upsert_intelligence_source(
                        url=(
                            "https://b.example/"
                        ),
                        display_name="Source B",
                        seen_at=(
                            "2026-08-12T09:00:00+00:00"
                        ),
                    )
                )

                reporter_a = (
                    main.upsert_intelligence_reporter(
                        identity_key=(
                            "reporter-a"
                        ),
                        display_name="Reporter A",
                        seen_at=(
                            "2026-08-12T09:00:00+00:00"
                        ),
                    )
                )

                reporter_b = (
                    main.upsert_intelligence_reporter(
                        identity_key=(
                            "reporter-b"
                        ),
                        display_name="Reporter B",
                        seen_at=(
                            "2026-08-12T09:00:00+00:00"
                        ),
                    )
                )

                media = main.upsert_media_item(
                    url=(
                        "https://a.example/"
                        "story"
                    ),
                    mode="article",
                    title="Story",
                    content_hash="hash-1",
                    source_id=source_a["id"],
                    reporter_id=(
                        reporter_a["id"]
                    ),
                    seen_at=(
                        "2026-08-12T10:00:00+00:00"
                    ),
                )

                story = (
                    main.upsert_intelligence_story(
                        canonical_key=(
                            "story|one"
                        ),
                        canonical_title=(
                            "Story One"
                        ),
                        seen_at=(
                            "2026-08-12T09:30:00+00:00"
                        ),
                    )
                )

                other_story = (
                    main.upsert_intelligence_story(
                        canonical_key=(
                            "story|other"
                        ),
                        canonical_title=(
                            "Other Story"
                        ),
                        seen_at=(
                            "2026-08-12T09:35:00+00:00"
                        ),
                    )
                )

                main.link_media_item_to_story(
                    story_id=story["id"],
                    media_item_id=media["id"],
                    relationship_type="reports",
                    confidence=0.8,
                )

                scoped_source_observation = (
                    main.record_source_observation(
                        source_id=source_a["id"],
                        story_id=story["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-12T10:10:00+00:00"
                        ),
                    )["observation"]
                )

                scoped_reporter_observation = (
                    main.record_reporter_observation(
                        reporter_id=(
                            reporter_a["id"]
                        ),
                        source_id=source_a["id"],
                        media_item_id=media["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-12T10:15:00+00:00"
                        ),
                    )["observation"]
                )

                upstream_reporter_observation = (
                    main.record_reporter_observation(
                        reporter_id=(
                            reporter_b["id"]
                        ),
                        source_id=source_b["id"],
                        story_id=other_story["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-12T09:45:00+00:00"
                        ),
                    )["observation"]
                )

                unrelated_downstream = (
                    main.record_source_observation(
                        source_id=source_b["id"],
                        story_id=(
                            other_story["id"]
                        ),
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-12T10:20:00+00:00"
                        ),
                    )["observation"]
                )

                scoped_source_dependency = (
                    main.record_observation_dependency(
                        downstream_source_observation_id=(
                            scoped_source_observation[
                                "id"
                            ]
                        ),
                        upstream_source_id=(
                            source_b["id"]
                        ),
                        relationship_type=(
                            "attributed_to"
                        ),
                        confidence=0.9,
                        observed_at=(
                            "2026-08-12T10:25:00+00:00"
                        ),
                    )["dependency"]
                )

                scoped_reporter_dependency = (
                    main.record_observation_dependency(
                        downstream_reporter_observation_id=(
                            scoped_reporter_observation[
                                "id"
                            ]
                        ),
                        upstream_reporter_observation_id=(
                            upstream_reporter_observation[
                                "id"
                            ]
                        ),
                        relationship_type=(
                            "derived_from"
                        ),
                        confidence=0.8,
                        observed_at=(
                            "2026-08-12T10:26:00+00:00"
                        ),
                    )["dependency"]
                )

                unrelated_dependency = (
                    main.record_observation_dependency(
                        downstream_source_observation_id=(
                            unrelated_downstream[
                                "id"
                            ]
                        ),
                        upstream_source_id=(
                            source_a["id"]
                        ),
                        relationship_type=(
                            "attributed_to"
                        ),
                        confidence=0.7,
                        observed_at=(
                            "2026-08-12T10:27:00+00:00"
                        ),
                    )["dependency"]
                )

                bundle = (
                    main.load_evidence_analysis_bundle_for_media_item(
                        media_item_id=media["id"],
                    )
                )

                dependency_ids = {
                    row["id"]
                    for row in bundle[
                        "observation_dependencies"
                    ]
                }

                self.assertEqual(
                    dependency_ids,
                    {
                        scoped_source_dependency[
                            "id"
                        ],
                        scoped_reporter_dependency[
                            "id"
                        ],
                    },
                )

                self.assertNotIn(
                    unrelated_dependency["id"],
                    dependency_ids,
                )

                loaded_reporter_observation_ids = {
                    row["id"]
                    for row in bundle[
                        "reporter_observations"
                    ]
                }

                self.assertNotIn(
                    upstream_reporter_observation[
                        "id"
                    ],
                    loaded_reporter_observation_ids,
                )

            finally:
                main.DB_PATH = (
                    original_db_path
                )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
