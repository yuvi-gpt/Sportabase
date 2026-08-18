from __future__ import annotations

import json
from types import SimpleNamespace
import unittest

from app.intelligence import claim_semantic_extraction_router as router
from app.models import artifacts as artifact_models
from app.models import intelligence_bridge as bridge_models
from app.services import semantic_execution
from app.services import structured_claim_fusion


SUBJECT = "player|jude_bellingham"
REAL_MADRID = "club|real_madrid"
DORTMUND = "club|borussia_dortmund"


def allowed_entities():
    return {
        SUBJECT: {
            "canonical_name": "Jude Bellingham",
            "entity_type": "player",
        },
        REAL_MADRID: {
            "canonical_name": "Real Madrid",
            "entity_type": "club",
        },
        DORTMUND: {
            "canonical_name": "Borussia Dortmund",
            "entity_type": "club",
        },
    }


def context():
    return (
        structured_claim_fusion
        .build_structured_claim_fusion_context(
            subject_key=SUBJECT,
            allowed_entity_keys=tuple(
                allowed_entities()
            ),
            allowed_entities=(
                allowed_entities()
            ),
        )
    )


def text_artifact():
    return artifact_models.ExtractionArtifact(
        artifact_id="source:text",
        artifact_kind="text_component",
        modality="text",
        source_item_ids=["item:test"],
        source_component_ids=["body"],
        content_hash="source-hash",
        payload={
            "role": "body",
            "text": (
                "Jude Bellingham later scored in a league match."
            ),
        },
    )


def partial_output():
    return {
        "version": (
            router
            .CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION
        ),
        "status": "partial",
        "candidate": {
            "subject_key": SUBJECT,
            "event_type": "match_event",
            "state": "scored",
            "negated": False,
            "roles": {},
            "facets": {},
        },
        "reason": (
            "The exact match identity is not specified."
        ),
    }


class FakeGenerator:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(dict(kwargs))
        return SimpleNamespace(
            text=json.dumps(
                self.payload
            )
        )


def interpreter(payload):
    generator = FakeGenerator(payload)
    value = semantic_execution.GeminiSemanticInterpreter(
        client_factory=lambda: object(),
        generator=generator,
        client_key="fusion-test",
    )
    return value, generator


