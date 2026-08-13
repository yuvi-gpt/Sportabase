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


class EvidenceIndependenceAssertionTests(
    unittest.TestCase
):
    def assertion_row(
        self,
        **overrides,
    ):
        row = {
            "id": "independence-1",
            "observation_a_source_observation_id": (
                "source-observation-1"
            ),
            "observation_a_reporter_observation_id": (
                None
            ),
            "observation_b_source_observation_id": (
                None
            ),
            "observation_b_reporter_observation_id": (
                "reporter-observation-2"
            ),
            "provenance_evidence_id": (
                "evidence-1"
            ),
            "verification_status": (
                " VERIFIED "
            ),
            "confidence": 0.9,
            "observed_at": (
                "2026-08-13T17:00:00+00:00"
            ),
            "recorded_at": (
                "2026-08-13T17:01:00+00:00"
            ),
            "metadata_json": (
                '{"capture":"first"}'
            ),
        }

        row.update(
            overrides
        )

        return row

    def test_bundle_version_is_v4(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1"
            )
        )

        self.assertEqual(
            bundle["version"],
            "evidence-analysis-v4",
        )

        self.assertEqual(
            bundle[
                "observation_independence_assertions"
            ],
            [],
        )

    def test_assertion_is_normalized(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row()
                ],
            )
        )

        assertion = bundle[
            "observation_independence_assertions"
        ][0]

        self.assertEqual(
            assertion[
                "verification_status"
            ],
            "verified",
        )

        self.assertEqual(
            {
                (
                    assertion[
                        "observation_a_type"
                    ],
                    assertion[
                        "observation_a_id"
                    ],
                ),
                (
                    assertion[
                        "observation_b_type"
                    ],
                    assertion[
                        "observation_b_id"
                    ],
                ),
            },
            {
                (
                    "source_observation",
                    "source-observation-1",
                ),
                (
                    "reporter_observation",
                    "reporter-observation-2",
                ),
            },
        )

        self.assertEqual(
            assertion[
                "provenance_evidence_id"
            ],
            "evidence-1",
        )

    def test_assertion_endpoint_order_is_semantically_symmetric(
        self,
    ):
        forward = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row()
                ],
            )
        )

        reverse = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row(
                        observation_a_source_observation_id=(
                            None
                        ),
                        observation_a_reporter_observation_id=(
                            "reporter-observation-2"
                        ),
                        observation_b_source_observation_id=(
                            "source-observation-1"
                        ),
                        observation_b_reporter_observation_id=(
                            None
                        ),
                    )
                ],
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )

    def test_operational_fields_do_not_change_bundle(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row()
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row(
                        recorded_at=(
                            "2026-08-13T20:00:00+00:00"
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

    def test_assertion_semantics_change_hash(
        self,
    ):
        verified = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row(
                        verification_status=(
                            "verified"
                        )
                    )
                ],
            )
        )

        unverified = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    self.assertion_row(
                        verification_status=(
                            "unverified"
                        )
                    )
                ],
            )
        )

        self.assertNotEqual(
            main.evidence_analysis_bundle_hash(
                verified
            ),
            main.evidence_analysis_bundle_hash(
                unverified
            ),
        )

    def test_assertion_input_order_is_stable(
        self,
    ):
        first_row = self.assertion_row()

        second_row = self.assertion_row(
            id="independence-2",
            observation_a_source_observation_id=(
                "source-observation-3"
            ),
            observation_b_reporter_observation_id=(
                "reporter-observation-4"
            ),
            provenance_evidence_id=(
                "evidence-2"
            ),
        )

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    first_row,
                    second_row,
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                observation_independence_assertions=[
                    second_row,
                    first_row,
                ],
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def retrieval_bundle(
        self,
    ):
        original_db_path = (
            main.DB_PATH
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            main.DB_PATH = (
                Path(temp_dir)
                / "independence-retrieval.db"
            )

            try:
                main.init_db()

                source_a = (
                    main.upsert_intelligence_source(
                        url="https://a.example/",
                        display_name="Source A",
                        seen_at=(
                            "2026-08-13T15:00:00+00:00"
                        ),
                    )
                )

                source_b = (
                    main.upsert_intelligence_source(
                        url="https://b.example/",
                        display_name="Source B",
                        seen_at=(
                            "2026-08-13T15:00:00+00:00"
                        ),
                    )
                )

                media = main.upsert_media_item(
                    url=(
                        "https://a.example/story"
                    ),
                    mode="article",
                    title="Story",
                    content_hash="hash-1",
                    source_id=source_a["id"],
                    seen_at=(
                        "2026-08-13T15:10:00+00:00"
                    ),
                )

                scoped_a = (
                    main.record_source_observation(
                        source_id=source_a["id"],
                        media_item_id=media["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-13T15:20:00+00:00"
                        ),
                    )["observation"]
                )

                scoped_b = (
                    main.record_source_observation(
                        source_id=source_b["id"],
                        media_item_id=media["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-13T15:21:00+00:00"
                        ),
                    )["observation"]
                )

                outside = (
                    main.record_source_observation(
                        source_id=source_b["id"],
                        subject_key="case-1",
                        observation_type="report",
                        status="unresolved",
                        observed_at=(
                            "2026-08-13T15:22:00+00:00"
                        ),
                    )["observation"]
                )

                provenance = (
                    main.record_evidence(
                        evidence_type=(
                            "primary_document"
                        ),
                        subject_key="case-1",
                        reference_key=(
                            "independence-proof"
                        ),
                        verification_status=(
                            "verified"
                        ),
                        observed_at=(
                            "2026-08-13T15:30:00+00:00"
                        ),
                    )["evidence"]
                )

                scoped_assertion = (
                    main.record_observation_independence_assertion(
                        left_source_observation_id=(
                            scoped_a["id"]
                        ),
                        right_source_observation_id=(
                            scoped_b["id"]
                        ),
                        provenance_evidence_id=(
                            provenance["id"]
                        ),
                        verification_status=(
                            "verified"
                        ),
                        confidence=0.95,
                        observed_at=(
                            "2026-08-13T15:40:00+00:00"
                        ),
                    )["assertion"]
                )

                outside_assertion = (
                    main.record_observation_independence_assertion(
                        left_source_observation_id=(
                            scoped_a["id"]
                        ),
                        right_source_observation_id=(
                            outside["id"]
                        ),
                        provenance_evidence_id=(
                            provenance["id"]
                        ),
                        verification_status=(
                            "verified"
                        ),
                        confidence=0.95,
                        observed_at=(
                            "2026-08-13T15:41:00+00:00"
                        ),
                    )["assertion"]
                )

                bundle = (
                    main.load_evidence_analysis_bundle_for_media_item(
                        media_item_id=(
                            media["id"]
                        )
                    )
                )

                return (
                    bundle,
                    scoped_assertion,
                    outside_assertion,
                    provenance,
                )

            finally:
                main.DB_PATH = (
                    original_db_path
                )

    def test_retrieval_requires_both_endpoints_in_scope(
        self,
    ):
        (
            bundle,
            scoped_assertion,
            outside_assertion,
            _,
        ) = self.retrieval_bundle()

        assertion_ids = {
            row["id"]
            for row in bundle[
                "observation_independence_assertions"
            ]
        }

        self.assertIn(
            scoped_assertion["id"],
            assertion_ids,
        )

        self.assertNotIn(
            outside_assertion["id"],
            assertion_ids,
        )

    def test_provenance_evidence_does_not_expand_bundle(
        self,
    ):
        (
            bundle,
            scoped_assertion,
            _,
            provenance,
        ) = self.retrieval_bundle()

        self.assertEqual(
            bundle[
                "observation_independence_assertions"
            ][0][
                "provenance_evidence_id"
            ],
            provenance["id"],
        )

        self.assertNotIn(
            provenance["id"],
            {
                row["id"]
                for row in bundle[
                    "evidence_records"
                ]
            },
        )

        self.assertEqual(
            bundle[
                "observation_independence_assertions"
            ][0]["id"],
            scoped_assertion["id"],
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
