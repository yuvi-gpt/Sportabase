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


class EvidencePersistenceTests(
    unittest.TestCase
):
    def setUp(self):
        self.original_db_path = main.DB_PATH

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "evidence-persistence-test.db"
        )

        main.init_db()

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def test_identical_evidence_is_idempotent(
        self,
    ):
        first = main.record_evidence(
            evidence_type=(
                "independent_report"
            ),
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Player A may join Club B."
            ),
            canonical_url=(
                "https://example.com/story"
                "?utm_source=first"
            ),
            verification_status="unverified",
            observed_at=(
                "2026-08-12T10:00:00+00:00"
            ),
            recorded_at=(
                "2026-08-12T10:01:00+00:00"
            ),
            metadata={
                "capture": "first",
            },
        )

        second = main.record_evidence(
            evidence_type=(
                "INDEPENDENT_REPORT"
            ),
            subject_key=(
                "transfer|player-a|club-b"
            ),
            claim_summary=(
                "Different descriptive wording."
            ),
            canonical_url=(
                "https://example.com/story"
                "?utm_source=second"
            ),
            verification_status="UNVERIFIED",
            observed_at=(
                "2026-08-12T10:00:00+00:00"
            ),
            recorded_at=(
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
            first["evidence"]["id"],
            second["evidence"]["id"],
        )

        self.assertEqual(
            first["evidence"]["evidence_key"],
            second["evidence"]["evidence_key"],
        )

        self.assertEqual(
            second["evidence"]["claim_summary"],
            "Player A may join Club B.",
        )

        self.assertEqual(
            second["evidence"]["recorded_at"],
            "2026-08-12T10:01:00+00:00",
        )

        conn = main.db_conn()

        try:
            count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM evidence_records
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        self.assertEqual(
            count,
            1,
        )

    def test_verification_progression_is_append_only(
        self,
    ):
        first = main.record_evidence(
            evidence_type="official_statement",
            subject_key="same-subject",
            canonical_url=(
                "https://example.com/statement"
            ),
            verification_status="unverified",
            observed_at=(
                "2026-08-12T10:00:00+00:00"
            ),
        )

        second = main.record_evidence(
            evidence_type="official_statement",
            subject_key="same-subject",
            canonical_url=(
                "https://example.com/statement"
            ),
            verification_status="verified",
            observed_at=(
                "2026-08-12T12:00:00+00:00"
            ),
        )

        self.assertTrue(
            first["created"]
        )

        self.assertTrue(
            second["created"]
        )

        self.assertNotEqual(
            first["evidence"]["id"],
            second["evidence"]["id"],
        )

        conn = main.db_conn()

        try:
            rows = conn.execute(
                """
                SELECT verification_status
                FROM evidence_records
                WHERE subject_key = ?
                ORDER BY observed_at ASC
                """,
                (
                    "same-subject",
                ),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(
            [
                str(
                    row["verification_status"]
                )
                for row in rows
            ],
            [
                "unverified",
                "verified",
            ],
        )

    def test_reference_key_can_identify_evidence(
        self,
    ):
        result = main.record_evidence(
            evidence_type="primary_document",
            subject_key="disciplinary-case-1",
            reference_key=(
                "FA-DECISION-2026-001"
            ),
            verification_status="verified",
            observed_at=(
                "2026-08-12T10:00:00+00:00"
            ),
        )

        self.assertTrue(
            result["created"]
        )

        self.assertEqual(
            result["evidence"]["canonical_url"],
            "",
        )

        self.assertEqual(
            result["evidence"]["reference_key"],
            "FA-DECISION-2026-001",
        )

    def test_evidence_requires_locator(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            main.record_evidence(
                evidence_type="quote",
                subject_key="test-subject",
                observed_at=(
                    "2026-08-12T10:00:00+00:00"
                ),
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )