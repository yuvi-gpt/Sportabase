import unittest
from unittest.mock import Mock, patch

from app.services import multimodal_shadow_api_enhanced as enhanced


class MultimodalEvolutionWiringTests(unittest.TestCase):
    def test_materialized_claim_runs_advisory_evolution_finalization(self):
        base_payload = {
            "status": "completed_shadow",
            "result": {
                "claim_id": "legacy-claim",
                "subject_key": "player|one",
                "left_candidate_id": "left-candidate",
                "right_candidate_id": "right-candidate",
                "stages": {},
                "policy": {},
            },
            "policy": {},
        }
        materialization = {
            "version": "structured-claim-ingestion-runtime-v1",
            "status": "materialized",
            "reason": "dual_full_identity_same_core",
            "production_claim_id": "legacy-claim",
            "canonical_claim_id": "canonical-claim",
            "mapping_status": "verified_equivalent",
            "policy": {"affects_live_merit": False},
        }
        finalization = {
            "version": "intelligence-runtime-finalization-v1",
            "status": "completed",
            "reason": "claim_evolution_reconciled",
            "canonical_claim_id": "canonical-claim",
            "story": {
                "status": "materialized",
                "story_id": "story-1",
            },
            "evolution": {
                "status": "reconciled",
                "family_key": "family-1",
                "family_claim_count": 2,
                "links_written": 1,
            },
            "policy": {"affects_live_merit": False},
        }

        with patch.object(
            enhanced,
            "build_structured_claim_allowlist",
            return_value={
                "status": "ready",
                "resolution_status": "resolved",
                "allowed_entity_keys": ["player|one"],
                "allowed_entities": {},
                "counts": {"entities": 1, "ambiguous_aliases_excluded": 0},
            },
        ), patch.object(
            enhanced.base_shadow_api,
            "execute_multimodal_shadow_api",
            return_value=base_payload,
        ), patch.object(
            enhanced,
            "materialize_selected_structured_claim_safely",
            return_value=materialization,
        ), patch.object(
            enhanced,
            "finalize_structured_claim_materialization",
            return_value=finalization,
        ) as finalize:
            result = enhanced.execute_multimodal_shadow_api(
                request_payload={
                    "subject_key": "player|one",
                    "left": {"capture": {}},
                    "right": {"capture": {}},
                },
                connection_factory=Mock(),
                gemini_client=object(),
                gemini_client_key="client",
                gemini_generator=Mock(),
                runtime_runner=Mock(),
                interpreter_factory=Mock(),
            )

        finalize.assert_called_once()
        self.assertEqual(
            result["result"]["stages"]["claim_evolution_reconciliation"]["status"],
            "completed",
        )
        self.assertEqual(
            result["result"]["stages"]["canonical_claim_story_materialization"][
                "story_id"
            ],
            "story-1",
        )
        self.assertEqual(
            result["result"]["structured_claim_ingestion"]["evolution"][
                "evolution_status"
            ],
            "reconciled",
        )
        self.assertEqual(
            result["result"]["structured_claim_ingestion"]["policy"][
                "additional_provider_calls"
            ],
            0,
        )
        self.assertFalse(
            result["result"]["structured_claim_ingestion"]["policy"][
                "affects_live_merit"
            ]
        )


if __name__ == "__main__":
    unittest.main()
