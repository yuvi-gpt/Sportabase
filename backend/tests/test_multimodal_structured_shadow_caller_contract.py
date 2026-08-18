from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from app.services import multimodal_structured_shadow_caller as caller
from app.services import multimodal_intelligence_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
MODULE = (
    ROOT
    / "app"
    / "services"
    / "multimodal_structured_shadow_caller.py"
)
RUNTIME = (
    ROOT
    / "app"
    / "services"
    / "multimodal_intelligence_runtime.py"
)
README = (
    ROOT
    / "app"
    / "services"
    / "README_MULTIMODAL_STRUCTURED_SHADOW_CALLER.md"
)


class MultimodalStructuredShadowCallerContractTests(
    unittest.TestCase
):
    def test_version_is_frozen(self):
        self.assertEqual(
            caller.MULTIMODAL_STRUCTURED_SHADOW_CALLER_VERSION,
            "multimodal-structured-shadow-caller-v1",
        )

    def test_default_policy_is_off(self):
        self.assertFalse(
            caller.MULTIMODAL_STRUCTURED_SHADOW_CALLER_POLICY[
                "shadow_default_enabled"
            ]
        )

    def test_policy_denies_shadow_authority(self):
        policy = caller.MULTIMODAL_STRUCTURED_SHADOW_CALLER_POLICY
        for field in (
            "shadow_output_can_select_claim",
            "shadow_output_can_filter_candidate",
            "shadow_output_can_persist_claim",
            "shadow_output_can_persist_evidence",
            "shadow_output_can_persist_observation",
            "shadow_output_can_create_story_membership",
            "shadow_output_can_establish_corroboration",
            "shadow_output_can_establish_authority",
            "shadow_output_can_establish_reliability",
            "shadow_output_can_establish_independence",
            "shadow_output_can_establish_truth",
            "shadow_output_can_affect_live_merit",
        ):
            with self.subTest(field=field):
                self.assertFalse(policy[field])

    def test_adapter_has_no_provider_or_database_imports(self):
        text = MODULE.read_text(encoding="utf-8")
        for marker in (
            "google.genai",
            "gemini_runtime",
            "generate_gemini_content",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "sqlite3",
            "requests.",
            "httpx.",
            "release_live_merit",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

    def test_adapter_exposes_only_expected_public_functions(self):
        public = {
            name
            for name, value in vars(caller).items()
            if callable(value)
            and getattr(value, "__module__", None) == caller.__name__
            and not name.startswith("_")
        }
        self.assertEqual(
            public,
            {
                "build_runtime_bridge_plan",
                "emit_structured_shadow_diagnostic",
                "structured_shadow_caller_descriptor",
            },
        )

    def test_runtime_signature_contains_default_off_shadow_flag(self):
        signature = inspect.signature(
            runtime.run_multimodal_intelligence_runtime
        )
        parameter = signature.parameters[
            "structured_claim_shadow_enabled"
        ]
        self.assertIs(parameter.default, False)

    def test_runtime_signature_contains_precomputed_shadow_inputs(self):
        signature = inspect.signature(
            runtime.run_multimodal_intelligence_runtime
        )
        for name in (
            "left_structured_claim_outputs",
            "right_structured_claim_outputs",
            "structured_claim_allowed_entity_keys",
            "structured_shadow_sink",
            "structured_shadow_bridge_builder",
        ):
            with self.subTest(name=name):
                self.assertIn(name, signature.parameters)

    def test_runtime_source_uses_caller_adapter(self):
        text = RUNTIME.read_text(encoding="utf-8")
        self.assertIn(
            "multimodal_structured_shadow_caller",
            text,
        )
        self.assertGreaterEqual(
            text.count("build_runtime_bridge_plan("),
            2,
        )

    def test_runtime_does_not_expose_shadow_in_response(self):
        text = RUNTIME.read_text(encoding="utf-8")
        return_tail = text[text.rfind("    return {"):]
        self.assertNotIn(
            '"structured_claim_shadow"',
            return_tail,
        )
        self.assertNotIn(
            '"structured_shadow_diagnostics"',
            return_tail,
        )

    def test_runtime_does_not_import_provider_for_new_shadow_path(self):
        tree = ast.parse(
            RUNTIME.read_text(encoding="utf-8-sig")
        )
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertNotIn(
            "app.services.structured_claim_shadow_bridge",
            imports,
        )

    def test_readme_freezes_no_feedback_boundary(self):
        text = README.read_text(encoding="utf-8")
        for marker in (
            "Default-off guarantee",
            "No response-schema change",
            "No authority",
            "zero Gemini calls",
            "zero Gemini tokens",
            "cannot influence claim selection or persistence",
            "change Live Merit behavior",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_descriptor_declares_zero_cost_and_no_identity_switch(self):
        descriptor = caller.structured_shadow_caller_descriptor()
        self.assertEqual(descriptor["provider_calls_expected"], 0)
        self.assertEqual(descriptor["provider_tokens_expected"], 0)
        self.assertEqual(descriptor["database_writes_expected"], 0)
        self.assertFalse(descriptor["production_identity_replaced"])
        self.assertFalse(descriptor["live_merit_effect"])


if __name__ == "__main__":
    unittest.main()
