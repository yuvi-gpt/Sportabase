from __future__ import annotations

import copy
import json
from types import SimpleNamespace
import unittest

from app.models import artifacts as artifact_models
from app.models import content
from app.models import intelligence_bridge as bridge_models
from app.services import artifact_extraction
from app.services import multimodal_structured_shadow_caller as caller
from app.services import semantic_execution
from app.services import structured_claim_input


ITEM_ID = "item:structured-input"
SUBJECT = "player|jude_bellingham"
CANDIDATE_ID = "claim-candidate:abc"


def structured_output(*, state="scored"):
    return {
        "version": "claim-semantic-extraction-router-output-v1",
        "status": "partial",
        "candidate": {
            "subject_key": SUBJECT,
            "event_type": "match_event",
            "state": state,
            "negated": False,
            "roles": {},
            "facets": {},
        },
        "reason": "event identity is incomplete",
    }


def candidate(candidate_id=CANDIDATE_ID, *, text="Bellingham scored in a league match."):
    return {
        "candidate_id": candidate_id,
        "text": text,
        "confidence": 0.88,
        "source_artifact_ids": ["source:text"],
        "modality_sources": ["text"],
        "uncertainty": "match identity is not specified",
    }


def claim_candidate_artifact(
    candidates,
    *,
    sidecar=None,
    artifact_id="artifact:claim-candidates",
):
    metadata = {"semantic_only": True}
    if sidecar is not None:
        metadata[
            structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD
        ] = sidecar

    return artifact_models.ExtractionArtifact(
        artifact_id=artifact_id,
        artifact_kind="claim_candidates",
        modality="multimodal",
        source_item_ids=[ITEM_ID],
        source_component_ids=[],
        content_hash="candidates-hash",
        payload={
            "semantic_execution_version": "semantic-execution-v1",
            "model": "gemini-3.5-flash",
            "candidates": candidates,
            "context_artifact_ids": [],
        },
        metadata=metadata,
    )


def source_artifact():
    return artifact_models.ExtractionArtifact(
        artifact_id="source:text",
        artifact_kind="text_component",
        modality="text",
        source_item_ids=[ITEM_ID],
        source_component_ids=["body"],
        content_hash="source-hash",
        payload={
            "role": "body",
            "text": "Bellingham scored in a league match.",
        },
    )


def manifest(*artifacts):
    return artifact_models.ItemArtifactManifest(
        item_id=ITEM_ID,
        artifacts=list(artifacts),
    )


def item():
    return content.UnifiedContentItem(
        item_id=ITEM_ID,
        platform="web",
        container_kind="post",
        canonical_url="https://example.com/story",
        observed_at="2026-08-18T12:00:00+00:00",
        text_components=[
            content.TextComponent(
                component_id="body",
                role="body",
                text="Bellingham scored in a league match.",
            )
        ],
    )


def bindings():
    return bridge_models.BridgeBindings(
        subject_key=SUBJECT,
        source_id="source:example",
        source_record_verified=True,
        media_item_id="media:example",
        media_item_record_verified=True,
    )


def plan():
    def proposal(operation, deterministic_id=""):
        return bridge_models.PersistenceProposal(
            operation=operation,
            readiness="ready",
            deterministic_id=deterministic_id,
            blocked_reasons=[],
            kwargs={},
        )

    row = bridge_models.CandidateBridgeRecord(
        candidate_id=CANDIDATE_ID,
        canonical_text="Bellingham scored in a league match.",
        interpretation_confidence=0.88,
        source_artifacts=[],
        claim=proposal("upsert_intelligence_claim", "production-claim"),
        evidence=proposal("record_evidence", "production-evidence"),
        claim_link=proposal("record_claim_link", "production-link"),
        source_observation=proposal("record_source_observation"),
        policy={
            "training_eligible": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    )

    return bridge_models.ItemIntelligenceBridgePlan(
        item_id=ITEM_ID,
        subject_key=SUBJECT,
        subject_resolution_status="explicit_binding",
        candidates=[row],
        independence_status="unknown",
        policy={
            "dry_run_only": True,
            "training_eligible": False,
            "establishes_truth": False,
            "establishes_independence": False,
            "affects_live_merit": False,
        },
    )


class FusionGenerator:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=json.dumps(self.output))


