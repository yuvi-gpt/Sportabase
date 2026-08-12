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


class EvidenceAnalysisBundleTests(
    unittest.TestCase
):
    def evidence_row(
        self,
        *,
        claim_summary="Club confirmed the move.",
    ):
        return {
            "id": "evidence-1",
            "evidence_key": "key-1",
            "evidence_type": "Official_Statement",
            "subject_key": "transfer|a|b",
            "claim_summary": claim_summary,
            "canonical_url": (
                "https://club.example/statement"
            ),
            "reference_key": "",
            "verification_status": "Verified",
            "observed_at": (
                "2026-08-12T10:00:00+00:00"
            ),
            "recorded_at": (
                "2026-08-12T10:01:00+00:00"
            ),
            "metadata_json": '{"ignored":true}',
        }

    def test_claim_summary_is_analysis_semantic(
        self,
    ):
        first_row = self.evidence_row(
            claim_summary="Club confirmed the move."
        )

        second_row = self.evidence_row(
            claim_summary="Club denied the move."
        )

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[first_row],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[second_row],
            )
        )

        self.assertNotEqual(
            first,
            second,
        )

        first_identity = (
            main.build_evidence_context(
                media_item_id="media-1",
                evidence_records=[first_row],
            )
        )

        second_identity = (
            main.build_evidence_context(
                media_item_id="media-1",
                evidence_records=[second_row],
            )
        )

        self.assertEqual(
            first_identity,
            second_identity,
        )

    def test_input_order_is_stable(
        self,
    ):
        first_evidence = self.evidence_row()

        second_evidence = {
            **self.evidence_row(
                claim_summary="League registration cleared."
            ),
            "id": "evidence-2",
            "evidence_key": "key-2",
            "reference_key": "league-record",
            "canonical_url": "",
        }

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    first_evidence,
                    second_evidence,
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    second_evidence,
                    first_evidence,
                ],
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_operational_fields_are_excluded(
        self,
    ):
        first_row = self.evidence_row()

        second_row = {
            **first_row,
            "recorded_at": (
                "2026-08-12T20:00:00+00:00"
            ),
            "metadata_json": (
                '{"different":true}'
            ),
        }

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[first_row],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[second_row],
            )
        )

        self.assertEqual(
            first,
            second,
        )

    def test_analysis_bundle_hash_is_stable(
        self,
    ):
        bundle = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    self.evidence_row()
                ],
            )
        )

        first_hash = (
            main.evidence_analysis_bundle_hash(
                bundle
            )
        )

        second_hash = (
            main.evidence_analysis_bundle_hash(
                bundle
            )
        )

        self.assertEqual(
            first_hash,
            second_hash,
        )

    def test_claim_summary_changes_analysis_hash(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    self.evidence_row(
                        claim_summary=(
                            "Club confirmed the move."
                        )
                    )
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    self.evidence_row(
                        claim_summary=(
                            "Club denied the move."
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

    def test_operational_fields_do_not_change_analysis_hash(
        self,
    ):
        first_row = self.evidence_row()

        second_row = {
            **first_row,
            "recorded_at": (
                "2026-08-12T20:00:00+00:00"
            ),
            "metadata_json": (
                '{"different":true}'
            ),
        }

        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    first_row
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_records=[
                    second_row
                ],
            )
        )

        self.assertEqual(
            main.evidence_analysis_bundle_hash(
                first
            ),
            main.evidence_analysis_bundle_hash(
                second
            ),
        )

    def test_analysis_bundle_hash_requires_dictionary(
        self,
    ):
        with self.assertRaises(ValueError):
            main.evidence_analysis_bundle_hash(
                []
            )

    def test_story_link_is_analysis_semantic(
        self,
    ):
        first = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                story_links=[
                    {
                        "story_id": "story-1",
                        "relationship_type": "reports",
                        "confidence": 0.8,
                    }
                ],
            )
        )

        second = (
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                story_links=[
                    {
                        "story_id": "story-1",
                        "relationship_type": (
                            "corroborates"
                        ),
                        "confidence": 0.8,
                    }
                ],
            )
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_conflicting_story_links_are_rejected(
        self,
    ):
        with self.assertRaises(ValueError):
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                story_links=[
                    {
                        "story_id": "story-1",
                        "relationship_type": "reports",
                        "confidence": 0.8,
                    },
                    {
                        "story_id": "story-1",
                        "relationship_type": (
                            "corroborates"
                        ),
                        "confidence": 0.8,
                    },
                ],
            )

    def test_link_requires_exactly_one_target(
        self,
    ):
        with self.assertRaises(ValueError):
            main.build_evidence_analysis_bundle(
                media_item_id="media-1",
                evidence_links=[
                    {
                        "id": "link-1",
                        "evidence_id": "evidence-1",
                        "media_item_id": "media-1",
                        "story_id": "story-1",
                        "relationship_type": "supports",
                        "confidence": 0.9,
                    }
                ],
            )

    def test_media_item_id_is_required(
        self,
    ):
        with self.assertRaises(ValueError):
            main.build_evidence_analysis_bundle(
                media_item_id="   ",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
