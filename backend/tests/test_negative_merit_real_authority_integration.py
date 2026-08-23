import json
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND_DIR),
    )


from app.db.connection import (
    connect_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.entities import (
    upsert_canonical_entity,
)

from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)

from app.intelligence.adjudication_history import (
    re_adjudicate_claim,
)

from app.intelligence.claims import (
    record_claim_link,
)

from app.intelligence.evidence import (
    record_evidence,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
    persist_direct_stakeholder_contradiction_verification,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
)

from app.services.machine_verified_revision_runtime import (
    MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
    persist_machine_verified_reference_revision,
)

from app.services.negative_merit_runtime import (
    NEGATIVE_MERIT_RUNTIME_VERSION,
    run_negative_merit_shadow,
)


class NegativeMeritRealAuthorityIntegrationTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp.name
            )
            / "negative-merit-real-authority.db"
        )

        conn = connect_database(
            self.db_path
        )

        try:
            conn.executescript(
                SCHEMA
            )
            conn.commit()

        finally:
            conn.close()

    def tearDown(
        self,
    ):
        self.temp.cleanup()

    def connection_factory(
        self,
    ):
        return connect_database(
            self.db_path
        )

    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip().lower()

    @staticmethod
    def legacy_score():
        return {
            "total": 74,
            "badge": "Good",
            "components": {},
            "calculation": {
                "final_total": 74,
            },
            "reasons": [],
        }

    def seed_graph(
        self,
        *,
        relationship_type="contradicts",
    ):
        conn = self.connection_factory()

        try:
            conn.execute(
                """
                INSERT INTO intelligence_sources (
                  id,
                  source_key,
                  display_name,
                  source_type,
                  canonical_domain,
                  first_seen_at,
                  last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-northbridge-fc",
                    "source|northbridge-fc",
                    "Northbridge FC",
                    "publisher",
                    "northbridgefc.test",
                    "2026-08-23T06:00:00Z",
                    "2026-08-23T06:00:00Z",
                ),
            )

            conn.execute(
                """
                INSERT INTO intelligence_claims (
                  id,
                  canonical_key,
                  subject_key,
                  canonical_text,
                  claim_type,
                  first_seen_at,
                  last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "claim-negative-integration-1",
                    (
                        "article-primary|"
                        "media-negative-integration|"
                        "transfer"
                    ),
                    (
                        "transfer|"
                        "orion-vale|"
                        "northbridge-fc"
                    ),
                    (
                        "Orion Vale has completed "
                        "a transfer to Northbridge FC."
                    ),
                    "transfer",
                    "2026-08-23T06:00:00Z",
                    "2026-08-23T06:00:00Z",
                ),
            )

            conn.execute(
                """
                INSERT INTO source_observations (
                  id,
                  source_id,
                  subject_key,
                  observation_type,
                  status,
                  claim_summary,
                  provenance_url,
                  confidence,
                  observed_at,
                  recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "observation-northbridge-1",
                    "source-northbridge-fc",
                    (
                        "transfer|"
                        "orion-vale|"
                        "northbridge-fc"
                    ),
                    "official_statement",
                    "captured",
                    (
                        "Northbridge FC records "
                        "a contradiction to the "
                        "reported transfer claim."
                    ),
                    (
                        "https://northbridgefc.test/"
                        "official-statement"
                    ),
                    0.99,
                    "2026-08-23T06:10:00Z",
                    "2026-08-23T06:10:01Z",
                ),
            )

            conn.execute(
                """
                INSERT INTO claim_links (
                  id,
                  claim_id,
                  source_observation_id,
                  relationship_type,
                  confidence,
                  observed_at,
                  recorded_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "claim-link-negative-integration-1",
                    "claim-negative-integration-1",
                    "observation-northbridge-1",
                    relationship_type,
                    0.99,
                    "2026-08-23T06:10:00Z",
                    "2026-08-23T06:10:02Z",
                ),
            )

            conn.commit()

        finally:
            conn.close()

    def seed_verified_direct_authority(
        self,
    ):
        entity = (
            upsert_canonical_entity(
                entity_key=(
                    "football|club|northbridge-fc"
                ),
                entity_type="club",
                canonical_name="Northbridge FC",
                sport_key="football",
                seen_at=(
                    "2026-08-23T06:02:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "entity"
            ]
        )

        source_evidence = (
            record_evidence(
                evidence_type=(
                    "entity_resolution_reference"
                ),
                subject_key=(
                    "entity|"
                    + entity[
                        "id"
                    ]
                ),
                observed_at=(
                    "2026-08-23T06:03:00Z"
                ),
                reference_key=(
                    "northbridge-official-site-proof"
                ),
                verification_status="verified",
                recorded_at=(
                    "2026-08-23T06:03:01Z"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "evidence"
            ]
        )

        participant_evidence = (
            record_evidence(
                evidence_type=(
                    "entity_resolution_reference"
                ),
                subject_key=(
                    "transfer|"
                    "orion-vale|"
                    "northbridge-fc"
                ),
                observed_at=(
                    "2026-08-23T06:04:00Z"
                ),
                reference_key=(
                    "northbridge-transfer-participant-proof"
                ),
                verification_status="verified",
                recorded_at=(
                    "2026-08-23T06:04:01Z"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "evidence"
            ]
        )

        source_binding = (
            record_verified_source_entity_binding(
                source_id=(
                    "source-northbridge-fc"
                ),
                entity_id=(
                    entity[
                        "id"
                    ]
                ),
                binding_type=(
                    "official_site"
                ),
                evidence_id=(
                    source_evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-23T06:03:00Z"
                ),
                recorded_at=(
                    "2026-08-23T06:05:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "binding"
            ]
        )

        participant = (
            record_verified_claim_entity_participant(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                entity_id=(
                    entity[
                        "id"
                    ]
                ),
                participant_role=(
                    "destination"
                ),
                evidence_id=(
                    participant_evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-23T06:04:00Z"
                ),
                recorded_at=(
                    "2026-08-23T06:06:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "participant"
            ]
        )

        return {
            "entity": entity,
            "source_evidence": (
                source_evidence
            ),
            "participant_evidence": (
                participant_evidence
            ),
            "source_binding": (
                source_binding
            ),
            "participant": (
                participant
            ),
        }

    def seed_model_adjudication_baseline(
        self,
    ):
        evidence = (
            record_evidence(
                evidence_type=(
                    "model_assisted_snapshot"
                ),
                subject_key=(
                    "transfer|"
                    "orion-vale|"
                    "northbridge-fc"
                ),
                observed_at=(
                    "2026-08-23T06:12:00Z"
                ),
                reference_key=(
                    "negative-two-gate-baseline:"
                    "claim-negative-integration-1"
                ),
                verification_status=(
                    "unverified"
                ),
                recorded_at=(
                    "2026-08-23T06:12:01Z"
                ),
                metadata={
                    "fixture": (
                        "negative_two_gate_baseline"
                    ),
                    "claim_truth_established": False,
                },
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "evidence"
            ]
        )

        record_claim_link(
            claim_id=(
                "claim-negative-integration-1"
            ),
            evidence_id=(
                evidence[
                    "id"
                ]
            ),
            relationship_type=(
                "baseline_semantics"
            ),
            confidence=0.90,
            observed_at=(
                "2026-08-23T06:12:00Z"
            ),
            recorded_at=(
                "2026-08-23T06:12:02Z"
            ),
            metadata={
                "model_assisted": True,
                "claim_truth_established": False,
            },
            connection_factory=(
                self.connection_factory
            ),
        )

        values = {
            "source_role": (
                "publisher"
            ),
            "authority_class": (
                "none"
            ),
            "reliability_class": (
                "unknown"
            ),
            "provenance_class": (
                "attributed_reporting"
            ),
            "stance": (
                "neutral"
            ),
            "independence_status": (
                "unknown"
            ),
        }

        judgments = []

        for field, value in (
            values.items()
        ):
            judgments.append(
                {
                    "id": (
                        "negative-two-gate-model-"
                        + field
                    ),
                    "field": field,
                    "value": value,
                    "confidence": 0.90,
                    "evaluator_id": (
                        "semantic-model-v1"
                    ),
                    "evaluator_family": (
                        "observation_semantic_model"
                    ),
                    "basis_class": (
                        "model_inference"
                    ),
                    "evidence_ids": [
                        evidence[
                            "id"
                        ]
                    ],
                    "training_eligible": False,
                }
            )

        result = (
            re_adjudicate_claim(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                evaluator_runs=[
                    {
                        "run_id": (
                            "negative-two-gate-model-run"
                        ),
                        "evaluator_id": (
                            "semantic-model-v1"
                        ),
                        "evaluator_family": (
                            "observation_semantic_model"
                        ),
                        "derivation_mode": (
                            "model_assisted"
                        ),
                        "judgments": (
                            judgments
                        ),
                    }
                ],
                as_of=(
                    "2026-08-23T06:13:00Z"
                ),
                trigger_type=(
                    "evidence_added"
                ),
                trigger_evidence_ids=[
                    evidence[
                        "id"
                    ]
                ],
                recorded_at=(
                    "2026-08-23T06:13:01Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        return {
            "evidence": evidence,
            "revision": (
                result[
                    "revision"
                ]
            ),
        }

    def seed_machine_verified_contradiction_semantics(
        self,
    ):
        return (
            persist_machine_verified_reference_revision(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                verification_evidence={
                    "observed_at": (
                        "2026-08-23T06:20:00Z"
                    ),
                    "reference_key": (
                        "negative-two-gate-machine-"
                        "contradiction:"
                        "claim-negative-integration-1"
                    ),
                    "claim_summary": (
                        "Orion Vale has completed "
                        "a transfer to Northbridge FC."
                    ),
                    "metadata": {
                        "fixture": (
                            "negative_two_gate_"
                            "machine_semantics"
                        ),
                        "claim_truth_established": False,
                    },
                },
                field_verifications=[
                    {
                        "field": (
                            "stance"
                        ),
                        "value": (
                            "contradicts"
                        ),
                        "confidence": 0.99,
                        "basis_class": (
                            "structured_fact"
                        ),
                    }
                ],
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-23T06:20:01Z"
                ),
            )
        )

    @staticmethod
    def bundle(
        *,
        relationship_type="contradicts",
    ):
        return {
            "claims": [
                {
                    "id": (
                        "claim-negative-integration-1"
                    ),
                    "canonical_key": (
                        "article-primary|"
                        "media-negative-integration|"
                        "transfer"
                    ),
                    "subject_key": (
                        "transfer|"
                        "orion-vale|"
                        "northbridge-fc"
                    ),
                }
            ],
            "claim_links": [
                {
                    "id": (
                        "claim-link-negative-integration-1"
                    ),
                    "claim_id": (
                        "claim-negative-integration-1"
                    ),
                    "source_observation_id": (
                        "observation-northbridge-1"
                    ),
                    "relationship_type": (
                        relationship_type
                    ),
                }
            ],
        }

    def test_real_persisted_two_gate_runtime_qualifies_without_mocks(
        self,
    ):
        self.seed_graph()

        lineage = (
            self.seed_verified_direct_authority()
        )

        baseline = (
            self.seed_model_adjudication_baseline()
        )

        machine = (
            self.seed_machine_verified_contradiction_semantics()
        )

        self.assertEqual(
            machine[
                "version"
            ],
            MACHINE_VERIFIED_REVISION_RUNTIME_VERSION,
        )

        self.assertEqual(
            machine[
                "claim_id"
            ],
            (
                "claim-negative-integration-1"
            ),
        )

        self.assertEqual(
            machine[
                "revision"
            ][
                "previous_revision_id"
            ],
            baseline[
                "revision"
            ][
                "revision_id"
            ],
        )

        machine_stance = [
            judgment
            for run
            in machine[
                "machine_evaluator_runs"
            ]
            for judgment
            in run[
                "judgments"
            ]
            if judgment[
                "field"
            ]
            == "stance"
        ]

        self.assertEqual(
            len(
                machine_stance
            ),
            1,
        )

        self.assertEqual(
            machine_stance[
                0
            ][
                "value"
            ],
            "contradicts",
        )

        self.assertEqual(
            machine_stance[
                0
            ][
                "basis_class"
            ],
            "structured_fact",
        )

        self.assertFalse(
            machine[
                "policy"
            ][
                "semantic_verification_does_not_establish_claim_truth"
            ]
            is False
        )

        runtime = (
            run_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                evidence_bundle=(
                    self.bundle()
                ),
                media_item_id=(
                    "media-negative-integration"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            runtime[
                "version"
            ],
            NEGATIVE_MERIT_RUNTIME_VERSION,
        )

        self.assertEqual(
            runtime[
                "status"
            ],
            (
                "negative_evidence_"
                "calibration_eligible"
            ),
        )

        self.assertEqual(
            runtime[
                "claim_id"
            ],
            (
                "claim-negative-integration-1"
            ),
        )

        self.assertTrue(
            runtime[
                "shadow"
            ][
                "evidence_gates"
            ][
                "direct_authority_contradiction_lineage"
            ]
        )

        self.assertTrue(
            runtime[
                "shadow"
            ][
                "evidence_gates"
            ][
                "machine_verified_contradiction_semantics"
            ]
        )

        self.assertTrue(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "signal"
            ],
            (
                "verified_authority_machine_"
                "semantic_contradiction"
            ),
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "severity_class"
            ],
            (
                "two_gate_negative_"
                "evidence_candidate"
            ),
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            74.0,
        )

        self.assertFalse(
            runtime[
                "live_merit_effect_enabled"
            ]
        )

        self.assertFalse(
            runtime[
                "claim_truth_established"
            ]
        )

        semantic = (
            runtime[
                "semantic_verification"
            ]
        )

        self.assertIsInstance(
            semantic,
            dict,
        )

        self.assertEqual(
            semantic[
                "status"
            ],
            (
                "persisted_verified_machine_"
                "contradiction_semantics"
            ),
        )

        self.assertTrue(
            semantic[
                "persisted"
            ]
        )

        self.assertTrue(
            bool(
                semantic[
                    "evidence_id"
                ]
            )
        )

        conn = (
            self.connection_factory()
        )

        try:
            semantic_row = (
                conn.execute(
                    """
                    SELECT *
                    FROM evidence_records
                    WHERE id = ?
                    """,
                    (
                        semantic[
                            "evidence_id"
                        ],
                    ),
                ).fetchone()
            )

        finally:
            conn.close()

        self.assertIsNotNone(
            semantic_row
        )

        semantic_row = dict(
            semantic_row
        )

        self.assertEqual(
            semantic_row[
                "evidence_type"
            ],
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
        )

        self.assertEqual(
            semantic_row[
                "verification_status"
            ],
            "verified",
        )

        semantic_metadata = json.loads(
            semantic_row[
                "metadata_json"
            ]
        )

        self.assertTrue(
            semantic_metadata[
                "contradiction_semantics_verified"
            ]
        )

        self.assertTrue(
            semantic_metadata[
                "contradiction_semantics_are_source_semantics"
            ]
        )

        self.assertFalse(
            semantic_metadata[
                "claim_truth_established"
            ]
        )

        self.assertFalse(
            semantic_metadata[
                "live_merit_changed"
            ]
        )

        self.assertEqual(
            semantic_metadata[
                "claim_id"
            ],
            (
                "claim-negative-integration-1"
            ),
        )

        self.assertEqual(
            lineage[
                "entity"
            ][
                "canonical_name"
            ],
            "Northbridge FC",
        )

    def test_real_direct_authority_without_semantics_does_not_qualify(
        self,
    ):
        self.seed_graph()

        lineage = (
            self.seed_verified_direct_authority()
        )

        persisted = (
            persist_direct_stakeholder_contradiction_verification(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                observation_id=(
                    "observation-northbridge-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-23T06:11:00Z"
                ),
            )
        )

        self.assertEqual(
            persisted[
                "version"
            ],
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
        )

        self.assertEqual(
            persisted[
                "status"
            ],
            (
                "persisted_verified_direct_"
                "stakeholder_contradiction_lineage"
            ),
        )

        self.assertTrue(
            persisted[
                "persisted"
            ]
        )

        metadata = json.loads(
            persisted[
                "evidence"
            ][
                "metadata_json"
            ]
        )

        self.assertTrue(
            metadata[
                "machine_verified_authority"
            ]
        )

        self.assertTrue(
            metadata[
                "recorded_contradiction_relationship"
            ]
        )

        self.assertFalse(
            metadata[
                "contradiction_semantics_verified"
            ]
        )

        self.assertFalse(
            metadata[
                "claim_truth_established"
            ]
        )

        self.assertEqual(
            metadata[
                "authority_lineage"
            ][
                "entity"
            ][
                "id"
            ],
            lineage[
                "entity"
            ][
                "id"
            ],
        )

        self.assertIn(
            lineage[
                "source_binding"
            ][
                "id"
            ],
            metadata[
                "authority_lineage"
            ][
                "source_binding_ids"
            ],
        )

        self.assertIn(
            lineage[
                "participant"
            ][
                "id"
            ],
            metadata[
                "authority_lineage"
            ][
                "claim_participant_ids"
            ],
        )

        runtime = (
            run_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                evidence_bundle=(
                    self.bundle()
                ),
                media_item_id=(
                    "media-negative-integration"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            runtime[
                "version"
            ],
            NEGATIVE_MERIT_RUNTIME_VERSION,
        )

        self.assertEqual(
            runtime[
                "status"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertFalse(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertTrue(
            runtime[
                "shadow"
            ][
                "evidence_gates"
            ][
                "direct_authority_contradiction_lineage"
            ]
        )

        self.assertFalse(
            runtime[
                "shadow"
            ][
                "evidence_gates"
            ][
                "machine_verified_contradiction_semantics"
            ]
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "adjustment"
            ],
            0.0,
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            74.0,
        )

        self.assertFalse(
            runtime[
                "live_merit_effect_enabled"
            ]
        )

    def test_real_direct_authority_support_only_does_not_qualify(
        self,
    ):
        self.seed_graph(
            relationship_type="supports"
        )

        self.seed_verified_direct_authority()

        persisted = (
            persist_direct_stakeholder_contradiction_verification(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                observation_id=(
                    "observation-northbridge-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertFalse(
            persisted[
                "persisted"
            ]
        )

        self.assertEqual(
            persisted[
                "status"
            ],
            (
                "explicit_contradiction_"
                "not_recorded"
            ),
        )

        runtime = (
            run_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                evidence_bundle=(
                    self.bundle(
                        relationship_type="supports"
                    )
                ),
                media_item_id=(
                    "media-negative-integration"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            runtime[
                "status"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertFalse(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            74.0,
        )

    def test_contradiction_without_verified_authority_fails_closed(
        self,
    ):
        self.seed_graph()

        persisted = (
            persist_direct_stakeholder_contradiction_verification(
                claim_id=(
                    "claim-negative-integration-1"
                ),
                observation_id=(
                    "observation-northbridge-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertFalse(
            persisted[
                "persisted"
            ]
        )

        self.assertEqual(
            persisted[
                "status"
            ],
            (
                "direct_stakeholder_not_verified"
            ),
        )

        runtime = (
            run_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                evidence_bundle=(
                    self.bundle()
                ),
                media_item_id=(
                    "media-negative-integration"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            runtime[
                "status"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertFalse(
            runtime[
                "shadow"
            ][
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            runtime[
                "shadow"
            ][
                "live"
            ][
                "total"
            ],
            74.0,
        )


if __name__ == "__main__":
    unittest.main()
