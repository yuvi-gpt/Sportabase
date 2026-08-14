import json
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


class ObservationIndependenceAssertionTests(
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
            / "observation-independence.db"
        )

        main.init_db()

        self.source_a = (
            main.upsert_intelligence_source(
                url="https://a.example/",
                display_name="Source A",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.source_b = (
            main.upsert_intelligence_source(
                url="https://b.example/",
                display_name="Source B",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.reporter_a = (
            main.upsert_intelligence_reporter(
                identity_key="reporter-a",
                display_name="Reporter A",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.reporter_b = (
            main.upsert_intelligence_reporter(
                identity_key="reporter-b",
                display_name="Reporter B",
                seen_at=(
                    "2026-08-13T10:00:00+00:00"
                ),
            )
        )

        self.source_obs_a = (
            main.record_source_observation(
                source_id=self.source_a["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T11:00:00+00:00"
                ),
            )["observation"]
        )

        self.source_obs_b = (
            main.record_source_observation(
                source_id=self.source_b["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T11:01:00+00:00"
                ),
            )["observation"]
        )

        self.reporter_obs_a = (
            main.record_reporter_observation(
                reporter_id=(
                    self.reporter_a["id"]
                ),
                source_id=self.source_a["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T11:02:00+00:00"
                ),
            )["observation"]
        )

        self.reporter_obs_b = (
            main.record_reporter_observation(
                reporter_id=(
                    self.reporter_b["id"]
                ),
                source_id=self.source_b["id"],
                subject_key="case-1",
                observation_type="report",
                status="unresolved",
                observed_at=(
                    "2026-08-13T11:03:00+00:00"
                ),
            )["observation"]
        )

        self.evidence_a = (
            main.record_evidence(
                evidence_type="primary_document",
                subject_key="case-1",
                reference_key=(
                    "independence-proof-a"
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-13T11:10:00+00:00"
                ),
            )["evidence"]
        )

        self.evidence_b = (
            main.record_evidence(
                evidence_type="quote",
                subject_key="case-1",
                reference_key=(
                    "independence-proof-b"
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-13T11:11:00+00:00"
                ),
            )["evidence"]
        )

    def tearDown(self):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    def record_default(
        self,
        **overrides,
    ):
        arguments = {
            "left_source_observation_id": (
                self.source_obs_a["id"]
            ),
            "right_source_observation_id": (
                self.source_obs_b["id"]
            ),
            "provenance_evidence_id": (
                self.evidence_a["id"]
            ),
            "verification_status": "verified",
            "confidence": 0.9,
            "observed_at": (
                "2026-08-13T11:20:00+00:00"
            ),
        }

        arguments.update(
            overrides
        )

        return (
            main.record_observation_independence_assertion(
                **arguments
            )
        )

    def test_schema_contract(
        self,
    ):
        conn = main.db_conn()

        try:
            columns = {
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA table_info(
                      observation_independence_assertions
                    )
                    """
                ).fetchall()
            }

            indexes = {
                str(row["name"])
                for row in conn.execute(
                    """
                    PRAGMA index_list(
                      observation_independence_assertions
                    )
                    """
                ).fetchall()
            }

            schema_sql = str(
                conn.execute(
                    """
                    SELECT sql
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name =
                        'observation_independence_assertions'
                    """
                ).fetchone()[0]
            )
        finally:
            conn.close()

        expected_columns = {
            "id",
            "observation_a_source_observation_id",
            "observation_a_reporter_observation_id",
            "observation_b_source_observation_id",
            "observation_b_reporter_observation_id",
            "provenance_evidence_id",
            "verification_status",
            "confidence",
            "observed_at",
            "recorded_at",
            "metadata_json",
        }

        self.assertEqual(
            columns,
            expected_columns,
        )

        self.assertIn(
            "idx_observation_independence_evidence",
            indexes,
        )

        self.assertIn(
            "idx_observation_independence_verification",
            indexes,
        )

        self.assertIn(
            "verification_status IN",
            schema_sql,
        )

    def test_identical_assertion_is_idempotent(
        self,
    ):
        first = self.record_default(
            recorded_at=(
                "2026-08-13T11:21:00+00:00"
            ),
            metadata={
                "capture": "first",
            },
        )

        second = self.record_default(
            recorded_at=(
                "2026-08-13T11:30:00+00:00"
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
            first["assertion"]["id"],
            second["assertion"]["id"],
        )

        self.assertEqual(
            second["assertion"][
                "recorded_at"
            ],
            "2026-08-13T11:21:00+00:00",
        )

        self.assertEqual(
            json.loads(
                second["assertion"][
                    "metadata_json"
                ]
            ),
            {
                "capture": "first",
            },
        )

    def test_endpoint_order_is_symmetric(
        self,
    ):
        forward = (
            main.observation_independence_assertion_id_for_record(
                left_source_observation_id=(
                    self.source_obs_a["id"]
                ),
                right_reporter_observation_id=(
                    self.reporter_obs_b["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="VERIFIED",
                confidence=0.9,
                observed_at=(
                    "2026-08-13T12:00:00+00:00"
                ),
            )
        )

        reverse = (
            main.observation_independence_assertion_id_for_record(
                left_reporter_observation_id=(
                    self.reporter_obs_b["id"]
                ),
                right_source_observation_id=(
                    self.source_obs_a["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="verified",
                confidence=0.9,
                observed_at=(
                    "2026-08-13T12:00:00+00:00"
                ),
            )
        )

        self.assertEqual(
            forward,
            reverse,
        )

    def test_verification_change_is_append_only(
        self,
    ):
        unverified = self.record_default(
            verification_status="UNVERIFIED"
        )

        verified = self.record_default(
            verification_status=" verified "
        )

        self.assertNotEqual(
            unverified["assertion"]["id"],
            verified["assertion"]["id"],
        )

        self.assertEqual(
            verified["assertion"][
                "verification_status"
            ],
            "verified",
        )

    def test_semantic_changes_create_history(
        self,
    ):
        baseline = self.record_default()

        confidence_change = (
            self.record_default(
                confidence=0.8
            )
        )

        time_change = self.record_default(
            observed_at=(
                "2026-08-13T11:21:00+00:00"
            )
        )

        evidence_change = (
            self.record_default(
                provenance_evidence_id=(
                    self.evidence_b["id"]
                )
            )
        )

        ids = {
            baseline["assertion"]["id"],
            confidence_change[
                "assertion"
            ]["id"],
            time_change[
                "assertion"
            ]["id"],
            evidence_change[
                "assertion"
            ]["id"],
        }

        self.assertEqual(
            len(ids),
            4,
        )

    def test_all_observation_pair_shapes_work(
        self,
    ):
        rows = [
            main.record_observation_independence_assertion(
                left_source_observation_id=(
                    self.source_obs_a["id"]
                ),
                right_source_observation_id=(
                    self.source_obs_b["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-13T12:10:00+00:00"
                ),
            ),
            main.record_observation_independence_assertion(
                left_source_observation_id=(
                    self.source_obs_a["id"]
                ),
                right_reporter_observation_id=(
                    self.reporter_obs_b["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-13T12:11:00+00:00"
                ),
            ),
            main.record_observation_independence_assertion(
                left_reporter_observation_id=(
                    self.reporter_obs_a["id"]
                ),
                right_reporter_observation_id=(
                    self.reporter_obs_b["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="verified",
                observed_at=(
                    "2026-08-13T12:12:00+00:00"
                ),
            ),
        ]

        self.assertTrue(
            all(
                row["created"]
                for row in rows
            )
        )

    def test_pair_cardinality_and_self_pair_are_validated(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                left_source_observation_id=None,
            )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                left_reporter_observation_id=(
                    self.reporter_obs_a["id"]
                ),
            )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                right_source_observation_id=(
                    self.source_obs_a["id"]
                ),
            )

    def test_semantic_field_validation(
        self,
    ):
        for confidence in (
            "bad",
            -0.01,
            1.01,
        ):
            with self.assertRaises(
                ValueError
            ):
                self.record_default(
                    confidence=confidence
                )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                verification_status="pending"
            )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                provenance_evidence_id=""
            )

        with self.assertRaises(
            ValueError
        ):
            self.record_default(
                observed_at=""
            )

    def test_foreign_key_errors_propagate(
        self,
    ):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.record_default(
                provenance_evidence_id=(
                    "missing-evidence"
                )
            )

        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            self.record_default(
                right_source_observation_id=(
                    "missing-observation"
                )
            )

    def test_normalization_is_deterministic(
        self,
    ):
        normalized = (
            main.observation_independence_assertion_id_for_record(
                left_source_observation_id=(
                    self.source_obs_a["id"]
                ),
                right_source_observation_id=(
                    self.source_obs_b["id"]
                ),
                provenance_evidence_id=(
                    self.evidence_a["id"]
                ),
                verification_status="verified",
                confidence=0.9,
                observed_at=(
                    "2026-08-13T13:00:00+00:00"
                ),
            )
        )

        padded = (
            main.observation_independence_assertion_id_for_record(
                left_source_observation_id=(
                    " "
                    + self.source_obs_a["id"]
                    + " "
                ),
                right_source_observation_id=(
                    " "
                    + self.source_obs_b["id"]
                    + " "
                ),
                provenance_evidence_id=(
                    " "
                    + self.evidence_a["id"]
                    + " "
                ),
                verification_status=(
                    " VERIFIED "
                ),
                confidence="0.9",
                observed_at=(
                    " 2026-08-13T13:00:00+00:00 "
                ),
            )
        )

        self.assertEqual(
            normalized,
            padded,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
