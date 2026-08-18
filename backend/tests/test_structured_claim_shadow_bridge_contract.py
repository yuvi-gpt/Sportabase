from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest

from app.services import structured_claim_shadow_bridge as shadow


class StructuredClaimShadowBridgeContractTests(unittest.TestCase):
    def test_01_import_surface_is_provider_and_database_free(self):
        source = inspect.getsource(shadow)
        tree = ast.parse(source)
        imports = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(
                    alias.name
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                imports.append(
                    node.module or ""
                )

        self.assertEqual(
            set(imports),
            {
                "__future__",
                "re",
                "typing",
                "app.intelligence",
                "app.models",
                "app.services",
            },
        )

    def test_02_no_provider_or_database_runtime_symbols(self):
        source = inspect.getsource(shadow)
        for forbidden in (
            "google.genai",
            "gemini_runtime",
            "generate_gemini_content",
            "generate_content(",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "requests.",
            "httpx.",
            "sqlite3",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(
                    forbidden,
                    source,
                )

    def test_03_no_persistence_api_is_called_by_shadow_module(self):
        source = inspect.getsource(shadow)
        tree = ast.parse(source)
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Call)
                and isinstance(
                    node.func,
                    ast.Attribute,
                )
            )
        }
        for forbidden in (
            "upsert_intelligence_claim",
            "record_evidence",
            "record_claim_link",
            "record_source_observation",
            "record_observation_dependency",
            "release_live_merit",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(
                    forbidden,
                    called_attributes,
                )

    def test_04_required_policy_guards_are_true(self):
        policy = shadow.STRUCTURED_CLAIM_SHADOW_POLICY
        for field in (
            "shadow_is_opt_in",
            "production_bridge_runs_first",
            "production_bridge_result_is_not_modified",
            "shadow_outputs_are_keyed_by_existing_candidate_id",
            "unbound_shadow_outputs_are_ignored",
            "protocol_ownership_is_product35g",
            "three_way_router_is_product35e",
            "partial_semantics_validator_is_product35d",
            "full_identity_authority_is_product35a",
        ):
            with self.subTest(field=field):
                self.assertIs(
                    policy[field],
                    True,
                )

    def test_05_forbidden_shadow_authorities_are_false(self):
        policy = shadow.STRUCTURED_CLAIM_SHADOW_POLICY
        for field in (
            "shadow_default_enabled",
            "shadow_failure_can_break_production_bridge",
            "shadow_can_replace_production_identity",
            "shadow_can_persist_claims",
            "shadow_can_persist_evidence",
            "shadow_can_persist_observations",
            "shadow_can_create_story_membership",
            "shadow_can_establish_corroboration",
            "shadow_can_establish_authority",
            "shadow_can_establish_reliability",
            "shadow_can_establish_independence",
            "shadow_can_establish_truth",
            "shadow_can_affect_live_merit",
            "shadow_can_create_training_labels",
        ):
            with self.subTest(field=field):
                self.assertIs(
                    policy[field],
                    False,
                )

    def test_06_zero_cost_policy_is_exact(self):
        policy = shadow.STRUCTURED_CLAIM_SHADOW_POLICY
        self.assertEqual(
            policy["provider_calls_expected"],
            0,
        )
        self.assertEqual(
            policy["provider_tokens_expected"],
            0,
        )
        self.assertEqual(
            policy["database_writes_expected"],
            0,
        )

    def test_07_public_exports_are_explicit(self):
        self.assertEqual(
            set(shadow.__all__),
            {
                "STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION",
                "SHADOW_STATUS_DISABLED",
                "SHADOW_STATUS_ACTIVE",
                "SHADOW_STATUS_NOT_PROVIDED",
                "SHADOW_STATUS_EVALUATED",
                "SHADOW_STATUS_ERROR",
                "STRUCTURED_CLAIM_SHADOW_POLICY",
                "StructuredClaimShadowBridgeError",
                "StructuredClaimShadowBridgeInputError",
                "structured_claim_shadow_descriptor",
                "build_item_intelligence_bridge_with_structured_shadow",
            },
        )

    def test_08_shadow_enabled_defaults_false(self):
        signature = inspect.signature(
            shadow.build_item_intelligence_bridge_with_structured_shadow
        )
        self.assertIs(
            signature.parameters[
                "shadow_enabled"
            ].default,
            False,
        )

    def test_09_production_bridge_is_built_before_any_shadow_parse(self):
        source = inspect.getsource(
            shadow.build_item_intelligence_bridge_with_structured_shadow
        )
        production_index = source.index(
            ".build_item_intelligence_bridge("
        )
        parse_index = source.index(
            ".parse_protocol_owned_claim_semantic_output("
        )
        self.assertLess(
            production_index,
            parse_index,
        )

    def test_10_disabled_return_precedes_shadow_parser_execution(self):
        source = inspect.getsource(
            shadow.build_item_intelligence_bridge_with_structured_shadow
        )
        disabled_index = source.index(
            "if not shadow_enabled:"
        )
        parse_index = source.index(
            ".parse_protocol_owned_claim_semantic_output("
        )
        self.assertLess(
            disabled_index,
            parse_index,
        )

    def test_11_readme_locks_no_feedback_and_zero_provider_boundary(self):
        readme = (
            Path(__file__).resolve().parents[1]
            / "app/services/README_STRUCTURED_CLAIM_SHADOW_BRIDGE.md"
        ).read_text(
            encoding="utf-8"
        )
        for marker in (
            "opt-in production-service shadow boundary",
            "does **not** switch production claim identity",
            "The production bridge plan object is returned untouched",
            "Shadow mode is observation only",
            "No feedback path",
            "zero Gemini calls",
            "zero Gemini tokens",
            "zero database writes",
            "affect Live Merit",
        ):
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    readme,
                )

    def test_12_readme_preserves_locked_stack_and_measured_history(self):
        readme = (
            Path(__file__).resolve().parents[1]
            / "app/services/README_STRUCTURED_CLAIM_SHADOW_BRIDGE.md"
        ).read_text(
            encoding="utf-8"
        )
        for marker in (
            "#35G -> model/internal protocol ownership",
            "#35E -> extracted / partial / insufficient routing",
            "#35D -> incomplete partial semantics",
            "#35B -> complete extraction validation",
            "#35A -> complete deterministic claim identity",
            "rewrite the #35C, #35F, or #35H measured baselines",
            "modify `multimodal_intelligence_bridge.py`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(
                    marker,
                    readme,
                )


if __name__ == "__main__":
    unittest.main()