class StructuredClaimFusionTests(unittest.TestCase):
    def test_01_descriptor_is_additional_zero_call(self):
        value = structured_claim_fusion.structured_claim_fusion_descriptor()
        self.assertFalse(value["provider_call_performed"])
        self.assertEqual(value["additional_provider_calls_expected"], 0)
        self.assertEqual(value["database_writes_expected"], 0)

    def test_02_context_normalizes_subject(self):
        value = structured_claim_fusion.build_structured_claim_fusion_context(
            subject_key=" Player|Jude_Bellingham ",
            allowed_entity_keys=(SUBJECT,),
        )
        self.assertEqual(value["subject_key"], SUBJECT)

    def test_03_context_requires_subject(self):
        with self.assertRaises(
            structured_claim_fusion.StructuredClaimFusionInputError
        ):
            structured_claim_fusion.build_structured_claim_fusion_context(
                subject_key="",
                allowed_entity_keys=(SUBJECT,),
            )

    def test_04_context_requires_allowlist(self):
        with self.assertRaises(
            structured_claim_fusion.StructuredClaimFusionInputError
        ):
            structured_claim_fusion.build_structured_claim_fusion_context(
                subject_key=SUBJECT,
                allowed_entity_keys=(),
            )

    def test_05_subject_must_be_allowed(self):
        with self.assertRaises(
            structured_claim_fusion.StructuredClaimFusionInputError
        ):
            structured_claim_fusion.build_structured_claim_fusion_context(
                subject_key=SUBJECT,
                allowed_entity_keys=(REAL_MADRID,),
            )

    def test_06_entity_metadata_is_preserved(self):
        value = context()
        self.assertEqual(
            value["allowed_entities"][REAL_MADRID]["canonical_name"],
            "Real Madrid",
        )

    def test_07_entity_type_is_inferred_from_key(self):
        value = structured_claim_fusion.build_structured_claim_fusion_context(
            subject_key=SUBJECT,
            allowed_entity_keys=(SUBJECT,),
        )
        self.assertEqual(
            value["allowed_entities"][SUBJECT]["entity_type"],
            "player",
        )

    def test_08_explicit_binding_builds_runtime_context(self):
        bindings = bridge_models.BridgeBindings(
            subject_key=SUBJECT
        )
        value = structured_claim_fusion.structured_claim_fusion_context_for_bindings(
            bindings=bindings,
            allowed_entity_keys=(SUBJECT,),
        )
        self.assertEqual(value["subject_key"], SUBJECT)

    def test_09_exact_unique_resolution_builds_runtime_context(self):
        bindings = bridge_models.BridgeBindings(
            subject_resolution={
                "status": "exact_unique",
                "entity": {
                    "entity_key": SUBJECT,
                },
            }
        )
        value = structured_claim_fusion.structured_claim_fusion_context_for_bindings(
            bindings=bindings,
            allowed_entity_keys=(SUBJECT,),
        )
        self.assertEqual(value["subject_key"], SUBJECT)

    def test_10_unresolved_binding_returns_none(self):
        bindings = bridge_models.BridgeBindings()
        value = structured_claim_fusion.structured_claim_fusion_context_for_bindings(
            bindings=bindings,
            allowed_entity_keys=(SUBJECT,),
        )
        self.assertIsNone(value)

    def test_11_missing_subject_in_runtime_allowlist_returns_none(self):
        bindings = bridge_models.BridgeBindings(
            subject_key=SUBJECT
        )
        value = structured_claim_fusion.structured_claim_fusion_context_for_bindings(
            bindings=bindings,
            allowed_entity_keys=(REAL_MADRID,),
        )
        self.assertIsNone(value)

    def test_12_prompt_fragment_requires_valid_context(self):
        with self.assertRaises(
            structured_claim_fusion.StructuredClaimFusionInputError
        ):
            structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
                {"version": "wrong"}
            )

    def test_13_prompt_fragment_contains_expected_subject(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn(SUBJECT, prompt)

    def test_14_prompt_fragment_contains_allowlisted_entity_keys(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn(REAL_MADRID, prompt)
        self.assertIn(DORTMUND, prompt)

    def test_15_prompt_fragment_uses_three_way_statuses(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn("extracted", prompt)
        self.assertIn("partial", prompt)
        self.assertIn("insufficient", prompt)

    def test_16_prompt_fragment_requires_router_output_version(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn(
            router.CLAIM_SEMANTIC_EXTRACTION_ROUTER_OUTPUT_VERSION,
            prompt,
        )

    def test_17_prompt_forbids_nested_candidate_version(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn(
            "Never put a contract version inside the nested candidate",
            prompt,
        )

    def test_18_prompt_declares_no_truth_or_merit_authority(self):
        prompt = structured_claim_fusion.build_structured_claim_fusion_prompt_fragment(
            context()
        )
        self.assertIn("does not decide identity", prompt)
        self.assertIn("truth", prompt)
        self.assertIn("Merit", prompt)

    def test_19_default_fusion_prompt_stays_unstructured(self):
        value, generator = interpreter(
            {
                "alignment_assessments": [],
                "claim_candidates": [],
            }
        )
        value.fuse(
            [text_artifact()],
            caption_media_pairs=[],
        )
        prompt = generator.calls[0]["contents"][0]
        self.assertNotIn("Task 3:", prompt)
        self.assertNotIn("structured_claim_output", prompt)

    def test_20_structured_context_extends_same_fusion_prompt(self):
        value, generator = interpreter(
            {
                "alignment_assessments": [],
                "claim_candidates": [],
            }
        )
        value.fuse(
            [text_artifact()],
            caption_media_pairs=[],
            structured_claim_context=context(),
        )
        self.assertEqual(len(generator.calls), 1)
        self.assertEqual(generator.calls[0]["mode"], "multimodal_fusion")
        prompt = generator.calls[0]["contents"][0]
        self.assertIn("Task 3:", prompt)
        self.assertIn("structured_claim_output", prompt)

    def test_21_structured_fusion_preserves_router_envelope(self):
        proposal = partial_output()
        value, _generator = interpreter(
            {
                "alignment_assessments": [],
                "claim_candidates": [
                    {
                        "text": (
                            "Jude Bellingham later scored in a league match."
                        ),
                        "confidence": 0.8,
                        "source_artifact_ids": ["source:text"],
                        "modality_sources": ["text"],
                        "uncertainty": "",
                        "structured_claim_output": proposal,
                    }
                ],
            }
        )
        result = value.fuse(
            [text_artifact()],
            caption_media_pairs=[],
            structured_claim_context=context(),
        )
        self.assertEqual(
            result["claim_candidates"][0]["structured_claim_output"],
            proposal,
        )

    def test_22_structured_output_does_not_change_candidate_id_formula(self):
        base = {
            "alignment_assessments": [],
            "claim_candidates": [
                {
                    "text": "Jude Bellingham later scored in a league match.",
                    "confidence": 0.8,
                    "source_artifact_ids": ["source:text"],
                    "modality_sources": ["text"],
                    "uncertainty": "",
                }
            ],
        }
        structured = json.loads(json.dumps(base))
        structured["claim_candidates"][0]["structured_claim_output"] = partial_output()
        first, _ = interpreter(base)
        second, _ = interpreter(structured)
        left = first.fuse([text_artifact()], caption_media_pairs=[])
        right = second.fuse(
            [text_artifact()],
            caption_media_pairs=[],
            structured_claim_context=context(),
        )
        self.assertEqual(
            left["claim_candidates"][0]["candidate_id"],
            right["claim_candidates"][0]["candidate_id"],
        )

    def test_23_executor_forwards_structured_context_to_fusion(self):
        class StubInterpreter:
            def __init__(self):
                self.context = None

            def fuse(
                self,
                _artifacts,
                *,
                caption_media_pairs,
                structured_claim_context=None,
            ):
                self.context = structured_claim_context
                return {
                    "model": "stub",
                    "alignment_assessments": [],
                    "claim_candidates": [],
                    "context_artifact_ids": [],
                }

        stub = StubInterpreter()
        executors = semantic_execution.build_semantic_executors(
            object(),
            interpreter=stub,
            perception_executor_builder=lambda *_args, **_kwargs: {},
            structured_claim_context=context(),
        )
        work = artifact_models.ArtifactWorkUnit(
            work_id="work:fusion",
            operation="multimodal_semantic_fusion",
            source_item_ids=["item:test"],
            source_component_ids=["body"],
            parameters={"caption_media_pairs": []},
        )
        executors["multimodal_semantic_fusion"](
            work,
            [text_artifact()],
            {},
        )
        self.assertEqual(stub.context["subject_key"], SUBJECT)

    def test_24_policy_has_no_identity_authority(self):
        policy = structured_claim_fusion.STRUCTURED_CLAIM_FUSION_POLICY
        self.assertTrue(policy["fusion_does_not_establish_identity"])
        self.assertTrue(policy["fusion_does_not_establish_truth"])
        self.assertTrue(policy["fusion_does_not_affect_live_merit"])


if __name__ == "__main__":
    unittest.main()
