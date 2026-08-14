import sqlite3
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


class EvidenceLinkPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-link-test.db"
        )

        main.init_db()

        self.evidence = main.record_evidence(
            evidence_type="primary_document",
            subject_key="case-1",
            reference_key="DOC-2026-001",
            verification_status="verified",
            observed_at=(
                "2026-08-12T10:00:00+00:00"
            ),
        )["evidence"]

        self.source = (
            main.upsert_intelligence_source(
                url="https://example.com/",
                display_name="Example Sports",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

        self.reporter = (
            main.upsert_intelligence_reporter(
                identity_key=(
                    "social|x|reporter-a"
                ),
                display_name="Reporter A",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

        self.media = main.upsert_media_item(
            url="https://example.com/article",
            mode="article",
            title="Example Article",
            content_hash="content-hash-1",
            source_id=self.source["id"],
            reporter_id=self.reporter["id"],
            seen_at=(
                "2026-08-12T09:30:00+00:00"
            ),
        )

        conn = main.db_conn()

        try:
            conn.execute(
                """
                INSERT INTO intelligence_stories (
                  id,
                  canonical_key,
                  canonical_title,
                  status,
                  first_seen_at,
                  last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "story-1",
                    "story-key-1",
                    "Example Story",
                    "developing",
                    "2026-08-12T09:00:00+00:00",
                    "2026-08-12T09:00:00+00:00",
                ),
            )

            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_identical_link_is_idempotent(
        self,
    ):
        first = main.record_evidence_link(
            evidence_id=self.evidence["id"],
            source_id=self.source["id"],
            relationship_type="published_by",
            confidence=0.70,
            linked_at=(
                "2026-08-12T10:01:00+00:00"
            ),
            metadata={
                "capture": "first",
            },
        )

        second = main.record_evidence_link(
            evidence_id=self.evidence["id"],
            source_id=self.source["id"],
            relationship_type="PUBLISHED_BY",
            confidence=0.95,
            linked_at=(
                "2026-08-12T10:05:00+00:00"
            ),
            metadata={
                "capture": "retry",
            },
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["link"]["id"],
            second["link"]["id"],
        )

        self.assertEqual(
            second["link"]["confidence"],
            0.70,
        )

        self.assertEqual(
            second["link"]["linked_at"],
            "2026-08-12T10:01:00+00:00",
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM evidence_links
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_each_target_type_is_supported(
        self,
    ):
        cases = [
            {
                "media_item_id": (
                    self.media["id"]
                ),
            },
            {
                "story_id": "story-1",
            },
            {
                "source_id": (
                    self.source["id"]
                ),
            },
            {
                "reporter_id": (
                    self.reporter["id"]
                ),
            },
        ]

        ids = []

        for target in cases:
            result = main.record_evidence_link(
                evidence_id=self.evidence["id"],
                relationship_type="supports",
                **target,
            )

            self.assertTrue(
                result["created"]
            )

            ids.append(
                result["link"]["id"]
            )

        self.assertEqual(
            len(
                set(ids)
            ),
            4,
        )

    def test_exactly_one_target_is_required(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.record_evidence_link(
                evidence_id=self.evidence["id"],
            )

        with self.assertRaises(
            ValueError
        ):
            main.record_evidence_link(
                evidence_id=self.evidence["id"],
                source_id=self.source["id"],
                reporter_id=self.reporter["id"],
            )

    def test_invalid_confidence_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.record_evidence_link(
                evidence_id=self.evidence["id"],
                source_id=self.source["id"],
                confidence=1.5,
            )

    def test_relationship_type_changes_identity(
        self,
    ):
        first = main.record_evidence_link(
            evidence_id=self.evidence["id"],
            source_id=self.source["id"],
            relationship_type="supports",
        )

        second = main.record_evidence_link(
            evidence_id=self.evidence["id"],
            source_id=self.source["id"],
            relationship_type="contradicts",
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["link"]["id"],
            second["link"]["id"],
        )

    def test_foreign_keys_are_enforced(
        self,
    ):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.record_evidence_link(
                evidence_id="missing-evidence",
                source_id=self.source["id"],
            )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.record_evidence_link(
                evidence_id=self.evidence["id"],
                source_id="missing-source",
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )