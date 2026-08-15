import copy
import sys
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


from app.analysis.observation_semantics import (
    normalize_claim_observation_semantics,
)

from app.analysis.snapshot_assembly import (
    ASSEMBLY_STATUSES,
    MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION,
    build_model_assisted_evidence_snapshot,
)


class ModelAssistedSnapshotAssemblyTests(
    unittest.TestCase
):
    def claim(
        self,
    ):
        return {
            "id": "claim-1",
            "canonical_text": (
                "Player A will join Team A."
            ),
        }

    def source(
        self,
        **overrides,
    ):
        data = {
            "url": (
                "https://example.com/team-statement"
            ),
            "actor_id": "team-a",
            "published_at": (
                "2026-08-15T02:00:00Z"
            ),
            "observed_at": (
                "2026-08-15T02:05:00Z"
            ),
        }

        data.update(
            overrides
        )

        return data

    def raw_semantics(
        self,
        **overrides,
    ):
        data = {
            "claim_relevance": (
                "same_claim"
            ),
            "source_role": (
                "primary_stakeholder"
            ),
            "authority_class": (
                "direct"
            ),
            "reliability_class": (
                "unknown"
            ),
            "provenance_class": (
                "direct_statement"
            ),
            "stance": "supports",
            "dependency_status": (
                "no_explicit_dependency_detected"
            ),
            "dependency_targets": [],
            "field_evidence": [
                (
                    "Team A announces "
                    "Player A will join."
                )
            ],
            "source_role_confidence": 0.99,
            "authority_confidence": 0.99,
            "reliability_confidence": 0.50,
            "provenance_confidence": 0.98,
            "stance_confidence": 0.99,
            "dependency_confidence": 0.90,
        }

        data.update(
            overrides
        )

        return data

    def semantics(
        self,
        raw=None,
        *,
        source_url=(
            "https://example.com/team-statement"
        ),
    ):
        if raw is None:
            raw = self.raw_semantics()

        return (
            normalize_claim_observation_semantics(
                raw,
                claim_id="claim-1",
                source_url=source_url,
                context={},
                evaluator_id=(
                    "semantic-model-v1"
                ),
            )
        )

    def build(
        self,
        *,
        source=None,
        assessment=None,
        as_of=(
            "2026-08-15T03:00:00Z"
        ),
    ):
        if source is None:
            source = self.source()

        if assessment is None:
            assessment = self.semantics()

        return (
            build_model_assisted_evidence_snapshot(
                claim=self.claim(),
                source=source,
                semantic_assessment=(
                    assessment
                ),
                as_of=as_of,
            )
        )

    def test_version_and_status_vocabulary(
        self,
    ):
        self.assertEqual(
            MODEL_ASSISTED_SNAPSHOT_ASSEMBLY_VERSION,
            "model-assisted-snapshot-assembly-v1",
        )

        self.assertEqual(
            set(
                ASSEMBLY_STATUSES
            ),
            {
                "assembled",
                "unresolved",
            },
        )

    def test_stakeholder_semantics_assemble_draft_snapshot(
        self,
    ):
        result = self.build()

        self.assertEqual(
            result[
                "status"
            ],
            "assembled",
        )

        snapshot = result[
            "snapshot"
        ]

        self.assertEqual(
            snapshot[
                "review"
            ][
                "status"
            ],
            "draft",
        )

        self.assertEqual(
            snapshot[
                "derivation"
            ][
                "mode"
            ],
            "model_assisted",
        )

        observation = snapshot[
            "observations"
        ][0]

        self.assertEqual(
            observation[
                "source_role"
            ],
            "primary_stakeholder",
        )

        self.assertEqual(
            observation[
                "authority_class"
            ],
            "direct",
        )

        self.assertEqual(
            observation[
                "provenance_class"
            ],
            "direct_statement",
        )

        self.assertEqual(
            observation[
                "stance"
            ],
            "supports",
        )

    def test_model_assisted_stakeholder_can_compute_auto_gold_but_not_train(
        self,
    ):
        result = self.build()

        adjudication = result[
            "authority_adjudication"
        ]

        self.assertEqual(
            adjudication[
                "automatic"
            ][
                "tier"
            ],
            "auto_gold",
        )

        self.assertEqual(
            adjudication[
                "automatic"
            ][
                "value"
            ],
            "stakeholder_confirmed",
        )

        self.assertEqual(
            adjudication[
                "evaluator"
            ][
                "snapshot_derivation_mode"
            ],
            "model_assisted",
        )

        self.assertFalse(
            adjudication[
                "evaluator"
            ][
                "reference_input_trusted"
            ]
        )

        self.assertFalse(
            adjudication[
                "learning_signal"
            ][
                "training_eligible"
            ]
        )

        self.assertEqual(
            adjudication[
                "learning_signal"
            ][
                "status"
            ],
            (
                "reference_blocked_"
                "untrusted_snapshot"
            ),
        )

    def test_explicit_dependency_is_preserved_without_fake_observation_edge(
        self,
    ):
        assessment = self.semantics(
            self.raw_semantics(
                source_role="publisher",
                authority_class="none",
                provenance_class=(
                    "attributed_reporting"
                ),
                dependency_status=(
                    "explicit_dependency"
                ),
                dependency_targets=[
                    "Reporter A",
                    "https://upstream.example/report",
                ],
            )
        )

        result = self.build(
            assessment=assessment
        )

        self.assertEqual(
            result[
                "status"
            ],
            "assembled",
        )

        observation = result[
            "snapshot"
        ][
            "observations"
        ][0]

        self.assertEqual(
            observation[
                "independence_status"
            ],
            "not_established",
        )

        self.assertEqual(
            observation[
                "depends_on_observation_ids"
            ],
            [],
        )

        self.assertEqual(
            result[
                "unresolved_dependency_targets"
            ],
            [
                "Reporter A",
                "https://upstream.example/report",
            ],
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "dependency_targets_are_not_fabricated_as_observation_ids"
            ]
        )

    def test_no_dependency_detection_keeps_publisher_independence_unknown(
        self,
    ):
        assessment = self.semantics(
            self.raw_semantics(
                source_role="publisher",
                authority_class="none",
                provenance_class=(
                    "firsthand_reporting"
                ),
            )
        )

        result = self.build(
            assessment=assessment
        )

        observation = result[
            "snapshot"
        ][
            "observations"
        ][0]

        self.assertEqual(
            observation[
                "independence_status"
            ],
            "unknown",
        )

    def test_unrelated_assessment_does_not_create_snapshot(
        self,
    ):
        assessment = self.semantics(
            self.raw_semantics(
                claim_relevance="unrelated",
                stance="supports",
            )
        )

        result = self.build(
            assessment=assessment
        )

        self.assertEqual(
            result[
                "status"
            ],
            "unresolved",
        )

        self.assertIsNone(
            result[
                "snapshot"
            ]
        )

        self.assertIn(
            "claim_relevance_not_same_claim",
            result[
                "blockers"
            ],
        )

    def test_uncertain_stance_does_not_create_snapshot(
        self,
    ):
        assessment = self.semantics(
            self.raw_semantics(
                stance="uncertain",
            )
        )

        result = self.build(
            assessment=assessment
        )

        self.assertEqual(
            result[
                "status"
            ],
            "unresolved",
        )

        self.assertIn(
            "stance_unresolved",
            result[
                "blockers"
            ],
        )

    def test_model_cannot_smuggle_established_independence(
        self,
    ):
        assessment = copy.deepcopy(
            self.semantics()
        )

        assessment[
            "independence_status"
        ] = "established"

        result = self.build(
            assessment=assessment
        )

        self.assertEqual(
            result[
                "status"
            ],
            "unresolved",
        )

        self.assertIn(
            "model_cannot_establish_independence",
            result[
                "blockers"
            ],
        )

    def test_semantic_claim_mismatch_is_rejected(
        self,
    ):
        assessment = copy.deepcopy(
            self.semantics()
        )

        assessment[
            "claim_id"
        ] = "other-claim"

        with self.assertRaisesRegex(
            ValueError,
            "claim ID does not match",
        ):
            self.build(
                assessment=assessment
            )

    def test_semantic_source_mismatch_is_rejected(
        self,
    ):
        assessment = copy.deepcopy(
            self.semantics()
        )

        assessment[
            "source_url"
        ] = (
            "https://other.example/story"
        )

        with self.assertRaisesRegex(
            ValueError,
            "source URL does not match",
        ):
            self.build(
                assessment=assessment
            )

    def test_model_assisted_semantics_cannot_claim_training_eligibility(
        self,
    ):
        assessment = copy.deepcopy(
            self.semantics()
        )

        assessment[
            "derivation"
        ][
            "training_eligible"
        ] = True

        with self.assertRaisesRegex(
            ValueError,
            "cannot be training eligible",
        ):
            self.build(
                assessment=assessment
            )

    def test_ids_are_deterministic(
        self,
    ):
        first = self.build()
        second = self.build()

        self.assertEqual(
            first[
                "observation_id"
            ],
            second[
                "observation_id"
            ],
        )

        self.assertEqual(
            first[
                "snapshot_id"
            ],
            second[
                "snapshot_id"
            ],
        )

        self.assertEqual(
            first[
                "semantic_assessment_id"
            ],
            second[
                "semantic_assessment_id"
            ],
        )

    def test_source_timing_is_preserved(
        self,
    ):
        result = self.build()

        observation = result[
            "snapshot"
        ][
            "observations"
        ][0]

        self.assertEqual(
            observation[
                "published_at"
            ],
            "2026-08-15T02:00:00Z",
        )

        self.assertEqual(
            observation[
                "observed_at"
            ],
            "2026-08-15T02:05:00Z",
        )

        self.assertEqual(
            observation[
                "availability"
            ][
                "precision"
            ],
            "timestamp",
        )

    def test_capture_metadata_is_preserved_when_available(
        self,
    ):
        source = self.source(
            capture={
                "method": "direct_http",
                "status": "captured",
                "captured_at": (
                    "2026-08-15T02:10:00Z"
                ),
                "content_sha256": (
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                ),
                "note": (
                    "Captured automatically."
                ),
            }
        )

        result = self.build(
            source=source
        )

        capture = result[
            "snapshot"
        ][
            "observations"
        ][0][
            "capture"
        ]

        self.assertEqual(
            capture[
                "method"
            ],
            "direct_http",
        )

        self.assertEqual(
            capture[
                "status"
            ],
            "captured",
        )

        self.assertEqual(
            capture[
                "content_sha256"
            ],
            (
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            ),
        )

    def test_missing_actor_is_rejected(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "actor ID is required",
        ):
            self.build(
                source=self.source(
                    actor_id=""
                )
            )

    def test_assembly_has_no_live_merit_effect(
        self,
    ):
        result = self.build()

        forbidden = {
            "merit",
            "merit_score",
            "score_adjustment",
            "live_total",
            "shadow_total",
        }

        self.assertTrue(
            forbidden.isdisjoint(
                result.keys()
            )
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "assembly_does_not_change_live_merit"
            ]
        )

        self.assertTrue(
            result[
                "policy"
            ][
                "assembly_does_not_establish_truth"
            ]
        )


if __name__ == "__main__":
    unittest.main()