def interpreter_for(output):
    return semantic_execution.GeminiSemanticInterpreter(
        client_factory=lambda: object(),
        generator=FusionGenerator(output),
        client_key="test",
    )


class DummyWorkspace:
    pass


class StructuredClaimInputTests(unittest.TestCase):
    def test_descriptor_is_zero_provider(self):
        descriptor = structured_claim_input.structured_claim_input_descriptor()
        self.assertFalse(descriptor["provider_call_performed"])
        self.assertEqual(descriptor["provider_calls_expected"], 0)
        self.assertEqual(descriptor["provider_tokens_expected"], 0)
        self.assertEqual(descriptor["database_writes_expected"], 0)
        self.assertFalse(descriptor["establishes_identity"])

    def test_empty_manifest_returns_empty_mapping(self):
        result = structured_claim_input.collect_structured_claim_outputs(manifest())
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["provided_count"], 0)

    def test_collects_sidecar_output_by_existing_candidate_id(self):
        expected = structured_output()
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: expected},
        )
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(artifact)
        )
        self.assertEqual(result["outputs_by_candidate_id"], {CANDIDATE_ID: expected})

    def test_collector_does_not_semantically_rewrite_sidecar(self):
        expected = {
            "version": "custom-version-left-for-downstream-validation",
            "status": "partial",
            "candidate": {"unknown_semantic_field": "x"},
            "reason": "bounded proposal",
        }
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: expected},
        )
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(artifact)
        )
        self.assertEqual(result["outputs_by_candidate_id"][CANDIDATE_ID], expected)

    def test_non_mapping_semantic_output_is_forwarded_for_downstream_fail_closed(self):
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: ["invalid-shape"]},
        )
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(artifact)
        )
        self.assertEqual(
            result["outputs_by_candidate_id"][CANDIDATE_ID],
            ["invalid-shape"],
        )

    def test_missing_sidecar_is_not_provided(self):
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(claim_candidate_artifact([candidate()]))
        )
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertEqual(result["candidate_rows"][0]["status"], "not_provided")

    def test_missing_candidate_id_is_reported(self):
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(claim_candidate_artifact([candidate(candidate_id="")]))
        )
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertTrue(
            any(value.startswith("candidate_id_missing:") for value in result["report_errors"])
        )

    def test_non_mapping_candidate_is_reported(self):
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(claim_candidate_artifact(["bad-candidate"]))
        )
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertTrue(
            any(value.startswith("candidate_not_mapping:") for value in result["report_errors"])
        )

    def test_non_mapping_sidecar_is_reported(self):
        artifact = claim_candidate_artifact([candidate()])
        artifact.metadata[
            structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD
        ] = "bad"
        result = structured_claim_input.collect_structured_claim_outputs(manifest(artifact))
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertTrue(
            any(value.startswith("structured_claim_sidecar_not_mapping:") for value in result["report_errors"])
        )

    def test_unbound_sidecar_output_is_ignored(self):
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={"claim-candidate:other": structured_output()},
        )
        result = structured_claim_input.collect_structured_claim_outputs(manifest(artifact))
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertEqual(
            result["unbound_output_candidate_ids"],
            ["claim-candidate:other"],
        )

    def test_duplicate_candidate_id_is_suppressed(self):
        first = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: structured_output(state="scored")},
            artifact_id="artifact:a",
        )
        second = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: structured_output(state="assisted")},
            artifact_id="artifact:b",
        )
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(first, second)
        )
        self.assertNotIn(CANDIDATE_ID, result["outputs_by_candidate_id"])
        self.assertEqual(result["duplicate_candidate_ids"], [CANDIDATE_ID])

    def test_duplicate_rows_are_marked_fail_closed(self):
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(
                claim_candidate_artifact([candidate()], artifact_id="artifact:a"),
                claim_candidate_artifact([candidate()], artifact_id="artifact:b"),
            )
        )
        self.assertTrue(
            all(row["status"] == "duplicate_candidate_id" for row in result["candidate_rows"])
        )

    def test_unrelated_artifacts_are_ignored(self):
        result = structured_claim_input.collect_structured_claim_outputs(
            manifest(source_artifact())
        )
        self.assertEqual(result["outputs_by_candidate_id"], {})
        self.assertEqual(result["candidate_rows"], [])

    def test_outputs_are_sorted_by_candidate_id(self):
        artifact = claim_candidate_artifact(
            [candidate("claim-candidate:z"), candidate("claim-candidate:a")],
            sidecar={
                "claim-candidate:z": structured_output(),
                "claim-candidate:a": structured_output(),
            },
        )
        result = structured_claim_input.collect_structured_claim_outputs(manifest(artifact))
        self.assertEqual(
            list(result["outputs_by_candidate_id"]),
            ["claim-candidate:a", "claim-candidate:z"],
        )

    def test_collector_returns_deep_copy(self):
        expected = structured_output()
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: expected},
        )
        result = structured_claim_input.collect_structured_claim_outputs(manifest(artifact))
        result["outputs_by_candidate_id"][CANDIDATE_ID]["reason"] = "changed"
        stored = artifact.metadata[
            structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD
        ][CANDIDATE_ID]
        self.assertNotEqual(stored["reason"], "changed")

    def test_report_rows_do_not_embed_structured_semantics(self):
        artifact = claim_candidate_artifact(
            [candidate()],
            sidecar={CANDIDATE_ID: structured_output()},
        )
        result = structured_claim_input.collect_structured_claim_outputs(manifest(artifact))
        serialized = json.dumps(result["candidate_rows"], sort_keys=True)
        self.assertNotIn("match_event", serialized)
        self.assertNotIn("event_type", serialized)
        self.assertFalse(result["raw_provider_response_stored"])

    def test_fuse_preserves_optional_structured_output_in_internal_candidate(self):
        output = structured_output()
        payload = {
            "alignment_assessments": [],
            "claim_candidates": [
                {
                    "text": "Bellingham scored in a league match.",
                    "confidence": 0.8,
                    "source_artifact_ids": ["source:text"],
                    "modality_sources": ["text"],
                    "uncertainty": "",
                    "structured_claim_output": output,
                }
            ],
        }
        result = interpreter_for(payload).fuse([source_artifact()], caption_media_pairs=[])
        self.assertEqual(
            result["claim_candidates"][0]["structured_claim_output"],
            output,
        )

    def test_structured_output_does_not_change_candidate_id(self):
        base = {
            "alignment_assessments": [],
            "claim_candidates": [
                {
                    "text": "Bellingham scored in a league match.",
                    "confidence": 0.8,
                    "source_artifact_ids": ["source:text"],
                    "modality_sources": ["text"],
                    "uncertainty": "",
                }
            ],
        }
        with_output = copy.deepcopy(base)
        with_output["claim_candidates"][0]["structured_claim_output"] = structured_output()

        first = interpreter_for(base).fuse([source_artifact()], caption_media_pairs=[])
        second = interpreter_for(with_output).fuse([source_artifact()], caption_media_pairs=[])
        self.assertEqual(
            first["claim_candidates"][0]["candidate_id"],
            second["claim_candidates"][0]["candidate_id"],
        )

    def test_semantic_fusion_executor_moves_structured_output_to_metadata(self):
        output = structured_output()

        class StubInterpreter:
            def fuse(self, _artifacts, *, caption_media_pairs):
                self.pairs = caption_media_pairs
                return {
                    "model": "stub",
                    "alignment_assessments": [],
                    "claim_candidates": [
                        {
                            **candidate(),
                            "structured_claim_output": output,
                        }
                    ],
                    "context_artifact_ids": ["source:text"],
                }

        executors = semantic_execution.build_semantic_executors(
            DummyWorkspace(),
            interpreter=StubInterpreter(),
            perception_executor_builder=lambda *_args, **_kwargs: {},
        )
        work = artifact_models.ArtifactWorkUnit(
            work_id="work:fusion",
            operation="multimodal_semantic_fusion",
            source_item_ids=[ITEM_ID],
            source_component_ids=["body"],
            parameters={"caption_media_pairs": []},
        )
        output_specs = executors["multimodal_semantic_fusion"](
            work,
            [source_artifact()],
            {},
        )
        claim_spec = next(
            row for row in output_specs if row["artifact_kind"] == "claim_candidates"
        )
        stored_candidate = claim_spec["payload"]["candidates"][0]
        self.assertNotIn("structured_claim_output", stored_candidate)
        self.assertEqual(
            claim_spec["metadata"][
                structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD
            ],
            {CANDIDATE_ID: output},
        )

    def test_sidecar_metadata_does_not_change_artifact_identity_or_content_hash(self):
        payload = {
            "semantic_execution_version": "semantic-execution-v1",
            "model": "stub",
            "candidates": [candidate()],
            "context_artifact_ids": ["source:text"],
        }
        provenance = artifact_models.ArtifactProvenance()
        base = artifact_extraction._artifact(
            artifact_kind="claim_candidates",
            modality="multimodal",
            source_item_ids=[ITEM_ID],
            source_component_ids=["body"],
            payload=payload,
            provenance=provenance,
            metadata={"semantic_only": True},
        )
        sidecar = artifact_extraction._artifact(
            artifact_kind="claim_candidates",
            modality="multimodal",
            source_item_ids=[ITEM_ID],
            source_component_ids=["body"],
            payload=payload,
            provenance=provenance,
            metadata={
                "semantic_only": True,
                structured_claim_input.STRUCTURED_CLAIM_METADATA_FIELD: {
                    CANDIDATE_ID: structured_output()
                },
            },
        )
        self.assertEqual(base.artifact_id, sidecar.artifact_id)
        self.assertEqual(base.content_hash, sidecar.content_hash)
        self.assertEqual(base.payload, sidecar.payload)

    def test_current_real_fusion_prompt_does_not_request_structured_output(self):
        generator = FusionGenerator(
            {"alignment_assessments": [], "claim_candidates": []}
        )
        semantic = semantic_execution.GeminiSemanticInterpreter(
            client_factory=lambda: object(),
            generator=generator,
            client_key="test",
        )
        semantic.fuse([source_artifact()], caption_media_pairs=[])
        self.assertNotIn("structured_claim_output", generator.calls[0]["contents"][0])

    def test_caller_auto_collects_manifest_sidecar_when_explicit_mapping_absent(self):
        expected = structured_output()
        semantic_manifest = manifest(
            source_artifact(),
            claim_candidate_artifact(
                [candidate()],
                sidecar={CANDIDATE_ID: expected},
            ),
        )
        captured = {}

        def shadow_bridge_builder(**kwargs):
            captured.update(kwargs)
            return {
                "production_plan": plan(),
                "structured_shadow": {
                    "status": "active",
                    "persistence_allowed": False,
                    "replaces_production_identity": False,
                    "story_membership_allowed": False,
                    "corroboration_allowed": False,
                    "live_merit_effect": False,
                },
            }

        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=semantic_manifest,
            bindings=bindings(),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=None,
            allowed_entity_keys=(SUBJECT,),
            production_bridge_builder=lambda **_: plan(),
            shadow_bridge_builder=shadow_bridge_builder,
        )
        self.assertEqual(
            captured["structured_outputs_by_candidate_id"],
            {CANDIDATE_ID: expected},
        )
        self.assertEqual(
            result["structured_shadow"]["structured_input"]["source"],
            "semantic_manifest_sidecar",
        )

    def test_explicit_mapping_overrides_manifest_collection(self):
        explicit = {CANDIDATE_ID: structured_output(state="assisted")}
        captured = {}

        def shadow_bridge_builder(**kwargs):
            captured.update(kwargs)
            return {
                "production_plan": plan(),
                "structured_shadow": {
                    "status": "active",
                    "persistence_allowed": False,
                    "replaces_production_identity": False,
                    "story_membership_allowed": False,
                    "corroboration_allowed": False,
                    "live_merit_effect": False,
                },
            }

        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=manifest(),
            bindings=bindings(),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=explicit,
            allowed_entity_keys=(SUBJECT,),
            production_bridge_builder=lambda **_: plan(),
            shadow_bridge_builder=shadow_bridge_builder,
            structured_input_collector=lambda _manifest: self.fail(
                "explicit input must bypass manifest sidecar collection"
            ),
        )
        self.assertEqual(captured["structured_outputs_by_candidate_id"], explicit)
        self.assertEqual(
            result["structured_shadow"]["structured_input"]["source"],
            "explicit_runtime_mapping",
        )

    def test_disabled_caller_does_not_collect_manifest_sidecar(self):
        calls = []
        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=manifest(),
            bindings=bindings(),
            shadow_enabled=False,
            production_bridge_builder=lambda **_: plan(),
            structured_input_collector=lambda _manifest: calls.append(True),
        )
        self.assertEqual(calls, [])
        self.assertEqual(result["structured_shadow"]["status"], "disabled")

    def test_collector_exception_falls_back_to_existing_bridge(self):
        bridge_calls = []
        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=manifest(),
            bindings=bindings(),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=None,
            allowed_entity_keys=(SUBJECT,),
            production_bridge_builder=lambda **_: (bridge_calls.append(True) or plan()),
            shadow_bridge_builder=lambda **_: self.fail(
                "shadow bridge must not run after collector failure"
            ),
            structured_input_collector=lambda _manifest: (_ for _ in ()).throw(
                RuntimeError("collector failed")
            ),
        )
        self.assertEqual(bridge_calls, [True])
        self.assertEqual(result["structured_shadow"]["status"], "error")
        self.assertIn("collector failed", result["structured_shadow"]["error"])

    def test_malformed_collector_result_falls_back(self):
        bridge_calls = []
        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=manifest(),
            bindings=bindings(),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=None,
            allowed_entity_keys=(SUBJECT,),
            production_bridge_builder=lambda **_: (bridge_calls.append(True) or plan()),
            structured_input_collector=lambda _manifest: {"bad": "shape"},
        )
        self.assertEqual(bridge_calls, [True])
        self.assertEqual(result["structured_shadow"]["status"], "error")

    def test_structured_input_summary_does_not_contain_raw_semantics(self):
        result = caller.build_runtime_bridge_plan(
            item=item(),
            manifest=manifest(
                claim_candidate_artifact(
                    [candidate()],
                    sidecar={CANDIDATE_ID: structured_output()},
                )
            ),
            bindings=bindings(),
            shadow_enabled=True,
            structured_outputs_by_candidate_id=None,
            allowed_entity_keys=(SUBJECT,),
            production_bridge_builder=lambda **_: plan(),
            shadow_bridge_builder=lambda **_: {
                "production_plan": plan(),
                "structured_shadow": {
                    "status": "active",
                    "persistence_allowed": False,
                    "replaces_production_identity": False,
                    "story_membership_allowed": False,
                    "corroboration_allowed": False,
                    "live_merit_effect": False,
                },
            },
        )
        summary = result["structured_shadow"]["structured_input"]
        serialized = json.dumps(summary, sort_keys=True)
        self.assertNotIn("match_event", serialized)
        self.assertNotIn("event_type", serialized)
        self.assertEqual(summary["provided_count"], 1)


if __name__ == "__main__":
    unittest.main()
