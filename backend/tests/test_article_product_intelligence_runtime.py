from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.article_product_runtime import (
    ARTICLE_PRODUCT_INTELLIGENCE_VERSION,
    attach_article_product_intelligence,
    build_article_product_intelligence,
)
from app.models.api import AnalyzeResponse
from app.routes import product_api


NOW = "2026-08-22T06:30:00+00:00"
URL = "https://example.com/story"


class ArticleProductIntelligenceRuntimeTests(unittest.TestCase):
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
              'source-1', 'source:example', 'Example', 'publisher',
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
              'media-1', ?, 'article', 'source-1', 'Example Story',
              'hash-1', ?, ?, '{}'
            )
            """,
            (URL, NOW, NOW),
        )

        structured_metadata = json.dumps(
            {
                "identity_source": "deterministic_structured_claim_core",
                "core_fingerprint": "core-fingerprint-1",
                "structured_claim": {
                    "version": "canonical-claim-contract-v1",
                    "subject_key": "football|player|player-one",
                    "event_type": "transfer",
                    "state": "completed",
                    "negated": False,
                    "roles": {
                        "destination": "football|club|arsenal",
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
              'claim-1', 'structured:claim-1',
              'football|player|player-one',
              'Player One completed a move to Arsenal',
              'structured_transfer', ?, ?, ?
            )
            """,
            (NOW, NOW, structured_metadata),
        )

        conn.execute(
            """
            INSERT INTO intelligence_claims (
              id, canonical_key, subject_key, canonical_text, claim_type,
              first_seen_at, last_seen_at, metadata_json
            ) VALUES (
              'claim-2', 'headline:claim-2',
              'article-media|media-1',
              'Example Story',
              'headline_assertion', ?, ?, '{}'
            )
            """,
            (NOW, NOW),
        )

        for observation_id, subject_key in (
            ("observation-1", "football|player|player-one"),
            ("observation-2", "article-media|media-1"),
        ):
            conn.execute(
                """
                INSERT INTO source_observations (
                  id, source_id, media_item_id, subject_key,
                  observation_type, status, claim_summary,
                  provenance_url, observed_at, recorded_at, metadata_json
                ) VALUES (
                  ?, 'source-1', 'media-1', ?,
                  'article_headline_report', 'reported', 'Example Story',
                  ?, ?, ?, '{}'
                )
                """,
                (observation_id, subject_key, URL, NOW, NOW),
            )

        conn.execute(
            """
            INSERT INTO claim_links (
              id, claim_id, source_observation_id, relationship_type,
              observed_at, recorded_at, metadata_json
            ) VALUES (
              'claim-link-1', 'claim-1', 'observation-1',
              'reports', ?, ?, '{}'
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
              'claim-link-2', 'claim-2', 'observation-2',
              'reports', ?, ?, '{}'
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
              'evidence-1', 'evidence:1', 'official_statement',
              'football|player|player-one', 'Official statement',
              'verified', ?, ?, '{}'
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
              'claim-evidence-link-1', 'claim-1', 'evidence-1',
              'supports', ?, ?, '{}'
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
              'story-1', 'story:one', 'Example Story', 'developing',
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
              'story-1', 'claim-1', 'exact_claim_group',
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
              'story-1', 'media-1', 'reports', 1.0, ?
            )
            """,
            (NOW,),
        )

    def test_build_runtime_projects_media_claims_and_stories(self):
        result = build_article_product_intelligence(
            url=URL,
            connection_factory=self.factory,
            stale_after_days=30,
        )

        self.assertEqual(result["version"], ARTICLE_PRODUCT_INTELLIGENCE_VERSION)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["media"]["id"], "media-1")
        self.assertEqual(result["counts"]["claims"], 2)
        self.assertEqual(result["counts"]["stories"], 1)
        self.assertEqual(result["counts"]["structured_claims"], 1)
        self.assertEqual(result["runtime_state"], "structured_claim_context_ready")
        self.assertFalse(result["policy"]["provider_call_performed"])
        self.assertFalse(result["policy"]["affects_live_merit"])

        structured = [
            item for item in result["claims"]
            if item["structured_identity"]
        ]
        self.assertEqual(len(structured), 1)
        self.assertEqual(structured[0]["claim_id"], "claim-1")
        self.assertEqual(
            structured[0]["structured_claim"]["event_type"],
            "transfer",
        )
        self.assertEqual(
            structured[0]["evidence"]["verified_supporting"],
            1,
        )

    def test_no_media_record_is_explicit_and_provider_free(self):
        result = build_article_product_intelligence(
            url="https://example.com/missing",
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "no_media_record")
        self.assertEqual(result["counts"]["claims"], 0)
        self.assertFalse(result["policy"]["provider_call_performed"])

    def test_attachment_fails_open_when_database_is_unavailable(self):
        response = AnalyzeResponse(
            url=URL,
            title="Example Story",
            tldr=["Summary."],
            merit_score=50,
            badge="Developing",
            intelligence={"status": "existing"},
            debug={"cache": {"hit": True}},
        )

        def broken_factory():
            raise RuntimeError("database down")

        attached = attach_article_product_intelligence(
            response=response,
            url=URL,
            connection_factory=broken_factory,
        )

        runtime = attached.intelligence["runtime"]
        self.assertEqual(runtime["status"], "unavailable")
        self.assertEqual(runtime["reason"], "runtime_exception")
        self.assertEqual(runtime["error_type"], "RuntimeError")
        self.assertNotIn("database down", json.dumps(runtime))
        self.assertEqual(
            attached.intelligence["status"],
            "existing",
        )
        self.assertEqual(
            attached.debug["intelligence_runtime"]["status"],
            "unavailable",
        )

    def _router(self, *, connection_factory):
        def analyze_handler(req, request):
            return AnalyzeResponse(
                url=req.url,
                title=req.title,
                tldr=["Summary."],
                merit_score=61,
                badge="Developing",
                intelligence={"status": "existing"},
                debug={"cache": {"hit": True}},
            )

        return product_api.build_router(
            health_handler=lambda: {"ok": True},
            ingest_handler=lambda: {
                "sources": 0,
                "fetched_items": 0,
                "inserted": 0,
                "skipped": 0,
            },
            stories_handler=lambda **kwargs: [],
            resolve_content_handler=lambda req: None,
            browser_capture_handler=lambda req: None,
            analyze_video_handler=lambda req, request: None,
            analyze_handler=analyze_handler,
            operational_event_recorder=None,
            connection_factory=connection_factory,
        )

    def test_product_analyze_route_attaches_fresh_runtime_context(self):
        app = FastAPI()
        app.include_router(self._router(connection_factory=self.factory))
        client = TestClient(app)

        response = client.post(
            "/analyze",
            json={
                "title": "Example Story",
                "url": URL,
                "text": (
                    "This is sufficiently long article text for the request "
                    "model and the product runtime integration test."
                ),
                "max_bullets": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["merit_score"], 61)
        self.assertEqual(payload["intelligence"]["status"], "existing")
        runtime = payload["intelligence"]["runtime"]
        self.assertEqual(runtime["status"], "ready")
        self.assertEqual(runtime["counts"]["claims"], 2)
        self.assertTrue(payload["debug"]["cache"]["hit"])
        self.assertEqual(
            payload["debug"]["intelligence_runtime"]["status"],
            "ready",
        )

    def test_router_remains_backward_compatible_without_database_dependency(self):
        app = FastAPI()
        app.include_router(self._router(connection_factory=None))
        client = TestClient(app)

        analysis = client.post(
            "/analyze",
            json={
                "title": "Example Story",
                "url": URL,
                "text": (
                    "This is sufficiently long article text for the request "
                    "model and compatibility test without a database."
                ),
            },
        )

        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(
            analysis.json()["intelligence"]["runtime"]["status"],
            "disabled",
        )


if __name__ == "__main__":
    unittest.main()
