from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.source_reporter_product_history import (
    reporter_history,
    source_history,
)
from app.routes.intelligence_product import build_router


T0 = "2026-09-04T10:00:00+00:00"
T1 = "2026-09-04T10:05:00+00:00"
T2 = "2026-09-04T10:10:00+00:00"
T3 = "2026-09-04T10:15:00+00:00"


def _factory(tmp_path):
    path = tmp_path / "product-history.db"

    def connection_factory():
        return connect_database(path)

    conn = connection_factory()
    try:
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO intelligence_sources (id,source_key,display_name,source_type,canonical_domain,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?,?)",
            ("src-1", "publisher:example.com", "Example Sports", "publisher", "example.com", T0, T3),
        )
        conn.execute(
            "INSERT INTO intelligence_reporters (id,identity_key,display_name,first_seen_at,last_seen_at) VALUES (?,?,?,?,?)",
            ("rep-1", "reporter:jane-doe", "Jane Doe", T0, T3),
        )
        conn.execute(
            "INSERT INTO media_items (id,canonical_url,mode,source_id,reporter_id,title,latest_content_hash,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?,?,?,?)",
            ("media-1", "https://example.com/story", "article", "src-1", "rep-1", "Example story", "hash-1", T0, T3),
        )
        conn.execute(
            "INSERT INTO intelligence_stories (id,canonical_key,canonical_title,status,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?)",
            ("story-1", "story:key", "Example developing story", "developing", T0, T3),
        )
        conn.execute(
            "INSERT INTO intelligence_claims (id,canonical_key,subject_key,canonical_text,claim_type,first_seen_at,last_seen_at) VALUES (?,?,?,?,?,?,?)",
            ("claim-1", "claim:key", "football:example", "A persisted claim", "assertion", T0, T3),
        )
        conn.execute(
            "INSERT INTO story_media_links (story_id,media_item_id,relationship_type,confidence,linked_at) VALUES (?,?,?,?,?)",
            ("story-1", "media-1", "reports", 0.9, T1),
        )
        conn.execute(
            "INSERT INTO story_claim_links (story_id,claim_id,relationship_type,link_basis,linked_at) VALUES (?,?,?,?,?)",
            ("story-1", "claim-1", "exact_claim_group", "downstream_exact_common_claim_id", T1),
        )
        conn.execute(
            "INSERT INTO source_observations (id,source_id,media_item_id,story_id,subject_key,observation_type,status,claim_summary,provenance_url,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("sobs-1", "src-1", "media-1", "story-1", "football:example", "reports", "unresolved", "Source observation", "https://example.com/story", 0.8, T1, T1),
        )
        conn.execute(
            "INSERT INTO reporter_observations (id,reporter_id,source_id,media_item_id,story_id,subject_key,observation_type,status,claim_summary,provenance_url,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("robs-1", "rep-1", "src-1", "media-1", "story-1", "football:example", "reports", "unresolved", "Reporter observation", "https://example.com/story", 0.8, T1, T1),
        )
        conn.execute(
            "INSERT INTO claim_links (id,claim_id,source_observation_id,relationship_type,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?)",
            ("cl-src", "claim-1", "sobs-1", "supports", 0.8, T2, T2),
        )
        conn.execute(
            "INSERT INTO claim_links (id,claim_id,reporter_observation_id,relationship_type,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?)",
            ("cl-rep", "claim-1", "robs-1", "supports", 0.8, T2, T2),
        )
        conn.execute(
            "INSERT INTO evidence_records (id,evidence_key,evidence_type,subject_key,claim_summary,canonical_url,reference_key,verification_status,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("ev-1", "evidence:key", "document", "football:example", "Independence provenance", "https://example.com/evidence", "ref-1", "verified", T2, T2),
        )
        conn.execute(
            "INSERT INTO evidence_links (id,evidence_id,source_id,relationship_type,confidence,linked_at) VALUES (?,?,?,?,?,?)",
            ("el-src", "ev-1", "src-1", "supports", 0.95, T2),
        )
        conn.execute(
            "INSERT INTO evidence_links (id,evidence_id,reporter_id,relationship_type,confidence,linked_at) VALUES (?,?,?,?,?,?)",
            ("el-rep", "ev-1", "rep-1", "supports", 0.95, T2),
        )
        conn.execute(
            "INSERT INTO observation_dependencies (id,downstream_reporter_observation_id,upstream_source_observation_id,relationship_type,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?)",
            ("dep-1", "robs-1", "sobs-1", "derived_from", 0.9, T2, T2),
        )
        conn.execute(
            "INSERT INTO observation_independence_assertions (id,observation_a_source_observation_id,observation_b_reporter_observation_id,provenance_evidence_id,verification_status,confidence,observed_at,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            ("ind-1", "sobs-1", "robs-1", "ev-1", "verified", 0.97, T3, T3),
        )
        conn.commit()
    finally:
        conn.close()

    return connection_factory


def test_source_profile_exposes_persisted_history_without_reliability_score(tmp_path):
    factory = _factory(tmp_path)
    result = source_history(source_id="src-1", connection_factory=factory)

    assert result is not None
    assert result["source"]["display_name"] == "Example Sports"
    assert result["counts"]["direct_source_observations"] == 1
    assert result["counts"]["reporter_observations"] == 1
    assert result["counts"]["media_items"] == 1
    assert result["counts"]["claims"] == 1
    assert result["counts"]["stories"] == 1
    assert result["counts"]["reporters"] == 1
    assert result["counts"]["dependency_links"] == 1
    assert result["counts"]["verified_independence_assertions"] == 1
    assert result["counts"]["evidence_links"] == 1
    assert result["policy"]["reporting_volume_is_not_reliability"] is True
    assert result["policy"]["dependency_is_not_falsehood"] is True
    assert result["policy"]["absence_of_verified_independence_is_not_dependence"] is True
    assert "reliability_score" not in result
    assert {event["type"] for event in result["events"]} >= {
        "source_observation",
        "reporter_observation",
        "claim_link",
        "observation_dependency",
        "independence_assertion",
    }


def test_reporter_profile_keeps_source_dependency_and_independence_distinct(tmp_path):
    factory = _factory(tmp_path)
    result = reporter_history(reporter_id="rep-1", connection_factory=factory)

    assert result is not None
    assert result["reporter"]["display_name"] == "Jane Doe"
    assert result["counts"]["observations"] == 1
    assert result["counts"]["sources"] == 1
    assert result["counts"]["dependency_links"] == 1
    assert result["counts"]["independence_assertions"] == 1
    assert result["counts"]["verified_independence_assertions"] == 1
    assert result["sources"][0]["id"] == "src-1"
    assert result["dependencies"][0]["id"] == "dep-1"
    assert result["independence_assertions"][0]["id"] == "ind-1"
    assert "reliability_score" not in result


def test_source_and_reporter_history_routes_are_public_product_endpoints(tmp_path):
    factory = _factory(tmp_path)
    app = FastAPI()
    app.include_router(build_router(connection_factory=factory))
    client = TestClient(app)

    source_response = client.get("/intelligence/sources/src-1/history")
    reporter_response = client.get("/intelligence/reporters/rep-1/history")
    missing_response = client.get("/intelligence/sources/missing/history")

    assert source_response.status_code == 200
    assert source_response.json()["source"]["id"] == "src-1"
    assert reporter_response.status_code == 200
    assert reporter_response.json()["reporter"]["id"] == "rep-1"
    assert missing_response.status_code == 404
