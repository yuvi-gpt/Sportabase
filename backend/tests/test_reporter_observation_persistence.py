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


class ReporterObservationPersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "reporter-observation-test.db"
        )

        main.init_db()

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

        self.source = (
            main.upsert_intelligence_source(
                url="https://example.com/",
                display_name="Example Sports",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

        self.other_source = (
            main.upsert_intelligence_source(
                url="https://other.example/",
                display_name="Other Sports",
                seen_at=(
                    "2026-08-12T09:00:00+00:00"
                ),
            )
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_identical_observation_is_idempotent(
        self,
    ):
        first = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="unresolved",
                claim_summary=(
                    "Player A may join Club B."
                ),
                provenance_url=(
                    "https://example.com/story"
                    "?utm_source=first"
                ),
                confidence=0.70,
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
                recorded_at=(
                    "2026-08-12T10:01:00+00:00"
                ),
            )
        )

        second = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="REPORT",
                status="UNRESOLVED",
                claim_summary=(
                    "Different descriptive wording."
                ),
                provenance_url=(
                    "https://example.com/story"
                    "?utm_source=second"
                ),
                confidence=0.7,
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
                recorded_at=(
                    "2026-08-12T10:05:00+00:00"
                ),
                metadata={
                    "retry": True,
                },
            )
        )

        self.assertTrue(
            first["created"]
        )

        self.assertFalse(
            second["created"]
        )

        self.assertEqual(
            first["observation"]["id"],
            second["observation"]["id"],
        )

        self.assertEqual(
            second["observation"][
                "recorded_at"
            ],
            "2026-08-12T10:01:00+00:00",
        )

        self.assertEqual(
            second["observation"][
                "claim_summary"
            ],
            "Player A may join Club B.",
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM reporter_observations
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_status_progression_is_append_only(
        self,
    ):
        first = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        second = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key=(
                    "transfer|player-a|club-b"
                ),
                observation_type="report",
                status="confirmed",
                observed_at=(
                    "2026-08-12T14:00:00+00:00"
                ),
            )
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["observation"]["id"],
            second["observation"]["id"],
        )

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                SELECT status
                FROM reporter_observations
                WHERE reporter_id = ?
                  AND subject_key = ?
                ORDER BY observed_at ASC
                """,
                (
                    self.reporter["id"],
                    "transfer|player-a|club-b",
                ),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(
            [
                str(row["status"])
                for row in rows
            ],
            [
                "unresolved",
                "confirmed",
            ],
        )

    def test_source_context_is_part_of_identity(
        self,
    ):
        first = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=self.source["id"],
                subject_key="same-claim",
                observation_type="report",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        second = (
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id=(
                    self.other_source["id"]
                ),
                subject_key="same-claim",
                observation_type="report",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["observation"]["id"],
            second["observation"]["id"],
        )

    def test_invalid_confidence_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                subject_key="test-subject",
                observation_type="report",
                confidence=1.5,
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )

    def test_unknown_reporter_is_rejected(
        self,
    ):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.record_reporter_observation(
                reporter_id="missing-reporter",
                subject_key="test-subject",
                observation_type="report",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )

    def test_unknown_source_is_rejected(
        self,
    ):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.record_reporter_observation(
                reporter_id=self.reporter["id"],
                source_id="missing-source",
                subject_key="test-subject",
                observation_type="report",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )