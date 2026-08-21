from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.db.schema import SCHEMA
from app.intelligence import observations


NOW = "2026-08-22T00:00:00+00:00"


class EntityObservationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._temp.name) / "sportabase-test.db"
        conn = self.connection_factory()
        try:
            conn.executescript(SCHEMA)
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type,
                  canonical_domain, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "source-1",
                    "publisher|example.com",
                    "Example",
                    "publisher",
                    "example.com",
                    NOW,
                    NOW,
                ),
            )
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id, entity_key, entity_type, sport_key,
                  canonical_name, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "arsenal",
                    "club|arsenal",
                    "club",
                    "football",
                    "Arsenal",
                    NOW,
                    NOW,
                ),
            )
            conn.execute(
                """
                INSERT INTO entity_aliases (
                  id, entity_id, alias_text, normalized_alias,
                  alias_type, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "alias-arsenal",
                    "arsenal",
                    "Arsenal",
                    "arsenal",
                    "canonical_name",
                    NOW,
                    NOW,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self._temp.cleanup()

    def connection_factory(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def normalize_url(value):
        return str(value or "").strip()

    def test_article_headline_observation_carries_candidate_resolution(self):
        result = observations.record_source_observation(
            source_id="source-1",
            subject_key="subject-1",
            observation_type="article_headline_report",
            observed_at=NOW,
            status="reported",
            claim_summary="Arsenal confirm a transfer update",
            provenance_url="https://example.com/story",
            metadata={
                "truth_established": False,
            },
            normalize_url=self.normalize_url,
            connection_factory=self.connection_factory,
        )

        metadata = json.loads(
            result["observation"]["metadata_json"]
        )
        resolution = metadata["entity_resolution"]

        self.assertEqual(resolution["status"], "resolved")
        self.assertEqual(
            resolution["resolved"][0]["entity_id"],
            "arsenal",
        )
        self.assertEqual(
            resolution["integration_version"],
            observations.ENTITY_OBSERVATION_INTEGRATION_VERSION,
        )
        self.assertFalse(resolution["policy"]["establishes_identity"])
        self.assertFalse(resolution["policy"]["affects_live_merit"])
        self.assertFalse(metadata["truth_established"])

        conn = self.connection_factory()
        try:
            verified_participants = conn.execute(
                "SELECT COUNT(*) FROM verified_claim_entity_participants"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(verified_participants, 0)

    def test_non_headline_observation_keeps_existing_metadata_only(self):
        result = observations.record_source_observation(
            source_id="source-1",
            subject_key="subject-2",
            observation_type="manual_note",
            observed_at=NOW,
            status="reported",
            claim_summary="Arsenal manual note",
            metadata={"existing": True},
            normalize_url=self.normalize_url,
            connection_factory=self.connection_factory,
        )

        metadata = json.loads(
            result["observation"]["metadata_json"]
        )
        self.assertEqual(metadata, {"existing": True})

    def test_resolution_failure_is_fail_open_for_observation_persistence(self):
        result = observations.record_source_observation(
            source_id="source-1",
            subject_key="subject-3",
            observation_type="article_headline_report",
            observed_at=NOW,
            status="reported",
            claim_summary="Unknown Entity headline",
            metadata={"existing": "kept"},
            normalize_url=self.normalize_url,
            connection_factory=self.connection_factory,
        )

        metadata = json.loads(
            result["observation"]["metadata_json"]
        )
        self.assertEqual(metadata, {"existing": "kept"})
        self.assertEqual(result["observation"]["status"], "reported")


if __name__ == "__main__":
    unittest.main()
