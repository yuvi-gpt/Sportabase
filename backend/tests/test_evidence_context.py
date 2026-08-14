import copy
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


class EvidenceContextTests(
    unittest.TestCase
):
    def source_observation(
        self,
        *,
        row_id="source-observation-1",
        status="unresolved",
    ):
        return {
            "id": row_id,
            "source_id": "source-1",
            "media_item_id": "media-1",
            "story_id": "",
            "subject_key": (
                "transfer|player-a|club-b"
            ),
            "observation_type": "report",
            "status": status,
            "claim_summary": (
                "Descriptive wording."
            ),
            "provenance_url": (
                "https://example.com/report"
            ),
            "confidence": 0.8,
            "observed_at": (
                "2026-08-12T10:00:00+00:00"
            ),
            "recorded_at": (
                "2026-08-12T10:01:00+00:00"
            ),
            "metadata_json": (
                '{"capture":"first"}'
            ),
        }

    def reporter_observation(
        self,
    ):
        return {
            "id": "reporter-observation-1",
            "reporter_id": "reporter-1",
            "source_id": "source-1",
            "media_item_id": "media-1",
            "story_id": "",
            "subject_key": (
                "transfer|player-a|club-b"
            ),
            "observation_type": "report",
            "status": "unresolved",
            "claim_summary": (
                "Reporter descriptive wording."
            ),
            "provenance_url": (
                "https://example.com/reporter"
            ),
            "confidence": 0.7,
            "observed_at": (
                "2026-08-12T10:02:00+00:00"
            ),
            "recorded_at": (
                "2026-08-12T10:03:00+00:00"
            ),
            "metadata_json": "{}",
        }

    def evidence_record(
        self,
    ):
        return {
            "id": "evidence-1",
            "evidence_key": "evidence-key-1",
            "evidence_type": (
                "independent_report"
            ),
            "subject_key": (
                "transfer|player-a|club-b"
            ),
            "claim_summary": (
                "Evidence descriptive wording."
            ),
            "canonical_url": (
                "https://example.com/evidence"
            ),
            "reference_key": "",
            "verification_status": (
                "unverified"
            ),
            "published_at": (
                "2026-08-12T09:50:00+00:00"
            ),
            "observed_at": (
                "2026-08-12T10:04:00+00:00"
            ),
            "recorded_at": (
                "2026-08-12T10:05:00+00:00"
            ),
            "metadata_json": "{}",
        }

    def evidence_link(
        self,
        *,
        relationship_type="supports",
    ):
        return {
            "id": "evidence-link-1",
            "evidence_id": "evidence-1",
            "media_item_id": "media-1",
            "story_id": None,
            "source_id": None,
            "reporter_id": None,
            "relationship_type": (
                relationship_type
            ),
            "confidence": 0.9,
            "linked_at": (
                "2026-08-12T10:06:00+00:00"
            ),
            "metadata_json": "{}",
        }

    def build_full_context(self):
        return main.build_evidence_context(
            source_observations=[
                self.source_observation(),
            ],
            reporter_observations=[
                self.reporter_observation(),
            ],
            evidence_records=[
                self.evidence_record(),
            ],
            evidence_links=[
                self.evidence_link(),
            ],
        )

    def test_empty_context_is_stable(
        self,
    ):
        first = main.build_evidence_context()
        second = main.build_evidence_context()

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            first["version"],
            main.EVIDENCE_CONTEXT_VERSION,
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_subject_scope_changes_hash(
        self,
    ):
        first = main.build_evidence_context(
            subject_key=(
                "transfer|player-a|club-b"
            ),
        )

        second = main.build_evidence_context(
            subject_key=(
                "transfer|player-a|club-c"
            ),
        )

        self.assertNotEqual(
            first,
            second,
        )

        self.assertNotEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_same_scope_is_stable(
        self,
    ):
        first = main.build_evidence_context(
            subject_key=(
                "transfer|player-a|club-b"
            ),
            media_item_id="media-1",
            story_id="story-1",
            source_id="source-1",
            reporter_id="reporter-1",
        )

        second = main.build_evidence_context(
            subject_key=(
                "transfer|player-a|club-b"
            ),
            media_item_id="media-1",
            story_id="story-1",
            source_id="source-1",
            reporter_id="reporter-1",
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            first["scope"],
            {
                "subject_key": (
                    "transfer|player-a|club-b"
                ),
                "media_item_id": "media-1",
                "story_id": "story-1",
                "source_id": "source-1",
                "reporter_id": "reporter-1",
            },
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_source_scope_changes_hash(
        self,
    ):
        first = main.build_evidence_context(
            source_id="source-1",
        )

        second = main.build_evidence_context(
            source_id="source-2",
        )

        self.assertNotEqual(
            first,
            second,
        )

        self.assertNotEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_reporter_scope_changes_hash(
        self,
    ):
        first = main.build_evidence_context(
            reporter_id="reporter-1",
        )

        second = main.build_evidence_context(
            reporter_id="reporter-2",
        )

        self.assertNotEqual(
            first,
            second,
        )

        self.assertNotEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_input_order_does_not_change_context(
        self,
    ):
        first_row = self.source_observation(
            row_id="source-observation-a",
        )

        second_row = self.source_observation(
            row_id="source-observation-b",
        )

        first = main.build_evidence_context(
            source_observations=[
                first_row,
                second_row,
            ],
        )

        second = main.build_evidence_context(
            source_observations=[
                second_row,
                first_row,
            ],
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_duplicate_rows_collapse_by_id(
        self,
    ):
        row = self.source_observation()

        context = main.build_evidence_context(
            source_observations=[
                row,
                copy.deepcopy(row),
            ],
        )

        self.assertEqual(
            len(
                context[
                    "source_observations"
                ]
            ),
            1,
        )

    def test_descriptive_fields_do_not_change_context(
        self,
    ):
        first_row = self.source_observation()
        second_row = copy.deepcopy(first_row)

        second_row["claim_summary"] = (
            "Completely different wording."
        )

        second_row["recorded_at"] = (
            "2026-08-12T12:00:00+00:00"
        )

        second_row["metadata_json"] = (
            '{"capture":"later"}'
        )

        first = main.build_evidence_context(
            source_observations=[
                first_row,
            ],
        )

        second = main.build_evidence_context(
            source_observations=[
                second_row,
            ],
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_meaningful_status_change_changes_hash(
        self,
    ):
        first = main.build_evidence_context(
            source_observations=[
                self.source_observation(
                    status="unresolved",
                ),
            ],
        )

        second = main.build_evidence_context(
            source_observations=[
                self.source_observation(
                    status="confirmed",
                ),
            ],
        )

        self.assertNotEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_relationship_change_changes_hash(
        self,
    ):
        first = main.build_evidence_context(
            evidence_links=[
                self.evidence_link(
                    relationship_type="supports",
                ),
            ],
        )

        second = main.build_evidence_context(
            evidence_links=[
                self.evidence_link(
                    relationship_type="contradicts",
                ),
            ],
        )

        self.assertNotEqual(
            main.evidence_context_hash(first),
            main.evidence_context_hash(second),
        )

    def test_conflicting_duplicate_ids_are_rejected(
        self,
    ):
        first_row = self.source_observation()
        second_row = self.source_observation(
            status="confirmed",
        )

        with self.assertRaises(ValueError):
            main.build_evidence_context(
                source_observations=[
                    first_row,
                    second_row,
                ],
            )

    def test_evidence_link_requires_exactly_one_target(
        self,
    ):
        link = self.evidence_link()
        link["story_id"] = "story-1"

        with self.assertRaises(ValueError):
            main.build_evidence_context(
                evidence_links=[
                    link,
                ],
            )

    def test_invalid_confidence_is_rejected(
        self,
    ):
        row = self.source_observation()
        row["confidence"] = 1.5

        with self.assertRaises(ValueError):
            main.build_evidence_context(
                source_observations=[
                    row,
                ],
            )


if __name__ == "__main__":
    unittest.main()
