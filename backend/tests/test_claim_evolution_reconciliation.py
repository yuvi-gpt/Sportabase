import tempfile
import unittest
from pathlib import Path

from app.db.connection import connect_database
from app.db.migrations import initialize_database
from app.db.schema import SCHEMA
from app.intelligence.claim_evolution import (
    CLAIM_EVOLUTION_VERSION,
    claim_evolution_family,
    classify_claim_evolution,
    load_claim_evolution,
    reconcile_claim_evolution,
    reconcile_claim_evolution_safely,
)
from app.intelligence.claim_materialization import materialize_canonical_claim


SUBJECT = "player|one"
DESTINATION = "club|arsenal"


class ClaimEvolutionReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "sportabase.sqlite3"
        initialize_database(self.factory, SCHEMA)

    def tearDown(self):
        self.tempdir.cleanup()

    def factory(self):
        return connect_database(self.db_path)

    @staticmethod
    def transfer(state, *, negated=False, origin=None, destination=DESTINATION):
        roles = {"destination": destination}
        if origin is not None:
            roles["origin"] = origin
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "transfer",
            "state": state,
            "negated": negated,
            "roles": roles,
            "facets": {},
        }

    @staticmethod
    def contract(state, *, effective_period=None):
        facets = {}
        if effective_period is not None:
            facets["effective_period"] = effective_period
        return {
            "version": "canonical-claim-contract-v1",
            "subject_key": SUBJECT,
            "event_type": "contract",
            "state": state,
            "negated": False,
            "roles": {"organization": DESTINATION},
            "facets": facets,
        }

    def materialize(self, candidate, observed_at):
        result = materialize_canonical_claim(
            candidate=candidate,
            claim_text="structured claim",
            observed_at=observed_at,
            connection_factory=self.factory,
        )
        return result["claim"]["id"]

    def count_links(self):
        conn = self.factory()
        try:
            return int(
                conn.execute(
                    "SELECT COUNT(*) FROM claim_evolution_links"
                ).fetchone()[0]
            )
        finally:
            conn.close()

    def test_family_ignores_state_but_keeps_destination_scope(self):
        interest = claim_evolution_family(self.transfer("interest"))
        completed = claim_evolution_family(self.transfer("completed"))
        chelsea = claim_evolution_family(
            self.transfer("completed", destination="club|chelsea")
        )

        self.assertEqual(interest["status"], "ready")
        self.assertEqual(interest["family_key"], completed["family_key"])
        self.assertNotEqual(interest["family_key"], chelsea["family_key"])
        self.assertFalse(interest["policy"]["affects_live_merit"])

    def test_transfer_forward_progression_is_deterministic(self):
        result = classify_claim_evolution(
            self.transfer("negotiating"),
            self.transfer("completed"),
        )
        self.assertEqual(result["status"], "related")
        self.assertEqual(result["relationship_type"], "progresses_to")
        self.assertEqual(result["reason"], "forward_state_progression")

    def test_transfer_terminal_outcome_resolves_prior_state(self):
        result = classify_claim_evolution(
            self.transfer("negotiating"),
            self.transfer("failed"),
        )
        self.assertEqual(result["status"], "related")
        self.assertEqual(result["relationship_type"], "resolves_to")

    def test_same_state_negation_flip_is_contradiction(self):
        result = classify_claim_evolution(
            self.transfer("completed"),
            self.transfer("completed", negated=True),
        )
        self.assertEqual(result["status"], "related")
        self.assertEqual(result["relationship_type"], "contradicts")
        self.assertEqual(result["reason"], "same_state_negation_flip")

    def test_backward_transition_is_not_auto_linked(self):
        result = classify_claim_evolution(
            self.transfer("completed"),
            self.transfer("interest"),
        )
        self.assertEqual(result["status"], "not_related")
        self.assertEqual(result["reason"], "unsupported_or_backward_transition")

    def test_material_conflict_fails_closed(self):
        result = classify_claim_evolution(
            self.transfer("interest", origin="club|one"),
            self.transfer("negotiating", origin="club|two"),
        )
        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["reason"], "material_conflict")
        self.assertEqual(result["material_conflicts"], ["roles.origin"])

    def test_recurrent_contract_without_period_fails_closed(self):
        family = claim_evolution_family(self.contract("offered"))
        self.assertEqual(family["status"], "insufficient_scope")
        self.assertEqual(
            family["reason"],
            "effective_period_required_for_recurrent_event",
        )

    def test_reconciliation_builds_adjacent_transfer_chain(self):
        interest_id = self.materialize(
            self.transfer("interest"),
            "2026-08-20T10:00:00+00:00",
        )
        negotiating_id = self.materialize(
            self.transfer("negotiating"),
            "2026-08-21T10:00:00+00:00",
        )
        completed_id = self.materialize(
            self.transfer("completed"),
            "2026-08-22T10:00:00+00:00",
        )

        result = reconcile_claim_evolution(
            claim_id=completed_id,
            connection_factory=self.factory,
        )

        self.assertEqual(result["version"], CLAIM_EVOLUTION_VERSION)
        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(result["family_claim_count"], 3)
        self.assertEqual(self.count_links(), 2)

        conn = self.factory()
        try:
            rows = conn.execute(
                """
                SELECT predecessor_claim_id, successor_claim_id, relationship_type
                FROM claim_evolution_links
                ORDER BY observed_at, id
                """
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual(
            [(row[0], row[1], row[2]) for row in rows],
            [
                (interest_id, negotiating_id, "progresses_to"),
                (negotiating_id, completed_id, "progresses_to"),
            ],
        )
        self.assertFalse(result["policy"]["does_not_establish_truth"] is False)
        self.assertFalse(result["policy"]["affects_live_merit"])

    def test_reconciliation_is_idempotent(self):
        self.materialize(
            self.transfer("interest"),
            "2026-08-20T10:00:00+00:00",
        )
        completed_id = self.materialize(
            self.transfer("completed"),
            "2026-08-22T10:00:00+00:00",
        )

        first = reconcile_claim_evolution(
            claim_id=completed_id,
            connection_factory=self.factory,
        )
        second = reconcile_claim_evolution(
            claim_id=completed_id,
            connection_factory=self.factory,
        )

        self.assertEqual(first["status"], "reconciled")
        self.assertEqual(second["status"], "reconciled")
        self.assertEqual(self.count_links(), 1)

    def test_out_of_order_materialization_reconciles_by_observed_time(self):
        completed_id = self.materialize(
            self.transfer("completed"),
            "2026-08-22T10:00:00+00:00",
        )
        interest_id = self.materialize(
            self.transfer("interest"),
            "2026-08-20T10:00:00+00:00",
        )

        result = reconcile_claim_evolution(
            claim_id=interest_id,
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(self.count_links(), 1)
        loaded = load_claim_evolution(
            claim_id=completed_id,
            connection_factory=self.factory,
        )
        self.assertEqual(len(loaded["links"]), 1)
        self.assertEqual(
            loaded["links"][0]["predecessor_claim_id"],
            interest_id,
        )

    def test_material_conflict_creates_no_link(self):
        self.materialize(
            self.transfer("interest", origin="club|one"),
            "2026-08-20T10:00:00+00:00",
        )
        negotiating_id = self.materialize(
            self.transfer("negotiating", origin="club|two"),
            "2026-08-21T10:00:00+00:00",
        )

        result = reconcile_claim_evolution(
            claim_id=negotiating_id,
            connection_factory=self.factory,
        )

        self.assertEqual(result["status"], "reconciled")
        self.assertEqual(self.count_links(), 0)
        self.assertTrue(
            any(item["reason"] == "material_conflict" for item in result["decisions"])
        )

    def test_safe_reconciliation_hides_database_error_message(self):
        def broken_factory():
            raise RuntimeError("secret database endpoint failed")

        result = reconcile_claim_evolution_safely(
            claim_id="claim-1",
            connection_factory=broken_factory,
        )

        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertNotIn("secret", str(result))
        self.assertFalse(result["policy"]["affects_live_merit"])


if __name__ == "__main__":
    unittest.main()
