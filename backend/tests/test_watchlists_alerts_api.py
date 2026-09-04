import concurrent.futures
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

from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.routes.watchlists_product import build_router
from app.watchlists.runtime import MAX_ALERTS_PER_WATCH, client_key, reconcile


T0 = "2025-01-01T00:00:00+00:00"


class WatchlistsAlertsApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "watchlists.db"

        def factory():
            conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            return conn

        self.factory = factory
        initialize_database(factory, SCHEMA)
        conn = factory()
        conn.execute("INSERT INTO canonical_entities VALUES (?,?,?,?,?,?,?,?)", ("entity-1","football:player:one","player","football","Player One",T0,T0,"{}"))
        conn.execute("INSERT INTO intelligence_stories VALUES (?,?,?,?,?,?,?)", ("story-1","story:one","Story One","developing",T0,T0,"{}"))
        conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)", ("claim-1","claim:one","football:player:one","Claim One","assertion",T0,T0,"{}"))
        conn.execute("INSERT INTO intelligence_sources VALUES (?,?,?,?,?,?,?,?,?,?)", ("source-1","example.com","Example","publisher","example.com",None,None,T0,T0,"{}"))
        conn.execute("INSERT INTO intelligence_reporters VALUES (?,?,?,?,?,?)", ("reporter-1","reporter:one","Reporter One",T0,T0,"{}"))
        conn.execute("INSERT INTO media_items VALUES (?,?,?,?,?,?,?,?,?,?,?)", ("media-1","https://example.com/one","article","source-1","reporter-1","Media One",T0,"hash",T0,T0,"{}"))
        conn.execute("INSERT INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ("evidence-1","evidence:one","statement","subject","Evidence One","https://example.com/evidence","ref","verified",T0,T0,T0,"{}"))
        # A substantial history exists before watches; all of it is baselined.
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)", ("participant-old","claim-1","entity-1","subject","evidence-1","verified",.99,T0,T0,"{}"))
        conn.execute("INSERT INTO story_claim_links VALUES (?,?,?,?,?,?)", ("story-1","claim-1","exact_claim_group","downstream_exact_common_claim_id",T0,"{}"))
        conn.execute("INSERT INTO story_media_links VALUES (?,?,?,?,?)", ("story-1","media-1","reports",.9,T0))
        conn.execute("INSERT INTO analysis_snapshots(media_item_id,story_id,analyzed_at,mode,analysis_version,scoring_version,content_hash,response_json) VALUES(?,?,?,?,?,?,?,?)", ("media-1","story-1",T0,"article","v0","s0","old","{}"))
        conn.commit(); conn.close()
        app = FastAPI()
        app.include_router(build_router(connection_factory=factory))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.tmp.cleanup()

    def headers(self, client="client-a"):
        return {"x-sportabase-client-id": client}

    def watch(self, kind="entity", target_id="entity-1", client="client-a"):
        response = self.client.post("/watchlists", headers=self.headers(client), json={"target_kind":kind,"target_id":target_id})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["watch"]

    def reconcile_http(self, client="client-a"):
        response = self.client.post("/watchlists/alerts/reconcile", headers=self.headers(client))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def alerts(self, client="client-a", **params):
        return self.client.get("/watchlists/alerts", headers=self.headers(client), params=params)

    def test_identity_is_explicit_private_and_has_no_ip_fallback(self):
        paths = [
            ("post","/watchlists", {"json":{"target_kind":"entity","target_id":"entity-1"}}),
            ("get","/watchlists", {}), ("delete","/watchlists/opaque", {}),
            ("post","/watchlists/alerts/reconcile", {}), ("get","/watchlists/alerts", {}),
            ("post","/watchlists/alerts/opaque/read", {}),
        ]
        for method, path, kwargs in paths:
            kwargs["headers"] = {"x-forwarded-for":"203.0.113.9"}
            self.assertEqual(getattr(self.client, method)(path, **kwargs).status_code, 401, path)
        self.assertEqual(self.client.get("/watchlists", headers={"x-sportabase-client-id":" "}).status_code, 401)
        self.assertEqual(self.client.get("/watchlists", headers=self.headers("x"*201)).status_code, 401)
        key = client_key("client-a")
        self.watch()
        conn=self.factory(); stored=conn.execute("SELECT client_key FROM product_watchlist_items").fetchone()[0]; conn.close()
        self.assertEqual(stored,key); self.assertNotEqual(stored,"client-a")
        self.assertNotIn("client-a", str(self.client.get("/watchlists",headers=self.headers()).json()))

    def test_create_is_idempotent_validated_capped_and_sql_safe(self):
        first=self.watch(); second=self.watch()
        self.assertEqual(first["id"],second["id"])
        self.assertEqual(self.client.post("/watchlists",headers=self.headers(),json={"target_kind":"source","target_id":"source-1"}).status_code,422)
        self.assertEqual(self.client.post("/watchlists",headers=self.headers(),json={"target_kind":"entity","target_id":"' OR 1=1 --"}).status_code,404)
        conn=self.factory()
        for n in range(2,102):
            conn.execute("INSERT INTO canonical_entities VALUES (?,?,?,?,?,?,?,?)",(f"entity-{n}",f"key:{n}","player","football",f"Player {n}",T0,T0,"{}"))
        conn.commit(); conn.close()
        for n in range(2,101): self.watch("entity",f"entity-{n}")
        response=self.client.post("/watchlists",headers=self.headers(),json={"target_kind":"entity","target_id":"entity-101"})
        self.assertEqual(response.status_code,409)

    def test_baseline_then_late_arriving_verified_participation_alerts_once(self):
        self.watch()
        self.assertEqual(self.reconcile_http()["new_alerts"],0)
        conn=self.factory()
        conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)",("claim-2","claim:two","subject","Older real-world event","assertion",T0,T0,"{}"))
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",("participant-new","claim-2","entity-1","subject","evidence-1","verified",.99,"2024-01-01T00:00:00+00:00","2025-02-01T00:00:00+00:00","{}"))
        conn.commit(); conn.close()
        self.assertEqual(self.reconcile_http()["new_alerts"],1)
        self.assertEqual(self.reconcile_http()["new_alerts"],0)
        items=self.alerts().json()["items"]
        self.assertEqual(len(items),1); self.assertEqual(items[0]["occurred_at"],"2024-01-01T00:00:00+00:00")
        rendered=str(items).lower()
        for word in ("breaking","confirmed","true","reliable","credibility"): self.assertNotIn(word,rendered)

    def test_story_claim_and_media_event_contracts(self):
        for kind,target in (("story","story-1"),("claim","claim-1"),("media","media-1")):
            self.watch(kind,target)
        conn=self.factory()
        conn.execute("INSERT INTO source_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",("obs-new","source-1","media-1","story-1","subject","report","observed","Summary","https://example.com",.8,T0,"2025-02-01T00:00:00+00:00","{}"))
        conn.execute("INSERT INTO reporter_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",("robs-new","reporter-1","source-1","media-1","story-1","subject","report","observed","Summary","https://example.com",.8,T0,"2025-02-01T00:00:00+00:00","{}"))
        conn.execute("INSERT INTO evidence_links VALUES (?,?,?,?,?,?,?,?,?,?)",("el-new","evidence-1",None,"story-1",None,None,"supports",.9,T0,"{}"))
        conn.execute("INSERT INTO claim_links VALUES (?,?,?,?,?,?,?,?,?,?)",("cl-new","claim-1","obs-new",None,None,"reports",.8,T0,"2025-02-01T00:00:00+00:00","{}"))
        conn.execute("INSERT INTO adjudication_state_revisions VALUES (?,?,?,?,?,?,?,?,?,?,?)",("rev-new","claim-1","v1","a1","sha",T0,None,"evidence_added","[]","{}","2025-02-01T00:00:00+00:00"))
        conn.execute("INSERT INTO adjudication_state_transitions VALUES (?,?,?,?,?,?,?,?)",("transition-new","rev-new","claim-1","status","changed",None,'"reviewed"',"2025-02-01T00:00:00+00:00"))
        conn.execute("INSERT INTO analysis_snapshots(media_item_id,story_id,analyzed_at,mode,analysis_version,scoring_version,content_hash,merit_score,response_json) VALUES(?,?,?,?,?,?,?,?,?)",("media-1","story-1",T0,"article","v1","s1","new",72,'{"secret":"never"}'))
        conn.commit(); conn.close()
        result=self.reconcile_http(); self.assertGreaterEqual(result["new_alerts"],7)
        items=self.alerts(limit=100).json()["items"]
        by_kind={kind:{x["event_type"] for x in items if x["target_kind"]==kind} for kind in ("story","claim","media")}
        self.assertTrue({"source_observation","reporter_observation","evidence","analysis_snapshot"} <= by_kind["story"])
        self.assertTrue({"claim_link","adjudication_revision","adjudication_transition"} <= by_kind["claim"])
        self.assertEqual(by_kind["media"],{"analysis_snapshot"})
        self.assertNotIn("secret",str(items)); self.assertNotIn("merit_score",str(items))

    def test_entity_graph_requires_verified_participation(self):
        self.watch()
        conn=self.factory()
        conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)",("claim-lexical","claim:lexical","subject","Player One mentioned","assertion",T0,T0,"{}"))
        conn.execute("INSERT INTO intelligence_stories VALUES (?,?,?,?,?,?,?)",("story-2","story:two","Story Two","developing",T0,T0,"{}"))
        conn.execute("INSERT INTO story_claim_links VALUES (?,?,?,?,?,?)",("story-2","claim-lexical","exact_claim_group","downstream_exact_common_claim_id",T0,"{}"))
        conn.commit(); conn.close()
        self.assertEqual(self.reconcile_http()["new_alerts"],0)
        conn=self.factory()
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",("participant-2","claim-lexical","entity-1","subject","evidence-1","verified",.99,T0,T0,"{}"))
        conn.execute("INSERT INTO media_items VALUES (?,?,?,?,?,?,?,?,?,?,?)",("media-2","https://example.com/two","article","source-1",None,"Media Two",T0,"h2",T0,T0,"{}"))
        conn.execute("INSERT INTO story_media_links VALUES (?,?,?,?,?)",("story-2","media-2","reports",.9,T0))
        conn.commit(); conn.close()
        self.assertEqual(self.reconcile_http()["new_alerts"],2)

    def test_multi_client_idor_read_state_and_delete_cascade(self):
        watch_a=self.watch(client="client-a"); watch_b=self.watch(client="client-b")
        conn=self.factory()
        conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)",("claim-2","claim:two","subject","Claim Two","assertion",T0,T0,"{}"))
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",("participant-2","claim-2","entity-1","subject","evidence-1","verified",.99,T0,T0,"{}"))
        conn.commit(); conn.close()
        self.reconcile_http("client-a"); self.reconcile_http("client-b")
        alert_a=self.alerts("client-a").json()["items"][0]; alert_b=self.alerts("client-b").json()["items"][0]
        self.assertNotEqual(alert_a["id"],alert_b["id"])
        self.assertEqual(self.client.post(f"/watchlists/alerts/{alert_b['id']}/read",headers=self.headers("client-a")).status_code,404)
        self.assertEqual(self.client.delete(f"/watchlists/{watch_b['id']}",headers=self.headers("client-a")).status_code,404)
        read=self.client.post(f"/watchlists/alerts/{alert_a['id']}/read",headers=self.headers("client-a"))
        self.assertIsNotNone(read.json()["read_at"])
        again=self.client.post(f"/watchlists/alerts/{alert_a['id']}/read",headers=self.headers("client-a"))
        self.assertEqual(again.json()["read_at"],read.json()["read_at"])
        self.assertEqual(self.alerts("client-a",unread_only=True).json()["items"],[])
        self.assertEqual(self.client.delete(f"/watchlists/{watch_a['id']}",headers=self.headers("client-a")).status_code,204)
        conn=self.factory()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM product_alert_events WHERE watch_id=?",(watch_a["id"],)).fetchone()[0],0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM product_watchlist_items WHERE id=?",(watch_b["id"],)).fetchone()[0],1)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM verified_claim_entity_participants").fetchone()[0],2); conn.close()

    def test_bounded_partial_batches_pagination_filters_and_cursor_validation(self):
        self.watch("media","media-1")
        conn=self.factory()
        for n in range(MAX_ALERTS_PER_WATCH+5):
            conn.execute("INSERT INTO analysis_snapshots(media_item_id,analyzed_at,mode,analysis_version,scoring_version,content_hash,response_json) VALUES(?,?,?,?,?,?,?)",("media-1",T0,"article",f"v{n+1}","s",f"h{n}","{}"))
        conn.commit(); conn.close()
        self.assertEqual(self.reconcile_http()["new_alerts"],MAX_ALERTS_PER_WATCH)
        self.assertEqual(self.reconcile_http()["new_alerts"],5)
        first=self.alerts(limit=10).json(); second=self.alerts(limit=10,cursor=first["pagination"]["next_cursor"]).json()
        self.assertFalse({x["id"] for x in first["items"]}&{x["id"] for x in second["items"]})
        cursor=first["pagination"]["next_cursor"]
        self.assertEqual(self.alerts(target_kind="claim",limit=10,cursor=cursor).status_code,422)
        self.assertEqual(self.alerts(cursor="not-a-cursor").status_code,422)
        self.assertEqual(self.alerts(target_kind="x' OR 1=1 --").status_code,422)
        detected=[x["detected_at"]+x["id"] for x in first["items"]]
        self.assertEqual(detected,sorted(detected,reverse=True))

    def test_concurrent_reconciliation_has_one_durable_alert(self):
        self.watch()
        conn=self.factory()
        conn.execute("INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)",("claim-2","claim:two","subject","Claim Two","assertion",T0,T0,"{}"))
        conn.execute("INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",("participant-2","claim-2","entity-1","subject","evidence-1","verified",.99,T0,T0,"{}"))
        conn.commit(); conn.close()
        owner=client_key("client-a")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _: reconcile(owner_key=owner,connection_factory=self.factory),range(2)))
        self.assertEqual(sum(x["new_alerts"] for x in results),1)
        conn=self.factory(); self.assertEqual(conn.execute("SELECT COUNT(*) FROM product_alert_events").fetchone()[0],1); conn.close()

    def test_schema_constraints_indexes_and_existing_database_startup(self):
        conn=self.factory()
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO product_watchlist_items VALUES (?,?,?,?,?,?,?)",("bad","key","source","source-1",T0,0,None))
        indexes={row[1] for row in conn.execute("PRAGMA index_list(product_alert_events)")}
        self.assertIn("idx_product_alert_events_inbox",indexes)
        foreign_keys=conn.execute("PRAGMA foreign_key_list(product_alert_events)").fetchall()
        self.assertTrue(any(row[2]=="product_watchlist_items" and row[6]=="CASCADE" for row in foreign_keys)); conn.close()
        initialize_database(self.factory,SCHEMA)


if __name__ == "__main__":
    unittest.main()
