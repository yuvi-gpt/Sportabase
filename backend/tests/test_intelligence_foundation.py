from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.schema import SCHEMA
from app.intelligence.entity_resolution_runtime import (
    ENTITY_MENTION_RESOLUTION_VERSION,
    resolve_entity_mentions,
)
from app.intelligence.source_health import (
    SOURCE_EVIDENCE_HEALTH_VERSION,
    build_source_evidence_health,
)
from app.routes import intelligence_admin


NOW = datetime(2026, 8, 22, 0, 0, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()
OLD_ISO = "2025-01-01T00:00:00+00:00"


class IntelligenceFoundationTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self._temp.name) / "sportabase-test.db"
        conn = self.connection_factory()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self._temp.cleanup()

    def connection_factory(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def insert_entity(
        self,
        *,
        entity_id: str,
        entity_key: str,
        entity_type: str,
        sport_key: str,
        canonical_name: str,
        aliases: list[tuple[str, str, str]],
    ):
        conn = self.connection_factory()
        try:
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id,
                  entity_key,
                  entity_type,
                  sport_key,
                  canonical_name,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    entity_id,
                    entity_key,
                    entity_type,
                    sport_key,
                    canonical_name,
                    NOW_ISO,
                    NOW_ISO,
                ),
            )

            for index, (alias_text, normalized_alias, alias_type) in enumerate(
                aliases,
                start=1,
            ):
                conn.execute(
                    """
                    INSERT INTO entity_aliases (
                      id,
                      entity_id,
                      alias_text,
                      normalized_alias,
                      alias_type,
                      first_seen_at,
                      last_seen_at,
                      metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                    """,
                    (
                        f"alias-{entity_id}-{index}",
                        entity_id,
                        alias_text,
                        normalized_alias,
                        alias_type,
                        NOW_ISO,
                        NOW_ISO,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

    def insert_source_fixture(self):
        conn = self.connection_factory()
        try:
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
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id, source_key, display_name, source_type,
                  canonical_domain, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "source-2",
                    "publisher|old.example",
                    "Old Example",
                    "publisher",
                    "old.example",
                    OLD_ISO,
                    OLD_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO media_items (
                  id, canonical_url, mode, source_id, title,
                  latest_content_hash, first_seen_at, last_seen_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "media-1",
                    "https://example.com/story",
                    "article",
                    "source-1",
                    "Arsenal update",
                    "hash-1",
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, media_item_id, subject_key,
                  observation_type, status, claim_summary,
                  provenance_url, observed_at, recorded_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "obs-1",
                    "source-1",
                    "media-1",
                    "subject-1",
                    "article_headline_report",
                    "reported",
                    "Arsenal update",
                    "https://example.com/story",
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO evidence_records (
                  id, evidence_key, evidence_type, subject_key,
                  claim_summary, canonical_url, reference_key,
                  verification_status, observed_at, recorded_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "evidence-1",
                    "evidence-key-1",
                    "official_statement",
                    "subject-1",
                    "Verified identity evidence",
                    "https://example.com/about",
                    "ref-1",
                    "verified",
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO evidence_links (
                  id, evidence_id, media_item_id,
                  relationship_type, confidence, linked_at,
                  metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    "evidence-link-1",
                    "evidence-1",
                    "media-1",
                    "supports",
                    0.99,
                    NOW_ISO,
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
                    "entity-1",
                    "club|arsenal",
                    "club",
                    "football",
                    "Arsenal",
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.execute(
                """
                INSERT INTO verified_source_entity_bindings (
                  id, source_id, entity_id, binding_type,
                  evidence_id, verification_status, confidence,
                  observed_at, recorded_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, 'verified', ?, ?, ?, '{}')
                """,
                (
                    "binding-1",
                    "source-1",
                    "entity-1",
                    "official_site",
                    "evidence-1",
                    0.99,
                    NOW_ISO,
                    NOW_ISO,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_unique_exact_aliases_resolve_without_fuzzy_guessing(self):
        self.insert_entity(
            entity_id="arsenal",
            entity_key="club|arsenal",
            entity_type="club",
            sport_key="football",
            canonical_name="Arsenal",
            aliases=[
                ("Arsenal", "arsenal", "canonical_name"),
                ("The Gunners", "the gunners", "common_name"),
            ],
        )

        result = resolve_entity_mentions(
            text="The Gunners face Arsenal tomorrow",
            connection_factory=self.connection_factory,
            sport_key="football",
        )

        self.assertEqual(result["version"], ENTITY_MENTION_RESOLUTION_VERSION)
        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["counts"]["resolved"], 1)
        self.assertEqual(result["resolved"][0]["entity_id"], "arsenal")
        self.assertTrue(result["policy"]["no_fuzzy_guessing"])
        self.assertFalse(result["policy"]["establishes_identity"])

    def test_ambiguous_alias_fails_closed(self):
        self.insert_entity(
            entity_id="united-a",
            entity_key="club|united-a",
            entity_type="club",
            sport_key="football",
            canonical_name="United A",
            aliases=[("United", "united", "short_name")],
        )
        self.insert_entity(
            entity_id="united-b",
            entity_key="club|united-b",
            entity_type="club",
            sport_key="football",
            canonical_name="United B",
            aliases=[("United", "united", "short_name")],
        )

        result = resolve_entity_mentions(
            text="United announce a signing",
            connection_factory=self.connection_factory,
            sport_key="football",
        )

        self.assertEqual(result["status"], "ambiguous")
        self.assertEqual(result["resolved"], [])
        self.assertEqual(result["ambiguous"][0]["candidate_count"], 2)

    def test_longest_alias_prevents_nested_false_ambiguity(self):
        self.insert_entity(
            entity_id="man-utd",
            entity_key="club|manchester-united",
            entity_type="club",
            sport_key="football",
            canonical_name="Manchester United",
            aliases=[
                ("Manchester United", "manchester united", "canonical_name"),
            ],
        )
        self.insert_entity(
            entity_id="other-united",
            entity_key="club|other-united",
            entity_type="club",
            sport_key="football",
            canonical_name="Other United",
            aliases=[("United", "united", "short_name")],
        )

        result = resolve_entity_mentions(
            text="Manchester United complete transfer",
            connection_factory=self.connection_factory,
        )

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved"][0]["entity_id"], "man-utd")
        self.assertEqual(result["ambiguous"], [])

    def test_sport_scope_disambiguates_same_alias(self):
        self.insert_entity(
            entity_id="football-city",
            entity_key="club|football-city",
            entity_type="club",
            sport_key="football",
            canonical_name="Football City",
            aliases=[("City", "city", "short_name")],
        )
        self.insert_entity(
            entity_id="basketball-city",
            entity_key="team|basketball-city",
            entity_type="team",
            sport_key="basketball",
            canonical_name="Basketball City",
            aliases=[("City", "city", "short_name")],
        )

        result = resolve_entity_mentions(
            text="City confirm squad news",
            connection_factory=self.connection_factory,
            sport_key="football",
        )

        self.assertEqual(result["status"], "resolved")
        self.assertEqual(result["resolved"][0]["entity_id"], "football-city")

    def test_source_health_reports_real_coverage_without_truth_claim(self):
        self.insert_source_fixture()

        result = build_source_evidence_health(
            connection_factory=self.connection_factory,
            days=30,
            now_provider=lambda: NOW,
        )

        self.assertEqual(result["version"], SOURCE_EVIDENCE_HEALTH_VERSION)
        self.assertEqual(result["aggregate"]["sources"], 2)
        self.assertEqual(result["aggregate"]["sources_with_observations"], 1)
        self.assertEqual(result["aggregate"]["sources_with_evidence"], 1)
        self.assertEqual(
            result["aggregate"]["sources_with_verified_entity_bindings"],
            1,
        )
        self.assertEqual(result["evidence_by_verification_status"]["verified"], 1)
        self.assertEqual(result["entities"]["canonical_entities"], 1)

        source_one = next(
            row for row in result["sources"] if row["source_id"] == "source-1"
        )
        source_two = next(
            row for row in result["sources"] if row["source_id"] == "source-2"
        )

        self.assertEqual(
            source_one["coverage_state"],
            "verified_identity_binding_observed",
        )
        self.assertEqual(source_two["coverage_state"], "unobserved")
        self.assertTrue(result["policy"]["coverage_is_observability_not_truth"])
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_admin_routes_are_protected_and_use_real_intelligence_store(self):
        self.insert_entity(
            entity_id="arsenal",
            entity_key="club|arsenal",
            entity_type="club",
            sport_key="football",
            canonical_name="Arsenal",
            aliases=[("Arsenal", "arsenal", "canonical_name")],
        )

        calls = []

        def require_admin(request):
            calls.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.connection_factory,
            )
        )
        client = TestClient(app)

        resolve_response = client.get(
            "/admin/intelligence/entities/resolve",
            params={
                "text": "Arsenal transfer update",
                "sport_key": "football",
            },
        )
        health_response = client.get(
            "/admin/intelligence/health",
            params={"days": 30},
        )

        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.json()["status"], "resolved")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "ok")
        self.assertEqual(
            calls,
            [
                "/admin/intelligence/entities/resolve",
                "/admin/intelligence/health",
            ],
        )

    def test_entity_resolution_does_not_write_database_state(self):
        self.insert_entity(
            entity_id="arsenal",
            entity_key="club|arsenal",
            entity_type="club",
            sport_key="football",
            canonical_name="Arsenal",
            aliases=[("Arsenal", "arsenal", "canonical_name")],
        )

        conn = self.connection_factory()
        try:
            before = conn.total_changes
        finally:
            conn.close()

        resolve_entity_mentions(
            text="Arsenal",
            connection_factory=self.connection_factory,
        )

        conn = self.connection_factory()
        try:
            counts = {
                "entities": conn.execute(
                    "SELECT COUNT(*) FROM canonical_entities"
                ).fetchone()[0],
                "aliases": conn.execute(
                    "SELECT COUNT(*) FROM entity_aliases"
                ).fetchone()[0],
                "participants": conn.execute(
                    "SELECT COUNT(*) FROM verified_claim_entity_participants"
                ).fetchone()[0],
            }
        finally:
            conn.close()

        self.assertEqual(before, 0)
        self.assertEqual(
            counts,
            {
                "entities": 1,
                "aliases": 1,
                "participants": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
