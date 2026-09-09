import json
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
from app.intelligence.analysis_result_context import (
    _stance_label,
    build_analysis_result_context,
)
from app.intelligence.claim_materialization import CLAIM_MATERIALIZATION_METADATA_VERSION
from app.intelligence.claims import identity as claim_identity
from app.intelligence.claims import repository as claim_repository
from app.routes.intelligence_product import build_router


T0 = "2025-01-01T00:00:00+00:00"
T1 = "2025-01-02T00:00:00+00:00"
T2 = "2025-01-03T00:00:00+00:00"
T3 = "2025-01-04T00:00:00+00:00"


class AnalysisResultContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "result-context.db"

        def factory():
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        self.factory = factory
        bootstrap = factory()
        bootstrap.executescript(SCHEMA)
        bootstrap.close()
        self._seed()
        app = FastAPI()
        app.include_router(build_router(connection_factory=factory))
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def _seed(self):
        conn = self.factory()
        candidate = claim_identity.normalize_canonical_claim({
            "version": "canonical-claim-contract-v1",
            "subject_key": "football|club|example",
            "event_type": "transfer",
            "state": "interest",
            "negated": False,
            "roles": {"destination": "football|club|example"},
            "facets": {},
        })
        canonical_key = claim_identity.canonical_claim_core_key(candidate)
        self.claim_id = claim_repository.claim_id_for_canonical_key(canonical_key)
        core_fingerprint = claim_identity.canonical_claim_core_fingerprint(candidate)
        specific_fingerprint = claim_identity.canonical_claim_specific_fingerprint(candidate)
        sources = [
            ("source-primary", "primary.example", "Primary News", "publisher", "primary.example"),
            ("source-official", "club.example", "Example FC", "official", "club.example"),
            ("source-independent", "independent.example", "Independent Desk", "publisher", "independent.example"),
            ("source-derived", "derived.example", "Derived Desk", "publisher", "derived.example"),
        ]
        for source_id, key, name, source_type, domain in sources:
            conn.execute(
                "INSERT INTO intelligence_sources VALUES (?,?,?,?,?,?,?,?,?,?)",
                (source_id, key, name, source_type, domain, None, None, T0, T0, "{}"),
            )
        conn.execute(
            "INSERT INTO canonical_entities VALUES (?,?,?,?,?,?,?,?)",
            ("entity-club", "football:club:example", "club", "football", "Example FC", T0, T0, "{}"),
        )
        conn.execute(
            "INSERT INTO intelligence_stories VALUES (?,?,?,?,?,?,?)",
            ("story-1", "story:transfer", "Transfer story", "developing", T0, T3, "{}"),
        )
        conn.execute(
            "INSERT INTO intelligence_claims VALUES (?,?,?,?,?,?,?,?)",
            (
                self.claim_id, canonical_key, "football|club|example",
                "Example FC agreed the transfer.", "event", T0, T3,
                json.dumps({
                    "materialization_version": CLAIM_MATERIALIZATION_METADATA_VERSION,
                    "identity_contract_version": claim_identity.CANONICAL_CLAIM_CONTRACT_VERSION,
                    "identity_source": "deterministic_structured_claim_core",
                    "core_fingerprint": core_fingerprint,
                    "merged_specific_fingerprint": specific_fingerprint,
                    "specific_fingerprints": [specific_fingerprint],
                    "structured_claim": candidate,
                }, sort_keys=True),
            ),
        )
        media = [
            ("media-primary", "https://primary.example/story", "source-primary", "Primary report", T0),
            ("media-official", "https://club.example/statement", "source-official", "Club statement", T1),
            ("media-independent", "https://independent.example/report", "source-independent", "Independent report", T2),
            ("media-derived", "https://derived.example/report", "source-derived", "Follow-up report", T3),
        ]
        for media_id, url, source_id, title, observed in media:
            conn.execute(
                "INSERT INTO media_items VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (media_id, url, "article", source_id, None, title, observed, "hash-" + media_id, observed, observed, "{}"),
            )
            conn.execute(
                "INSERT INTO story_media_links VALUES (?,?,?,?,?)",
                ("story-1", media_id, "reports", .99, observed),
            )
        conn.execute(
            "INSERT INTO story_claim_links VALUES (?,?,?,?,?,?)",
            ("story-1", self.claim_id, "exact_claim_group", "downstream_exact_common_claim_id", T0, "{}"),
        )
        for evidence_id, evidence_type, observed in [
            ("evidence-support", "official_statement", T1),
            ("evidence-independence", "independence_verification", T2),
            ("evidence-participant", "claim_entity_participant_reference", T1),
        ]:
            conn.execute(
                "INSERT INTO evidence_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (evidence_id, "key:" + evidence_id, evidence_type, "football|club|example", evidence_type, "", evidence_id, "verified", observed, observed, observed, "{}"),
            )
        conn.execute(
            "INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("participant-verified", self.claim_id, "entity-club", "subject", "evidence-participant", "verified", .99, T1, T1, "{}"),
        )
        conn.execute(
            "INSERT INTO verified_source_entity_bindings VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("source-binding", "source-official", "entity-club", "official_publication", "evidence-support", "verified", .99, T1, T1, "{}"),
        )
        observations = [
            ("obs-primary", "source-primary", "media-primary", T0),
            ("obs-official", "source-official", "media-official", T1),
            ("obs-independent", "source-independent", "media-independent", T2),
            ("obs-derived", "source-derived", "media-derived", T3),
        ]
        for obs_id, source_id, media_id, observed in observations:
            conn.execute(
                "INSERT INTO source_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (obs_id, source_id, media_id, "story-1", "football|club|example", "report", "confirmed", "Example FC agreed the transfer.", "", .99, observed, observed, "{}"),
            )
        for link_id, observation_id, relationship, observed in [
            ("link-primary", "obs-primary", "reports", T0),
            ("link-official", "obs-official", "supports", T1),
            ("link-independent", "obs-independent", "supports", T2),
            ("link-derived", "obs-derived", "supports", T3),
        ]:
            conn.execute(
                "INSERT INTO claim_links(id,claim_id,source_observation_id,relationship_type,confidence,observed_at,recorded_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
                (link_id, self.claim_id, observation_id, relationship, .99, observed, observed, "{}"),
            )
        conn.execute(
            "INSERT INTO claim_links(id,claim_id,evidence_id,relationship_type,confidence,observed_at,recorded_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
            ("link-evidence", self.claim_id, "evidence-support", "supports", .99, T1, T1, "{}"),
        )
        conn.execute(
            "INSERT INTO observation_dependencies(id,downstream_source_observation_id,upstream_source_observation_id,relationship_type,confidence,observed_at,recorded_at,metadata_json) VALUES(?,?,?,?,?,?,?,?)",
            ("dependency-derived", "obs-derived", "obs-primary", "derived_from", .99, T3, T3, "{}"),
        )
        conn.execute(
            "INSERT INTO observation_independence_assertions(id,observation_a_source_observation_id,observation_b_source_observation_id,provenance_evidence_id,verification_status,confidence,observed_at,recorded_at,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
            ("independence-1", "obs-primary", "obs-independent", "evidence-independence", "verified", .99, T2, T2, "{}"),
        )
        conn.commit()
        conn.close()

    def _counts(self):
        conn = self.factory()
        try:
            names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            return {name: conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in names}
        finally:
            conn.close()

    def test_endpoint_resolves_exact_media_and_returns_persisted_context_read_only(self):
        before = self._counts()
        response = self.client.get("/intelligence/result-context", params={"url": "https://primary.example/story"})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["media"]["id"], "media-primary")
        self.assertEqual(payload["primary_claim"]["id"], self.claim_id)
        self.assertEqual(payload["story"]["id"], "story-1")
        self.assertEqual(payload["evidence"]["distinct_source_count"], 4)
        self.assertEqual(payload["evidence"]["verification_pairs"], 1)
        self.assertEqual(payload["evidence"]["independence_status"], "Verified independent reporting")
        relationships = {item["media_item_id"]: item["relationship"] for item in payload["related_reports"]}
        self.assertEqual(relationships["media-official"], "Official stakeholder")
        self.assertEqual(relationships["media-independent"], "Independent reporting")
        self.assertEqual(relationships["media-derived"], "Repeats earlier report")
        self.assertEqual([item["observed_at"] for item in payload["related_reports"]], [T1, T2, T3])
        self.assertEqual(payload["stakeholders"][0]["entity_id"], "entity-club")
        self.assertEqual(payload["policy"]["provider_call_performed"], False)
        self.assertEqual(before, self._counts())
        serialized = response.text.casefold()
        self.assertNotIn("truth_probability", serialized)
        self.assertNotIn("credibility", serialized)
        self.assertNotIn("reliability_score", serialized)
        evolution_times = [item["occurred_at"] for item in payload["evolution"]]
        self.assertEqual(evolution_times, sorted(evolution_times))

    def test_independence_and_stakeholders_are_not_inferred(self):
        conn = self.factory()
        conn.execute("DELETE FROM observation_independence_assertions")
        conn.execute("DELETE FROM verified_source_entity_bindings")
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(
            "INSERT INTO verified_claim_entity_participants VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("participant-unverified", self.claim_id, "entity-club", "actor", "evidence-participant", "unverified", .5, T2, T2, "{}"),
        )
        conn.commit()
        conn.close()
        payload = build_analysis_result_context(url="https://primary.example/story", connection_factory=self.factory)
        self.assertNotEqual(payload["evidence"]["independence_status"], "Verified independent reporting")
        self.assertTrue(all(item["verification_status"] == "verified" for item in payload["stakeholders"]))
        self.assertNotIn("Official stakeholder", {item["relationship"] for item in payload["related_reports"]})
        self.assertNotIn("Independent reporting", {item["relationship"] for item in payload["related_reports"]})
        self.assertNotEqual(payload["evidence"]["distinct_source_count"], payload["evidence"]["verification_pairs"])

    def test_missing_media_is_truthful_and_relationship_vocabulary_is_explicit(self):
        response = self.client.get("/intelligence/result-context", params={"url": "https://missing.example/story"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "no_media_record")
        self.assertEqual(response.json()["related_reports"], [])
        self.assertEqual(_stance_label({"supports"}), "Supports claim")
        self.assertEqual(_stance_label({"qualifies"}), "Qualifies claim")
        self.assertEqual(_stance_label({"contradicts"}), "Contradicts claim")
        self.assertEqual(_stance_label({"reports"}), "")


if __name__ == "__main__":
    unittest.main()
