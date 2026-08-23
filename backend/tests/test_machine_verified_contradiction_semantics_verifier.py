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

from app.intelligence.evidence import (
    record_evidence,
)

from app.services.machine_verified_revision_runtime import (
    persist_machine_verified_reference_revision,
)

from app.services.machine_verified_contradiction_semantics_verifier import (
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
    MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
    build_machine_verified_contradiction_semantics_candidate,
    persist_machine_verified_contradiction_semantics_verification,
)


class MachineVerifiedContradictionSemanticsVerifierTests(
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
            / "negative-semantic-gate.db"
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

        self.claim = (
            upsert_intelligence_claim(
                canonical_key=(
                    "article-primary|"
                    "media-semantic-gate|"
                    "headline"
                ),
                subject_key=(
                    "semantic-gate|"
                    "example-player|"
                    "example-club"
                ),
                canonical_text=(
                    "Example Player has joined "
                    "Example Club."
                ),
                claim_type=(
                    "headline_assertion"
                ),
                seen_at=(
                    "2026-08-23T08:00:00Z"
                ),
                id_resolver=(
                    claim_id_for_canonical_key
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

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

    def seed_model_baseline(
        self,
        *,
        stance="neutral",
    ):
        evidence = (
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
                    "2026-08-23T08:05:00Z"
                ),
                reference_key=(
                    "model-baseline:"
                    + self.claim[
                        "id"
                    ]
                ),
                verification_status=(
                    "unverified"
                ),
                recorded_at=(
                    "2026-08-23T08:06:00Z"
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
                evidence[
                    "id"
                ]
            ),
            relationship_type=(
                "baseline_semantics"
            ),
            confidence=0.90,
            observed_at=(
                "2026-08-23T08:05:00Z"
            ),
            recorded_at=(
                "2026-08-23T08:06:00Z"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        model_values = {
            "source_role": "publisher",
            "authority_class": "none",
            "reliability_class": "unknown",
            "provenance_class": (
                "attributed_reporting"
            ),
            "stance": stance,
            "independence_status": "unknown",
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
                        + self.claim[
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
                    "2026-08-23T08:10:00Z"
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
                    "2026-08-23T08:11:00Z"
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )[
                "revision"
            ]
        )

    def machine_stance(
        self,
        *,
        value,
        observed_at,
        recorded_at,
        reference_suffix,
    ):
        return (
            persist_machine_verified_reference_revision(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                verification_evidence={
                    "observed_at": (
                        observed_at
                    ),
                    "reference_key": (
                        "semantic-gate:"
                        + reference_suffix
                        + ":"
                        + self.claim[
                            "id"
                        ]
                    ),
                    "claim_summary": (
                        self.claim[
                            "canonical_text"
                        ]
                    ),
                    "metadata": {
                        "fixture": (
                            "machine_verified_"
                            "semantic_gate"
                        ),
                        "claim_truth_established": False,
                    },
                },
                field_verifications=[
                    {
                        "field": "stance",
                        "value": value,
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
                    recorded_at
                ),
            )
        )

    def test_machine_verified_contradiction_is_recognized_and_persisted(
        self,
    ):
        self.seed_model_baseline()

        machine = self.machine_stance(
            value="contradicts",
            observed_at=(
                "2026-08-23T08:20:00Z"
            ),
            recorded_at=(
                "2026-08-23T08:21:00Z"
            ),
            reference_suffix=(
                "contradiction"
            ),
        )

        candidate = (
            build_machine_verified_contradiction_semantics_candidate(
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
                "version"
            ],
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_VERIFIER_VERSION,
        )

        self.assertEqual(
            candidate[
                "status"
            ],
            (
                "verified_machine_"
                "contradiction_semantics"
            ),
        )

        self.assertEqual(
            candidate[
                "candidate"
            ][
                "stance"
            ],
            "contradicts",
        )

        self.assertEqual(
            candidate[
                "candidate"
            ][
                "basis_classes"
            ],
            [
                "structured_fact"
            ],
        )

        self.assertIn(
            machine[
                "evidence"
            ][
                "id"
            ],
            candidate[
                "candidate"
            ][
                "semantic_evidence_ids"
            ],
        )

        persisted = (
            persist_machine_verified_contradiction_semantics_verification(
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                connection_factory=(
                    self.connection_factory
                ),
                recorded_at=(
                    "2026-08-23T08:22:00Z"
                ),
            )
        )

        self.assertEqual(
            persisted[
                "status"
            ],
            (
                "persisted_verified_machine_"
                "contradiction_semantics"
            ),
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
                "evidence_type"
            ],
            MACHINE_VERIFIED_CONTRADICTION_SEMANTICS_EVIDENCE_TYPE,
        )

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
                "contradiction_semantics_verified"
            ]
        )

        self.assertTrue(
            metadata[
                "contradiction_semantics_are_source_semantics"
            ]
        )

        self.assertFalse(
            metadata[
                "claim_truth_established"
            ]
        )

        self.assertFalse(
            metadata[
                "live_merit_changed"
            ]
        )

        self.assertEqual(
            persisted[
                "claim_link"
            ][
                "relationship_type"
            ],
            "verifies_semantics",
        )

    def test_model_only_contradiction_is_rejected(
        self,
    ):
        self.seed_model_baseline(
            stance="contradicts"
        )

        candidate = (
            build_machine_verified_contradiction_semantics_candidate(
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
            "no_machine_verified_stance",
        )

        self.assertIsNone(
            candidate[
                "candidate"
            ]
        )

    def test_machine_verified_support_is_not_negative_semantics(
        self,
    ):
        self.seed_model_baseline()

        self.machine_stance(
            value="supports",
            observed_at=(
                "2026-08-23T08:20:00Z"
            ),
            recorded_at=(
                "2026-08-23T08:21:00Z"
            ),
            reference_suffix="support",
        )

        candidate = (
            build_machine_verified_contradiction_semantics_candidate(
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
                "no_machine_verified_"
                "contradiction_semantics"
            ),
        )

        self.assertEqual(
            candidate[
                "machine_stance_values"
            ],
            [
                "supports"
            ],
        )

    def test_conflicting_machine_verified_stance_fails_closed(
        self,
    ):
        self.seed_model_baseline()

        self.machine_stance(
            value="contradicts",
            observed_at=(
                "2026-08-23T08:20:00Z"
            ),
            recorded_at=(
                "2026-08-23T08:21:00Z"
            ),
            reference_suffix=(
                "contradiction"
            ),
        )

        self.machine_stance(
            value="supports",
            observed_at=(
                "2026-08-23T08:30:00Z"
            ),
            recorded_at=(
                "2026-08-23T08:31:00Z"
            ),
            reference_suffix=(
                "support-later"
            ),
        )

        candidate = (
            build_machine_verified_contradiction_semantics_candidate(
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
                "conflicting_machine_"
                "verified_stance"
            ),
        )

        self.assertEqual(
            candidate[
                "machine_stance_values"
            ],
            [
                "contradicts",
                "supports",
            ],
        )

        self.assertIsNone(
            candidate[
                "candidate"
            ]
        )


if __name__ == "__main__":
    unittest.main()
