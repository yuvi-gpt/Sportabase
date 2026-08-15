import copy
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


from app.analysis.adjudication_state import (
    build_adjudication_state_revision,
)

from app.analysis.multi_evaluator_adjudication import (
    build_multi_evaluator_adjudication,
)

from app.db.connection import (
    connect_database,
)

from app.db.migrations import (
    initialize_database,
)

from app.db.schema import (
    SCHEMA,
)

from app.intelligence.adjudication_history import (
    load_latest_adjudication_state_revision,
    persist_adjudication_state_revision,
    re_adjudicate_claim,
)

from app.intelligence.claims import (
    record_claim_link,
)

from app.intelligence.evidence import (
    record_evidence,
)


class AutomatedAdjudicationHistoryTests(
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
            / "adjudication-history.db"
        )

        initialize_database(
            self.connection_factory,
            SCHEMA,
        )

        conn = self.connection_factory()

        try:
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
                VALUES (
                  ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    "claim-1",
                    "claim-one",
                    "subject-1",
                    (
                        "Player A will "
                        "join Team A."
                    ),
                    "assertion",
                    (
                        "2026-08-15T05:00:00+00:00"
                    ),
                    (
                        "2026-08-15T05:00:00+00:00"
                    ),
                    "{}",
                ),
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
        ).strip()

    def count(
        self,
        table,
    ):
        conn = self.connection_factory()

        try:
            return int(
                conn.execute(
                    (
                        f"SELECT COUNT(*) "
                        f"FROM {table}"
                    )
                ).fetchone()[0]
            )

        finally:
            conn.close()

    def seed_evidence(
        self,
        *,
        reference_key,
        linked=True,
    ):
        result = record_evidence(
            evidence_type=(
                "canonical_fact"
            ),
            subject_key="subject-1",
            observed_at=(
                "2026-08-15T06:00:00Z"
            ),
            reference_key=(
                reference_key
            ),
            verification_status=(
                "verified"
            ),
            normalize_url=(
                self.normalize_url
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        evidence_id = (
            result[
                "evidence"
            ][
                "id"
            ]
        )

        if linked:
            record_claim_link(
                claim_id="claim-1",
                relationship_type=(
                    "supports"
                ),
                observed_at=(
                    "2026-08-15T06:00:00Z"
                ),
                evidence_id=(
                    evidence_id
                ),
                connection_factory=(
                    self.connection_factory
                ),
            )

        return evidence_id

    def judgment(
        self,
        *,
        row_id,
        field,
        value,
        confidence,
        evaluator_id,
        evaluator_family,
        basis_class,
        evidence_ids=None,
        training_eligible=False,
    ):
        return {
            "id": row_id,
            "field": field,
            "value": value,
            "confidence": confidence,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "basis_class": (
                basis_class
            ),
            "evidence_ids": (
                evidence_ids
                or []
            ),
            "training_eligible": (
                training_eligible
            ),
        }

    def evaluator_run(
        self,
        *,
        run_id,
        evaluator_id,
        evaluator_family,
        derivation_mode,
        judgments,
    ):
        return {
            "run_id": run_id,
            "evaluator_id": (
                evaluator_id
            ),
            "evaluator_family": (
                evaluator_family
            ),
            "derivation_mode": (
                derivation_mode
            ),
            "judgments": judgments,
        }

    def contested_runs(
        self,
    ):
        return [
            self.evaluator_run(
                run_id="model",
                evaluator_id="model-v1",
                evaluator_family=(
                    "semantic_model"
                ),
                derivation_mode=(
                    "model_assisted"
                ),
                judgments=[
                    self.judgment(
                        row_id="model-authority",
                        field=(
                            "authority_class"
                        ),
                        value="direct",
                        confidence=0.99,
                        evaluator_id=(
                            "model-v1"
                        ),
                        evaluator_family=(
                            "semantic_model"
                        ),
                        basis_class=(
                            "model_inference"
                        ),
                    )
                ],
            ),
            self.evaluator_run(
                run_id="graph",
                evaluator_id="graph-v1",
                evaluator_family=(
                    "provenance_graph"
                ),
                derivation_mode=(
                    "machine_verified"
                ),
                judgments=[
                    self.judgment(
                        row_id="graph-authority",
                        field=(
                            "authority_class"
                        ),
                        value="indirect",
                        confidence=0.96,
                        evaluator_id=(
                            "graph-v1"
                        ),
                        evaluator_family=(
                            "provenance_graph"
                        ),
                        basis_class=(
                            "provenance_graph"
                        ),
                    )
                ],
            ),
        ]

    def verified_runs(
        self,
        evidence_id,
    ):
        return [
            self.evaluator_run(
                run_id="verified",
                evaluator_id=(
                    "authority-record-v1"
                ),
                evaluator_family=(
                    "authority_record"
                ),
                derivation_mode=(
                    "machine_verified"
                ),
                judgments=[
                    self.judgment(
                        row_id=(
                            "verified-authority"
                        ),
                        field=(
                            "authority_class"
                        ),
                        value="direct",
                        confidence=0.99,
                        evaluator_id=(
                            "authority-record-v1"
                        ),
                        evaluator_family=(
                            "authority_record"
                        ),
                        basis_class=(
                            "direct_authority_record"
                        ),
                        evidence_ids=[
                            evidence_id
                        ],
                        training_eligible=True,
                    )
                ],
            )
        ]

    def test_schema_tables_exist(
        self,
    ):
        conn = self.connection_factory()

        try:
            names = {
                row[
                    "name"
                ]
                for row
                in conn.execute(
                    """
                    SELECT name
                    FROM sqlite_master
                    WHERE type = 'table'
                    """
                ).fetchall()
            }

        finally:
            conn.close()

        self.assertIn(
            "adjudication_state_revisions",
            names,
        )

        self.assertIn(
            "adjudication_state_transitions",
            names,
        )

    def test_initial_revision_is_persisted(
        self,
    ):
        result = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
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

    def test_identical_latest_event_is_replay_safe(
        self,
    ):
        kwargs = {
            "claim_id": "claim-1",
            "evaluator_runs": [],
            "as_of": (
                "2026-08-15T05:00:00Z"
            ),
            "trigger_type": (
                "initial_evaluation"
            ),
            "connection_factory": (
                self.connection_factory
            ),
        }

        first = re_adjudicate_claim(
            **kwargs
        )

        second = re_adjudicate_claim(
            **kwargs
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
            second[
                "status"
            ],
            "replayed",
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

    def test_trigger_evidence_must_link_to_claim(
        self,
    ):
        evidence_id = (
            self.seed_evidence(
                reference_key=(
                    "unlinked"
                ),
                linked=False,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not linked to the claim",
        ):
            re_adjudicate_claim(
                claim_id="claim-1",
                evaluator_runs=[],
                as_of=(
                    "2026-08-15T06:00:00Z"
                ),
                trigger_type=(
                    "evidence_added"
                ),
                trigger_evidence_ids=[
                    evidence_id
                ],
                connection_factory=(
                    self.connection_factory
                ),
            )

    def test_contested_can_transition_to_verified_gold(
        self,
    ):
        first = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=(
                self.contested_runs()
            ),
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        self.assertEqual(
            first[
                "revision"
            ][
                "fields"
            ][
                "authority_class"
            ][
                "state"
            ][
                "tier"
            ],
            "contested",
        )

        evidence_id = (
            self.seed_evidence(
                reference_key=(
                    "official-confirmation"
                )
            )
        )

        second = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=(
                self.verified_runs(
                    evidence_id
                )
            ),
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
            trigger_type=(
                "evidence_verified"
            ),
            trigger_evidence_ids=[
                evidence_id
            ],
            connection_factory=(
                self.connection_factory
            ),
        )

        authority = (
            second[
                "revision"
            ][
                "fields"
            ][
                "authority_class"
            ][
                "state"
            ]
        )

        self.assertEqual(
            authority[
                "tier"
            ],
            "auto_gold",
        )

        self.assertTrue(
            authority[
                "training_reference_allowed"
            ]
        )

        transitions = {
            row[
                "field"
            ]: row
            for row
            in second[
                "revision"
            ][
                "transitions"
            ]
        }

        self.assertIn(
            "authority_class",
            transitions,
        )

        self.assertEqual(
            transitions[
                "authority_class"
            ][
                "from_state"
            ][
                "tier"
            ],
            "contested",
        )

        self.assertEqual(
            transitions[
                "authority_class"
            ][
                "to_state"
            ][
                "tier"
            ],
            "auto_gold",
        )

    def test_new_evidence_same_state_has_no_transition(
        self,
    ):
        re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        evidence_id = (
            self.seed_evidence(
                reference_key=(
                    "new-neutral-evidence"
                )
            )
        )

        second = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
            trigger_type=(
                "evidence_added"
            ),
            trigger_evidence_ids=[
                evidence_id
            ],
            connection_factory=(
                self.connection_factory
            ),
        )

        self.assertEqual(
            second[
                "revision"
            ][
                "transitions"
            ],
            [],
        )

        self.assertEqual(
            self.count(
                "adjudication_state_revisions"
            ),
            2,
        )

        self.assertEqual(
            self.count(
                "adjudication_state_transitions"
            ),
            6,
        )

    def test_history_cannot_fork(
        self,
    ):
        first = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        evidence_id = (
            self.seed_evidence(
                reference_key=(
                    "second-event"
                )
            )
        )

        re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T06:00:00Z"
            ),
            trigger_type=(
                "evidence_added"
            ),
            trigger_evidence_ids=[
                evidence_id
            ],
            connection_factory=(
                self.connection_factory
            ),
        )

        adjudication = (
            build_multi_evaluator_adjudication(
                claim_id="claim-1",
                evaluator_runs=[],
            )
        )

        stale = (
            build_adjudication_state_revision(
                adjudication=(
                    adjudication
                ),
                as_of=(
                    "2026-08-15T07:00:00Z"
                ),
                trigger_type=(
                    "evaluator_refresh"
                ),
                previous_revision=(
                    first[
                        "revision"
                    ]
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not the latest claim revision",
        ):
            persist_adjudication_state_revision(
                revision=stale,
                connection_factory=(
                    self.connection_factory
                ),
            )

    def test_tampered_revision_is_rejected(
        self,
    ):
        first = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        tampered = copy.deepcopy(
            first[
                "revision"
            ]
        )

        tampered[
            "fields"
        ][
            "stance"
        ][
            "state"
        ][
            "tier"
        ] = "auto_gold"

        with self.assertRaisesRegex(
            ValueError,
            "collision detected",
        ):
            persist_adjudication_state_revision(
                revision=tampered,
                connection_factory=(
                    self.connection_factory
                ),
            )

    def test_latest_revision_can_be_loaded(
        self,
    ):
        first = re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        latest = (
            load_latest_adjudication_state_revision(
                claim_id="claim-1",
                connection_factory=(
                    self.connection_factory
                ),
            )
        )

        self.assertEqual(
            latest[
                "revision_id"
            ],
            first[
                "revision"
            ][
                "revision_id"
            ],
        )

    def test_re_adjudication_does_not_touch_live_merit(
        self,
    ):
        re_adjudicate_claim(
            claim_id="claim-1",
            evaluator_runs=[],
            as_of=(
                "2026-08-15T05:00:00Z"
            ),
            trigger_type=(
                "initial_evaluation"
            ),
            connection_factory=(
                self.connection_factory
            ),
        )

        self.assertEqual(
            self.count(
                "analysis_snapshots"
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
