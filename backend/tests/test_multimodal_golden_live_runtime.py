from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest

from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from app.db.schema import SCHEMA
from app.intelligence import entities as entity_runtime
from evals import golden_live
from evals import golden_live_budget
from evals import golden_live_scoring
from evals import run_multimodal_golden_live


class _FakeModels:
    def __init__(self):
        self.calls = []

    def generate_content(self, *, model, contents):
        self.calls.append((model, contents))
        raise AssertionError("Provider must not be called in this test.")


class _FakeClient:
    def __init__(self):
        self.models = _FakeModels()


def _usage_db():
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "usage.db"
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return tmp, path


class TestLiveSubsetContract(unittest.TestCase):
    def test_frozen_subset_is_exactly_bellingham(self):
        self.assertEqual(
            golden_live_scoring.DEFAULT_LIVE_CASE_IDS,
            ("football_bellingham_real_madrid_2023",),
        )

    def test_provider_plan_keeps_all_three_pairs(self):
        plan = golden_live_scoring.provider_call_plan()
        self.assertEqual(plan["candidate_pair_count"], 3)
        self.assertEqual(
            plan["cases"][0]["candidate_labels"],
            [
                "related_primary",
                "related_secondary",
                "hard_negative_same_subject",
            ],
        )

    def test_provider_plan_is_six_to_twelve(self):
        plan = golden_live_scoring.provider_call_plan()
        self.assertEqual(plan["guaranteed_semantic_calls"], 6)
        self.assertEqual(plan["conditional_observation_calls"], 6)
        self.assertEqual(plan["minimum_calls"], 6)
        self.assertEqual(plan["maximum_calls"], 12)
        self.assertEqual(
            plan["possible_actual_calls"],
            [6, 8, 10, 12],
        )
        self.assertFalse(
            plan["exact_pre_run_count_available"]
        )

    def test_eval_pair_client_buckets_are_three_distinct_keys(self):
        mapping = golden_live.EVAL_CLIENT_KEYS_BY_LABEL
        self.assertEqual(
            set(mapping),
            {
                "related_primary",
                "related_secondary",
                "hard_negative_same_subject",
            },
        )
        self.assertEqual(
            len(set(mapping.values())),
            3,
        )

    def test_live_model_is_capacity_managed_model(self):
        self.assertEqual(
            golden_live.LIVE_MODEL,
            "gemini-3.5-flash",
        )


class TestCapacityPreflight(unittest.TestCase):
    def test_empty_usage_db_has_full_envelope(self):
        tmp, path = _usage_db()
        try:
            snapshot = golden_live.live_capacity_preflight(
                usage_connection_factory=(
                    golden_live_budget
                    .sqlite_connection_factory(path)
                ),
                max_calls=12,
            )
            self.assertTrue(snapshot["ready"])
            self.assertEqual(snapshot["candidate_pair_count"], 3)
            self.assertEqual(snapshot["guaranteed_calls"], 6)
            self.assertEqual(snapshot["conditional_calls"], 6)
            self.assertEqual(
                snapshot["possible_actual_calls"],
                [6, 8, 10, 12],
            )
            self.assertEqual(snapshot["hard_eval_cap"], 12)
            self.assertEqual(
                snapshot["pair_client_bucket_count"],
                3,
            )
        finally:
            tmp.cleanup()

    def test_ten_call_budget_fails_before_provider(self):
        tmp, path = _usage_db()
        try:
            snapshot = golden_live.live_capacity_preflight(
                usage_connection_factory=(
                    golden_live_budget
                    .sqlite_connection_factory(path)
                ),
                max_calls=10,
            )
            self.assertFalse(snapshot["ready"])
            self.assertIn(
                "configured_eval_budget_below_full_case_maximum",
                snapshot["failures"],
            )
        finally:
            tmp.cleanup()

    def test_runtime_case_uses_production_entity_id(self):
        case = (
            golden_live_scoring
            .selected_cases(
                golden_live_scoring
                .DEFAULT_LIVE_CASE_IDS
            )[0]
        )

        frozen_id = (
            case["entities"][0]["id"]
        )

        runtime = (
            golden_live
            ._runtime_case(case)
        )

        expected = (
            entity_runtime
            .canonical_entity_id_for_key(
                case["entities"][0][
                    "entity_key"
                ]
            )
        )

        self.assertEqual(
            runtime["entities"][0]["id"],
            expected,
        )

        self.assertNotEqual(
            frozen_id,
            expected,
        )

        self.assertEqual(
            case["entities"][0]["id"],
            frozen_id,
        )


