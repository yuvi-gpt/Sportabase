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

from app.intelligence.claims import (
    claim_id_for_canonical_key,
    upsert_intelligence_claim,
)

from app.intelligence.entities import (
    upsert_canonical_entity,
)

from app.intelligence.entity_bindings import (
    VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE,
    VERIFIED_ENTITY_BINDING_VERSION,
    VERIFIED_ENTITY_MATCH_VERSION,
    load_verified_source_claim_entity_matches,
    record_verified_claim_entity_participant,
    record_verified_source_entity_binding,
    verified_claim_entity_participant_id_for_record,
    verified_source_entity_binding_id_for_record,
)

from app.intelligence.evidence import (
    record_evidence,
)

from app.intelligence.sources import (
    source_domain_for_url,
    source_id_for_url,
    source_key_for_url,
    upsert_intelligence_source,
)


class VerifiedEntityBindingTests(
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
            / "entity-bindings.db"
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
                display_name=(
                    "Arsenal"
                ),
                source_type=(
                    "publisher"
                ),
                seen_at=(
                    "2026-08-15T17:00:00Z"
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
                claim_type=(
                    "transfer"
                ),
                seen_at=(
                    "2026-08-15T17:00:00Z"
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
            upsert_canonical_entity(
                entity_key=(
                    "football|club|arsenal"
                ),
                entity_type="club",
                canonical_name="Arsenal",
                sport_key="football",
                seen_at=(
                    "2026-08-15T17:00:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "entity"
            ]
        )

        self.player = (
            upsert_canonical_entity(
                entity_key=(
                    "football|player|player-a"
                ),
                entity_type="player",
                canonical_name="Player A",
                sport_key="football",
                seen_at=(
                    "2026-08-15T17:00:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "entity"
            ]
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
        url,
    ):
        return source_domain_for_url(
            url,
            normalize_url=(
                self.normalize_url
            ),
        )

    def verified_evidence(
        self,
        *,
        key,
        subject_key,
        verified=True,
        observed_at=(
            "2026-08-15T17:30:00Z"
        ),
    ):
        return (
            record_evidence(
                evidence_type=(
                    "entity_resolution_reference"
                ),
                subject_key=subject_key,
                observed_at=(
                    observed_at
                ),
                reference_key=key,
                verification_status=(
                    "verified"
                    if verified
                    else "unverified"
                ),
                recorded_at=(
                    "2026-08-15T17:31:00Z"
                ),
                metadata={
                    "fixture": True,
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

    def test_source_entity_binding_is_deterministic_and_idempotent(
        self,
    ):
        evidence = (
            self.verified_evidence(
                key="arsenal-domain-control",
                subject_key=(
                    "entity|arsenal"
                ),
            )
        )

        kwargs = {
            "source_id": (
                self.source[
                    "id"
                ]
            ),
            "entity_id": (
                self.arsenal[
                    "id"
                ]
            ),
            "binding_type": (
                "official_site"
            ),
            "evidence_id": (
                evidence[
                    "id"
                ]
            ),
            "confidence": 0.99,
            "observed_at": (
                "2026-08-15T17:40:00Z"
            ),
            "recorded_at": (
                "2026-08-15T17:41:00Z"
            ),
            "connection_factory": (
                self.connection_factory
            ),
        }

        first = (
            record_verified_source_entity_binding(
                **kwargs
            )
        )

        second = (
            record_verified_source_entity_binding(
                **kwargs
            )
        )

        expected_id = (
            verified_source_entity_binding_id_for_record(
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
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:40:00Z"
                ),
            )
        )

        self.assertEqual(
            first[
                "version"
            ],
            VERIFIED_ENTITY_BINDING_VERSION,
        )

        self.assertTrue(
            first[
                "created"
            ]
        )

        self.assertFalse(
            second[
                "created"
            ]
        )

        self.assertEqual(
            first[
                "binding"
            ][
                "id"
            ],
            expected_id,
        )

        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            1,
        )

        self.assertTrue(
            first[
                "policy"
            ][
                "binding_alone_does_not_assign_authority_class"
            ]
        )

    def test_claim_entity_participant_is_deterministic_and_idempotent(
        self,
    ):
        evidence = (
            self.verified_evidence(
                key=(
                    "arsenal-claim-participant"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
            )
        )

        kwargs = {
            "claim_id": (
                self.claim[
                    "id"
                ]
            ),
            "entity_id": (
                self.arsenal[
                    "id"
                ]
            ),
            "participant_role": (
                "destination"
            ),
            "evidence_id": (
                evidence[
                    "id"
                ]
            ),
            "confidence": 0.99,
            "observed_at": (
                "2026-08-15T17:45:00Z"
            ),
            "recorded_at": (
                "2026-08-15T17:46:00Z"
            ),
            "connection_factory": (
                self.connection_factory
            ),
        }

        first = (
            record_verified_claim_entity_participant(
                **kwargs
            )
        )

        second = (
            record_verified_claim_entity_participant(
                **kwargs
            )
        )

        expected_id = (
            verified_claim_entity_participant_id_for_record(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                entity_id=(
                    self.arsenal[
                        "id"
                    ]
                ),
                participant_role=(
                    "destination"
                ),
                evidence_id=(
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:45:00Z"
                ),
            )
        )

        self.assertEqual(
            first[
                "participant"
            ][
                "id"
            ],
            expected_id,
        )

        self.assertFalse(
            second[
                "created"
            ]
        )

        self.assertEqual(
            self.count(
                "verified_claim_entity_participants"
            ),
            1,
        )

    def test_unverified_evidence_cannot_create_source_binding(
        self,
    ):
        evidence = (
            self.verified_evidence(
                key="unverified-source",
                subject_key="entity|arsenal",
                verified=False,
            )
        )

        with self.assertRaises(
            ValueError
        ):
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
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:40:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            0,
        )

    def test_unverified_evidence_cannot_create_claim_participant(
        self,
    ):
        evidence = (
            self.verified_evidence(
                key="unverified-participant",
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                verified=False,
            )
        )

        with self.assertRaises(
            ValueError
        ):
            record_verified_claim_entity_participant(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                entity_id=(
                    self.arsenal[
                        "id"
                    ]
                ),
                participant_role=(
                    "destination"
                ),
                evidence_id=(
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:45:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        self.assertEqual(
            self.count(
                "verified_claim_entity_participants"
            ),
            0,
        )

    def test_binding_confidence_floor_is_095(
        self,
    ):
        self.assertEqual(
            VERIFIED_ENTITY_BINDING_MIN_CONFIDENCE,
            0.95,
        )

        evidence = (
            self.verified_evidence(
                key="low-confidence",
                subject_key="entity|arsenal",
            )
        )

        for confidence in (
            0.949,
            1.001,
            True,
        ):
            with self.assertRaises(
                ValueError
            ):
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
                        evidence[
                            "id"
                        ]
                    ),
                    confidence=(
                        confidence
                    ),
                    observed_at=(
                        "2026-08-15T17:40:00Z"
                    ),
                    connection_factory=(
                        self.connection_factory
                    ),
                )

        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            0,
        )

    def test_verified_intersection_creates_authority_candidate_only(
        self,
    ):
        source_evidence = (
            self.verified_evidence(
                key=(
                    "arsenal-official-site"
                ),
                subject_key=(
                    "entity|arsenal"
                ),
            )
        )

        participant_evidence = (
            self.verified_evidence(
                key=(
                    "arsenal-transfer-party"
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
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
                "2026-08-15T17:40:00Z"
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
                self.arsenal[
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
                "2026-08-15T17:45:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        result = (
            load_verified_source_claim_entity_matches(
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
            VERIFIED_ENTITY_MATCH_VERSION,
        )

        self.assertEqual(
            result[
                "match_count"
            ],
            1,
        )

        self.assertEqual(
            result[
                "matches"
            ][0][
                "entity"
            ][
                "id"
            ],
            self.arsenal[
                "id"
            ],
        )

        self.assertEqual(
            result[
                "policy"
            ][
                "authority_class"
            ],
            "",
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "authority_not_adjudicated_here"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "match_is_authority_candidate_only"
            ]
        )

    def test_different_entities_do_not_create_match(
        self,
    ):
        source_evidence = (
            self.verified_evidence(
                key="arsenal-site",
                subject_key="entity|arsenal",
            )
        )

        player_evidence = (
            self.verified_evidence(
                key="player-participant",
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
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
                "2026-08-15T17:40:00Z"
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
                "2026-08-15T17:45:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        result = (
            load_verified_source_claim_entity_matches(
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
                "match_count"
            ],
            0,
        )

    def test_alias_only_cannot_create_verified_binding(
        self,
    ):
        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "verified_claim_entity_participants"
            ),
            0,
        )

    def test_unknown_ids_and_bad_vocab_fail_closed(
        self,
    ):
        evidence = (
            self.verified_evidence(
                key="verified-ref",
                subject_key="entity|arsenal",
            )
        )

        with self.assertRaises(
            ValueError
        ):
            record_verified_source_entity_binding(
                source_id="missing-source",
                entity_id=(
                    self.arsenal[
                        "id"
                    ]
                ),
                binding_type=(
                    "official_site"
                ),
                evidence_id=(
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:40:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        with self.assertRaises(
            ValueError
        ):
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
                    "maybe_official"
                ),
                evidence_id=(
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:40:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        with self.assertRaises(
            ValueError
        ):
            record_verified_claim_entity_participant(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                entity_id=(
                    self.arsenal[
                        "id"
                    ]
                ),
                participant_role=(
                    "rumored_friend"
                ),
                evidence_id=(
                    evidence[
                        "id"
                    ]
                ),
                confidence=0.99,
                observed_at=(
                    "2026-08-15T17:45:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        self.assertEqual(
            self.count(
                "verified_source_entity_bindings"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "verified_claim_entity_participants"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()