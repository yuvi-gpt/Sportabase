import json
import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import main


class ClaimLinkPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_db_path = main.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()

        main.DB_PATH = (
            Path(self.temp_dir.name)
            / "claim-link-persistence.db"
        )

        main.init_db()

        source = main.upsert_intelligence_source(
            url="https://source.example/",
            display_name="Source",
            seen_at="2026-08-13T10:00:00+00:00",
        )

        reporter = main.upsert_intelligence_reporter(
            identity_key="reporter-a",
            display_name="Reporter A",
            seen_at="2026-08-13T10:00:00+00:00",
        )

        self.claim = main.upsert_intelligence_claim(
            canonical_key="transfer|a|b|agreement",
            subject_key="transfer|a|b",
            canonical_text="Agreement reached.",
            seen_at="2026-08-13T10:00:00+00:00",
        )

        self.source_observation = (
            main.record_source_observation(
                source_id=source["id"],
                subject_key="transfer|a|b",
                observation_type="report",
                status="unresolved",
                observed_at="2026-08-13T10:01:00+00:00",
            )["observation"]
        )

        self.reporter_observation = (
            main.record_reporter_observation(
                reporter_id=reporter["id"],
                source_id=source["id"],
                subject_key="transfer|a|b",
                observation_type="report",
                status="unresolved",
                observed_at="2026-08-13T10:02:00+00:00",
            )["observation"]
        )

        self.evidence = main.record_evidence(
            evidence_type="quote",
            subject_key="transfer|a|b",
            observed_at="2026-08-13T10:03:00+00:00",
            reference_key="quote-1",
        )["evidence"]

    def tearDown(self):
        main.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def base_args(self):
        return {
            "claim_id": self.claim["id"],
            "relationship_type": "aligned_to",
            "observed_at": "2026-08-13T10:04:00+00:00",
            "confidence": 0.9,
            "source_observation_id": (
                self.source_observation["id"]
            ),
        }

    def test_id_is_deterministic_and_normalized(self):
        first = main.claim_link_id_for_record(
            **self.base_args()
        )

        args = self.base_args()
        args["relationship_type"] = "  ALIGNED_TO  "

        second = main.claim_link_id_for_record(
            **args
        )

        self.assertEqual(first, second)

    def test_each_target_type_is_supported(self):
        targets = (
            {
                "source_observation_id":
                    self.source_observation["id"],
            },
            {
                "reporter_observation_id":
                    self.reporter_observation["id"],
            },
            {
                "evidence_id":
                    self.evidence["id"],
            },
        )

        for index, target in enumerate(targets):
            with self.subTest(target=target):
                result = main.record_claim_link(
                    claim_id=self.claim["id"],
                    relationship_type="aligned_to",
                    observed_at=(
                        f"2026-08-13T10:0{index + 4}:00+00:00"
                    ),
                    confidence=0.9,
                    **target,
                )

                self.assertTrue(result["created"])

    def test_exact_replay_is_idempotent(self):
        first = main.record_claim_link(
            **self.base_args()
        )

        second = main.record_claim_link(
            **self.base_args()
        )

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])

        self.assertEqual(
            first["link"]["id"],
            second["link"]["id"],
        )

        conn = main.db_conn()

        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM claim_links"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 1)

    def test_semantic_changes_append(self):
        first = main.record_claim_link(
            **self.base_args()
        )

        changed_confidence = self.base_args()
        changed_confidence["confidence"] = 0.8

        second = main.record_claim_link(
            **changed_confidence
        )

        changed_time = self.base_args()
        changed_time["observed_at"] = (
            "2026-08-13T10:05:00+00:00"
        )

        third = main.record_claim_link(
            **changed_time
        )

        self.assertNotEqual(
            first["link"]["id"],
            second["link"]["id"],
        )

        self.assertNotEqual(
            first["link"]["id"],
            third["link"]["id"],
        )

    def test_operational_fields_do_not_change_identity(self):
        args = self.base_args()

        first = main.record_claim_link(
            **args,
            metadata={"ingest": 1},
            recorded_at="2026-08-13T11:00:00+00:00",
        )

        second = main.record_claim_link(
            **args,
            metadata={"ingest": 2},
            recorded_at="2026-08-13T12:00:00+00:00",
        )

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])

        self.assertEqual(
            json.loads(
                second["link"]["metadata_json"]
            ),
            {"ingest": 1},
        )

        self.assertEqual(
            second["link"]["recorded_at"],
            "2026-08-13T11:00:00+00:00",
        )

    def test_invalid_target_shapes_and_confidence_rejected(self):
        with self.assertRaises(ValueError):
            main.record_claim_link(
                claim_id=self.claim["id"],
                relationship_type="aligned_to",
                observed_at="2026-08-13T10:04:00+00:00",
            )

        with self.assertRaises(ValueError):
            main.record_claim_link(
                claim_id=self.claim["id"],
                relationship_type="aligned_to",
                observed_at="2026-08-13T10:04:00+00:00",
                source_observation_id=(
                    self.source_observation["id"]
                ),
                evidence_id=self.evidence["id"],
            )

        with self.assertRaises(ValueError):
            main.record_claim_link(
                claim_id=self.claim["id"],
                relationship_type="aligned_to",
                observed_at="2026-08-13T10:04:00+00:00",
                confidence=1.01,
                source_observation_id=(
                    self.source_observation["id"]
                ),
            )

    def test_foreign_keys_are_enforced(self):
        with self.assertRaises(
            sqlite3.IntegrityError
        ):
            main.record_claim_link(
                claim_id="missing-claim",
                relationship_type="aligned_to",
                observed_at="2026-08-13T10:04:00+00:00",
                source_observation_id=(
                    self.source_observation["id"]
                ),
            )


if __name__ == "__main__":
    unittest.main()
