import json
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import Mock


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
from app.db.schema import SCHEMA

from app.analysis.negative_merit import (
    NEGATIVE_MERIT_SHADOW_VERSION,
    build_negative_merit_shadow,
)

from app.services.direct_authority_verifier import (
    DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION,
)

from app.services.direct_stakeholder_contradiction_verifier import (
    DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
    build_direct_stakeholder_contradiction_candidate,
    persist_direct_stakeholder_contradiction_verification,
)


class NegativeMeritEvidenceTests(
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
            / "negative-merit.db"
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

    def seed(
        self,
        *,
        relationship_type=(
            "contradicts"
        ),
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
                    "source-official-club",
                    "source|official-club",
                    "Example FC",
                    "publisher",
                    "examplefc.test",
                    "2026-08-23T05:00:00Z",
                    "2026-08-23T05:00:00Z",
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
                    "claim-transfer-1",
                    "article-primary|media-test-1|transfer",
                    "transfer|test-player|example-fc",
                    "Test Player has joined Example FC.",
                    "transfer",
                    "2026-08-23T05:00:00Z",
                    "2026-08-23T05:00:00Z",
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
                    "observation-official-1",
                    "source-official-club",
                    "transfer|test-player|example-fc",
                    "official_statement",
                    "captured",
                    "Example FC denies completion.",
                    "https://examplefc.test/statement",
                    0.99,
                    "2026-08-23T05:10:00Z",
                    "2026-08-23T05:10:01Z",
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
                    "claim-link-1",
                    "claim-transfer-1",
                    "observation-official-1",
                    relationship_type,
                    0.99,
                    "2026-08-23T05:10:00Z",
                    "2026-08-23T05:10:02Z",
                ),
            )

            conn.commit()

        finally:
            conn.close()

    @staticmethod
    def authority_result():
        return {
            "version": (
                DIRECT_AUTHORITY_ENTITY_VERIFIER_VERSION
            ),
            "status": (
                "verified_direct_stakeholder"
            ),
            "candidate": {
                "entity": {
                    "id": "entity-example-fc",
                    "entity_key": (
                        "football|club|example-fc"
                    ),
                    "entity_type": "club",
                    "sport_key": "football",
                    "canonical_name": (
                        "Example FC"
                    ),
                },
                "source_role": (
                    "primary_stakeholder"
                ),
                "authority_class": "direct",
                "confidence": 0.99,
                "availability_at": (
                    "2026-08-23T05:05:00+00:00"
                ),
                "source_binding_ids": [
                    "binding-1"
                ],
                "claim_participant_ids": [
                    "participant-1"
                ],
                "source_evidence_ids": [
                    "source-evidence-1"
                ],
                "participant_evidence_ids": [
                    "participant-evidence-1"
                ],
            },
        }

    def authority_builder(
        self,
        **kwargs,
    ):
        return self.authority_result()

    @staticmethod
    def legacy_score():
        return {
            "total": 70,
            "badge": "Good",
            "components": {},
            "calculation": {
                "final_total": 70,
            },
            "reasons": [],
        }

    def test_verified_authority_contradiction_lineage_persists(
        self,
    ):
        self.seed()

        candidate = (
            build_direct_stakeholder_contradiction_candidate(
                claim_id="claim-transfer-1",
                observation_id=(
                    "observation-official-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
                authority_candidate_builder=(
                    self.authority_builder
                ),
            )
        )

        self.assertEqual(
            candidate["version"],
            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION,
        )

        self.assertEqual(
            candidate["status"],
            (
                "verified_direct_stakeholder_"
                "contradiction_lineage"
            ),
        )

        self.assertEqual(
            candidate["candidate"][
                "contradiction_link_ids"
            ],
            [
                "claim-link-1"
            ],
        )

        persisted = (
            persist_direct_stakeholder_contradiction_verification(
                claim_id="claim-transfer-1",
                observation_id=(
                    "observation-official-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-23T05:11:00Z"
                ),
                candidate_builder=(
                    lambda **kwargs: candidate
                ),
            )
        )

        self.assertTrue(
            persisted[
                "persisted"
            ]
        )

        evidence = persisted[
            "evidence"
        ]

        self.assertEqual(
            evidence[
                "verification_status"
            ],
            "verified",
        )

        metadata = json.loads(
            evidence[
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

        shadow = (
            build_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                claim_id=(
                    "claim-transfer-1"
                ),
                contradiction_verification=(
                    persisted
                ),
            )
        )

        self.assertEqual(
            shadow[
                "version"
            ],
            NEGATIVE_MERIT_SHADOW_VERSION,
        )

        self.assertEqual(
            shadow[
                "signal"
            ],
            (
                "verified_authority_"
                "contradiction_recorded"
            ),
        )

        self.assertEqual(
            shadow[
                "severity_class"
            ],
            (
                "strong_negative_evidence_candidate"
            ),
        )

        self.assertTrue(
            shadow[
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertFalse(
            shadow[
                "live"
            ][
                "score_effect_enabled"
            ]
        )

        self.assertEqual(
            shadow[
                "live"
            ][
                "total"
            ],
            70.0,
        )

    def test_support_only_does_not_qualify(
        self,
    ):
        self.seed(
            relationship_type="supports"
        )

        builder = Mock(
            return_value=(
                self.authority_result()
            )
        )

        result = (
            build_direct_stakeholder_contradiction_candidate(
                claim_id="claim-transfer-1",
                observation_id=(
                    "observation-official-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
                authority_candidate_builder=(
                    builder
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "explicit_contradiction_"
                "not_recorded"
            ),
        )

        builder.assert_not_called()

    def test_same_observation_support_and_contradiction_fails_closed(
        self,
    ):
        self.seed(
            relationship_type="supports"
        )

        conn = self.connection_factory()

        try:
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
                    "claim-link-2",
                    "claim-transfer-1",
                    "observation-official-1",
                    "contradicts",
                    0.99,
                    "2026-08-23T05:12:00Z",
                    "2026-08-23T05:12:01Z",
                ),
            )
            conn.commit()

        finally:
            conn.close()

        result = (
            build_direct_stakeholder_contradiction_candidate(
                claim_id="claim-transfer-1",
                observation_id=(
                    "observation-official-1"
                ),
                connection_factory=(
                    self.connection_factory
                ),
                authority_candidate_builder=(
                    self.authority_builder
                ),
            )
        )

        self.assertEqual(
            result[
                "status"
            ],
            (
                "same_observation_has_support_"
                "and_contradiction"
            ),
        )

    def test_model_only_or_unverified_result_never_qualifies(
        self,
    ):
        fake = {
            "version": (
                DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
            ),
            "status": (
                "persisted_verified_direct_stakeholder_"
                "contradiction_lineage"
            ),
            "persisted": True,
            "evidence": {
                "evidence_type": (
                    "direct_stakeholder_"
                    "contradiction_reference"
                ),
                "verification_status": (
                    "verified"
                ),
                "subject_key": (
                    "merit-negative-evidence|"
                    "claim-transfer-1"
                ),
                "metadata_json": json.dumps(
                    {
                        "verifier_version": (
                            DIRECT_STAKEHOLDER_CONTRADICTION_VERIFIER_VERSION
                        ),
                        "machine_verified_authority": False,
                        "recorded_contradiction_relationship": True,
                        "contradiction_semantics_verified": False,
                        "claim_truth_established": False,
                        "live_merit_changed": False,
                    }
                ),
            },
        }

        result = (
            build_negative_merit_shadow(
                legacy_score=(
                    self.legacy_score()
                ),
                claim_id=(
                    "claim-transfer-1"
                ),
                contradiction_verification=(
                    fake
                ),
            )
        )

        self.assertEqual(
            result[
                "signal"
            ],
            (
                "no_certified_negative_evidence"
            ),
        )

        self.assertFalse(
            result[
                "proposed"
            ][
                "eligible_for_penalty_calibration"
            ]
        )

        self.assertEqual(
            result[
                "live"
            ][
                "total"
            ],
            70.0,
        )


if __name__ == "__main__":
    unittest.main()
