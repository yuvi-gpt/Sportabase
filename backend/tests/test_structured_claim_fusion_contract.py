from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from app.services import multimodal_intelligence_runtime
from app.services import semantic_execution
from app.services import structured_claim_fusion


ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "semantic_execution.py"
)
RUNTIME_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "multimodal_intelligence_runtime.py"
)


class StructuredClaimFusionContractTests(unittest.TestCase):
    def test_01_version(self):
        self.assertEqual(
            structured_claim_fusion.STRUCTURED_CLAIM_FUSION_VERSION,
            "structured-claim-fusion-v1",
        )

    def test_02_context_version(self):
        self.assertEqual(
            structured_claim_fusion.STRUCTURED_CLAIM_FUSION_CONTEXT_VERSION,
            "structured-claim-fusion-context-v1",
        )

    def test_03_default_disabled(self):
        self.assertFalse(
            structured_claim_fusion.STRUCTURED_CLAIM_FUSION_POLICY[
                "default_enabled"
            ]
        )

    def test_04_same_fusion_call_policy(self):
        policy = structured_claim_fusion.STRUCTURED_CLAIM_FUSION_POLICY
        self.assertTrue(policy["existing_multimodal_fusion_call_reused"])
        self.assertFalse(policy["additional_provider_call_required"])
        self.assertTrue(
            policy[
                "context_transport_uses_existing_perception_options"
            ]
        )
        self.assertTrue(
            policy[
                "context_option_removed_before_perception_builder"
            ]
        )

    def test_05_no_authority_policy(self):
        policy = structured_claim_fusion.STRUCTURED_CLAIM_FUSION_POLICY
        for field in (
            "fusion_does_not_establish_identity",
            "fusion_does_not_establish_truth",
            "fusion_does_not_establish_authority",
            "fusion_does_not_establish_reliability",
            "fusion_does_not_establish_independence",
            "fusion_does_not_establish_corroboration",
            "fusion_does_not_affect_live_merit",
            "fusion_does_not_create_training_labels",
        ):
            self.assertTrue(policy[field], field)

    def test_06_semantic_fuse_has_optional_context_parameter(self):
        signature = inspect.signature(
            semantic_execution.GeminiSemanticInterpreter.fuse
        )
        parameter = signature.parameters[
            "structured_claim_context"
        ]
        self.assertIsNone(parameter.default)

    def test_07_build_executors_has_optional_context_parameter(self):
        signature = inspect.signature(
            semantic_execution.build_semantic_executors
        )
        self.assertIsNone(
            signature.parameters[
                "structured_claim_context"
            ].default
        )

    def test_08_execute_manifest_keeps_existing_runner_signature(self):
        signature = inspect.signature(
            semantic_execution.execute_semantic_manifest
        )
        self.assertNotIn(
            "structured_claim_context",
            signature.parameters,
        )
        source = SEMANTIC_PATH.read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "STRUCTURED_CLAIM_CONTEXT_OPTION",
            source,
        )
        self.assertIn(
            "perception_options.pop(",
            source,
        )

    def test_09_runtime_accepts_optional_entity_metadata(self):
        signature = inspect.signature(
            multimodal_intelligence_runtime.run_multimodal_intelligence_runtime
        )
        self.assertIsNone(
            signature.parameters[
                "structured_claim_allowed_entities"
            ].default
        )

    def test_10_semantic_source_imports_fusion_context_only(self):
        tree = ast.parse(
            SEMANTIC_PATH.read_text(
                encoding="utf-8"
            )
        )

        service_imports = set()
        intelligence_imports = set()

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue

            imported_names = {
                alias.name
                for alias in node.names
            }

            if node.module == "app.services":
                service_imports.update(
                    imported_names
                )

            if node.module == "app.intelligence":
                intelligence_imports.update(
                    imported_names
                )

        self.assertIn(
            "structured_claim_fusion",
            service_imports,
        )
        self.assertNotIn(
            "canonical_claims",
            intelligence_imports,
        )
        self.assertNotIn(
            "claim_semantic_protocol_ownership",
            intelligence_imports,
        )

    def test_11_runtime_builds_context_only_for_shadow_auto_input(self):
        source = RUNTIME_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "structured_claim_fusion_context_for_bindings",
            source,
        )
        self.assertIn(
            "left_structured_claim_outputs is None",
            source,
        )
        self.assertIn(
            "right_structured_claim_outputs is None",
            source,
        )
        self.assertIn(
            "STRUCTURED_CLAIM_CONTEXT_OPTION",
            source,
        )

    def test_12_runtime_default_shadow_remains_false(self):
        signature = inspect.signature(
            multimodal_intelligence_runtime.run_multimodal_intelligence_runtime
        )
        self.assertIs(
            signature.parameters[
                "structured_claim_shadow_enabled"
            ].default,
            False,
        )

    def test_13_no_new_runtime_generator_parameter(self):
        signature = inspect.signature(
            multimodal_intelligence_runtime.run_multimodal_intelligence_runtime
        )
        names = set(signature.parameters)
        self.assertNotIn("structured_claim_generator", names)
        self.assertNotIn("structured_claim_client", names)

    def test_14_fusion_module_has_no_provider_import(self):
        source = inspect.getsource(
            structured_claim_fusion
        )
        for forbidden in (
            "google.genai",
            "gemini_runtime",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "requests.",
            "httpx.",
            "sqlite3",
        ):
            self.assertNotIn(forbidden, source)

    def test_15_fusion_module_has_no_persistence_call(self):
        source = inspect.getsource(
            structured_claim_fusion
        )
        for forbidden in (
            "upsert_intelligence_claim",
            "record_evidence",
            "record_source_observation",
            "record_claim_link",
            "release_live_merit",
        ):
            self.assertNotIn(forbidden, source)

    def test_16_semantic_execution_still_uses_one_fusion_generate_site(self):
        tree = ast.parse(
            SEMANTIC_PATH.read_text(
                encoding="utf-8"
            )
        )
        calls = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "_generate"
            ):
                for keyword in node.keywords:
                    if (
                        keyword.arg == "mode"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value == "multimodal_fusion"
                    ):
                        calls.append(node)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
