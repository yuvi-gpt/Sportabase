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


from app.analysis.trusted_validation import (
    validation_partition_for_claim,
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

from app.services.first_party_statement_verifier import (
    FIRST_PARTY_FIXED_BASIS,
    FIRST_PARTY_FIXED_VALUES,
    FIRST_PARTY_STATEMENT_VERIFIER_VERSION,
    build_first_party_statement_semantic_candidate,
    persist_first_party_statement_verified_revision,
)

from app.services.validation_dataset_runtime import (
    build_persisted_validation_bundle,
)


class FirstPartyStatementVerifierTests(
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
            / "first-party-verifier.db"
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

    def claim_for_partition(
        self,
        partition,
        *,
        canonical_text=(
            "Player A signs for Arsenal"
        ),
    ):
        for index in range(
            10000
        ):
            canonical_key = (
                "first-party-verifier|"
                + partition
                + "|"
                + str(
                    index
                )
            )

            claim_id = (
                claim_id_for_canonical_key(
                    canonical_key
                )
            )

            if (
                validation_partition_for_claim(
                    claim_id
                )
                != partition
            ):
                continue

            return (
                upsert_intelligence_claim(
                    canonical_key=(
                        canonical_key
                    ),
                    subject_key=(
                        "first-party-validation|"
                        + claim_id
                    ),
                    canonical_text=(
                        canonical_text
                    ),
                    claim_type=(
                        "headline_assertion"
                    ),
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

        raise AssertionError(
            "Unable to create requested partition."
        )

    def verified_evidence(
        self,
        *,
        evidence_type,
        subject_key,
        reference_key,
        observed_at,
        canonical_url="",
        metadata=None,
    ):
        return (
            record_evidence(
                evidence_type=(
                    evidence_type
                ),
                subject_key=(
                    subject_key
                ),
                observed_at=(
                    observed_at
                ),
                canonical_url=(
                    canonical_url
                ),
                reference_key=(
                    reference_key
                ),
                verification_status=(
                    "verified"
                ),
                recorded_at=(
                    observed_at
                ),
                metadata=(
                    metadata
                    or {}
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

    def seed_baseline(
        self,
        *,
        claim,
    ):
        evidence = (
            record_evidence(
                evidence_type=(
                    "model_assisted_snapshot"
                ),
                subject_key=(
                    claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:05:00Z"
                ),
                reference_key=(
                    "baseline:"
                    + claim[
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
                claim[
                    "id"
                ]
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
                "2026-08-15T18:05:00Z"
            ),
            recorded_at=(
                "2026-08-15T18:06:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        model_values = {
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
            model_values.items()
        ):
            judgments.append(
                {
                    "id": (
                        "model-"
                        + field
                        + "-"
                        + claim[
                            "id"
                        ]
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
                        ],
                    ],
                    "training_eligible": False,
                }
            )

        return (
            re_adjudicate_claim(
                claim_id=(
                    claim[
                        "id"
                    ]
                ),
                evaluator_runs=[
                    {
                        "run_id": (
                            "model-run-"
                            + claim[
                                "id"
                            ]
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
                    },
                ],
                as_of=(
                    "2026-08-15T18:10:00Z"
                ),
                trigger_type=(
                    "evidence_added"
                ),
                trigger_evidence_ids=[
                    evidence[
                        "id"
                    ],
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

    def seed_context(
        self,
        partition,
        *,
        create_proof_link=True,
    ):
        source_url = (
            "https://www.arsenal.com/"
            "news/player-a-signs-for-arsenal"
        )

        source = (
            upsert_intelligence_source(
                url=(
                    source_url
                ),
                display_name=(
                    "Arsenal"
                ),
                source_type=(
                    "publisher"
                ),
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

        claim = (
            self.claim_for_partition(
                partition
            )
        )

        entity = (
            upsert_canonical_entity(
                entity_key=(
                    "football|club|arsenal"
                ),
                entity_type=(
                    "club"
                ),
                canonical_name=(
                    "Arsenal"
                ),
                sport_key=(
                    "football"
                ),
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

        baseline = (
            self.seed_baseline(
                claim=claim
            )
        )

        ownership_evidence = (
            self.verified_evidence(
                evidence_type=(
                    "source_entity_reference"
                ),
                subject_key=(
                    "source-entity|"
                    + source[
                        "id"
                    ]
                    + "|"
                    + entity[
                        "id"
                    ]
                ),
                reference_key=(
                    "ownership:"
                    + entity[
                        "id"
                    ]
                ),
                observed_at=(
                    "2026-08-15T18:20:00Z"
                ),
                metadata={
                    "machine_verified": True,
                    "claim_truth_established": False,
                },
            )
        )

        source_binding = (
            record_verified_source_entity_binding(
                source_id=(
                    source[
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
                    ownership_evidence[
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
            )[
                "binding"
            ]
        )

        proof_evidence = (
            self.verified_evidence(
                evidence_type=(
                    "claim_entity_participant_reference"
                ),
                subject_key=(
                    claim[
                        "subject_key"
                    ]
                ),
                reference_key=(
                    "first-party-proof:"
                    + claim[
                        "id"
                    ]
                ),
                canonical_url=(
                    source_url
                ),
                observed_at=(
                    "2026-08-15T18:22:00Z"
                ),
                metadata={
                    "machine_verified": True,
                    "proof_kind": (
                        "explicit_official_article_participation"
                    ),
                    "entity_id": (
                        entity[
                            "id"
                        ]
                    ),
                    "entity_key": (
                        entity[
                            "entity_key"
                        ]
                    ),
                    "participant_role": (
                        "destination"
                    ),
                    "participant_alias": (
                        "Arsenal"
                    ),
                    "title": (
                        claim[
                            "canonical_text"
                        ]
                    ),
                    "content_sha256": (
                        "a" * 64
                    ),
                    "claim_truth_established": False,
                },
            )
        )

        proof_link = None

        if create_proof_link:
            proof_link = (
                record_claim_link(
                    claim_id=(
                        claim[
                            "id"
                        ]
                    ),
                    evidence_id=(
                        proof_evidence[
                            "id"
                        ]
                    ),
                    relationship_type=(
                        "verifies_entity_participation"
                    ),
                    confidence=1.0,
                    observed_at=(
                        "2026-08-15T18:22:00Z"
                    ),
                    recorded_at=(
                        "2026-08-15T18:22:30Z"
                    ),
                    metadata={
                        "machine_verified": True,
                        "semantic_reference_only": True,
                        "claim_truth_established": False,
                    },
                    connection_factory=(
                        self.connection_factory
                    ),
                )
            )

        participant = (
            record_verified_claim_entity_participant(
                claim_id=(
                    claim[
                        "id"
                    ]
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
                    proof_evidence[
                        "id"
                    ]
                ),
                confidence=0.98,
                observed_at=(
                    "2026-08-15T18:22:00Z"
                ),
                recorded_at=(
                    "2026-08-15T18:23:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "participant"
            ]
        )

        return {
            "source": source,
            "claim": claim,
            "entity": entity,
            "baseline": baseline,
            "ownership_evidence": (
                ownership_evidence
            ),
            "source_binding": (
                source_binding
            ),
            "proof_evidence": (
                proof_evidence
            ),
            "proof_link": (
                proof_link
            ),
            "participant": (
                participant
            ),
        }

    def count(
        self,
        table,
    ):
        conn = (
            self.connection_factory()
        )

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

    def test_candidate_has_six_fixed_fields(
        self,
    ):
        context = (
            self.seed_context(
                "holdout"
            )
        )

        result = (
            build_first_party_statement_semantic_candidate(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    context[
                        "proof_evidence"
                    ][
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
                "version"
            ],
            (
                FIRST_PARTY_STATEMENT_VERIFIER_VERSION
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "verified_first_party_statement"
            ),
        )

        fields = {
            row[
                "field"
            ]: row
            for row
            in result[
                "candidate"
            ][
                "field_verifications"
            ]
        }

        self.assertEqual(
            set(
                fields
            ),
            set(
                FIRST_PARTY_FIXED_VALUES
            ),
        )

        for field in (
            FIRST_PARTY_FIXED_VALUES
        ):
            self.assertEqual(
                fields[
                    field
                ][
                    "value"
                ],
                (
                    FIRST_PARTY_FIXED_VALUES[
                        field
                    ]
                ),
            )

            self.assertEqual(
                fields[
                    field
                ][
                    "basis_class"
                ],
                (
                    FIRST_PARTY_FIXED_BASIS[
                        field
                    ]
                ),
            )

        self.assertEqual(
            fields[
                "reliability_class"
            ][
                "value"
            ],
            "not_applicable",
        )

        self.assertEqual(
            fields[
                "independence_status"
            ][
                "value"
            ],
            "not_applicable",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "reliability_not_applicable_is_not_a_reliability_rating"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "independence_not_applicable_is_not_independence_established"
            ]
        )

    def test_holdout_revision_covers_all_six_without_training(
        self,
    ):
        context = (
            self.seed_context(
                "holdout"
            )
        )

        result = (
            persist_first_party_statement_verified_revision(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    context[
                        "proof_evidence"
                    ][
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
                "persisted_verified_first_party_semantics"
            ),
        )

        runtime = (
            result[
                "revision_runtime"
            ]
        )

        self.assertEqual(
            runtime[
                "partition"
            ],
            "holdout",
        )

        judgments = [
            judgment
            for run
            in runtime[
                "machine_evaluator_runs"
            ]
            for judgment
            in run[
                "judgments"
            ]
        ]

        self.assertEqual(
            len(
                judgments
            ),
            6,
        )

        self.assertTrue(
            all(
                judgment[
                    "training_eligible"
                ]
                is False
                for judgment
                in judgments
            )
        )

        revision = (
            result[
                "revision"
            ]
        )

        self.assertEqual(
            revision[
                "previous_revision_id"
            ],
            context[
                "baseline"
            ][
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

        dataset = (
            build_persisted_validation_bundle(
                connection_factory=(
                    self.connection_factory
                )
            )
        )

        summary = (
            dataset[
                "summary"
            ]
        )

        self.assertEqual(
            summary[
                "calibration_case_count"
            ],
            0,
        )

        self.assertEqual(
            summary[
                "holdout_case_count"
            ],
            6,
        )

        self.assertEqual(
            summary[
                "holdout_claim_count"
            ],
            1,
        )

        self.assertEqual(
            set(
                summary[
                    "holdout_field_coverage"
                ]
            ),
            set(
                FIRST_PARTY_FIXED_VALUES
            ),
        )

        self.assertEqual(
            summary[
                "missing_holdout_fields"
            ],
            [],
        )

    def test_calibration_only_authority_class_can_train(
        self,
    ):
        context = (
            self.seed_context(
                "calibration"
            )
        )

        result = (
            persist_first_party_statement_verified_revision(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    context[
                        "proof_evidence"
                    ][
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

        runtime = (
            result[
                "revision_runtime"
            ]
        )

        self.assertEqual(
            runtime[
                "partition"
            ],
            "calibration",
        )

        training_fields = {
            judgment[
                "field"
            ]
            for run
            in runtime[
                "machine_evaluator_runs"
            ]
            for judgment
            in run[
                "judgments"
            ]
            if (
                judgment[
                    "training_eligible"
                ]
                is True
            )
        }

        self.assertEqual(
            training_fields,
            {
                "authority_class",
            },
        )

        dataset = (
            build_persisted_validation_bundle(
                connection_factory=(
                    self.connection_factory
                )
            )
        )

        summary = (
            dataset[
                "summary"
            ]
        )

        self.assertEqual(
            summary[
                "calibration_case_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "calibration_claim_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "holdout_case_count"
            ],
            0,
        )

    def test_tampered_statement_title_fails_before_machine_write(
        self,
    ):
        context = (
            self.seed_context(
                "holdout"
            )
        )

        conn = (
            self.connection_factory()
        )

        try:
            row = conn.execute(
                """
                SELECT metadata_json
                FROM evidence_records
                WHERE id = ?
                """,
                (
                    context[
                        "proof_evidence"
                    ][
                        "id"
                    ],
                ),
            ).fetchone()

            metadata = json.loads(
                row[
                    "metadata_json"
                ]
            )

            metadata[
                "title"
            ] = (
                "Different statement"
            )

            conn.execute(
                """
                UPDATE evidence_records
                SET metadata_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        metadata,
                        sort_keys=True,
                    ),
                    context[
                        "proof_evidence"
                    ][
                        "id"
                    ],
                ),
            )

            conn.commit()

        finally:
            conn.close()

        evidence_before = (
            self.count(
                "evidence_records"
            )
        )

        revision_before = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly match",
        ):
            persist_first_party_statement_verified_revision(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    context[
                        "proof_evidence"
                    ][
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

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            evidence_before,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            revision_before,
        )

    def test_missing_claim_proof_link_fails_closed(
        self,
    ):
        context = (
            self.seed_context(
                "holdout",
                create_proof_link=False,
            )
        )

        evidence_before = (
            self.count(
                "evidence_records"
            )
        )

        revision_before = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly one",
        ):
            build_first_party_statement_semantic_candidate(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    context[
                        "proof_evidence"
                    ][
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

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            evidence_before,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            revision_before,
        )

    def test_unrelated_verified_evidence_cannot_enter_trust_path(
        self,
    ):
        context = (
            self.seed_context(
                "holdout"
            )
        )

        unrelated = (
            self.verified_evidence(
                evidence_type=(
                    "claim_entity_participant_reference"
                ),
                subject_key=(
                    context[
                        "claim"
                    ][
                        "subject_key"
                    ]
                ),
                reference_key=(
                    "unrelated-proof:"
                    + context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                canonical_url=(
                    "https://www.arsenal.com/"
                    "news/player-a-signs-for-arsenal"
                ),
                observed_at=(
                    "2026-08-15T18:22:10Z"
                ),
                metadata={
                    "machine_verified": True,
                    "proof_kind": (
                        "explicit_official_article_participation"
                    ),
                    "entity_id": (
                        context[
                            "entity"
                        ][
                            "id"
                        ]
                    ),
                    "title": (
                        context[
                            "claim"
                        ][
                            "canonical_text"
                        ]
                    ),
                    "content_sha256": (
                        "b" * 64
                    ),
                    "claim_truth_established": False,
                },
            )
        )

        record_claim_link(
            claim_id=(
                context[
                    "claim"
                ][
                    "id"
                ]
            ),
            evidence_id=(
                unrelated[
                    "id"
                ]
            ),
            relationship_type=(
                "verifies_entity_participation"
            ),
            confidence=1.0,
            observed_at=(
                "2026-08-15T18:22:10Z"
            ),
            recorded_at=(
                "2026-08-15T18:22:20Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        revision_before = (
            self.count(
                "adjudication_state_revisions"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "lineage",
        ):
            persist_first_party_statement_verified_revision(
                source_id=(
                    context[
                        "source"
                    ][
                        "id"
                    ]
                ),
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                proof_evidence_id=(
                    unrelated[
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

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            revision_before,
        )


if __name__ == "__main__":
    unittest.main()
