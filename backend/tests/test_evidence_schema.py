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


class EvidenceSchemaTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-schema-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_evidence_tables_exist(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                    'evidence_records',
                    'evidence_links'
                  )
                """
            ).fetchall()
        finally:
            conn.close()

        names = {
            str(row["name"])
            for row in rows
        }

        self.assertEqual(
            names,
            {
                "evidence_records",
                "evidence_links",
            },
        )

    def test_evidence_record_columns(
        self,
    ):
        expected = {
            "id",
            "evidence_key",
            "evidence_type",
            "subject_key",
            "claim_summary",
            "canonical_url",
            "reference_key",
            "verification_status",
            "published_at",
            "observed_at",
            "recorded_at",
            "metadata_json",
        }

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA table_info(
                  evidence_records
                )
                """
            ).fetchall()

            actual = {
                str(row["name"])
                for row in rows
            }
        finally:
            conn.close()

        self.assertEqual(
            actual,
            expected,
        )

    def test_evidence_link_columns(
        self,
    ):
        expected = {
            "id",
            "evidence_id",
            "media_item_id",
            "story_id",
            "source_id",
            "reporter_id",
            "relationship_type",
            "confidence",
            "linked_at",
            "metadata_json",
        }

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA table_info(
                  evidence_links
                )
                """
            ).fetchall()

            actual = {
                str(row["name"])
                for row in rows
            }
        finally:
            conn.close()

        self.assertEqual(
            actual,
            expected,
        )

    def test_evidence_link_foreign_keys(
        self,
    ):
        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                PRAGMA foreign_key_list(
                  evidence_links
                )
                """
            ).fetchall()

            relationships = {
                (
                    str(row["from"]),
                    str(row["table"]),
                    str(row["to"]),
                )
                for row in rows
            }
        finally:
            conn.close()

        expected = {
            (
                "evidence_id",
                "evidence_records",
                "id",
            ),
            (
                "media_item_id",
                "media_items",
                "id",
            ),
            (
                "story_id",
                "intelligence_stories",
                "id",
            ),
            (
                "source_id",
                "intelligence_sources",
                "id",
            ),
            (
                "reporter_id",
                "intelligence_reporters",
                "id",
            ),
        }

        self.assertTrue(
            expected.issubset(
                relationships
            )
        )

    def test_evidence_link_constraints(
        self,
    ):
        source = (
            main.upsert_intelligence_source(
                url="https://example.com/",
                display_name="Example Sports",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

        reporter = (
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

        conn = main.db_conn()

        try:
            conn.execute(
                """
                INSERT INTO evidence_records (
                  id,
                  evidence_key,
                  evidence_type,
                  subject_key,
                  observed_at,
                  recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "evidence-1",
                    "test|evidence-1",
                    "independent_report",
                    "test-subject",
                    "2026-08-12T10:00:00+00:00",
                    "2026-08-12T10:01:00+00:00",
                ),
            )

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO evidence_links (
                      id,
                      evidence_id,
                      relationship_type,
                      linked_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        "zero-target",
                        "evidence-1",
                        "supports",
                        "2026-08-12T10:02:00+00:00",
                    ),
                )

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO evidence_links (
                      id,
                      evidence_id,
                      source_id,
                      reporter_id,
                      relationship_type,
                      linked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "two-targets",
                        "evidence-1",
                        source["id"],
                        reporter["id"],
                        "published_by",
                        "2026-08-12T10:02:00+00:00",
                    ),
                )

            with self.assertRaises(
                sqlite3.IntegrityError
            ):
                conn.execute(
                    """
                    INSERT INTO evidence_links (
                      id,
                      evidence_id,
                      source_id,
                      relationship_type,
                      confidence,
                      linked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "invalid-confidence",
                        "evidence-1",
                        source["id"],
                        "published_by",
                        1.5,
                        "2026-08-12T10:02:00+00:00",
                    ),
                )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )