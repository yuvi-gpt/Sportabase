from __future__ import annotations

import copy
import unittest

from app.services import multimodal_structured_shadow_caller as caller
from app.services import structured_claim_shadow_bridge
from app.services import multimodal_intelligence_runtime as runtime

import test_multimodal_intelligence_runtime as runtime_fixtures


class StructuredShadowHarness(
    runtime_fixtures.Harness
):
    def __init__(self):
        super().__init__()
        self.shadow_reports = {
            "left": self.report("left"),
            "right": self.report("right"),
        }

    def report(self, side):
        return {
            "version": (
                structured_claim_shadow_bridge
                .STRUCTURED_CLAIM_SHADOW_BRIDGE_VERSION
            ),
            "status": "active",
            "candidate_rows": [
                {
                    "candidate_id": f"candidate-{side}",
                    "shadow_status": "evaluated",
                    "router_status": "partial",
                    "route": "partial_semantics",
                    "candidate": {
                        "subject_key": runtime_fixtures.SUBJECT,
                        "event_type": "match_event",
                        "state": "scored",
                        "roles": {},
                        "facets": {},
                    },
                    "identity_complete": False,
                    "missing_identity_fields": [
                        "facets.event_key"
                    ],
                    "core_key": "",
                    "core_fingerprint": "",
                    "specific_fingerprint": "",
                    "safe_acceptance": False,
                    "safe_exclusion": False,
                    "persistence_allowed": False,
                    "replaces_production_identity": False,
                    "story_membership_allowed": False,
                    "corroboration_allowed": False,
                    "live_merit_effect": False,
                }
            ],
            "unbound_output_candidate_ids": [],
            "raw_model_outputs_stored": False,
            "persistence_allowed": False,
            "replaces_production_identity": False,
            "story_membership_allowed": False,
            "corroboration_allowed": False,
            "live_merit_effect": False,
            "policy": dict(
                structured_claim_shadow_bridge
                .STRUCTURED_CLAIM_SHADOW_POLICY
            ),
        }

    def structured_shadow(
        self,
        *,
        item,
        manifest,
        bindings,
        relationships=(),
        shadow_enabled=False,
        structured_outputs_by_candidate_id=None,
        allowed_entity_keys=(),
    ):
        side = self.side(item.item_id)
        self.calls.append(
            (
                "structured_shadow",
                side,
                shadow_enabled,
                manifest.item_id,
                bindings.media_item_id,
                tuple(relationships),
                structured_outputs_by_candidate_id,
                tuple(allowed_entity_keys),
            )
        )

        return {
            "production_plan": self.plans[side],
            "structured_shadow": copy.deepcopy(
                self.shadow_reports[side]
            ),
        }


def run_runtime(
    harness,
    **overrides,
):
    values = harness.kwargs()
    values.update(overrides)
    return runtime.run_multimodal_intelligence_runtime(
        **values
    )


class MultimodalStructuredShadowCallerTests(
    unittest.TestCase
):
    def test_descriptor_is_zero_provider(self):
        descriptor = caller.structured_shadow_caller_descriptor()
        self.assertFalse(descriptor["provider_call_performed"])
        self.assertEqual(descriptor["provider_calls_expected"], 0)
        self.assertEqual(descriptor["provider_tokens_expected"], 0)
        self.assertEqual(descriptor["database_writes_expected"], 0)

    def test_adapter_disabled_uses_existing_builder_directly(self):
        harness = StructuredShadowHarness()
        result = caller.build_runtime_bridge_plan(
            item=harness.items["left"],
            manifest=harness.semantic_manifests["left"],
            bindings=runtime_fixtures.binding("left"),
            shadow_enabled=False,
            structured_outputs_by_candidate_id="ignored",
            production_bridge_builder=harness.bridge,
            shadow_bridge_builder=lambda **_: self.fail(
                "disabled path must not call shadow builder"
            ),
        )
        self.assertIs(result["production_plan"], harness.plans["left"])
        self.assertEqual(result["structured_shadow"]["status"], "disabled")
        self.assertEqual(
            [row[0] for row in harness.calls],
            ["bridge"],
        )

    def test_adapter_enabled_uses_shadow_builder(self):
        harness = StructuredShadowHarness()
        result = caller.build_runtime_bridge_plan(
            item=harness.items["left"],
            manifest=harness.semantic_manifests["left"],
            bindings=runtime_fixtures.binding("left"),
            shadow_enabled=True,
            structured_outputs_by_candidate_id={"candidate-left": {}},
            allowed_entity_keys=(runtime_fixtures.SUBJECT,),
            production_bridge_builder=harness.bridge,
            shadow_bridge_builder=harness.structured_shadow,
        )
        self.assertIs(result["production_plan"], harness.plans["left"])
        self.assertEqual(result["structured_shadow"]["status"], "active")
        self.assertEqual(
            [row[0] for row in harness.calls],
            ["structured_shadow"],
        )

    def test_adapter_shadow_exception_falls_back_to_production_builder(self):
        harness = StructuredShadowHarness()
        result = caller.build_runtime_bridge_plan(
            item=harness.items["left"],
            manifest=harness.semantic_manifests["left"],
            bindings=runtime_fixtures.binding("left"),
            shadow_enabled=True,
            production_bridge_builder=harness.bridge,
            shadow_bridge_builder=lambda **_: (_ for _ in ()).throw(
                RuntimeError("boom")
            ),
        )
        self.assertIs(result["production_plan"], harness.plans["left"])
        self.assertEqual(result["structured_shadow"]["status"], "error")
        self.assertIn("boom", result["structured_shadow"]["error"])
        self.assertEqual(
            [row[0] for row in harness.calls],
            ["bridge"],
        )

    def test_adapter_rejects_authority_leak_then_falls_back(self):
        harness = StructuredShadowHarness()

        def bad(**kwargs):
            value = harness.structured_shadow(**kwargs)
            value["structured_shadow"]["persistence_allowed"] = True
            return value

        result = caller.build_runtime_bridge_plan(
            item=harness.items["left"],
            manifest=harness.semantic_manifests["left"],
            bindings=runtime_fixtures.binding("left"),
            shadow_enabled=True,
            production_bridge_builder=harness.bridge,
            shadow_bridge_builder=bad,
        )
        self.assertEqual(result["structured_shadow"]["status"], "error")
        self.assertIs(result["production_plan"], harness.plans["left"])
        self.assertEqual(
            [row[0] for row in harness.calls],
            ["structured_shadow", "bridge"],
        )

    def test_adapter_rejects_wrong_item_plan_then_falls_back(self):
        harness = StructuredShadowHarness()

        def bad(**kwargs):
            value = harness.structured_shadow(**kwargs)
            value["production_plan"] = runtime_fixtures.plan("right")
            return value

        result = caller.build_runtime_bridge_plan(
            item=harness.items["left"],
            manifest=harness.semantic_manifests["left"],
            bindings=runtime_fixtures.binding("left"),
            shadow_enabled=True,
            production_bridge_builder=harness.bridge,
            shadow_bridge_builder=bad,
        )
        self.assertEqual(result["structured_shadow"]["status"], "error")
        self.assertIs(result["production_plan"], harness.plans["left"])

    def test_sink_receives_sanitized_diagnostic(self):
        rows = []
        emitted = caller.emit_structured_shadow_diagnostic(
            sink=rows.append,
            side="LEFT",
            report={
                "status": "active",
                "raw_model_outputs_stored": False,
                "persistence_allowed": False,
            },
        )
        self.assertTrue(emitted)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["side"], "left")
        self.assertTrue(rows[0]["policy"]["diagnostic_only"])
        self.assertFalse(rows[0]["policy"]["can_persist"])

    def test_sink_none_is_noop(self):
        self.assertFalse(
            caller.emit_structured_shadow_diagnostic(
                sink=None,
                side="left",
                report={},
            )
        )

    def test_sink_exception_is_swallowed(self):
        self.assertFalse(
            caller.emit_structured_shadow_diagnostic(
                sink=lambda _: (_ for _ in ()).throw(
                    RuntimeError("sink failed")
                ),
                side="left",
                report={},
            )
        )

    def test_runtime_default_path_does_not_call_structured_shadow_builder(self):
        harness = StructuredShadowHarness()
        result = run_runtime(
            harness,
            structured_shadow_bridge_builder=(
                lambda **_: self.fail(
                    "default-off runtime called shadow builder"
                )
            ),
            left_structured_claim_outputs="ignored-left",
            right_structured_claim_outputs="ignored-right",
        )
        self.assertEqual(result["claim_id"], runtime_fixtures.CLAIM_ID)
        self.assertEqual(
            [row[0] for row in harness.calls].count("bridge"),
            2,
        )
        self.assertNotIn("structured_shadow", [row[0] for row in harness.calls])

    def test_runtime_default_path_response_matches_historical_path(self):
        baseline_harness = StructuredShadowHarness()
        baseline = run_runtime(baseline_harness)

        shadow_harness = StructuredShadowHarness()
        candidate = run_runtime(
            shadow_harness,
            structured_claim_shadow_enabled=False,
            structured_shadow_bridge_builder=shadow_harness.structured_shadow,
            left_structured_claim_outputs={"ignored": 1},
            right_structured_claim_outputs={"ignored": 2},
            structured_claim_allowed_entity_keys=("ignored",),
        )

        self.assertEqual(candidate, baseline)

    def test_runtime_enabled_path_response_is_unchanged(self):
        baseline_harness = StructuredShadowHarness()
        baseline = run_runtime(baseline_harness)

        harness = StructuredShadowHarness()
        result = run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
            left_structured_claim_outputs={"candidate-left": {}},
            right_structured_claim_outputs={"candidate-right": {}},
            structured_claim_allowed_entity_keys=(runtime_fixtures.SUBJECT,),
        )

        self.assertEqual(result, baseline)
        self.assertEqual(
            [row[0] for row in harness.calls].count("structured_shadow"),
            2,
        )
        self.assertEqual(
            [row[0] for row in harness.calls].count("bridge"),
            0,
        )

    def test_runtime_enabled_path_emits_two_diagnostics(self):
        harness = StructuredShadowHarness()
        diagnostics = []
        run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
            structured_shadow_sink=diagnostics.append,
            left_structured_claim_outputs={"candidate-left": {}},
            right_structured_claim_outputs={"candidate-right": {}},
            structured_claim_allowed_entity_keys=(runtime_fixtures.SUBJECT,),
        )
        self.assertEqual([row["side"] for row in diagnostics], ["left", "right"])
        self.assertTrue(
            all(row["policy"]["diagnostic_only"] for row in diagnostics)
        )

    def test_runtime_disabled_path_does_not_emit_diagnostics(self):
        harness = StructuredShadowHarness()
        diagnostics = []
        run_runtime(
            harness,
            structured_claim_shadow_enabled=False,
            structured_shadow_sink=diagnostics.append,
        )
        self.assertEqual(diagnostics, [])

    def test_runtime_sink_failure_does_not_break_pipeline(self):
        baseline_harness = StructuredShadowHarness()
        baseline = run_runtime(baseline_harness)

        harness = StructuredShadowHarness()
        result = run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
            structured_shadow_sink=lambda _: (_ for _ in ()).throw(
                RuntimeError("sink boom")
            ),
        )
        self.assertEqual(result, baseline)

    def test_runtime_shadow_builder_failure_falls_back_and_completes(self):
        baseline_harness = StructuredShadowHarness()
        baseline = run_runtime(baseline_harness)

        harness = StructuredShadowHarness()
        diagnostics = []

        def fail(**_):
            raise RuntimeError("shadow unavailable")

        result = run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=fail,
            structured_shadow_sink=diagnostics.append,
        )

        self.assertEqual(result, baseline)
        self.assertEqual(
            [row[0] for row in harness.calls].count("bridge"),
            2,
        )
        self.assertEqual(len(diagnostics), 2)
        self.assertTrue(
            all(
                row["structured_shadow"]["status"] == "error"
                for row in diagnostics
            )
        )

    def test_runtime_shadow_does_not_change_selected_claim(self):
        harness = StructuredShadowHarness()
        result = run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
        )
        self.assertEqual(result["claim_id"], runtime_fixtures.CLAIM_ID)

    def test_runtime_shadow_does_not_change_persistence_candidate_count(self):
        harness = StructuredShadowHarness()
        run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
        )
        persist_calls = [row for row in harness.calls if row[0] == "persist"]
        self.assertEqual(len(persist_calls), 2)
        self.assertTrue(all(row[2] == 1 for row in persist_calls))

    def test_runtime_forwards_left_and_right_structured_outputs_separately(self):
        harness = StructuredShadowHarness()
        left = {"candidate-left": {"left": True}}
        right = {"candidate-right": {"right": True}}
        run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
            left_structured_claim_outputs=left,
            right_structured_claim_outputs=right,
            structured_claim_allowed_entity_keys=("a", "b"),
        )
        calls = [row for row in harness.calls if row[0] == "structured_shadow"]
        self.assertEqual(calls[0][6], left)
        self.assertEqual(calls[1][6], right)
        self.assertEqual(calls[0][7], ("a", "b"))
        self.assertEqual(calls[1][7], ("a", "b"))

    def test_runtime_result_has_no_new_structured_shadow_response_field(self):
        harness = StructuredShadowHarness()
        result = run_runtime(
            harness,
            structured_claim_shadow_enabled=True,
            structured_shadow_bridge_builder=harness.structured_shadow,
        )
        self.assertNotIn("structured_claim_shadow", result)
        self.assertNotIn("structured_shadow_diagnostics", result)
        self.assertNotIn("structured_claim_shadow", result["stages"]["left"])
        self.assertNotIn("structured_claim_shadow", result["stages"]["right"])


if __name__ == "__main__":
    unittest.main()
