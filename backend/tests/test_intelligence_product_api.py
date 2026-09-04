import sqlite3
import sys
import tempfile
import unittest

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.schema import SCHEMA
from app.routes.intelligence_product import build_router


class IntelligenceProductApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "product.db"

        def factory():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        self.factory = factory
        conn = factory()
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO intelligence_sources VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("src-1", "arsenal.com", "Arsenal FC", "publisher", "arsenal.com", None, None, "2025-01-01T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{}"),
            ("src-2", "example.com", "Example News", "publisher", "example.com", None, None, "2025-01-01T00:00:00+00:00", "2025-01-09T00:00:00+00:00", "{}"),
        ])
        conn.execute("INSERT INTO intelligence_reporters VALUES (?,?,?,?,?,?)", ("rep-1", "david-ornstein", "David Ornstein", "2025-01-01T00:00:00+00:00", "2025-01-08T00:00:00+00:00", "{}"))
        conn.executemany("INSERT INTO canonical_entities VALUES (?,?,?,?,?,?,?,?)", [
            ("entity-saka", "football:player:bukayo-saka", "player", "football", "Bukayo Saka", "2025-01-01T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{}"),
            ("entity-arsenal", "football:club:arsenal", "club", "football", "Arsenal", "2025-01-01T00:00:00+00:00", "2025-01-09T00:00:00+00:00", "{}"),
            ("entity-unrelated", "football:person:saka-rumour", "person", "football", "Saka Rumour", "2025-01-01T00:00:00+00:00", "2025-01-02T00:00:00+00:00", "{}"),
        ])
        conn.executemany("INSERT INTO entity_aliases VALUES (?,?,?,?,?,?,?,?)", [
            ("alias-1", "entity-saka", "Bukayo Saka", "bukayo saka", "canonical_name", "2025-01-01T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{}"),
            ("alias-2", "entity-saka", "Saka", "saka", "common_name", "2025-01-01T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{}"),
        ])
        conn.executemany("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)", [
            ("claim-1", "claim:saka-return", "football:player:saka", "Saka returns to training", "availability", "2025-01-02T00:00:00+00:00", "2025-01-09T00:00:00+00:00", "{}"),
            ("claim-2", "claim:lexical-only", "football:topic:rumour", "A Saka lexical mention only", "assertion", "2025-01-03T00:00:00+00:00", "2025-01-04T00:00:00+00:00", "{}"),
        ])
        conn.execute("INSERT INTO intelligence_stories VALUES (?,?,?,?,?,?,?)", ("story-1", "story:saka-return", "Saka returns for Arsenal", "developing", "2025-01-03T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{}"))
        conn.execute("INSERT INTO story_claim_links VALUES (?,?,?,?,?,?)", ("story-1", "claim-1", "exact_claim_group", "downstream_exact_common_claim_id", "2025-01-04T00:00:00+00:00", "{}"))
        conn.execute("INSERT INTO media_items VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("media-1", "https://example.com/saka", "article", "src-2", "rep-1", "Saka training update", "2025-01-04T00:00:00+00:00", "hash-2", "2025-01-04T00:00:00+00:00", "2025-01-10T00:00:00+00:00", "{\"private\":\"never\"}"))
        conn.execute("INSERT INTO media_items VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("media-video", "https://video.example/watch/1", "video", "src-2", None, "Training analysis video", None, "video-hash", "2025-01-04T00:00:00+00:00", "2025-01-08T00:00:00+00:00", "{}"))
        conn.execute("INSERT INTO story_media_links VALUES (?,?,?,?,?)", ("story-1", "media-1", "reports", .9, "2025-01-05T00:00:00+00:00"))
        conn.execute("INSERT INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("ev-1", "evidence:1", "official_statement", "football:player:saka", "Training statement", "https://arsenal.com/statement", "ref-1", "verified", "2025-01-05T00:00:00+00:00", "2025-01-05T00:00:00+00:00", "2025-01-05T01:00:00+00:00", "{}"))
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)", ("part-1", "claim-1", "entity-saka", "subject", "ev-1", "verified", .99, "2025-01-05T00:00:00+00:00", "2025-01-05T01:00:00+00:00", "{}"))
        conn.execute("INSERT INTO source_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("obs-1", "src-1", "media-1", "story-1", "football:player:saka", "report", "observed", "Saka trained", "https://arsenal.com/statement", .9, "2025-01-06T00:00:00+00:00", "2025-01-06T01:00:00+00:00", "{}"))
        conn.execute("INSERT INTO reporter_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("robs-1", "rep-1", "src-2", "media-1", "story-1", "football:player:saka", "report", "observed", "Saka trained", "https://example.com/saka", .8, "2025-01-06T02:00:00+00:00", "2025-01-06T03:00:00+00:00", "{}"))
        conn.execute("INSERT INTO evidence_links VALUES (?,?,?,?,?,?,?,?,?,?)", ("el-1", "ev-1", None, "story-1", None, None, "supports", .99, "2025-01-06T04:00:00+00:00", "{}"))
        conn.executemany("INSERT INTO claim_links VALUES (?,?,?,?,?,?,?,?,?,?)", [
            ("cl-1", "claim-1", "obs-1", None, None, "reports", .9, "2025-01-06T00:00:00+00:00", "2025-01-06T01:00:00+00:00", "{}"),
            ("cl-2", "claim-1", None, "robs-1", None, "reports", .8, "2025-01-06T02:00:00+00:00", "2025-01-06T03:00:00+00:00", "{}"),
            ("cl-3", "claim-1", None, None, "ev-1", "supports", .99, "2025-01-06T04:00:00+00:00", "2025-01-06T05:00:00+00:00", "{}"),
        ])
        conn.execute("INSERT INTO observation_dependencies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("dep-1", None, "robs-1", "obs-1", None, None, None, "attributed_to", .95, "2025-01-06T03:00:00+00:00", "2025-01-06T04:00:00+00:00", "{}"))
        conn.execute("INSERT INTO adjudication_state_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("rev-1", "claim-1", "state-v1", "adj-v1", "sha", "2025-01-07T00:00:00+00:00", None, "evidence_added", '["ev-1"]', "{}", "2025-01-07T00:00:00+00:00"))
        conn.execute("INSERT INTO adjudication_state_transitions VALUES (?,?,?,?,?,?,?,?)", ("trans-1", "rev-1", "claim-1", "status", "changed", '"unknown"', '"reviewed"', "2025-01-07T01:00:00+00:00"))
        conn.executemany("INSERT INTO analysis_snapshots (media_item_id,story_id,analyzed_at,mode,analysis_version,scoring_version,content_hash,merit_score,evidence_score,logic_score,badge,verdict,article_type,reasons_json,response_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
            ("media-1", "story-1", "2025-01-07T00:00:00+00:00", "article", "analysis-v1", "score-v1", "hash-1", 61, None, None, "Good", "", "news", '["Clear sourcing"]', '{"client_key":"secret","raw":"no"}'),
            ("media-1", "story-1", "2025-01-08T00:00:00+00:00", "article", "analysis-v2", "score-v2", "hash-2", 72, None, None, "Great", "", "news", '["More context"]', '{"secret":"no"}'),
            ("media-video", None, "2025-01-08T00:00:00+00:00", "video", "analysis-v1", "score-v1", "video-hash", None, 70, 55, "", "Mixed", "", '[]', '{"combined_score":999}'),
        ])
        conn.execute("INSERT INTO user_history VALUES (?,?,?,?,?,?)", ("private-client", "media-1", "2025-01-07T00:00:00+00:00", "2025-01-08T00:00:00+00:00", 2, 2))
        conn.commit()
        conn.close()
        app = FastAPI()
        app.include_router(build_router(connection_factory=factory))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_search_all_kinds_alias_case_filters_and_no_duplicates(self):
        alias = self.client.get("/intelligence/search", params={"q": "sAkA"})
        self.assertEqual(alias.status_code, 200)
        results = alias.json()["results"]
        self.assertEqual(sum(x["id"] == "entity-saka" for x in results), 1)
        self.assertEqual(next(x for x in results if x["id"] == "entity-saka")["match_type"], "alias")
        for query, kind, expected in [
            ("Saka returns for", "story", "story-1"), ("returns to training", "claim", "claim-1"),
            ("football:player:saka", "claim", "claim-1"), ("training update", "media", "media-1"),
            ("arsenal.com", "source", "src-1"), ("David Ornstein", "reporter", "rep-1")]:
            body = self.client.get("/intelligence/search", params={"q": query, "kind": kind}).json()
            self.assertEqual([x["id"] for x in body["results"]], [expected])
        filtered = self.client.get("/intelligence/search", params={"q": "Saka", "kind": "entity", "sport_key": "football"}).json()
        self.assertTrue(all(x["kind"] == "entity" and x["sport_key"] == "football" for x in filtered["results"]))
        related = self.client.get("/intelligence/search", params={"q": "Bukayo Saka", "kind": "claim"}).json()
        self.assertEqual(related["results"][0]["id"], "claim-1")
        self.assertEqual(related["results"][0]["matched_field"], "verified_entity")

    def test_search_ranking_pagination_bounds_and_input_safety(self):
        body = self.client.get("/intelligence/search", params={"q": "Saka", "limit": 2}).json()
        self.assertEqual(len(body["results"]), 2)
        self.assertEqual(body["results"][0]["id"], "entity-saka")
        page2 = self.client.get("/intelligence/search", params={"q": "Saka", "limit": 2, "cursor": body["pagination"]["next_cursor"]}).json()
        self.assertFalse({(x["kind"], x["id"]) for x in body["results"]} & {(x["kind"], x["id"]) for x in page2["results"]})
        self.assertEqual(self.client.get("/intelligence/search", params={"q": " "}).status_code, 422)
        self.assertEqual(self.client.get("/intelligence/search", params={"q": "x" * 201}).status_code, 422)
        self.assertEqual(self.client.get("/intelligence/search", params={"q": "Saka", "kind": "table"}).status_code, 422)
        self.assertEqual(self.client.get("/intelligence/search", params={"q": "Saka", "cursor": "bad"}).status_code, 422)
        for hostile in ["' OR 1=1 --", "%_", '"']:
            response = self.client.get("/intelligence/search", params={"q": hostile})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["results"], [])

    def test_entity_history_uses_verified_graph_only_and_is_read_only(self):
        conn = self.factory(); before = conn.total_changes; counts = conn.execute("SELECT COUNT(*) FROM verified_claim_entity_participants").fetchone()[0]; conn.close()
        response = self.client.get("/intelligence/entities/entity-saka/history")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["claims"], ["claim-1"])
        self.assertNotIn("claim-2", str(body))
        self.assertEqual([e["occurred_at"] for e in body["events"]], sorted(e["occurred_at"] for e in body["events"]))
        conn = self.factory(); self.assertEqual(conn.execute("SELECT COUNT(*) FROM verified_claim_entity_participants").fetchone()[0], counts); self.assertEqual(conn.total_changes, 0); conn.close()
        self.assertEqual(self.client.get("/intelligence/entities/missing/history").status_code, 404)

    def test_story_and_claim_histories_preserve_provenance_and_paginate(self):
        story = self.client.get("/intelligence/stories/story-1/history", params={"limit": 3}).json()
        self.assertEqual(len(story["events"]), 3)
        self.assertIsNotNone(story["pagination"]["next_cursor"])
        self.assertIn("source_observation", str(self.client.get("/intelligence/stories/story-1/history").json()))
        claim = self.client.get("/intelligence/claims/claim-1/history").json()
        rendered = str(claim)
        for value in ["src-1", "rep-1", "ev-1", "dep-1", "rev-1", "trans-1", "story-1"]:
            self.assertIn(value, rendered)
        self.assertTrue(claim["policy"]["dependencies_remain_distinct"])
        self.assertNotIn("truth_score", rendered)
        self.assertEqual(self.client.get("/intelligence/stories/missing/history").status_code, 404)
        self.assertEqual(self.client.get("/intelligence/claims/missing/history").status_code, 404)
        self.assertEqual(self.client.get("/intelligence/claims/claim-1/history", params={"after": "not-time"}).status_code, 422)

    def test_media_history_preserves_article_and_video_semantics_without_raw_json(self):
        article = self.client.get("/intelligence/media/media-1/history").json()
        self.assertEqual([x["merit_score"] for x in article["events"]], [61, 72])
        self.assertEqual([x["analysis_version"] for x in article["events"]], ["analysis-v1", "analysis-v2"])
        rendered = str(article)
        for forbidden in ["response_json", "client_key", "private-client", "secret", "score_calculation"]:
            self.assertNotIn(forbidden, rendered)
        video = self.client.get("/intelligence/media/media-video/history").json()
        snapshot = video["events"][0]
        self.assertEqual((snapshot["evidence_score"], snapshot["logic_score"], snapshot["verdict"]), (70, 55, "Mixed"))
        self.assertNotIn("merit_score", snapshot)
        self.assertNotIn("combined_score", str(video))
        self.assertEqual(self.client.get("/intelligence/media/missing/history").status_code, 404)

    def test_routes_are_registered_once_and_public_router_has_no_admin_route(self):
        paths = [(route.path, tuple(route.methods or ())) for route in self.client.app.routes]
        for path in ["/intelligence/search", "/intelligence/entities/{entity_id}/history", "/intelligence/stories/{story_id}/history", "/intelligence/claims/{claim_id}/history", "/intelligence/media/{media_item_id}/history"]:
            self.assertEqual(sum(item[0] == path and "GET" in item[1] for item in paths), 1)
        self.assertFalse(any(path.startswith("/admin/") for path, _ in paths))


if __name__ == "__main__":
    unittest.main()
