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

from app.services.canonical_outcome_resolution_verifier import (
    CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE,
    CANONICAL_OUTCOME_PROOF_KIND,
    CANONICAL_OUTCOME_PROOF_RELATIONSHIP,
    CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
    build_canonical_outcome_resolution_candidate,
    persist_canonical_outcome_resolution_verified_revision,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    persist_machine_verified_contradiction_semantics_verification,
)


PLAYER = (
    "football|player|orion-vale"
)

DESTINATION = (
    "football|club|northbridge-fc"
)

ORIGIN = (
    "football|club|southport-fc"
)


class CanonicalOutcomeResolutionVerifierTests(
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
            / "canonical-outcome-resolution.db"
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

    @staticmethod
    def completed_claim():
        return {
            "subject_key": PLAYER,
            "event_type": "transfer",
            "state": "completed",
            "negated": False,
            "roles": {
                "destination": (
                    DESTINATION
                ),
                "origin": ORIGIN,
            },
            "facets": {
                "effective_period": (
                    "2026-summer"
                ),
                "transfer_kind": (
                    "permanent"
                ),
            },
        }

    @staticmethod
    def outcome(
        state="failed",
    ):
        return {
            "subject_key": PLAYER,
            "event_type": "transfer",
            "state": state,
            "negated": False,
            "roles": {
                "destination": (
                    DESTINATION
                ),
                "origin": ORIGIN,
            },
            "facets": {
                "effective_period": (
                    "2026-summer"
                ),
                "transfer_kind": (
                    "permanent"
                ),
            },
        }

    def seed_baseline(
        self,
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
                    "2026-08-23T12:05:00Z"
                ),
                reference_key=(
                    "canonical-outcome-baseline:"
                    + claim[
                        "id"
                    ]
                ),
                verification_status=(
                    "unverified"
                ),
                recorded_at=(
                    "2026-08-23T12:06:00Z"
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
                "2026-08-23T12:05:00Z"
            ),
            recorded_at=(
                "2026-08-23T12:06:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        values = {
            "source_role": "publisher",
            "authority_class": "none",
            "reliability_class": "unknown",
            "provenance_class": (
                "attributed_reporting"
            ),
            "stance": "neutral",
            "independence_status": "unknown",
        }

        judgments = []

        for field, value in values.items():
            judgments.append(
                {
                    "id": (
                        "canonical-outcome-model-"
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
                        ]
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
                            "canonical-outcome-model-run-"
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
                    }
                ],
                as_of=(
                    "2026-08-23T12:10:00Z"
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
                    "2026-08-23T12:11:00Z"
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
        *,
        outcome_state="failed",
        proof_url=None,
        include_participant=True,
        include_claim_structure=True,
    ):
        official_url = (
            "https://www.northbridgefc.test/"
            "news/orion-vale-transfer-update"
        )

        source = (
            upsert_intelligence_source(
                url=(
                    official_url
                ),
                display_name=(
                    "Northbridge FC"
                ),
                source_type="publisher",
                seen_at=(
                    "2026-08-23T12:00:00Z"
                ),
                domain_resolver=(
                    self.domain_resolver
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        claim_metadata = {}

        if include_claim_structure:
            claim_metadata[
                "canonical_claim_candidate"
            ] = self.completed_claim()

        claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "article-primary|"
                    "media-canonical-outcome|"
                    "transfer"
                ),
                subject_key=PLAYER,
                canonical_text=(
                    "Orion Vale has completed "
                    "a transfer to Northbridge FC."
                ),
                claim_type=(
                    "headline_assertion"
                ),
                metadata=(
                    claim_metadata
                ),
                seen_at=(
                    "2026-08-23T12:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        baseline = (
            self.seed_baseline(
                claim
            )
        )

        entity = (
            upsert_canonical_entity(
                entity_key=DESTINATION,
                entity_type="club",
                canonical_name=(
                    "Northbridge FC"
                ),
                sport_key="football",
                seen_at=(
                    "2026-08-23T12:15:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "entity"
            ]
        )

        ownership = (
            record_evidence(
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
                observed_at=(
                    "2026-08-23T12:16:00Z"
                ),
                reference_key=(
                    "northbridge-source-control:"
                    + entity[
                        "id"
                    ]
                ),
                verification_status=(
                    "verified"
                ),
                recorded_at=(
                    "2026-08-23T12:17:00Z"
                ),
                metadata={
                    "machine_verified": True,
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
                    ownership[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-23T12:16:00Z"
                ),
                recorded_at=(
                    "2026-08-23T12:18:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "binding"
            ]
        )

        outcome_proof = (
            record_evidence(
                evidence_type=(
                    CANONICAL_OUTCOME_PROOF_EVIDENCE_TYPE
                ),
                subject_key=(
                    claim[
                        "subject_key"
                    ]
                ),
                observed_at=(
                    "2026-08-23T12:30:00Z"
                ),
                canonical_url=(
                    proof_url
                    or official_url
                ),
                reference_key=(
                    "canonical-outcome-proof:"
                    + claim[
                        "id"
                    ]
                ),
                verification_status=(
                    "verified"
                ),
                recorded_at=(
                    "2026-08-23T12:30:30Z"
                ),
                metadata={
                    "proof_kind": (
                        CANONICAL_OUTCOME_PROOF_KIND
                    ),
                    "source_id": (
                        source[
                            "id"
                        ]
                    ),
                    "claim_id": (
                        claim[
                            "id"
                        ]
                    ),
                    "entity_id": (
                        entity[
                            "id"
                        ]
                    ),
                    "outcome_candidate": (
                        self.outcome(
                            outcome_state
                        )
                    ),
                    "content_sha256": (
                        "a" * 64
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

        proof_link = (
            record_claim_link(
                claim_id=(
                    claim[
                        "id"
                    ]
                ),
                evidence_id=(
                    outcome_proof[
                        "id"
                    ]
                ),
                relationship_type=(
                    CANONICAL_OUTCOME_PROOF_RELATIONSHIP
                ),
                confidence=1.0,
                observed_at=(
                    "2026-08-23T12:30:00Z"
                ),
                recorded_at=(
                    "2026-08-23T12:31:00Z"
                ),
                metadata={
                    "machine_verifiable": True,
                    "claim_truth_established": False,
                },
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "link"
            ]
        )

        participant = None

        if include_participant:
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
                        outcome_proof[
                            "id"
                        ]
                    ),
                    confidence=0.99,
                    observed_at=(
                        "2026-08-23T12:30:00Z"
                    ),
                    recorded_at=(
                        "2026-08-23T12:32:00Z"
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
            "baseline": baseline,
            "entity": entity,
            "ownership": ownership,
            "source_binding": source_binding,
            "outcome_proof": outcome_proof,
            "proof_link": proof_link,
            "participant": participant,
        }

    def test_verified_official_outcome_persists_canonical_resolution(
        self,
    ):
        context = (
            self.seed_context()
        )

        candidate = (
            build_canonical_outcome_resolution_candidate(
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
                        "outcome_proof"
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
            candidate[
                "version"
            ],
            CANONICAL_OUTCOME_RESOLUTION_VERIFIER_VERSION,
        )

        self.assertEqual(
            candidate[
                "status"
            ],
            (
                "verified_canonical_outcome_against_claim"
            ),
        )

        self.assertEqual(
            candidate[
                "canonical_resolution"
            ][
                "status"
            ],
            (
                "resolution_against_claim_candidate"
            ),
        )

        self.assertEqual(
            candidate[
                "candidate"
            ][
                "rule_id"
            ],
            (
                "transfer_completed_then_failed"
            ),
        )

        result = (
            persist_canonical_outcome_resolution_verified_revision(
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
                        "outcome_proof"
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
                    "2026-08-23T12:33:00Z"
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "persisted_verified_canonical_outcome_resolution"
            ),
        )

        self.assertTrue(
            result[
                "persisted"
            ]
        )

        judgments = [
            judgment
            for run
            in result[
                "revision_runtime"
            ][
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
            1,
        )

        self.assertEqual(
            judgments[
                0
            ][
                "field"
            ],
            "stance",
        )

        self.assertEqual(
            judgments[
                0
            ][
                "value"
            ],
            "contradicts",
        )

        self.assertEqual(
            judgments[
                0
            ][
                "basis_class"
            ],
            "canonical_resolution",
        )

        runtime_evidence = (
            result[
                "revision_runtime"
            ][
                "evidence"
            ]
        )

        metadata = json.loads(
            runtime_evidence[
                "metadata_json"
            ]
        )

        self.assertTrue(
            metadata[
                "canonical_outcome_resolution_verified"
            ]
        )

        self.assertTrue(
            metadata[
                "resolved_against_claim"
            ]
        )

        self.assertFalse(
            metadata[
                "claim_truth_established"
            ]
        )

        semantic = (
            persist_machine_verified_contradiction_semantics_verification(
                claim_id=(
                    context[
                        "claim"
                    ][
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-23T12:34:00Z"
                ),
            )
        )

        self.assertTrue(
            semantic[
                "persisted"
            ]
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

    def test_supporting_outcome_does_not_create_negative_resolution(
        self,
    ):
        context = (
            self.seed_context(
                outcome_state="completed"
            )
        )

        result = (
            persist_canonical_outcome_resolution_verified_revision(
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
                        "outcome_proof"
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

        self.assertFalse(
            result[
                "persisted"
            ]
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "canonical_outcome_not_against_claim"
            ),
        )

    def test_proof_url_must_belong_to_verified_source(
        self,
    ):
        context = (
            self.seed_context(
                proof_url=(
                    "https://fake-source.test/"
                    "transfer-update"
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            (
                "does not belong to the "
                "verified source"
            ),
        ):
            build_canonical_outcome_resolution_candidate(
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
                        "outcome_proof"
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

    def test_missing_verified_participant_fails_closed(
        self,
    ):
        context = (
            self.seed_context(
                include_participant=False
            )
        )

        result = (
            build_canonical_outcome_resolution_candidate(
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
                        "outcome_proof"
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

    def test_missing_persisted_claim_structure_fails_closed(
        self,
    ):
        context = (
            self.seed_context(
                include_claim_structure=False
            )
        )

        result = (
            build_canonical_outcome_resolution_candidate(
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
                        "outcome_proof"
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
                "status"
            ],
            (
                "canonical_claim_structure_unavailable"
            ),
        )

        self.assertIsNone(
            result[
                "candidate"
            ]
        )


if __name__ == "__main__":
    unittest.main()
