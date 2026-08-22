from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claim_entity_context import (
    build_claim_entity_context,
)
from app.intelligence.claim_story_context import (
    build_claim_intelligence_context,
    build_story_intelligence_context,
)
from app.intelligence import observations
from app.routes import intelligence_admin


NOW = "2026-08-22T05:30:00+00:00"


class ClaimStoryContextTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        conn = self.factory()
        try:
            conn.executescript(SCHEMA)
            self._seed(conn)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    def _seed(self, conn):
        entities = [
            ("entity-player", "player:one", "player", "football", "Player One"),
            ("entity-arsenal", "club:arsenal", "club", "football", "Arsenal"),
            ("entity-united-a", "club:united-a", "club", "football", "United A"),
            ("entity-united-b", "club:united-b", "club", "football", "United B"),
        ]
        for entity_id, entity_key, entity_type, sport_key, name in entities:
            conn.execute(
                """
                INSERT INTO canonical_entities (
                  id, entity_key, entity_type, sport_key, canonical_name,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (entity_id, entity_key, entity_type, sport_key, name, NOW, NOW),
            )

        aliases = [
            ("alias-player", "entity-player", "Player One", "player one", "canonical_name"),
            ("alias-arsenal", "entity-arsenal", "Arsenal", "arsenal", "canonical_name"),
            ("alias-united-a", "entity-united-a", "United", "united", "common_name"),
            ("alias-united-b", "entity-united-b", "United", "united", "common_name"),
        ]
        for alias_id, entity_id, alias_text, normalized_alias, alias_type in aliases:
            conn.execute(
                """
                INSERT INTO entity_aliases (
                  id, entity_id, alias_text, normalized_alias, alias_type,
                  first_seen_at, last_seen_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '{}')
                """,
                (
                    alias_id,
                    entity_id,
                    alias_text,
                    normalized_alias,
                    alias_type,
                    NOW,
                    NOW,
                ),
            )

        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id, source_key, display_name, source_type, canonical_domain,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, 'publisher', ?, ?, ?, '{}')
            """,
            ("source-1", "source:example", "Example Sports", "example.com", NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO media_items (
              id, canonical_url, mode, source_id, title, latest_content_hash,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, 'article', ?, ?, ?, ?, ?, '{}')
            """,
            (
                "media-1",
                "https://example.com/story",
                "source-1",
                "Player One agrees move to Arsenal",
                "hash-1",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, ?, 'assertion', ?, ?, '{}')
            """,
            (
                "claim-1",
                "claim:player-one-to-arsenal",
                "player:one",
                "Player One agrees move to Arsenal",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id, canonical_key, canonical_title, status,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (?, ?, ?, 'developing', ?, ?, '{}')
            """,
            (
                "story-1",
                "story:player-one-to-arsenal",
                "Player One to Arsenal",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO story_claim_links (
              story_id, claim_id, relationship_type, link_basis,
              linked_at, metadata_json
            ) VALUES (?, ?, 'exact_claim_group', 'downstream_exact_common_claim_id', ?, '{}')
            """,
            ("story-1", "claim-1", NOW),
        )
        conn.execute(
            """
            INSERT INTO story_media_links (
              story_id, media_item_id, relationship_type, confidence, linked_at
            ) VALUES (?, ?, 'exact_claim_member', 1.0, ?)
            """,
            ("story-1", "media-1", NOW),
        )
        conn.execute(
            """
            INSERT INTO evidence_records (
              id, evidence_key, evidence_type, subject_key, claim_summary,
              verification_status, observed_at, recorded_at, metadata_json
            ) VALUES (?, ?, 'official_statement', ?, ?, 'verified', ?, ?, '{}')
            """,
            (
                "evidence-1",
                "evidence:official-player-one",
                "player:one",
                "Official identity evidence",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO verified_claim_entity_participants (
              id, claim_id, entity_id, participant_role, evidence_id,
              verification_status, confidence, observed_at, recorded_at,
              metadata_json
            ) VALUES (?, ?, ?, 'subject', ?, 'verified', 0.99, ?, ?, '{}')
            """,
            (
                "participant-1",
                "claim-1",
                "entity-player",
                "evidence-1",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, evidence_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (?, ?, ?, 'supports', ?, ?, '{}')
            """,
            ("claim-link-evidence", "claim-1", "evidence-1", NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO evidence_links (
              id, evidence_id, story_id, relationship_type,
              linked_at, metadata_json
            ) VALUES (?, ?, ?, 'supports', ?, '{}')
            """,
            ("story-evidence-link", "evidence-1", "story-1", NOW),
        )

        conn.commit()

        observation = observations.record_source_observation(
            source_id="source-1",
            subject_key="player:one",
            observation_type="article_headline_report",
            observed_at=NOW,
            claim_summary="Player One agrees move to Arsenal",
            connection_factory=self.factory,
        )["observation"]

        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, source_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (?, ?, ?, 'reports', ?, ?, '{}')
            """,
            (
                "claim-link-observation",
                "claim-1",
                observation["id"],
                NOW,
                NOW,
            ),
        )

    def test_claim_entity_context_builds_deterministic_allowlist(self):
        result = build_claim_entity_context(
            claim_text="Player One agrees move to Arsenal",
            subject_key="player:one",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            set(result["allowed_entities"]),
            {"player:one", "club:arsenal"},
        )
        self.assertEqual(result["counts"]["ambiguous_mentions"], 0)
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_claim_entity_context_excludes_ambiguous_aliases(self):
        result = build_claim_entity_context(
            claim_text="Player One linked with United",
            subject_key="player:one",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "partial_ambiguity")
        self.assertEqual(set(result["allowed_entities"]), {"player:one"})
        self.assertEqual(result["counts"]["ambiguous_mentions"], 1)

    def test_headline_observation_persists_claim_entity_context(self):
        conn = self.factory()
        try:
            row = conn.execute(
                """
                SELECT metadata_json
                FROM source_observations
                WHERE source_id = 'source-1'
                ORDER BY recorded_at DESC
                LIMIT 1
                """
            ).fetchone()
        finally:
            conn.close()

        metadata = json.loads(row["metadata_json"])
        self.assertEqual(metadata["entity_resolution"]["status"], "resolved")
        self.assertEqual(metadata["claim_entity_context"]["status"], "ready")
        self.assertIn(
            "club:arsenal",
            metadata["claim_entity_context"]["allowed_entities"],
        )

    def test_claim_context_collects_evidence_sources_and_verified_entities(self):
        result = build_claim_intelligence_context(
            claim_id="claim-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["verified_participants"], 1)
        self.assertEqual(result["counts"]["evidence_records"], 1)
        self.assertEqual(result["counts"]["source_observations"], 1)
        self.assertEqual(result["counts"]["distinct_observed_sources"], 1)
        self.assertEqual(result["counts"]["stories"], 1)
        self.assertEqual(
            result["source_observations"][0]["candidate_context"]
            ["claim_entity_context"]["status"],
            "ready",
        )
        self.assertTrue(
            result["policy"]["verified_evidence_status_is_not_claim_truth"]
        )

    def test_story_context_rolls_claim_media_and_evidence_without_truth_inference(self):
        result = build_story_intelligence_context(
            story_id="story-1",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["claims"], 1)
        self.assertEqual(result["counts"]["media_items"], 1)
        self.assertEqual(result["counts"]["distinct_media_sources"], 1)
        self.assertEqual(result["counts"]["direct_story_evidence"], 1)
        self.assertEqual(result["counts"]["claim_evidence_records"], 1)
        self.assertEqual(result["counts"]["verified_claim_participants"], 1)
        self.assertFalse(result["policy"]["establishes_truth"])
        self.assertFalse(result["policy"]["establishes_independence"])

    def test_context_builders_return_explicit_not_found(self):
        claim = build_claim_intelligence_context(
            claim_id="missing",
            connection_factory=self.factory,
        )
        story = build_story_intelligence_context(
            story_id="missing",
            connection_factory=self.factory,
        )

        self.assertEqual(claim["status"], "not_found")
        self.assertEqual(story["status"], "not_found")

    def test_admin_context_routes_are_guarded_and_expose_read_models(self):
        guarded = []

        def require_admin(request):
            guarded.append(request.url.path)

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=require_admin,
                connection_factory=self.factory,
            )
        )
        client = TestClient(app)

        claim_response = client.get(
            "/admin/intelligence/claims/claim-1/context"
        )
        story_response = client.get(
            "/admin/intelligence/stories/story-1/context"
        )
        preview_response = client.get(
            "/admin/intelligence/claim-entity-context",
            params={
                "text": "Player One agrees move to Arsenal",
                "subject_key": "player:one",
            },
        )
        missing_response = client.get(
            "/admin/intelligence/claims/missing/context"
        )

        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(story_response.status_code, 200)
        self.assertEqual(preview_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(len(guarded), 4)


if __name__ == "__main__":
    unittest.main()
