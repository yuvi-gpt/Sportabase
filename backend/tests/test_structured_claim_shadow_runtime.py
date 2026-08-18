from __future__ import annotations

import copy
import json
import unittest

from app.models import intelligence_bridge as bridge_models
from app.services import structured_claim_shadow_runtime as shadow_runtime


SUBJECT = "club|arsenal"
LEFT_MEDIA = "media-left"
RIGHT_MEDIA = "media-right"


class FakeItem:
    def __init__(self, item_id):
        self.item_id = item_id


def bindings(media_item_id):
    return bridge_models.BridgeBindings(
        subject_key=SUBJECT,
        source_id="source-" + media_item_id,
        source_record_verified=True,
        media_item_id=media_item_id,
        media_item_record_verified=True,
    )


def plan(item_id):
    return bridge_models.ItemIntelligenceBridgePlan(
        item_id=item_id,
        subject_key=SUBJECT,
        subject_resolution_status="explicit_binding",
        policy={
            "dry_run_only": True,
            "training_eligible": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    )


def base_runtime_result():
    return {
        "version": "multimodal-intelligence-runtime-v1",
        "status": "completed_shadow",
        "claim_id": "production-claim",
        "subject_key": SUBJECT,
        "sentinel": {
            "nested": [1, 2, 3],
        },
        "policy": {
            "affects_live_merit": False,
        },
    }


class Harness:
    def __init__(self):
        self.runtime_result = base_runtime_result()
        self.runtime_calls = []
        self.shadow_calls = []
        self.fallback_calls = []
        self.bridge_plans = []
        self.exercise_bridges = False
        self.shadow_failure_side = ""
        self.fallback_failure_side = ""

    def runtime(self, **kwargs):
        self.runtime_calls.append(kwargs)

        if self.exercise_bridges:
            builder = kwargs["bridge_builder"]

            left_plan = builder(
                item=FakeItem("item-left"),
                manifest=object(),
                bindings=kwargs["left_bindings"],
                relationships=("left-rel",),
            )

            right_plan = builder(
                item=FakeItem("item-right"),
                manifest=object(),
                bindings=kwargs["right_bindings"],
                relationships=("right-rel",),
            )

            self.bridge_plans = [
                left_plan,
                right_plan,
            ]

        return self.runtime_result

    def shadow_bridge(
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
        side = (
            "left"
            if bindings.media_item_id == LEFT_MEDIA
            else "right"
        )

        self.shadow_calls.append(
            {
                "side": side,
                "item_id": item.item_id,
                "manifest": manifest,
                "bindings": bindings,
                "relationships": tuple(relationships),
                "shadow_enabled": shadow_enabled,
                "outputs": structured_outputs_by_candidate_id,
                "allowed_entity_keys": tuple(allowed_entity_keys),
            }
        )

        if self.shadow_failure_side == side:
            raise ValueError(
                "shadow failed "
                + ("x" * 700)
            )

        return {
            "version": "structured-claim-shadow-bridge-v1",
            "production_plan": plan(item.item_id),
            "structured_shadow": {
                "version": "structured-claim-shadow-bridge-v1",
                "enabled": True,
                "status": "active",
                "subject_key": SUBJECT,
                "candidate_rows": [],
                "unbound_output_candidate_ids": [],
                "report_errors": [],
                "raw_model_outputs_stored": False,
                "persistence_allowed": False,
                "replaces_production_identity": False,
                "story_membership_allowed": False,
                "corroboration_allowed": False,
                "live_merit_effect": False,
            },
        }

    def fallback(
        self,
        *,
        item,
        manifest,
        bindings,
        relationships=(),
    ):
        side = (
            "left"
            if bindings.media_item_id == LEFT_MEDIA
            else "right"
        )

        self.fallback_calls.append(
            {
                "side": side,
                "item_id": item.item_id,
                "relationships": tuple(relationships),
            }
        )

        if self.fallback_failure_side == side:
            raise RuntimeError(
                "production bridge failure"
            )

        return plan(item.item_id)

    def kwargs(self):
        return {
            "left_capture": {"side": "left"},
            "right_capture": {"side": "right"},
            "left_bindings": bindings(LEFT_MEDIA),
            "right_bindings": bindings(RIGHT_MEDIA),
            "legacy_score": {"total": 64.0},
            "as_of": "2026-08-18T12:00:00Z",
            "connection_factory": object(),
            "semantic_interpreter": object(),
            "gemini_client": object(),
            "gemini_client_key": "existing-client",
            "gemini_generator": object(),
        }


def enabled_call(
    harness=None,
    **overrides,
):
    harness = harness or Harness()
    harness.exercise_bridges = True

    values = {
        "structured_claim_shadow_enabled": True,
        "left_structured_outputs_by_candidate_id": {
            "candidate-left": {
                "secret": "LEFT_RAW_MODEL_OUTPUT",
            }
        },
        "right_structured_outputs_by_candidate_id": {
            "candidate-right": {
                "secret": "RIGHT_RAW_MODEL_OUTPUT",
            }
        },
        "structured_allowed_entity_keys": (
            SUBJECT,
            "club|counterparty",
        ),
        "runtime_runner": harness.runtime,
        "structured_shadow_bridge_builder": (
            harness.shadow_bridge
        ),
        "production_bridge_builder": (
            harness.fallback
        ),
        **harness.kwargs(),
    }

    values.update(overrides)

    return (
        harness,
        shadow_runtime
        .run_multimodal_intelligence_runtime_with_structured_shadow(
            **values
        ),
    )


class StructuredClaimShadowRuntimeTests(
    unittest.TestCase
):
    def test_version_constant(self):
        self.assertEqual(
            shadow_runtime
            .STRUCTURED_CLAIM_SHADOW_RUNTIME_VERSION,
            "structured-claim-shadow-runtime-v1",
        )

    def test_policy_defaults_shadow_off(self):
        policy = (
            shadow_runtime
            .STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY
        )
        self.assertTrue(policy["shadow_is_opt_in"])
        self.assertFalse(policy["shadow_default_enabled"])

    def test_policy_forbids_authority_paths(self):
        policy = (
            shadow_runtime
            .STRUCTURED_CLAIM_SHADOW_RUNTIME_POLICY
        )
        for field in (
            "shadow_can_replace_production_identity",
            "shadow_can_filter_production_candidates",
            "shadow_can_change_persistence_scope",
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
                self.assertFalse(policy[field])

    def test_descriptor_has_zero_additional_provider_budget(self):
        result = (
            shadow_runtime
            .structured_claim_shadow_runtime_descriptor()
        )
        self.assertEqual(
            result[
                "shadow_additional_provider_calls_expected"
            ],
            0,
        )
        self.assertEqual(
            result[
                "shadow_additional_provider_tokens_expected"
            ],
            0,
        )

    def test_descriptor_records_no_existing_file_changes(self):
        result = (
            shadow_runtime
            .structured_claim_shadow_runtime_descriptor()
        )
        self.assertFalse(result["production_runtime_changed"])
        self.assertFalse(result["production_shadow_api_changed"])
        self.assertFalse(result["production_bridge_changed"])

    def test_disabled_returns_exact_runtime_object(self):
        harness = Harness()
        result = (
            shadow_runtime
            .run_multimodal_intelligence_runtime_with_structured_shadow(
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )
        )
        self.assertIs(result, harness.runtime_result)

    def test_disabled_does_not_validate_left_output(self):
        harness = Harness()
        result = (
            shadow_runtime
            .run_multimodal_intelligence_runtime_with_structured_shadow(
                left_structured_outputs_by_candidate_id=(
                    "not-a-mapping"
                ),
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )
        )
        self.assertIs(result, harness.runtime_result)

    def test_disabled_does_not_validate_right_output(self):
        harness = Harness()
        result = (
            shadow_runtime
            .run_multimodal_intelligence_runtime_with_structured_shadow(
                right_structured_outputs_by_candidate_id=(
                    "not-a-mapping"
                ),
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )
        )
        self.assertIs(result, harness.runtime_result)

    def test_disabled_does_not_validate_entity_allowlist(self):
        harness = Harness()
        result = (
            shadow_runtime
            .run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_allowed_entity_keys=(
                    "not-a-sequence-of-keys"
                ),
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )
        )
        self.assertIs(result, harness.runtime_result)

    def test_disabled_does_not_inject_bridge_builder(self):
        harness = Harness()
        shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
            runtime_runner=harness.runtime,
            **harness.kwargs(),
        )
        self.assertNotIn(
            "bridge_builder",
            harness.runtime_calls[0],
        )

    def test_disabled_preserves_caller_bridge_builder(self):
        harness = Harness()
        sentinel = object()
        shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
            runtime_runner=harness.runtime,
            bridge_builder=sentinel,
            **harness.kwargs(),
        )
        self.assertIs(
            harness.runtime_calls[0][
                "bridge_builder"
            ],
            sentinel,
        )

    def test_enabled_requires_boolean_flag(self):
        harness = Harness()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled="true",
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )

    def test_runtime_runner_must_be_callable(self):
        harness = Harness()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                runtime_runner=None,
                **harness.kwargs(),
            )

    def test_enabled_rejects_caller_bridge_builder(self):
        harness = Harness()
        with self.assertRaisesRegex(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError,
            "caller-supplied bridge_builder",
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                bridge_builder=object(),
                **harness.kwargs(),
            )

    def test_enabled_requires_callable_shadow_builder(self):
        harness = Harness()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                structured_shadow_bridge_builder=None,
                **harness.kwargs(),
            )

    def test_enabled_requires_callable_fallback_builder(self):
        harness = Harness()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                production_bridge_builder=None,
                **harness.kwargs(),
            )

    def test_enabled_left_outputs_must_be_mapping(self):
        harness = Harness()
        with self.assertRaisesRegex(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError,
            "Left structured outputs",
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                left_structured_outputs_by_candidate_id=[],
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )

    def test_enabled_right_outputs_must_be_mapping(self):
        harness = Harness()
        with self.assertRaisesRegex(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError,
            "Right structured outputs",
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                right_structured_outputs_by_candidate_id=[],
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )

    def test_entity_allowlist_rejects_string(self):
        harness = Harness()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                structured_allowed_entity_keys=SUBJECT,
                runtime_runner=harness.runtime,
                **harness.kwargs(),
            )

    def test_entity_allowlist_deduplicates_keys(self):
        harness, _ = enabled_call(
            structured_allowed_entity_keys=(
                SUBJECT,
                "  " + SUBJECT + "  ",
                "club|counterparty",
                "",
            )
        )
        for call in harness.shadow_calls:
            self.assertEqual(
                call["allowed_entity_keys"],
                (
                    SUBJECT,
                    "club|counterparty",
                ),
            )

    def test_enabled_requires_bridge_bindings(self):
        harness = Harness()
        values = harness.kwargs()
        values["left_bindings"] = object()
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                **values,
            )

    def test_enabled_requires_nonempty_left_media_binding(self):
        harness = Harness()
        values = harness.kwargs()
        values["left_bindings"] = bindings("")
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                **values,
            )

    def test_enabled_requires_nonempty_right_media_binding(self):
        harness = Harness()
        values = harness.kwargs()
        values["right_bindings"] = bindings("")
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                **values,
            )

    def test_enabled_requires_distinct_media_bindings(self):
        harness = Harness()
        values = harness.kwargs()
        values["right_bindings"] = bindings(LEFT_MEDIA)
        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeInputError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=harness.runtime,
                **values,
            )

    def test_enabled_injects_bridge_builder(self):
        harness, _ = enabled_call()
        self.assertIn(
            "bridge_builder",
            harness.runtime_calls[0],
        )
        self.assertTrue(
            callable(
                harness.runtime_calls[0][
                    "bridge_builder"
                ]
            )
        )

    def test_enabled_invokes_shadow_builder_for_both_sides(self):
        harness, _ = enabled_call()
        self.assertEqual(
            [
                row["side"]
                for row in harness.shadow_calls
            ],
            ["left", "right"],
        )

    def test_left_outputs_go_only_to_left_call(self):
        harness, _ = enabled_call()
        left = harness.shadow_calls[0]
        self.assertEqual(
            left["outputs"],
            {
                "candidate-left": {
                    "secret": "LEFT_RAW_MODEL_OUTPUT",
                }
            },
        )

    def test_right_outputs_go_only_to_right_call(self):
        harness, _ = enabled_call()
        right = harness.shadow_calls[1]
        self.assertEqual(
            right["outputs"],
            {
                "candidate-right": {
                    "secret": "RIGHT_RAW_MODEL_OUTPUT",
                }
            },
        )

    def test_relationships_are_forwarded_to_shadow_bridge(self):
        harness, _ = enabled_call()
        self.assertEqual(
            harness.shadow_calls[0][
                "relationships"
            ],
            ("left-rel",),
        )
        self.assertEqual(
            harness.shadow_calls[1][
                "relationships"
            ],
            ("right-rel",),
        )

    def test_entity_keys_are_forwarded_to_both_sides(self):
        harness, _ = enabled_call()
        expected = (
            SUBJECT,
            "club|counterparty",
        )
        self.assertTrue(
            all(
                call["allowed_entity_keys"]
                == expected
                for call in harness.shadow_calls
            )
        )

    def test_only_production_plans_return_to_runtime(self):
        harness, _ = enabled_call()
        self.assertEqual(
            [
                row.item_id
                for row in harness.bridge_plans
            ],
            ["item-left", "item-right"],
        )
        self.assertTrue(
            all(
                isinstance(
                    row,
                    bridge_models
                    .ItemIntelligenceBridgePlan,
                )
                for row in harness.bridge_plans
            )
        )

    def test_enabled_output_preserves_runtime_fields(self):
        _, result = enabled_call()
        self.assertEqual(
            result["claim_id"],
            "production-claim",
        )
        self.assertEqual(
            result["sentinel"],
            {"nested": [1, 2, 3]},
        )

    def test_existing_runtime_result_is_not_mutated(self):
        harness = Harness()
        before = copy.deepcopy(
            harness.runtime_result
        )
        _, result = enabled_call(
            harness
        )
        self.assertEqual(
            harness.runtime_result,
            before,
        )
        self.assertNotIn(
            "structured_claim_shadow",
            harness.runtime_result,
        )
        self.assertIn(
            "structured_claim_shadow",
            result,
        )

    def test_top_level_shadow_report_is_active(self):
        _, result = enabled_call()
        report = result[
            "structured_claim_shadow"
        ]
        self.assertTrue(report["enabled"])
        self.assertEqual(
            report["status"],
            "active",
        )

    def test_side_reports_are_active(self):
        _, result = enabled_call()
        report = result[
            "structured_claim_shadow"
        ]
        self.assertEqual(
            report["left"]["status"],
            "active",
        )
        self.assertEqual(
            report["right"]["status"],
            "active",
        )

    def test_raw_model_outputs_are_not_copied_to_result(self):
        _, result = enabled_call()
        serialized = json.dumps(
            result,
            sort_keys=True,
            default=str,
        )
        self.assertNotIn(
            "LEFT_RAW_MODEL_OUTPUT",
            serialized,
        )
        self.assertNotIn(
            "RIGHT_RAW_MODEL_OUTPUT",
            serialized,
        )
        self.assertFalse(
            result[
                "structured_claim_shadow"
            ][
                "raw_model_outputs_stored"
            ]
        )

    def test_runtime_shadow_authority_flags_are_false(self):
        _, result = enabled_call()
        report = result[
            "structured_claim_shadow"
        ]
        for field in (
            "production_result_mutated",
            "production_identity_replaced",
            "production_candidate_filter_applied",
            "persistence_scope_changed",
            "story_membership_created",
            "corroboration_established",
            "authority_established",
            "reliability_established",
            "independence_established",
            "truth_established",
            "live_merit_effect",
        ):
            with self.subTest(field=field):
                self.assertFalse(report[field])

    def test_shadow_failure_falls_back_and_runtime_completes(self):
        harness = Harness()
        harness.shadow_failure_side = "left"
        harness, result = enabled_call(
            harness
        )
        self.assertEqual(
            result["status"],
            "completed_shadow",
        )
        self.assertEqual(
            [
                row["side"]
                for row in harness.fallback_calls
            ],
            ["left"],
        )
        self.assertEqual(
            result[
                "structured_claim_shadow"
            ]["left"]["status"],
            "error",
        )

    def test_one_side_shadow_failure_does_not_block_other_side(self):
        harness = Harness()
        harness.shadow_failure_side = "left"
        _, result = enabled_call(
            harness
        )
        report = result[
            "structured_claim_shadow"
        ]
        self.assertEqual(
            report["left"]["status"],
            "error",
        )
        self.assertEqual(
            report["right"]["status"],
            "active",
        )

    def test_real_production_fallback_failure_propagates(self):
        harness = Harness()
        harness.shadow_failure_side = "left"
        harness.fallback_failure_side = "left"
        with self.assertRaisesRegex(
            RuntimeError,
            "production bridge failure",
        ):
            enabled_call(harness)

    def test_shadow_error_message_is_bounded(self):
        harness = Harness()
        harness.shadow_failure_side = "left"
        _, result = enabled_call(
            harness
        )
        message = result[
            "structured_claim_shadow"
        ]["left"]["error"]
        self.assertLessEqual(
            len(message),
            500,
        )

    def test_factory_returns_callable(self):
        harness = Harness()
        runner = (
            shadow_runtime
            .make_structured_claim_shadow_runtime_runner(
                runtime_runner=harness.runtime,
                structured_shadow_bridge_builder=(
                    harness.shadow_bridge
                ),
                production_bridge_builder=(
                    harness.fallback
                ),
            )
        )
        self.assertTrue(callable(runner))

    def test_factory_disabled_preserves_exact_runtime_result(self):
        harness = Harness()
        runner = (
            shadow_runtime
            .make_structured_claim_shadow_runtime_runner(
                runtime_runner=harness.runtime,
            )
        )
        result = runner(
            **harness.kwargs()
        )
        self.assertIs(
            result,
            harness.runtime_result,
        )

    def test_factory_enabled_attaches_shadow_report(self):
        harness = Harness()
        harness.exercise_bridges = True
        runner = (
            shadow_runtime
            .make_structured_claim_shadow_runtime_runner(
                structured_claim_shadow_enabled=True,
                left_structured_outputs_by_candidate_id={},
                right_structured_outputs_by_candidate_id={},
                structured_allowed_entity_keys=(SUBJECT,),
                runtime_runner=harness.runtime,
                structured_shadow_bridge_builder=(
                    harness.shadow_bridge
                ),
                production_bridge_builder=(
                    harness.fallback
                ),
            )
        )
        result = runner(
            **harness.kwargs()
        )
        self.assertIn(
            "structured_claim_shadow",
            result,
        )

    def test_factory_forwards_configured_outputs(self):
        harness = Harness()
        harness.exercise_bridges = True
        left = {"left-id": {"value": 1}}
        right = {"right-id": {"value": 2}}
        runner = (
            shadow_runtime
            .make_structured_claim_shadow_runtime_runner(
                structured_claim_shadow_enabled=True,
                left_structured_outputs_by_candidate_id=left,
                right_structured_outputs_by_candidate_id=right,
                structured_allowed_entity_keys=(SUBJECT,),
                runtime_runner=harness.runtime,
                structured_shadow_bridge_builder=(
                    harness.shadow_bridge
                ),
                production_bridge_builder=(
                    harness.fallback
                ),
            )
        )
        runner(
            **harness.kwargs()
        )
        self.assertIs(
            harness.shadow_calls[0]["outputs"],
            left,
        )
        self.assertIs(
            harness.shadow_calls[1]["outputs"],
            right,
        )

    def test_missing_bridge_invocation_is_reported_not_observed(self):
        harness = Harness()
        harness.exercise_bridges = False
        _, result = enabled_call(
            harness
        )
        report = result[
            "structured_claim_shadow"
        ]
        self.assertEqual(
            report["left"]["status"],
            "not_observed",
        )
        self.assertEqual(
            report["right"]["status"],
            "not_observed",
        )

    def test_enabled_runtime_must_return_mapping(self):
        harness = Harness()
        harness.exercise_bridges = False

        def bad_runtime(**_kwargs):
            return []

        with self.assertRaises(
            shadow_runtime
            .StructuredClaimShadowRuntimeIntegrityError
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=True,
                runtime_runner=bad_runtime,
                left_bindings=bindings(LEFT_MEDIA),
                right_bindings=bindings(RIGHT_MEDIA),
            )

    def test_existing_runtime_failure_propagates(self):
        def failing_runtime(**_kwargs):
            raise RuntimeError(
                "existing runtime failure"
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "existing runtime failure",
        ):
            shadow_runtime.run_multimodal_intelligence_runtime_with_structured_shadow(
                structured_claim_shadow_enabled=False,
                runtime_runner=failing_runtime,
            )

    def test_runtime_report_never_replaces_production_identity(self):
        _, result = enabled_call()
        report = result[
            "structured_claim_shadow"
        ]
        self.assertFalse(
            report[
                "production_identity_replaced"
            ]
        )
        self.assertEqual(
            result["claim_id"],
            "production-claim",
        )

    def test_additional_provider_and_database_counters_are_zero(self):
        _, result = enabled_call()
        report = result[
            "structured_claim_shadow"
        ]
        self.assertEqual(
            report[
                "additional_provider_calls"
            ],
            0,
        )
        self.assertEqual(
            report[
                "additional_provider_tokens"
            ],
            0,
        )
        self.assertEqual(
            report[
                "database_writes"
            ],
            0,
        )


if __name__ == "__main__":
    unittest.main()
