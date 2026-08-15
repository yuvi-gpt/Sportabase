import json
import sys
import tempfile
import unittest

from pathlib import Path


BACKEND_DIR = Path(
    __file__
).resolve().parents[1]

if str(
    BACKEND_DIR
) not in sys.path:
    sys.path.insert(
        0,
        str(
            BACKEND_DIR
        ),
    )


from app.db.connection import (
    connect_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.adjudication_history import (
    re_adjudicate_claim,
)

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    record_claim_link,
    upsert_intelligence_claim,
)

from app.intelligence.entities import (
    upsert_canonical_entity,
)

from app.intelligence.entity_bindings import (
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
)

from app.intelligence.evidence import (
    record_evidence,
)

from app.intelligence.sources import (
    source_domain_for_url,
    upsert_intelligence_source,
)

from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
    build_direct_authority_entity_candidate,
    persist_direct_authority_verified_revision,
)


class DirectAuthorityEntityVerifierTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        self.db_path = (
            Path(
                self.temp_dir.name
            )
            / "direct-authority.db"
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

        self.source = (
            upsert_intelligence_source(
                url=(
                    "https://www.arsenal.com/"
                ),
                display_name="Arsenal",
                source_type="publisher",
                seen_at=(
                    "2026-08-15T18:00:00Z"
                ),
                domain_resolver=(
                    self.domain_resolver
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player-a|arsenal|join"
                ),
                subject_key=(
                    "transfer|player-a|arsenal"
                ),
                canonical_text=(
                    "Player A will join Arsenal."
                ),
                claim_type="transfer",
                seen_at=(
                    "2026-08-15T18:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.arsenal = (
            self.entity(
                key=(
                    "football|club|arsenal"
                ),
                entity_type="club",
                name="Arsenal",
            )
        )

        self.player = (
            self.entity(
                key=(
                    "football|player|player-a"
                ),
                entity_type="player",
                name="Player A",
            )
        )

    def tearDown(
        self,
    ):
        self.temp_dir.cleanup()

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

    def domain_resolver(
        self,
        value,
    ):
        return source_domain_for_url(
            value,
            normalize_url=(
                self.normalize_url
            ),
        )

    def entity(
        self,
        *,
        key,
        entity_type,
        name,
    ):
        return (
            upsert_canonical_entity(
                entity_key=key,
                entity_type=(
                    entity_type
                ),
                canonical_name=name,
                sport_key="football",
                seen_at=(
                    "2026-08-15T18:00:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "entity"
            ]
        )

    def evidence(
        self,
        *,
        key,
        subject,
        observed_at,
    ):
        return (
            record_evidence(
                evidence_type=(
                    "entity_resolution_reference"
                ),
                subject_key=subject,
                observed_at=(
                    observed_at
                ),
                reference_key=key,
                verification_status="verified",
                recorded_at=(
                    observed_at
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

    def bind(
        self,
        *,
        entity,
        participant_role,
        suffix="primary",
        source_recorded_at=(
            "2026-08-15T18:21:00Z"
        ),
        participant_recorded_at=(
            "2026-08-15T18:23:00Z"
        ),
    ):
        source_evidence = (
            self.evidence(
                key=(
                    "source-control-"
                    + suffix
                ),
                subject=(
                    "entity|"
                    + entity[
                        "id"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:20:00Z"
                ),
            )
        )

        participant_evidence = (
            self.evidence(
                key=(
                    "claim-participant-"
                    + suffix
                ),
                subject=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:22:00Z"
                ),
            )
        )

        source_binding = (
            record_verified_source_entity_binding(
                source_id=(
                    self.source[
                        "id"
                    ]
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
                    "2026-08-15T18:20:00Z"
                ),
                recorded_at=(
                    source_recorded_at
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
                    self.claim[
                        "id"
                    ]
                ),
                entity_id=(
                    entity[
                        "id"
                    ]
                ),
                participant_role=(
                    participant_role
                ),
                evidence_id=(
                    participant_evidence[
                        "id"
                    ]
                ),
                confidence=0.98,
                observed_at=(
                    "2026-08-15T18:22:00Z"
                ),
                recorded_at=(
                    participant_recorded_at
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "participant"
            ]
        )

        return {
            "source_binding": (
                source_binding
            ),
            "participant": (
                participant
            ),
            "source_evidence": (
                source_evidence
            ),
            "participant_evidence": (
                participant_evidence
            ),
        }

    def seed_baseline(
        self,
    ):
        baseline_evidence = (
            record_evidence(
                evidence_type=(
                    "model_assisted_snapshot"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:05:00Z"
                ),
                reference_key=(
                    "baseline:"
                    + self.claim[
                        "id"
                    ]
                ),
                verification_status=(
                    "unverified"
                ),
                recorded_at=(
                    "2026-08-15T18:06:00Z"
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

        record_claim_link(
            claim_id=(
                self.claim[
                    "id"
                ]
            ),
            evidence_id=(
                baseline_evidence[
                    "id"
                ]
            ),
            relationship_type=(
                "baseline_semantics"
            ),
            confidence=0.90,
            observed_at=(
                "2026-08-15T18:05:00Z"
            ),
            recorded_at=(
                "2026-08-15T18:06:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        return (
            re_adjudicate_claim(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    {
                        "run_id": (
                            "model-run-"
                            + self.claim[
                                "id"
                            ]
                        ),
                        "evaluator_id": (
                            "semantic-model-v1"
                        ),
                        "evaluator_family": (
                            "semantic_model"
                        ),
                        "derivation_mode": (
                            "model_assisted"
                        ),
                        "judgments": [
                            {
                                "id": (
                                    "model-authority-"
                                    + self.claim[
                                        "id"
                                    ]
                                ),
                                "field": (
                                    "authority_class"
                                ),
                                "value": "none",
                                "confidence": 0.90,
                                "evaluator_id": (
                                    "semantic-model-v1"
                                ),
                                "evaluator_family": (
                                    "semantic_model"
                                ),
                                "basis_class": (
                                    "model_inference"
                                ),
                                "evidence_ids": [
                                    baseline_evidence[
                                        "id"
                                    ]
                                ],
                                "training_eligible": False,
                            },
                        ],
                    },
                ],
                as_of=(
                    "2026-08-15T18:10:00Z"
                ),
                trigger_type=(
                    "evidence_added"
                ),
                trigger_evidence_ids=[
                    baseline_evidence[
                        "id"
                    ]
                ],
                recorded_at=(
                    "2026-08-15T18:11:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "revision"
            ]
        )

    def count(
        self,
        table,
    ):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    (
                        "SELECT COUNT(*) "
                        f"FROM {table}"
                    )
                ).fetchone()[0]
            )

        finally:
            conn.close()

    def test_verified_intersection_builds_fixed_direct_authority_candidate(
        self,
    ):
        proof = self.bind(
            entity=self.arsenal,
            participant_role=(
                "destination"
            ),
        )

        result = (
            build_direct_authority_entity_candidate(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "verified_direct_stakeholder",
        )

        candidate = result[
            "candidate"
        ]

        self.assertEqual(
            candidate[
                "entity"
            ][
                "id"
            ],
            self.arsenal[
                "id"
            ],
        )

        self.assertEqual(
            candidate[
                "source_role"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            candidate[
                "authority_class"
            ],
            "direct",
        )

        self.assertEqual(
            candidate[
                "confidence"
            ],
            0.98,
        )

        self.assertEqual(
            candidate[
                "availability_at"
            ],
            "2026-08-15T18:23:00+00:00",
        )

        fields = {
            row[
                "field"
            ]: row
            for row
            in candidate[
                "field_verifications"
            ]
        }

        self.assertEqual(
            fields[
                "source_role"
            ][
                "value"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            fields[
                "authority_class"
            ][
                "value"
            ],
            "direct",
        )

        self.assertEqual(
            {
                row[
                    "basis_class"
                ]
                for row
                in fields.values()
            },
            {
                "direct_authority_record",
            },
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "aliases_are_not_authority_evidence"
            ]
        )

    def test_direct_authority_verifier_persists_machine_verified_revision(
        self,
    ):
        baseline = (
            self.seed_baseline()
        )

        proof = self.bind(
            entity=self.arsenal,
            participant_role=(
                "destination"
            ),
        )

        result = (
            persist_direct_authority_verified_revision(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-15T18:24:00Z"
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "persisted_verified_direct_authority"
            ),
        )

        revision = result[
            "revision"
        ]

        self.assertEqual(
            revision[
                "previous_revision_id"
            ],
            baseline[
                "revision_id"
            ],
        )

        self.assertEqual(
            revision[
                "trigger"
            ][
                "type"
            ],
            "evidence_verified",
        )

        authority = (
            revision[
                "fields"
            ][
                "authority_class"
            ]
        )

        self.assertEqual(
            authority[
                "state"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            authority[
                "state"
            ][
                "value"
            ],
            "direct",
        )

        runtime = (
            result[
                "revision_runtime"
            ]
        )

        machine_fields = {
            judgment[
                "field"
            ]: judgment
            for run
            in runtime[
                "machine_evaluator_runs"
            ]
            for judgment
            in run[
                "judgments"
            ]
        }

        self.assertEqual(
            machine_fields[
                "source_role"
            ][
                "value"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            machine_fields[
                "authority_class"
            ][
                "value"
            ],
            "direct",
        )

        self.assertEqual(
            {
                judgment[
                    "basis_class"
                ]
                for judgment
                in machine_fields.values()
            },
            {
                "direct_authority_record",
            },
        )

        metadata = json.loads(
            runtime[
                "evidence"
            ][
                "metadata_json"
            ]
        )

        self.assertIn(
            proof[
                "source_evidence"
            ][
                "id"
            ],
            metadata[
                "source_evidence_ids"
            ],
        )

        self.assertIn(
            proof[
                "participant_evidence"
            ][
                "id"
            ],
            metadata[
                "participant_evidence_ids"
            ],
        )

        self.assertFalse(
            metadata[
                "claim_truth_established"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "authority_values_are_verifier_fixed"
            ]
        )

    def test_multiple_verified_direct_entities_fail_closed(
        self,
    ):
        second_club = (
            self.entity(
                key=(
                    "football|club|second-club"
                ),
                entity_type="club",
                name="Second Club",
            )
        )

        self.seed_baseline()

        self.bind(
            entity=self.arsenal,
            participant_role=(
                "destination"
            ),
            suffix="arsenal",
        )

        self.bind(
            entity=second_club,
            participant_role=(
                "origin"
            ),
            suffix="second",
        )

        before_evidence = (
            self.count(
                "evidence_records"
            )
        )

        before_revisions = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        candidate = (
            build_direct_authority_entity_candidate(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            candidate[
                "status"
            ],
            (
                "ambiguous_verified_direct_stakeholder_match"
            ),
        )

        self.assertEqual(
            len(
                candidate[
                    "candidate_entity_ids"
                ]
            ),
            2,
        )

        result = (
            persist_direct_authority_verified_revision(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertFalse(
            result[
                "persisted"
            ]
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            before_evidence,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            before_revisions,
        )

    def test_governing_body_is_not_laundered_into_direct_authority(
        self,
    ):
        governing_body = (
            self.entity(
                key=(
                    "football|governing-body|fa"
                ),
                entity_type=(
                    "governing_body"
                ),
                name="The FA",
            )
        )

        self.bind(
            entity=governing_body,
            participant_role=(
                "governing_body"
            ),
            suffix="fa",
        )

        result = (
            build_direct_authority_entity_candidate(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "no_verified_direct_stakeholder_match"
            ),
        )

        self.assertIsNone(
            result[
                "candidate"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "governing_bodies_are_not_direct_stakeholders_here"
            ]
        )

    def test_source_and_claim_on_different_entities_do_not_verify(
        self,
    ):
        source_evidence = (
            self.evidence(
                key="source-arsenal",
                subject="entity|arsenal",
                observed_at=(
                    "2026-08-15T18:20:00Z"
                ),
            )
        )

        player_evidence = (
            self.evidence(
                key="claim-player",
                subject=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:22:00Z"
                ),
            )
        )

        record_verified_source_entity_binding(
            source_id=(
                self.source[
                    "id"
                ]
            ),
            entity_id=(
                self.arsenal[
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
                "2026-08-15T18:20:00Z"
            ),
            recorded_at=(
                "2026-08-15T18:21:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        record_verified_claim_entity_participant(
            claim_id=(
                self.claim[
                    "id"
                ]
            ),
            entity_id=(
                self.player[
                    "id"
                ]
            ),
            participant_role=(
                "subject"
            ),
            evidence_id=(
                player_evidence[
                    "id"
                ]
            ),
            confidence=0.99,
            observed_at=(
                "2026-08-15T18:22:00Z"
            ),
            recorded_at=(
                "2026-08-15T18:23:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        result = (
            build_direct_authority_entity_candidate(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "no_verified_direct_stakeholder_match"
            ),
        )

    def test_no_verified_binding_means_no_machine_reference(
        self,
    ):
        self.seed_baseline()

        before_evidence = (
            self.count(
                "evidence_records"
            )
        )

        before_revisions = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        result = (
            persist_direct_authority_verified_revision(
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "no_verified_direct_stakeholder_match"
            ),
        )

        self.assertFalse(
            result[
                "persisted"
            ]
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            before_evidence,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            before_revisions,
        )


if __name__ == "__main__":
    unittest.main()