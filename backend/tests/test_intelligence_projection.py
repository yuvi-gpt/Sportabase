from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.projection import (
    CLAIM_PROJECTION_VERSION,
    STORY_PROJECTION_VERSION,
    SUBJECT_TIMELINE_VERSION,
    build_claim_projection,
    build_story_projection,
    build_subject_timeline,
)
from app.routes import intelligence_admin


NOW = "2026-08-22T06:30:00+00:00"
OLD = "2026-06-01T06:30:00+00:00"


class IntelligenceProjectionTests(unittest.TestCase):
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

    @staticmethod
    def clock():
        return datetime(2026, 8, 22, 6, 30, tzinfo=timezone.utc)

    def _seed(self, conn):
        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id, source_key, display_name, source_type, canonical_domain,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'source-a', 'source:a', 'Source A', 'publisher', 'a.example',
              ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO intelligence_reporters (
              id, identity_key, display_name, first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'reporter-a', 'reporter:a', 'Reporter A', ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'claim-1', 'claim:one', 'player:one',
              'Player One agrees move to Arsenal', 'assertion', ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id, canonical_key, canonical_title, status,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'story-1', 'story:one', 'Player One to Arsenal',
              'developing', ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO story_claim_links (
              story_id, claim_id, relationship_type, link_basis,
              linked_at, metadata_json
            ) VALUES (
              'story-1', 'claim-1', 'exact_claim_group',
              'downstream_exact_common_claim_id', ?, '{}'
            )
            """,
            (NOW,),
        )
        conn.execute(
            """
            INSERT INTO media_items (
              id, canonical_url, mode, source_id, title, latest_content_hash,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'media-1', 'https://a.example/story', 'article', 'source-a',
              'Player One agrees move to Arsenal', 'hash-1', ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO story_media_links (
              story_id, media_item_id, relationship_type, confidence, linked_at
            ) VALUES ('story-1', 'media-1', 'reports', 1.0, ?)
            """,
            (NOW,),
        )
        conn.execute(
            """
            INSERT INTO source_observations (
              id, source_id, media_item_id, story_id, subject_key,
              observation_type, status, claim_summary, provenance_url,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'obs-source', 'source-a', 'media-1', 'story-1', 'player:one',
              'article_headline_report', 'unresolved',
              'Player One agrees move to Arsenal', '', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO reporter_observations (
              id, reporter_id, source_id, media_item_id, story_id, subject_key,
              observation_type, status, claim_summary, provenance_url,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'obs-reporter', 'reporter-a', 'source-a', 'media-1', 'story-1',
              'player:one', 'article_report', 'unresolved',
              'Player One agrees move to Arsenal', '', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, source_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'claim-link-source', 'claim-1', 'obs-source', 'reports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, reporter_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'claim-link-reporter', 'claim-1', 'obs-reporter', 'reports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO evidence_records (
              id, evidence_key, evidence_type, subject_key, claim_summary,
              verification_status, observed_at, recorded_at, metadata_json
            ) VALUES (
              'evidence-1', 'evidence:one', 'official_statement', 'player:one',
              'Official statement exists', 'verified', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, evidence_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'claim-link-evidence', 'claim-1', 'evidence-1', 'supports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO evidence_links (
              id, evidence_id, story_id, relationship_type, linked_at, metadata_json
            ) VALUES (
              'story-evidence', 'evidence-1', 'story-1', 'supports', ?, '{}'
            )
            """,
            (NOW,),
        )
        conn.execute(
            """
            INSERT INTO canonical_entities (
              id, entity_key, entity_type, sport_key, canonical_name,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'entity-player', 'player:one', 'player', 'football', 'Player One',
              ?, ?, '{}'
            )
            """,
            (OLD, NOW),
        )
        conn.execute(
            """
            INSERT INTO verified_claim_entity_participants (
              id, claim_id, entity_id, participant_role, evidence_id,
              verification_status, confidence, observed_at, recorded_at, metadata_json
            ) VALUES (
              'participant-1', 'claim-1', 'entity-player', 'subject', 'evidence-1',
              'verified', 0.99, ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO analysis_snapshots (
              media_item_id, story_id, analyzed_at, mode, analysis_version,
              scoring_version, content_hash, context_hash, merit_score,
              evidence_score, logic_score, badge, verdict, article_type,
              score_components_json, score_calculation_json, reasons_json,
              response_json
            ) VALUES (
              'media-1', 'story-1', ?, 'article', 'analysis-v1',
              'score-v1', 'hash-1', 'context-1', 72, 70, 74,
              'solid', 'contextual', 'transfer', '{}', '{}', '[]', '{}'
            )
            """,
            (NOW,),
        )

    def _add_adjudication_leaf(self, revision_id="revision-1", previous=None):
        conn = self.factory()
        try:
            conn.execute(
                """
                INSERT INTO adjudication_state_revisions (
                  id, claim_id, state_version, adjudication_version,
                  adjudication_sha256, as_of, previous_revision_id,
                  trigger_type, trigger_evidence_ids_json, revision_json,
                  recorded_at
                ) VALUES (?, 'claim-1', 'state-v1', 'adjudication-v1',
                          ?, ?, ?, 'evidence_verified', '["evidence-1"]', ?, ?)
                """,
                (
                    revision_id,
                    "sha-" + revision_id,
                    NOW,
                    previous,
                    '{"revision_id":"' + revision_id + '"}',
                    NOW,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def test_claim_projection_combines_state_adjudication_identity_and_freshness(self):
        self._add_adjudication_leaf()

        result = build_claim_projection(
            claim_id="claim-1",
            connection_factory=self.factory,
            now_provider=self.clock,
        )

        self.assertEqual(result["version"], CLAIM_PROJECTION_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["freshness"]["state"], "current")
        self.assertEqual(result["adjudication"]["status"], "ready")
        self.assertEqual(
            result["adjudication"]["revision"]["trigger_evidence_ids"],
            ["evidence-1"],
        )
        self.assertEqual(result["counts"]["verified_participants"], 1)
        self.assertEqual(result["counts"]["stories"], 1)
        self.assertTrue(result["policy"]["projection_is_operational_context_not_truth"])
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_multiple_active_adjudication_leaves_fail_closed(self):
        self._add_adjudication_leaf("revision-a")
        self._add_adjudication_leaf("revision-b")

        result = build_claim_projection(
            claim_id="claim-1",
            connection_factory=self.factory,
            now_provider=self.clock,
        )

        self.assertEqual(result["adjudication"]["status"], "multiple_active_leaves")
        self.assertEqual(result["projection_state"], "adjudication_history_conflict")

    def test_stale_claim_context_is_temporal_not_truth(self):
        conn = self.factory()
        try:
            conn.execute(
                "UPDATE intelligence_claims SET last_seen_at = ? WHERE id = 'claim-1'",
                (OLD,),
            )
            conn.execute("DELETE FROM claim_links")
            conn.execute("DELETE FROM source_observations")
            conn.execute("DELETE FROM reporter_observations")
            conn.commit()
        finally:
            conn.close()

        result = build_claim_projection(
            claim_id="claim-1",
            connection_factory=self.factory,
            stale_after_days=30,
            now_provider=self.clock,
        )

        self.assertEqual(result["freshness"]["state"], "stale")
        self.assertEqual(result["projection_state"], "stale_claim_context")
        self.assertTrue(result["policy"]["staleness_is_temporal_context_not_falsehood"])

    def test_story_projection_rolls_claims_and_latest_product_snapshot(self):
        result = build_story_projection(
            story_id="story-1",
            connection_factory=self.factory,
            now_provider=self.clock,
        )

        self.assertEqual(result["version"], STORY_PROJECTION_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["claims"], 1)
        self.assertEqual(result["counts"]["media_items"], 1)
        self.assertEqual(result["counts"]["direct_story_evidence"], 1)
        self.assertEqual(
            result["runtime_context"]["latest_analysis_snapshot"]["merit_score"],
            72,
        )
        self.assertTrue(
            result["policy"]["latest_analysis_snapshot_is_historical_product_output_not_truth"]
        )
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_subject_timeline_unifies_claim_reporting_and_evidence_chronology(self):
        result = build_subject_timeline(
            subject_key="player:one",
            connection_factory=self.factory,
            limit=50,
        )

        self.assertEqual(result["version"], SUBJECT_TIMELINE_VERSION)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["counts"]["claims"], 1)
        self.assertEqual(result["counts"]["source_observations"], 1)
        self.assertEqual(result["counts"]["reporter_observations"], 1)
        self.assertEqual(result["counts"]["evidence_records"], 1)
        event_types = {item["event_type"] for item in result["events"]}
        self.assertEqual(
            event_types,
            {"claim_seen", "source_observation", "reporter_observation", "evidence_observed"},
        )
        self.assertTrue(result["policy"]["timeline_is_chronology_not_truth"])

    def test_projection_builders_return_explicit_not_found(self):
        claim = build_claim_projection(
            claim_id="missing",
            connection_factory=self.factory,
            now_provider=self.clock,
        )
        story = build_story_projection(
            story_id="missing",
            connection_factory=self.factory,
            now_provider=self.clock,
        )

        self.assertEqual(claim["status"], "not_found")
        self.assertEqual(story["status"], "not_found")

    def test_admin_projection_routes_are_guarded(self):
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
            "/admin/intelligence/claims/claim-1/projection"
        )
        story_response = client.get(
            "/admin/intelligence/stories/story-1/projection"
        )
        timeline_response = client.get(
            "/admin/intelligence/subjects/timeline",
            params={"subject_key": "player:one", "limit": 25},
        )
        missing_response = client.get(
            "/admin/intelligence/claims/missing/projection"
        )

        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(story_response.status_code, 200)
        self.assertEqual(timeline_response.status_code, 200)
        self.assertEqual(missing_response.status_code, 404)
        self.assertEqual(len(guarded), 4)


if __name__ == "__main__":
    unittest.main()
