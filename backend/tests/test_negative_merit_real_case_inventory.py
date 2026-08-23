import hashlib
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

from evals.negative_merit_real_case_inventory import (
    NEGATIVE_MERIT_REAL_CASE_INVENTORY_REPORT_VERSION,
    build_negative_merit_real_case_inventory,
)


class NegativeMeritRealCaseInventoryTests(
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
            / "inventory.db"
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

    def connection(
        self,
    ):
        return connect_database(
            self.db_path
        )

    def seed_case(
        self,
        *,
        suffix,
        authority=False,
        semantics=False,
        resolved=False,
        source_bound=True,
        stored_total=78,
        legacy_total=72,
    ):
        source_id = (
            "source-"
            + suffix
        )

        media_item_id = (
            "media-"
            + suffix
        )

        claim_id = (
            "claim-"
            + suffix
        )

        article_url = (
            "https://publisher-"
            + suffix
            + ".example/story"
        )

        article_hash = (
            "1" * 64
        )

        conn = self.connection()

        try:
            if source_bound:
                conn.execute(
                    """
                    INSERT INTO intelligence_sources (
                      id,
                      source_key,
                      display_name,
                      source_type,
                      canonical_domain,
                      first_seen_at,
                      last_seen_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        (
                            "source-key-"
                            + suffix
                        ),
                        (
                            "Publisher "
                            + suffix
                        ),
                        "publisher",
                        (
                            "publisher-"
                            + suffix
                            + ".example"
                        ),
                        (
                            "2026-08-23T10:00:00+00:00"
                        ),
                        (
                            "2026-08-23T10:30:00+00:00"
                        ),
                        "{}",
                    ),
                )

            conn.execute(
                """
                INSERT INTO media_items (
                  id,
                  canonical_url,
                  mode,
                  source_id,
                  reporter_id,
                  title,
                  published_at,
                  latest_content_hash,
                  first_seen_at,
                  last_seen_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_item_id,
                    article_url,
                    "article",
                    (
                        source_id
                        if source_bound
                        else None
                    ),
                    None,
                    (
                        "Article "
                        + suffix
                    ),
                    None,
                    article_hash,
                    (
                        "2026-08-23T10:00:00+00:00"
                    ),
                    (
                        "2026-08-23T10:30:00+00:00"
                    ),
                    "{}",
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
                  last_seen_at,
                  metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim_id,
                    (
                        "article-primary|"
                        + media_item_id
                        + "|transfer"
                    ),
                    (
                        "football|player|"
                        + suffix
                    ),
                    (
                        "Primary claim "
                        + suffix
                    ),
                    "headline_assertion",
                    (
                        "2026-08-23T10:00:00+00:00"
                    ),
                    (
                        "2026-08-23T10:30:00+00:00"
                    ),
                    "{}",
                ),
            )

            response = {
                "debug": {
                    "live_merit_release": {
                        "legacy_total": (
                            legacy_total
                        ),
                        "live_total": (
                            stored_total
                        ),
                        "adjustment": (
                            stored_total
                            - legacy_total
                        ),
                    },
                    "negative_merit_shadow": {
                        "shadow": {
                            "legacy": {
                                "total": (
                                    legacy_total
                                ),
                            },
                        },
                    },
                },
            }

            conn.execute(
                """
                INSERT INTO analysis_snapshots (
                  media_item_id,
                  story_id,
                  analyzed_at,
                  mode,
                  analysis_version,
                  scoring_version,
                  content_hash,
                  context_hash,
                  merit_score,
                  evidence_score,
                  logic_score,
                  badge,
                  verdict,
                  article_type,
                  score_components_json,
                  score_calculation_json,
                  reasons_json,
                  response_json
                )
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    media_item_id,
                    None,
                    (
                        "2026-08-23T10:31:00+00:00"
                    ),
                    "article",
                    "inventory-test",
                    (
                        "merit-v2-certified-corroboration"
                    ),
                    article_hash,
                    "",
                    stored_total,
                    None,
                    None,
                    "Measured",
                    "",
                    "transfer_rumor",
                    "{}",
                    "{}",
                    "[]",
                    json.dumps(
                        response
                    ),
                ),
            )

            if authority:
                authority_metadata = {
                    "verifier_version": (
                        "direct-stakeholder-"
                        "contradiction-verifier-v1"
                    ),
                    "verification_scope": (
                        "authority_and_persisted_"
                        "relationship_lineage_only"
                    ),
                    "basis": (
                        "verified_direct_stakeholder_"
                        "with_recorded_claim_contradiction"
                    ),
                    "claim_id": (
                        claim_id
                    ),
                    "observation_id": (
                        "observation-"
                        + suffix
                    ),
                    "source_id": (
                        source_id
                    ),
                    "machine_verified_authority": True,
                    "recorded_contradiction_relationship": True,
                    "contradiction_semantics_verified": False,
                    "claim_truth_established": False,
                    "live_merit_changed": False,
                }

                conn.execute(
                    """
                    INSERT INTO evidence_records (
                      id,
                      evidence_key,
                      evidence_type,
                      subject_key,
                      claim_summary,
                      canonical_url,
                      reference_key,
                      verification_status,
                      published_at,
                      observed_at,
                      recorded_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            "authority-evidence-"
                            + suffix
                        ),
                        (
                            "authority-key-"
                            + suffix
                        ),
                        (
                            "direct_stakeholder_"
                            "contradiction_reference"
                        ),
                        (
                            "merit-negative-evidence|"
                            + claim_id
                        ),
                        "",
                        "",
                        (
                            "authority-reference-"
                            + suffix
                        ),
                        "verified",
                        None,
                        (
                            "2026-08-23T10:32:00+00:00"
                        ),
                        (
                            "2026-08-23T10:33:00+00:00"
                        ),
                        json.dumps(
                            authority_metadata
                        ),
                    ),
                )

            if semantics:
                semantic_metadata = {
                    "verifier_version": (
                        "machine-verified-"
                        "contradiction-semantics-"
                        "verifier-v1"
                    ),
                    "claim_id": (
                        claim_id
                    ),
                    "stance": (
                        "contradicts"
                    ),
                    "contradiction_semantics_verified": True,
                    "contradiction_semantics_are_source_semantics": True,
                    "claim_truth_established": False,
                    "live_merit_changed": False,
                }

                conn.execute(
                    """
                    INSERT INTO evidence_records (
                      id,
                      evidence_key,
                      evidence_type,
                      subject_key,
                      claim_summary,
                      canonical_url,
                      reference_key,
                      verification_status,
                      published_at,
                      observed_at,
                      recorded_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            "semantic-evidence-"
                            + suffix
                        ),
                        (
                            "semantic-key-"
                            + suffix
                        ),
                        (
                            "machine_verified_"
                            "contradiction_semantics_reference"
                        ),
                        (
                            "merit-negative-semantic-evidence|"
                            + claim_id
                        ),
                        "",
                        "",
                        (
                            "semantic-reference-"
                            + suffix
                        ),
                        "verified",
                        None,
                        (
                            "2026-08-23T10:34:00+00:00"
                        ),
                        (
                            "2026-08-23T10:35:00+00:00"
                        ),
                        json.dumps(
                            semantic_metadata
                        ),
                    ),
                )

            if resolved:
                official_url = (
                    "https://publisher-"
                    + suffix
                    + ".example/official-outcome"
                )

                outcome_hash = (
                    "a" * 64
                )

                proof_id = (
                    "proof-evidence-"
                    + suffix
                )

                machine_id = (
                    "machine-resolution-"
                    + suffix
                )

                proof_metadata = {
                    "proof_kind": (
                        "explicit_official_"
                        "canonical_outcome"
                    ),
                    "source_id": (
                        source_id
                    ),
                    "claim_id": (
                        claim_id
                    ),
                    "entity_id": (
                        "entity-"
                        + suffix
                    ),
                    "content_sha256": (
                        outcome_hash
                    ),
                    "claim_truth_established": False,
                }

                conn.execute(
                    """
                    INSERT INTO evidence_records (
                      id,
                      evidence_key,
                      evidence_type,
                      subject_key,
                      claim_summary,
                      canonical_url,
                      reference_key,
                      verification_status,
                      published_at,
                      observed_at,
                      recorded_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        proof_id,
                        (
                            "proof-key-"
                            + suffix
                        ),
                        (
                            "canonical_outcome_reference"
                        ),
                        (
                            "football|player|"
                            + suffix
                        ),
                        "",
                        official_url,
                        (
                            "proof-reference-"
                            + suffix
                        ),
                        "verified",
                        None,
                        (
                            "2026-08-23T11:00:00+00:00"
                        ),
                        (
                            "2026-08-23T11:01:00+00:00"
                        ),
                        json.dumps(
                            proof_metadata
                        ),
                    ),
                )

                resolution_metadata = {
                    (
                        "canonical_outcome_"
                        "resolution_verifier_version"
                    ): (
                        "canonical-outcome-"
                        "resolution-verifier-v1"
                    ),
                    "proof_evidence_id": (
                        proof_id
                    ),
                    "content_sha256": (
                        outcome_hash
                    ),
                    "canonical_resolution": {
                        "status": (
                            "resolution_against_"
                            "claim_candidate"
                        ),
                        "direction": (
                            "against_claim"
                        ),
                        "rule_id": (
                            "transfer_completed_"
                            "then_failed"
                        ),
                    },
                    (
                        "canonical_outcome_"
                        "resolution_verified"
                    ): True,
                    "resolved_against_claim": True,
                    "claim_truth_established": False,
                    "live_merit_changed": False,
                }

                conn.execute(
                    """
                    INSERT INTO evidence_records (
                      id,
                      evidence_key,
                      evidence_type,
                      subject_key,
                      claim_summary,
                      canonical_url,
                      reference_key,
                      verification_status,
                      published_at,
                      observed_at,
                      recorded_at,
                      metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        machine_id,
                        (
                            "machine-key-"
                            + suffix
                        ),
                        (
                            "machine_verified_"
                            "semantic_reference"
                        ),
                        (
                            "football|player|"
                            + suffix
                        ),
                        "",
                        official_url,
                        (
                            "machine-reference-"
                            + suffix
                        ),
                        "verified",
                        None,
                        (
                            "2026-08-23T11:00:00+00:00"
                        ),
                        (
                            "2026-08-23T11:02:00+00:00"
                        ),
                        json.dumps(
                            resolution_metadata
                        ),
                    ),
                )

                revision = {
                    "version": (
                        "automated-adjudication-"
                        "state-v1"
                    ),
                    "revision_id": (
                        "revision-"
                        + suffix
                    ),
                    "claim_id": (
                        claim_id
                    ),
                    "adjudication_version": (
                        "inventory-test"
                    ),
                    "adjudication_sha256": (
                        "b" * 64
                    ),
                    "as_of": (
                        "2026-08-23T11:02:00+00:00"
                    ),
                    "previous_revision_id": "",
                    "trigger": {
                        "type": (
                            "evidence_added"
                        ),
                        "evidence_ids": [
                            machine_id
                        ],
                    },
                    "adjudication": {
                        "evaluators": [
                            {
                                "run_id": (
                                    "run-"
                                    + suffix
                                ),
                                "evaluator_id": (
                                    "canonical-resolution-"
                                    "verifier-v1"
                                ),
                                "evaluator_family": (
                                    "canonical_resolution_"
                                    "verifier"
                                ),
                                "derivation_mode": (
                                    "machine_verified"
                                ),
                                "judgments": [
                                    {
                                        "id": (
                                            "judgment-"
                                            + suffix
                                        ),
                                        "field": (
                                            "stance"
                                        ),
                                        "value": (
                                            "contradicts"
                                        ),
                                        "confidence": (
                                            0.99
                                        ),
                                        "basis_class": (
                                            "canonical_resolution"
                                        ),
                                        "evidence_ids": [
                                            machine_id
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                    "transitions": [],
                }

                conn.execute(
                    """
                    INSERT INTO adjudication_state_revisions (
                      id,
                      claim_id,
                      state_version,
                      adjudication_version,
                      adjudication_sha256,
                      as_of,
                      previous_revision_id,
                      trigger_type,
                      trigger_evidence_ids_json,
                      revision_json,
                      recorded_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        (
                            "revision-"
                            + suffix
                        ),
                        claim_id,
                        (
                            "automated-adjudication-"
                            "state-v1"
                        ),
                        (
                            "inventory-test"
                        ),
                        (
                            "b" * 64
                        ),
                        (
                            "2026-08-23T11:02:00+00:00"
                        ),
                        None,
                        (
                            "evidence_added"
                        ),
                        json.dumps(
                            [
                                machine_id
                            ]
                        ),
                        json.dumps(
                            revision
                        ),
                        (
                            "2026-08-23T11:03:00+00:00"
                        ),
                    ),
                )

            conn.commit()

        finally:
            conn.close()

        return {
            "claim_id": claim_id,
            "media_item_id": (
                media_item_id
            ),
        }

    def test_empty_database_is_valid_empty_inventory(
        self,
    ):
        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        self.assertEqual(
            report[
                "version"
            ],
            NEGATIVE_MERIT_REAL_CASE_INVENTORY_REPORT_VERSION,
        )

        self.assertEqual(
            report[
                "status"
            ],
            "empty",
        )

        self.assertEqual(
            report[
                "metrics"
            ][
                "primary_claims"
            ],
            0,
        )

        self.assertTrue(
            report[
                "policy"
            ][
                "database_opened_read_only"
            ]
        )

    def test_two_gate_case_is_discovered(
        self,
    ):
        self.seed_case(
            suffix="two-gate",
            authority=True,
            semantics=True,
        )

        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        case = report[
            "cases"
        ][
            0
        ]

        self.assertEqual(
            case[
                "suggested_observation_class"
            ],
            "two_gate_observation",
        )

        self.assertTrue(
            case[
                "evidence_gates"
            ][
                "both"
            ]
        )

        self.assertEqual(
            case[
                "snapshot"
            ][
                "legacy_merit"
            ][
                "total"
            ],
            72.0,
        )

        self.assertEqual(
            case[
                "snapshot"
            ][
                "stored_merit_total"
            ],
            78.0,
        )

        self.assertTrue(
            case[
                "corpus_export_ready"
            ]
        )

    def test_resolved_case_is_discovered_separately(
        self,
    ):
        self.seed_case(
            suffix="resolved",
            authority=True,
            semantics=True,
            resolved=True,
        )

        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        case = report[
            "cases"
        ][
            0
        ]

        self.assertEqual(
            case[
                "suggested_observation_class"
            ],
            (
                "resolved_against_claim_"
                "observation"
            ),
        )

        self.assertTrue(
            case[
                "canonical_resolution"
            ][
                "ready"
            ]
        )

        self.assertEqual(
            case[
                "canonical_resolution"
            ][
                "rule_id"
            ],
            (
                "transfer_completed_"
                "then_failed"
            ),
        )

        self.assertTrue(
            case[
                "corpus_export_ready"
            ]
        )

    def test_no_evidence_case_is_not_called_exclusive(
        self,
    ):
        self.seed_case(
            suffix="no-evidence",
        )

        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        case = report[
            "cases"
        ][
            0
        ]

        self.assertEqual(
            case[
                "suggested_observation_class"
            ],
            "no_negative_evidence_control",
        )

        self.assertTrue(
            case[
                "exclusive_control_review"
            ][
                "required"
            ]
        )

        self.assertFalse(
            case[
                "exclusive_control_review"
            ][
                "machine_classified_as_exclusive"
            ]
        )

    def test_missing_article_source_binding_blocks_export(
        self,
    ):
        self.seed_case(
            suffix="unbound",
            source_bound=False,
        )

        report = (
            build_negative_merit_real_case_inventory(
                db_path=(
                    self.db_path
                )
            )
        )

        case = report[
            "cases"
        ][
            0
        ]

        self.assertFalse(
            case[
                "corpus_export_ready"
            ]
        )

        self.assertIn(
            "article_source_identity_missing",
            case[
                "blockers"
            ],
        )

    def test_inventory_does_not_modify_database_file(
        self,
    ):
        self.seed_case(
            suffix="readonly",
            authority=True,
            semantics=True,
        )

        before = hashlib.sha256(
            self.db_path.read_bytes()
        ).hexdigest()

        build_negative_merit_real_case_inventory(
            db_path=(
                self.db_path
            )
        )

        after = hashlib.sha256(
            self.db_path.read_bytes()
        ).hexdigest()

        self.assertEqual(
            before,
            after,
        )


if __name__ == "__main__":
    unittest.main()