class TestLiveEvaluationControl(unittest.TestCase):
    def test_missing_api_key_requires_client(self):
        tmp, path = _usage_db()
        try:
            with self.assertRaises(
                golden_live_budget.MultimodalGoldenLiveInputError
            ):
                golden_live.evaluate_live_golden_subset(
                    api_key="",
                    usage_db_path=path,
                )
        finally:
            tmp.cleanup()

    def test_not_ready_is_quality_failure_not_hard_safety_failure(self):
        tmp, path = _usage_db()
        try:
            def cluster_runner(**kwargs):
                raise (
                    golden_live
                    .inbox_story_cluster_orchestration
                    .MultimodalInboxStoryClusterNotReady(
                        "no exact common claim"
                    )
                )

            report = golden_live.evaluate_live_golden_subset(
                api_key="",
                usage_db_path=path,
                client=_FakeClient(),
                cluster_runner=cluster_runner,
            )
            self.assertTrue(report["provider_complete"])
            self.assertEqual(
                report["hard_safety_status"],
                "pass",
            )
            self.assertEqual(
                report["quality_case_failures"],
                [
                    golden_live_scoring
                    .DEFAULT_LIVE_CASE_IDS[0]
                ],
            )
            self.assertEqual(
                report["provider"]["call_count"],
                0,
            )
        finally:
            tmp.cleanup()

    def test_report_declares_34a_capacity_and_real_usage_ledger(self):
        tmp, path = _usage_db()
        try:
            def cluster_runner(**kwargs):
                raise (
                    golden_live
                    .inbox_story_cluster_orchestration
                    .MultimodalInboxStoryClusterNotReady(
                        "expected"
                    )
                )

            report = golden_live.evaluate_live_golden_subset(
                api_key="",
                usage_db_path=path,
                client=_FakeClient(),
                cluster_runner=cluster_runner,
            )
            policy = report["policy"]
            self.assertTrue(
                policy["uses_product34a_capacity_runtime"]
            )
            self.assertTrue(
                policy["provider_day_preflight_required"]
            )
            self.assertTrue(
                policy["production_usage_ledger_written"]
            )
            self.assertTrue(
                policy["real_database_used_for_capacity_ledger"]
            )
            self.assertFalse(
                policy["real_database_used_for_eval_state"]
            )
            self.assertFalse(
                policy["live_merit_effect_allowed"]
            )
        finally:
            tmp.cleanup()


class TestLiveCliHelpers(unittest.TestCase):
    def test_zero_budget_is_true_dry_run(self):
        output = io.StringIO()
        with redirect_stdout(output):
            code = run_multimodal_golden_live.main(
                ["--max-calls", "0"]
            )
        self.assertEqual(code, 0)
        text = output.getvalue()
        self.assertIn(
            "exactly 0 Gemini calls made",
            text,
        )
        self.assertIn("API key read: FALSE", text)
        self.assertIn("token usage: 0", text)

    def test_cli_refuses_nonzero_without_live_opt_in(self):
        error = io.StringIO()
        with redirect_stderr(error):
            code = run_multimodal_golden_live.main([])
        self.assertEqual(code, 2)
        self.assertIn(
            "explicit --live opt-in",
            error.getvalue(),
        )

    def test_cli_rejects_budget_above_twelve(self):
        error = io.StringIO()
        with redirect_stderr(error):
            code = run_multimodal_golden_live.main(
                ["--live", "--max-calls", "13"]
            )
        self.assertEqual(code, 2)
        self.assertIn(
            "between 0 and 12",
            error.getvalue(),
        )

    def test_event_logger_prints_token_fields(self):
        output = io.StringIO()
        with redirect_stdout(output):
            run_multimodal_golden_live._provider_event_logger(
                {
                    "event": "provider_call_completed",
                    "call_index": 2,
                    "max_calls": 12,
                    "mode": "fusion",
                    "model": "gemini-test",
                    "prompt_tokens": 10,
                    "output_tokens": 5,
                    "thought_tokens": 3,
                    "cached_tokens": 1,
                    "total_tokens": 18,
                    "cumulative_calls": 2,
                    "cumulative_total_tokens": 31,
                }
            )
        text = output.getvalue()
        self.assertIn("prompt=10", text)
        self.assertIn("output=5", text)
        self.assertIn("thought=3", text)
        self.assertIn("cached=1", text)
        self.assertIn("total=18", text)
        self.assertIn("cumulative_tokens=31", text)


