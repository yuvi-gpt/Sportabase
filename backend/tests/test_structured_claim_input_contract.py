from __future__ import annotations

import ast
import inspect
import unittest
from pathlib import Path

from app.services import multimodal_structured_shadow_caller as caller
from app.services import semantic_execution
from app.services import structured_claim_input


ROOT = Path(__file__).resolve().parents[1]
INPUT_MODULE = ROOT / "app" / "services" / "structured_claim_input.py"
SEMANTIC_EXECUTION = ROOT / "app" / "services" / "semantic_execution.py"
CALLER = ROOT / "app" / "services" / "multimodal_structured_shadow_caller.py"
README = ROOT / "app" / "services" / "README_STRUCTURED_CLAIM_INPUT.md"


class StructuredClaimInputContractTests(unittest.TestCase):
    def test_version_and_sidecar_field_are_frozen(self):
        self.assertEqual(
            structured_claim_input.STRUCTURED_CLAIM_INPUT_VERSION,
            "structured-claim-input-v1",
        )
        self.assertEqual(
            structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD,
            "structured_claim_outputs_by_candidate_id",
        )

    def test_input_policy_denies_authority(self):
        policy = structured_claim_input.STRUCTURED_CLAIM_INPUT_POLICY
        for field in (
            "establishes_identity",
            "establishes_truth",
            "establishes_authority",
            "establishes_reliability",
            "establishes_independence",
            "establishes_corroboration",
            "affects_live_merit",
        ):
            with self.subTest(field=field):
                self.assertFalse(policy[field])

    def test_input_policy_is_zero_provider_and_zero_database(self):
        policy = structured_claim_input.STRUCTURED_CLAIM_INPUT_POLICY
        self.assertEqual(policy["provider_calls_expected"], 0)
        self.assertEqual(policy["provider_tokens_expected"], 0)
        self.assertEqual(policy["database_writes_expected"], 0)

    def test_policy_requires_sidecar_and_unchanged_candidate_payload(self):
        policy = structured_claim_input.STRUCTURED_CLAIM_INPUT_POLICY
        self.assertTrue(policy["reads_claim_candidate_metadata_sidecar_only"])
        self.assertTrue(policy["claim_candidate_payload_is_not_modified"])
        self.assertTrue(policy["outputs_are_keyed_by_existing_candidate_id"])
        self.assertTrue(policy["candidate_ids_are_never_generated_here"])

    def test_collector_public_surface_is_small(self):
        public = {
            name
            for name, value in vars(structured_claim_input).items()
            if callable(value)
            and getattr(value, "__module__", None) == structured_claim_input.__name__
            and not name.startswith("_")
        }
        self.assertEqual(
            public,
            {
                "StructuredClaimInputError",
                "collect_structured_claim_outputs",
                "structured_claim_input_descriptor",
            },
        )

    def test_collector_has_no_provider_network_or_database_imports(self):
        text = INPUT_MODULE.read_text(encoding="utf-8")
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

    def test_collector_does_not_import_claim_identity_or_router_modules(self):
        tree = ast.parse(INPUT_MODULE.read_text(encoding="utf-8-sig"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        for forbidden in (
            "app.intelligence.canonical_claims",
            "app.intelligence.canonical_claim_extraction",
            "app.intelligence.partial_claim_semantics",
            "app.intelligence.claim_semantic_extraction_router",
            "app.intelligence.claim_semantic_protocol_ownership",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, imports)

    def test_semantic_execution_contains_sidecar_field_but_prompt_does_not_request_it(self):
        text = SEMANTIC_EXECUTION.read_text(encoding="utf-8")
        self.assertIn("structured_claim_outputs_by_candidate_id", text)
        prompt_start = text.index('"You are Sportabase\'s multimodal semantic fusion interpreter.')
        prompt_end = text.index('payload = self._generate(', prompt_start)
        prompt_source = text[prompt_start:prompt_end]
        self.assertNotIn("structured_claim_output", prompt_source)
        self.assertNotIn("structured_claim_outputs_by_candidate_id", prompt_source)

    def test_candidate_id_hash_does_not_include_structured_output(self):
        text = SEMANTIC_EXECUTION.read_text(encoding="utf-8")
        start = text.index('candidate_id = _stable_id(')
        end = text.index('if candidate_id in seen:', start)
        identity_block = text[start:end]
        self.assertIn('"text": text.casefold()', identity_block)
        self.assertIn('"source_artifact_ids"', identity_block)
        self.assertNotIn("structured_claim_output", identity_block)

    def test_caller_signature_contains_injected_input_collector(self):
        signature = inspect.signature(caller.build_runtime_bridge_plan)
        self.assertIn("structured_input_collector", signature.parameters)
        self.assertIsNotNone(signature.parameters["structured_input_collector"].default)

    def test_caller_source_uses_sidecar_autowiring(self):
        text = CALLER.read_text(encoding="utf-8")
        self.assertIn("structured_claim_input", text)
        self.assertIn("structured_input_collector", text)
        self.assertIn('"semantic_manifest_sidecar"', text)
        self.assertIn('"explicit_runtime_mapping"', text)

    def test_caller_policy_keeps_explicit_override_and_default_off(self):
        policy = caller.MULTIMODAL_STRUCTURED_SHADOW_CALLER_POLICY
        self.assertFalse(policy["shadow_default_enabled"])
        self.assertTrue(policy["manifest_structured_input_autowiring"])
        self.assertTrue(policy["explicit_structured_input_overrides_manifest"])
        self.assertFalse(policy["manifest_input_collection_can_establish_identity"])

    def test_readme_freezes_sidecar_and_penultimate_boundary(self):
        text = README.read_text(encoding="utf-8")
        for marker in (
            "Sidecar instead of candidate-payload mutation",
            "does **not** change the real Gemini fusion prompt",
            "Candidate identity is preserved",
            "Correlation only",
            "Automatic runtime wiring",
            "No extra model spend",
            "final Claim Intelligence checkpoint",
            "zero Gemini calls",
            "zero Gemini tokens",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_readme_uses_actual_system_heading(self):
        heading = README.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(
            heading,
            "# Sportabase — Structured Claim Input Wiring",
        )

    def test_current_real_fusion_mode_remains_one_existing_mode(self):
        source = inspect.getsource(semantic_execution.GeminiSemanticInterpreter.fuse)
        self.assertEqual(source.count('mode="multimodal_fusion"'), 1)
        self.assertNotIn("claim_semantic_extraction_router", source)


if __name__ == "__main__":
    unittest.main()
