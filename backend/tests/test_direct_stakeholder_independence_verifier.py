import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.connection import connect_database
from app.db.schema import SCHEMA
from app.intelligence.claims import claim_id_for_canonical_key, record_claim_link, upsert_intelligence_claim
from app.intelligence.dependencies import record_observation_dependency
from app.intelligence.entities import upsert_canonical_entity
from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)
from app.intelligence.evidence import record_evidence
from app.intelligence.observations import record_source_observation
from app.intelligence.sources import source_domain_for_url, upsert_intelligence_source
from app.services.direct_stakeholder_independence_verifier import (
    DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION,
    build_direct_stakeholder_independence_candidate,
    persist_direct_stakeholder_independence_verification,
)


class DirectStakeholderIndependenceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test.db"
        conn = connect_database(self.db_path)
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def connection_factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def normalize_url(value):
        return str(value or "").strip().lower()

    def domain_resolver(self, value):
        return source_domain_for_url(value, normalize_url=self.normalize_url)

    def verified_evidence(self, reference_key, subject_key):
        return record_evidence(
            evidence_type="machine_reference",
            subject_key=subject_key,
            observed_at="2026-08-15T10:00:00Z",
            reference_key=reference_key,
            verification_status="verified",
            recorded_at="2026-08-15T10:00:01Z",
            connection_factory=self.connection_factory,
        )["evidence"]

    def seed(self, *, same_source=False, roles=("origin", "destination")):
        claim = upsert_intelligence_claim(
            canonical_key="transfer|kepa|chelsea|arsenal|2025",
            subject_key="transfer|kepa|chelsea|arsenal",
            canonical_text="Kepa moves from Chelsea to Arsenal.",
            claim_type="transfer",
            seen_at="2026-08-15T10:00:00Z",
            id_resolver=claim_id_for_canonical_key,
            connection_factory=self.connection_factory,
        )

        urls = [
            "https://www.chelseafc.com/en/news/article/kepa-departs-for-arsenal",
            (
                "https://www.chelseafc.com/en/news/article/kepa-second-page"
                if same_source
                else "https://www.arsenal.com/news/kepa-arrizabalaga-signs-arsenal"
            ),
        ]
        names = ["Chelsea", "Chelsea" if same_source else "Arsenal"]
        keys = ["football|club|chelsea", "football|club|chelsea" if same_source else "football|club|arsenal"]

        sources = []
        entities = []
        observations = []

        for index, (url, name, entity_key) in enumerate(zip(urls, names, keys), start=1):
            source = upsert_intelligence_source(
                url=url,
                display_name=name,
                source_type="publisher",
                seen_at="2026-08-15T10:00:00Z",
                domain_resolver=self.domain_resolver,
                connection_factory=self.connection_factory,
            )
            entity = upsert_canonical_entity(
                entity_key=entity_key,
                entity_type="club",
                canonical_name=name,
                sport_key="football",
                seen_at="2026-08-15T10:00:00Z",
                connection_factory=self.connection_factory,
            )["entity"]

            binding_evidence = self.verified_evidence(
                f"binding-{index}",
                f"binding|{source['id']}|{entity['id']}",
            )
            record_verified_source_entity_binding(
                source_id=source["id"],
                entity_id=entity["id"],
                binding_type="official_site",
                evidence_id=binding_evidence["id"],
                confidence=0.99,
                observed_at="2026-08-15T10:00:00Z",
                recorded_at="2026-08-15T10:00:02Z",
                connection_factory=self.connection_factory,
            )

            participant_evidence = self.verified_evidence(
                f"participant-{index}",
                f"participant|{claim['id']}|{entity['id']}",
            )
            record_verified_claim_entity_participant(
                claim_id=claim["id"],
                entity_id=entity["id"],
                participant_role=roles[index - 1],
                evidence_id=participant_evidence["id"],
                confidence=0.99,
                observed_at="2026-08-15T10:00:00Z",
                recorded_at="2026-08-15T10:00:03Z",
                connection_factory=self.connection_factory,
            )

            observation = record_source_observation(
                source_id=source["id"],
                subject_key=claim["subject_key"],
                observation_type="official_statement",
                observed_at=f"2026-08-15T10:0{index}:00Z",
                status="captured",
                claim_summary=claim["canonical_text"],
                provenance_url=url,
                confidence=0.99,
                recorded_at=f"2026-08-15T10:0{index}:01Z",
                normalize_url=self.normalize_url,
                connection_factory=self.connection_factory,
            )["observation"]
            record_claim_link(
                claim_id=claim["id"],
                source_observation_id=observation["id"],
                relationship_type="supports",
                confidence=0.99,
                observed_at=f"2026-08-15T10:0{index}:00Z",
                recorded_at=f"2026-08-15T10:0{index}:02Z",
                connection_factory=self.connection_factory,
            )

            sources.append(source)
            entities.append(entity)
            observations.append(observation)

        return {
            "claim": claim,
            "sources": sources,
            "entities": entities,
            "observations": observations,
        }

    def test_origin_destination_direct_stakeholders_persist_verified_independence(self):
        seeded = self.seed()
        result = persist_direct_stakeholder_independence_verification(
            claim_id=seeded["claim"]["id"],
            left_observation_id=seeded["observations"][0]["id"],
            right_observation_id=seeded["observations"][1]["id"],
            connection_factory=self.connection_factory,
            recorded_at="2026-08-15T10:10:00Z",
        )

        self.assertEqual(result["version"], DIRECT_STAKEHOLDER_INDEPENDENCE_VERIFIER_VERSION)
        self.assertEqual(result["status"], "persisted_verified_direct_stakeholder_independence")
        self.assertTrue(result["persisted"])
        self.assertEqual(result["evidence"]["verification_status"], "verified")
        self.assertEqual(result["assertion"]["assertion"]["verification_status"], "verified")

        candidate = result["candidate"]["candidate"]
        self.assertEqual(candidate["participant_roles"], ["destination", "origin"])
        self.assertEqual(len(candidate["source_ids"]), 2)
        self.assertEqual(len(candidate["entity_ids"]), 2)

    def test_recorded_cross_dependency_fails_closed(self):
        seeded = self.seed()
        first, second = seeded["observations"]
        record_observation_dependency(
            relationship_type="derived_from",
            observed_at="2026-08-15T10:05:00Z",
            confidence=0.99,
            downstream_source_observation_id=second["id"],
            upstream_source_observation_id=first["id"],
            recorded_at="2026-08-15T10:05:01Z",
            connection_factory=self.connection_factory,
        )

        result = build_direct_stakeholder_independence_candidate(
            claim_id=seeded["claim"]["id"],
            left_observation_id=first["id"],
            right_observation_id=second["id"],
            connection_factory=self.connection_factory,
        )
        self.assertEqual(result["status"], "recorded_dependency_conflict")
        self.assertIsNone(result["candidate"])

    def test_same_publisher_fails_closed(self):
        seeded = self.seed(same_source=True, roles=("origin", "origin"))
        result = build_direct_stakeholder_independence_candidate(
            claim_id=seeded["claim"]["id"],
            left_observation_id=seeded["observations"][0]["id"],
            right_observation_id=seeded["observations"][1]["id"],
            connection_factory=self.connection_factory,
        )
        self.assertEqual(result["status"], "same_source")
        self.assertIsNone(result["candidate"])

    def test_non_transfer_role_pair_fails_closed(self):
        seeded = self.seed(roles=("counterparty", "destination"))
        result = build_direct_stakeholder_independence_candidate(
            claim_id=seeded["claim"]["id"],
            left_observation_id=seeded["observations"][0]["id"],
            right_observation_id=seeded["observations"][1]["id"],
            connection_factory=self.connection_factory,
        )
        self.assertEqual(result["status"], "transfer_role_not_verified")
        self.assertIsNone(result["candidate"])


if __name__ == "__main__":
    unittest.main()
