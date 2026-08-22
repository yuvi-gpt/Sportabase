from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.background_pipeline_runtime import (
    BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION,
    BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
    build_background_intelligence_refresh,
    load_background_intelligence_job,
    refresh_completed_job_intelligence,
)
from app.operations import job_runtime, job_worker_runtime
from app.routes import intelligence_admin


NOW = "2026-08-22T07:30:00+00:00"
URL = "https://example.com/background-story"


class BackgroundIntelligenceRuntimeTests(unittest.TestCase):
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
        conn.execute(
            """
            INSERT INTO intelligence_sources (
              id, source_key, display_name, source_type, canonical_domain,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'source-bg', 'source:bg', 'Background Source', 'publisher',
              'example.com', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO media_items (
              id, canonical_url, mode, source_id, title,
              latest_content_hash, first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'media-bg', ?, 'article', 'source-bg', 'Background Story',
              'hash-bg', ?, ?, '{}'
            )
            """,
            (URL, NOW, NOW),
        )

        structured_metadata = json.dumps(
            {
                "identity_source": "deterministic_structured_claim_core",
                "core_fingerprint": "core-bg",
                "structured_claim": {
                    "version": "canonical-claim-contract-v1",
                    "subject_key": "football|player|player-bg",
                    "event_type": "transfer",
                    "state": "completed",
                    "negated": False,
                    "roles": {
                        "destination": "football|club|club-bg",
                    },
                    "facets": {},
                },
            },
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'claim-bg', 'structured:bg', 'football|player|player-bg',
              'Player BG completed a move to Club BG',
              'structured_transfer', ?, ?, ?
            )
            """,
            (NOW, NOW, structured_metadata),
        )
        conn.execute(
            """
            INSERT INTO source_observations (
              id, source_id, media_item_id, subject_key,
              observation_type, status, claim_summary, provenance_url,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'observation-bg', 'source-bg', 'media-bg',
              'football|player|player-bg', 'article_headline_report',
              'reported', 'Background Story', ?, ?, ?, '{}'
            )
            """,
            (URL, NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, source_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'claim-link-bg', 'claim-bg', 'observation-bg',
              'reports', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )

        conn.execute(
            """
            INSERT INTO intelligence_stories (
              id, canonical_key, canonical_title, status,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'story-bg', 'story:bg', 'Background Story', 'developing',
              ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )
        conn.execute(
            """
            INSERT INTO story_claim_links (
              story_id, claim_id, relationship_type, link_basis,
              linked_at, metadata_json
            ) VALUES (
              'story-bg', 'claim-bg', 'exact_claim_group',
              'downstream_exact_common_claim_id', ?, '{}'
            )
            """,
            (NOW,),
        )
        conn.execute(
            """
            INSERT INTO story_media_links (
              story_id, media_item_id, relationship_type, confidence, linked_at
            ) VALUES (
              'story-bg', 'media-bg', 'reports', 1.0, ?
            )
            """,
            (NOW,),
        )

        conn.execute(
            """
            INSERT INTO browser_capture_inbox (
              id, capture_hash, canonical_url, platform, platform_surface,
              normalized_item_id, normalized_content_hash, observed_at,
              first_received_at, last_received_at, receive_count,
              capture_json, metadata_json
            ) VALUES (
              'capture-bg', 'capture-hash-bg', ?, 'web', 'article',
              'normalized-bg', 'normalized-content-bg', ?, ?, ?, 1,
              '{}', '{}'
            )
            """,
            (URL, NOW, NOW, NOW),
        )

        persisted_summary = {
            "version": "multimodal-inbox-story-cluster-v1",
            "status": "completed_shadow",
            "claim_ids": ["claim-bg"],
            "story_ids": ["story-bg"],
            "baseline_resolution": {
                "media_item_id": "media-bg",
            },
        }
        conn.execute(
            """
            INSERT INTO browser_capture_automation_jobs (
              id, capture_record_id, analysis_version, scoring_version,
              status, attempts, max_attempts, available_at_epoch,
              lease_owner, lease_expires_at_epoch, created_at, updated_at,
              started_at, finished_at, last_outcome, error_type,
              error_detail, result_json
            ) VALUES (
              'job-bg', 'capture-bg', 'analysis-v1', 'score-v1',
              'completed', 1, 24, 0, '', 0, ?, ?, ?, ?,
              'completed_shadow', '', '', ?
            )
            """,
            (
                NOW,
                NOW,
                NOW,
                NOW,
                json.dumps(persisted_summary, sort_keys=True),
            ),
        )

    def completed_result(self):
        return {
            "status": "completed",
            "execution_mode": "article_history_merit",
            "job": {
                "id": "job-bg",
                "status": "completed",
                "attempts": 1,
                "max_attempts": 24,
                "last_outcome": "completed_shadow",
            },
            "result": {
                "claim_ids": ["claim-bg"],
                "story_ids": ["story-bg"],
                "baseline_resolution": {
                    "media_item_id": "media-bg",
                },
            },
        }

    def test_build_refresh_projects_completed_background_result(self):
        refresh = build_background_intelligence_refresh(
            result=self.completed_result(),
            connection_factory=self.factory,
        )

        self.assertEqual(
            refresh["version"],
            BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
        )
        self.assertEqual(refresh["status"], "ready")
        self.assertEqual(refresh["counts"]["claims"], 1)
        self.assertEqual(refresh["counts"]["stories"], 1)
        self.assertEqual(refresh["counts"]["structured_claims"], 1)
        self.assertEqual(refresh["counts"]["projection_failures"], 0)
        self.assertEqual(refresh["claim_states"][0]["id"], "claim-bg")
        self.assertTrue(refresh["claim_states"][0]["structured_identity"])
        self.assertEqual(refresh["article_runtime"]["status"], "ready")
        self.assertEqual(
            refresh["article_runtime"]["counts"]["structured_claims"],
            1,
        )
        self.assertFalse(refresh["policy"]["provider_call_performed"])
        self.assertFalse(refresh["policy"]["historical_snapshots_mutated"])
        self.assertFalse(refresh["policy"]["affects_live_merit"])

    def test_refresh_persists_bounded_summary_into_completed_job(self):
        result = refresh_completed_job_intelligence(
            result=self.completed_result(),
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["intelligence_refresh"]["status"], "ready")
        self.assertIn("intelligence_refresh", result["result"])

        conn = self.factory()
        try:
            row = conn.execute(
                "SELECT result_json FROM browser_capture_automation_jobs "
                "WHERE id = 'job-bg'"
            ).fetchone()
        finally:
            conn.close()

        payload = json.loads(row["result_json"])
        persisted = payload["intelligence_refresh"]
        self.assertEqual(persisted["status"], "ready")
        self.assertEqual(persisted["counts"]["claims"], 1)
        self.assertNotIn("claim_states", persisted)
        self.assertNotIn("story_states", persisted)

    def test_refresh_failure_is_advisory_and_does_not_reclassify_job(self):
        def broken_factory():
            raise RuntimeError("private database failure detail")

        result = refresh_completed_job_intelligence(
            result=self.completed_result(),
            connection_factory=broken_factory,
        )

        self.assertEqual(result["status"], "completed")
        refresh = result["intelligence_refresh"]
        self.assertEqual(refresh["status"], "unavailable")
        self.assertEqual(refresh["error_type"], "RuntimeError")
        self.assertNotIn(
            "private database failure detail",
            json.dumps(refresh),
        )
        self.assertFalse(refresh["policy"]["affects_live_merit"])

    def test_non_completed_result_is_not_refreshed(self):
        original = {
            "status": "retry_scheduled",
            "retry_delay_seconds": 10,
        }
        result = refresh_completed_job_intelligence(
            result=original,
            connection_factory=self.factory,
        )

        self.assertEqual(result, original)
        self.assertNotIn("intelligence_refresh", result)

    def test_admin_job_view_returns_only_bounded_job_and_refresh_data(self):
        refresh_completed_job_intelligence(
            result=self.completed_result(),
            connection_factory=self.factory,
        )

        view = load_background_intelligence_job(
            job_id="job-bg",
            connection_factory=self.factory,
        )

        self.assertEqual(
            view["version"],
            BACKGROUND_INTELLIGENCE_JOB_VIEW_VERSION,
        )
        self.assertEqual(view["status"], "ok")
        self.assertEqual(view["job"]["id"], "job-bg")
        self.assertEqual(view["intelligence_refresh"]["status"], "ready")
        self.assertTrue(view["policy"]["raw_result_json_not_returned"])
        self.assertNotIn("result_json", view["job"])
        self.assertNotIn("error_detail", view["job"])

    def test_admin_route_authenticates_before_database_read(self):
        database_calls = []

        def denied(_request):
            raise HTTPException(status_code=401, detail="denied")

        def forbidden_factory():
            database_calls.append(True)
            raise AssertionError("database should not be read before auth")

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=denied,
                connection_factory=forbidden_factory,
            )
        )
        response = TestClient(app).get(
            "/admin/intelligence/background-jobs/job-bg"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(database_calls, [])

    def test_admin_route_returns_refresh_view(self):
        refresh_completed_job_intelligence(
            result=self.completed_result(),
            connection_factory=self.factory,
        )

        app = FastAPI()
        app.include_router(
            intelligence_admin.build_router(
                require_admin=lambda _request: None,
                connection_factory=self.factory,
            )
        )
        response = TestClient(app).get(
            "/admin/intelligence/background-jobs/job-bg"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["intelligence_refresh"]["status"],
            "ready",
        )

    def test_refresh_telemetry_is_aggregate_and_privacy_minimized(self):
        events = []
        result = self.completed_result()
        result["intelligence_refresh"] = {
            "version": BACKGROUND_INTELLIGENCE_REFRESH_VERSION,
            "status": "ready",
            "counts": {
                "claims": 3,
                "stories": 2,
                "structured_claims": 1,
                "stale_claims": 0,
                "conflict_claims": 0,
                "projection_failures": 0,
            },
            "claim_ids": ["private-claim-id"],
        }

        job_worker_runtime._emit_intelligence_refresh_event(
            lambda **event: events.append(event),
            result,
        )

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(
            event["event_type"],
            "intelligence.background_refreshed",
        )
        self.assertEqual(event["mode"], "article")
        self.assertEqual(event["details"]["claims"], 3)
        self.assertEqual(event["details"]["stories"], 2)
        self.assertNotIn("claim_ids", event["details"])
        self.assertNotIn("job_id", event["details"])

    def test_job_completion_telemetry_carries_refresh_counts_without_ids(self):
        events = []
        result = self.completed_result()
        result["intelligence_refresh"] = {
            "status": "ready",
            "counts": {
                "claims": 2,
                "stories": 1,
                "structured_claims": 1,
                "projection_failures": 0,
            },
            "claim_ids": ["private-claim-id"],
        }

        job_runtime.record_browser_capture_job_result(
            event_recorder=lambda **event: events.append(event),
            result=result,
        )

        self.assertEqual(len(events), 1)
        details = events[0]["details"]
        self.assertEqual(details["intelligence_refresh_status"], "ready")
        self.assertEqual(details["intelligence_claims"], 2)
        self.assertEqual(details["intelligence_stories"], 1)
        self.assertEqual(details["intelligence_structured_claims"], 1)
        self.assertNotIn("claim_ids", details)


if __name__ == "__main__":
    unittest.main()