class TestTextOnlyGoldenSemanticAdapter(
    unittest.TestCase
):
    def test_text_only_manifest_adapter_executes_fusion(
        self,
    ):
        from app.models import artifacts as artifact_models
        from app.services import media_execution

        calls = []

        class FakeInterpreter:
            def fuse(
                self,
                artifacts,
                *,
                caption_media_pairs,
            ):
                calls.append(
                    {
                        "artifact_count":
                            len(artifacts),
                        "pairs":
                            list(
                                caption_media_pairs
                            ),
                    }
                )

                source = next(
                    artifact
                    for artifact
                    in artifacts
                    if (
                        artifact
                        .artifact_kind
                        == "text_component"
                    )
                )

                return {
                    "model": "fake-eval-model",
                    "alignment_assessments": [],
                    "claim_candidates": [
                        {
                            "candidate_id":
                                "claim-candidate:test",
                            "text":
                                (
                                    "Jude Bellingham "
                                    "completed his move "
                                    "to Real Madrid in 2023."
                                ),
                            "confidence": 0.9,
                            "source_artifact_ids": [
                                source.artifact_id
                            ],
                            "modality_sources": [
                                "text"
                            ],
                            "uncertainty": "",
                        }
                    ],
                    "context_artifact_ids": [
                        source.artifact_id
                    ],
                }

        provenance = (
            artifact_models
            .ArtifactProvenance(
                source_url=(
                    "https://eval.sportabase.test/"
                    "bellingham"
                ),
                observed_at=(
                    "2024-01-01T00:00:00Z"
                ),
                extraction_method="test",
            )
        )

        manifest = (
            artifact_models
            .ItemArtifactManifest(
                item_id="item:test",
                artifacts=[
                    artifact_models
                    .ExtractionArtifact(
                        artifact_id=(
                            "artifact:test-text"
                        ),
                        artifact_kind=(
                            "text_component"
                        ),
                        modality="text",
                        source_item_ids=[
                            "item:test"
                        ],
                        source_component_ids=[
                            "component:text"
                        ],
                        content_hash="test-hash",
                        payload={
                            "role": "body",
                            "text": (
                                "Jude Bellingham "
                                "completed his move "
                                "to Real Madrid in 2023."
                            ),
                            "language": "en",
                        },
                        provenance=provenance,
                    )
                ],
                work_units=[],
            )
        )

        with (
            media_execution
            .MediaWorkspace()
        ) as workspace:
            result = (
                golden_live
                ._eval_text_semantic_manifest(
                    manifest,
                    workspace=workspace,
                    interpreter=(
                        FakeInterpreter()
                    ),
                )
            )

        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            manifest.work_units,
            [],
        )

        fusion = [
            work
            for work
            in result.work_units
            if (
                work.operation
                == "multimodal_semantic_fusion"
            )
        ]

        self.assertEqual(
            len(fusion),
            1,
        )

        self.assertEqual(
            fusion[0].status,
            "completed",
        )

        self.assertTrue(
            any(
                artifact.artifact_kind
                == "claim_candidates"
                for artifact
                in result.artifacts
            )
        )


if __name__ == "__main__":
    unittest.main()
