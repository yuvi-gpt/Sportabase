from __future__ import annotations

import ast
import inspect
import unittest

from app.intelligence import claim_semantic_protocol_ownership as ownership


class TestClaimSemanticProtocolOwnershipContract(unittest.TestCase):
    def test_01_policy_rejects_model_candidate_version_authority(self):
        self.assertFalse(
            ownership.MODEL_PROTOCOL_POLICY[
                "model_controls_candidate_contract_version"
            ]
        )

    def test_02_policy_keeps_outer_version_strict(self):
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "outer_envelope_version_remains_strict"
            ]
        )

    def test_03_policy_removes_only_candidate_contract_metadata(self):
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "candidate_contract_version_removed_before_validation"
            ]
        )
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "validator_assigns_internal_candidate_contract_version"
            ]
        )

    def test_04_policy_does_not_rewrite_semantics_or_status(self):
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "semantic_fields_are_not_rewritten"
            ]
        )
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "status_is_not_rewritten"
            ]
        )
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "reason_is_not_rewritten"
            ]
        )

    def test_05_policy_keeps_fail_closed_semantic_checks(self):
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "unknown_semantic_fields_still_fail_closed"
            ]
        )
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "forbidden_identity_fields_still_fail_closed"
            ]
        )
        self.assertTrue(
            ownership.MODEL_PROTOCOL_POLICY[
                "status_mismatch_still_fails_closed"
            ]
        )

    def test_06_policy_never_grants_partial_same_claim_authority(self):
        self.assertFalse(
            ownership.MODEL_PROTOCOL_POLICY[
                "partial_semantics_can_establish_same_claim"
            ]
        )

    def test_07_policy_has_no_truth_or_authority_effect(self):
        for field in (
            "establishes_truth",
            "establishes_authority",
            "establishes_reliability",
            "establishes_independence",
            "establishes_corroboration",
            "affects_live_merit",
            "training_eligible",
        ):
            self.assertFalse(ownership.MODEL_PROTOCOL_POLICY[field])

    def test_08_descriptor_is_zero_provider(self):
        value = ownership.protocol_ownership_descriptor()
        self.assertFalse(value["provider_call_performed"])
        self.assertEqual(value["provider_calls_expected"], 0)
        self.assertEqual(value["provider_tokens_expected"], 0)

    def test_09_descriptor_has_no_production_or_db_effect(self):
        value = ownership.protocol_ownership_descriptor()
        self.assertFalse(value["production_bridge_changed"])
        self.assertFalse(value["database_mutation_expected"])
        self.assertFalse(value["live_merit_effect"])

    def test_10_module_has_no_provider_or_network_imports(self):
        source = inspect.getsource(ownership)
        forbidden = (
            "google.genai",
            "gemini_runtime",
            "generate_gemini_content",
            "generate_content(",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "requests.",
            "httpx.",
            "sqlite3",
        )
        for marker in forbidden:
            self.assertNotIn(marker, source)

    def test_11_module_import_surface_is_narrow(self):
        source = inspect.getsource(ownership)
        tree = ast.parse(source)
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertEqual(
            set(imports),
            {"__future__", "json", "re", "typing", "app.intelligence"},
        )

    def test_12_public_api_contains_only_protocol_boundary_functions(self):
        exported = set(ownership.__all__)
        self.assertIn("sanitize_model_protocol_metadata", exported)
        self.assertIn("parse_protocol_owned_claim_semantic_output", exported)
        self.assertIn("protocol_ownership_descriptor", exported)
        self.assertNotIn("compare_canonical_claims", exported)
        self.assertNotIn("generate_content", exported)


if __name__ == "__main__":
    unittest.main()
