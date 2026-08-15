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


from app import main

from app.analysis.observation_semantics import (
    normalize_claim_observation_semantics,
)

from app.analysis.snapshot_assembly import (
    build_model_assisted_evidence_snapshot,
)

from app.services.model_assisted_baseline_runtime import (
    MODEL_ASSISTED_BASELINE_RUNTIME_VERSION,
    persist_model_assisted_baseline_revision,
)

from app.services.validation_dataset_runtime import (
    build_persisted_validation_bundle,
)


class ModelAssistedBaselineRuntimeTests(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.original_db_path = (
            main.DB_PATH
        )

        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )

        main.DB_PATH = (
            Path(
                self.temp_dir.name
            )
            / "baseline-runtime.db"
        )

        main.init_db()

        self.source_url = (
            "https://example.com/"
            "transfer-report"
        )

        self.source = (
            main.upsert_intelligence_source(
                url=(
                    self.source_url
                ),
                display_name=(
                    "Example Publisher"
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

        self.claim = (
            main.upsert_intelligence_claim(
                canonical_key=(
                    "transfer|player-a|"
                    "team-a|join"
                ),
                subject_key=(
                    "transfer|player-a|team-a"
                ),
                canonical_text=(
                    "Player A will join Team A."
                ),
                seen_at=(
                    "2026-08-15T02:05:00Z"
                ),
            )
        )

    def tearDown(
        self,
    ):
        main.DB_PATH = (
            self.original_db_path
        )

        self.temp_dir.cleanup()

    @staticmethod
    def normalize_url(
        value,
    ):
        return str(
            value or ""
        ).strip()

    def raw_semantics(
        self,
    ):
        return {
            "claim_relevance": (
                "same_claim"
            ),
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
                "firsthand_reporting"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [
                (
                    "Publisher reports that "
                    "Player A will join Team A."
                )
            ],
            "source_role_confidence": 0.93,
            "authority_confidence": 0.97,
            "reliability_confidence": 0.50,
            "provenance_confidence": 0.91,
            "stance_confidence": 0.94,
            "dependency_confidence": 0.89,
        }

    def assessment(
        self,
    ):
        return (
            normalize_claim_observation_semantics(
                self.raw_semantics(),
                claim_id=(
                    self.claim[
                        "id"
                    ]
                ),
                source_url=(
                    self.source_url
                ),
                context={},
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

    def assembly(
        self,
        *,
        assessment=None,
    ):
        assessment = (
            assessment
            or self.assessment()
        )

        return (
            build_model_assisted_evidence_snapshot(
                claim={
                    "id": (
                        self.claim[
                            "id"
                        ]
                    ),
                    "canonical_text": (
                        self.claim[
                            "canonical_text"
                        ]
                    ),
                },
                source={
                    "url": (
                        self.source_url
                    ),
                    "actor_id": (
                        "example-publisher"
                    ),
                    "published_at": (
                        "2026-08-15T02:00:00Z"
                    ),
                    "observed_at": (
                        "2026-08-15T02:05:00Z"
                    ),
                },
                semantic_assessment=(
                    assessment
                ),
                as_of=(
                    "2026-08-15T03:00:00Z"
                ),
            )
        )

    def run_runtime(
        self,
        *,
        assessment=None,
        assembly=None,
    ):
        assessment = (
            assessment
            or self.assessment()
        )

        assembly = (
            assembly
            or self.assembly(
                assessment=assessment
            )
        )

        return (
            persist_model_assisted_baseline_revision(
                assembly=assembly,
                semantic_assessment=(
                    assessment
                ),
                source_id=(
                    self.source[
                        "id"
                    ]
                ),
                subject_key=(
                    self.claim[
                        "subject_key"
                    ]
                ),
                recorded_at=(
                    "2026-08-15T03:01:00Z"
                ),
                normalize_url=(
                    self.normalize_url
                ),
                connection_factory=(
                    main.db_conn
                ),
            )
        )

    def count(
        self,
        table,
    ):
        conn = main.db_conn()

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

    def rows(
        self,
        table,
    ):
        conn = main.db_conn()

        try:
            return [
                dict(
                    row
                )
                for row
                in conn.execute(
                    (
                        f"SELECT * FROM {table} "
                        "ORDER BY id"
                    )
                ).fetchall()
            ]

        finally:
            conn.close()

    def test_persists_unverified_snapshot_and_initial_baseline_revision(
        self,
    ):
        result = (
            self.run_runtime()
        )

        self.assertEqual(
            result[
                "version"
            ],
            (
                MODEL_ASSISTED_BASELINE_RUNTIME_VERSION
            ),
        )

        self.assertEqual(
            result[
                "status"
            ],
            "persisted",
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_transitions"
            ),
            6,
        )

        evidence_id = (
            result[
                "snapshot_evidence_id"
            ]
        )

        evidence = (
            self.rows(
                "evidence_records"
            )[0]
        )

        self.assertEqual(
            evidence[
                "id"
            ],
            evidence_id,
        )

        self.assertEqual(
            evidence[
                "verification_status"
            ],
            "unverified",
        )

        revision = result[
            "revision"
        ]

        self.assertEqual(
            revision[
                "previous_revision_id"
            ],
            "",
        )

        self.assertEqual(
            revision[
                "trigger"
            ],
            {
                "type": "evidence_added",
                "evidence_ids": [
                    evidence_id
                ],
            },
        )

        adjudication = (
            revision[
                "adjudication"
            ]
        )

        for run in adjudication[
            "evaluators"
        ]:
            self.assertEqual(
                run[
                    "derivation_mode"
                ],
                "model_assisted",
            )

            self.assertFalse(
                run[
                    "reference_trusted"
                ]
            )

            for judgment in run[
                "judgments"
            ]:
                self.assertEqual(
                    judgment[
                        "evidence_ids"
                    ],
                    [
                        evidence_id
                    ],
                )

                self.assertFalse(
                    judgment[
                        "training_eligible"
                    ]
                )

        for packet in adjudication[
            "fields"
        ].values():
            self.assertFalse(
                packet[
                    "reference_gate"
                ][
                    "training_reference_allowed"
                ]
            )

            self.assertEqual(
                packet[
                    "reference_gate"
                ][
                    "trusted_hard_reference_judgment_ids"
                ],
                [],
            )

        self.assertTrue(
            result[
                "policy"
            ][
                "does_not_change_live_merit"
            ]
        )

    def test_exact_replay_does_not_duplicate_snapshot_or_revision(
        self,
    ):
        assessment = (
            self.assessment()
        )

        assembly = (
            self.assembly(
                assessment=assessment
            )
        )

        first = (
            self.run_runtime(
                assessment=assessment,
                assembly=assembly,
            )
        )

        second = (
            self.run_runtime(
                assessment=assessment,
                assembly=assembly,
            )
        )

        self.assertEqual(
            first[
                "status"
            ],
            "persisted",
        )

        self.assertEqual(
            second[
                "status"
            ],
            "replayed",
        )

        self.assertEqual(
            first[
                "revision"
            ][
                "revision_id"
            ],
            second[
                "revision"
            ][
                "revision_id"
            ],
        )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            1,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_transitions"
            ),
            6,
        )

    def test_unverified_baseline_revision_cannot_create_validation_cases(
        self,
    ):
        self.run_runtime()

        result = (
            build_persisted_validation_bundle(
                connection_factory=(
                    main.db_conn
                )
            )
        )

        summary = result[
            "summary"
        ]

        self.assertEqual(
            summary[
                "persisted_revision_count"
            ],
            1,
        )

        self.assertEqual(
            summary[
                "verified_evidence_count"
            ],
            0,
        )

        self.assertEqual(
            summary[
                "consecutive_pair_count"
            ],
            0,
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
            0,
        )

        self.assertEqual(
            summary[
                "shadow_result_count"
            ],
            0,
        )

    def test_semantic_snapshot_mismatch_fails_before_writes(
        self,
    ):
        assessment = (
            self.assessment()
        )

        assembly = (
            self.assembly(
                assessment=assessment
            )
        )

        tampered = dict(
            assessment
        )

        tampered[
            "source_url"
        ] = (
            "https://other.example/"
            "different-source"
        )

        with self.assertRaises(
            ValueError
        ):
            (
                self.run_runtime(
                    assessment=tampered,
                    assembly=assembly,
                )
            )

        self.assertEqual(
            self.count(
                "evidence_records"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "claim_links"
            ),
            0,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()