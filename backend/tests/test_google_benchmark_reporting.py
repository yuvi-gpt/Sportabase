from __future__ import annotations

import json
import sys
import unittest

from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.ai.benchmark import article_benchmark_case
from app.ai.benchmark_reporting import (
    ARTICLE_BENCHMARK_REPORTING_VERSION,
    evaluation_observation_from_payload,
    score_article_observations_with_reliability,
)
from app.ai.evaluation import EvaluationObservation
from app.ai.tasks import ARTICLE_SINGLE_PASS


class GoogleBenchmarkReportingTests(unittest.TestCase):
    def _observation(
        self,
        *,
        case_id: str,
        resource_id: str,
        article_type: str,
        bullets: list[str],
        success: bool = True,
        latency_ms: int = 100,
        total_tokens: int = 50,
        failure_type: str = "",
        failure_detail: str = "",
    ) -> EvaluationObservation:
        output = None

        if success:
            output = {
                "text": json.dumps(
                    {
                        "article_type": article_type,
                        "article_subtype": "benchmark",
                        "confidence": 0.9,
                        "reason": "Benchmark result.",
                        "bullets": bullets,
                        "ui_labels": {},
                    }
                )
            }

        return EvaluationObservation(
            case_id=case_id,
            task_id=ARTICLE_SINGLE_PASS,
            resource_id=resource_id,
            success=success,
            latency_ms=latency_ms,
            prompt_tokens=30 if success else 0,
            output_tokens=20 if success else 0,
            thought_tokens=0,
            total_tokens=total_tokens if success else 0,
            output=output,
            failure_type=failure_type,
            failure_detail=failure_detail,
        )

    def test_successful_quality_is_not_dragged_down_by_provider_failure(self):
        case = article_benchmark_case(
            "injury-confirmed-club-statement"
        )
        bullets = [
            "Riverside Athletic confirmed Luis Moreno underwent ACL surgery.",
            "Luis Moreno is expected to miss approximately six months.",
            "Riverside will review the timetable during rehabilitation.",
        ]

        observations = (
            self._observation(
                case_id=case.case_id,
                resource_id="gemini-3.7-flash",
                article_type="injury_confirmed",
                bullets=bullets,
                success=True,
            ),
            self._observation(
                case_id=case.case_id,
                resource_id="gemini-3.7-flash",
                article_type="injury_confirmed",
                bullets=bullets,
                success=False,
                failure_type="ServerError",
                failure_detail="503 UNAVAILABLE",
            ),
        )

        report = score_article_observations_with_reliability(
            observations,
            cases=(case,),
        )
        summary = report.resource_summaries[0]

        self.assertEqual(
            report.version,
            ARTICLE_BENCHMARK_REPORTING_VERSION,
        )
        self.assertEqual(summary.observation_count, 2)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.failure_count, 1)
        self.assertEqual(summary.success_rate, 0.5)
        self.assertEqual(summary.successful_average_score, 1.0)
        self.assertEqual(
            summary.reliability_adjusted_average_score,
            0.5,
        )
        self.assertEqual(
            summary.successful_classification_accuracy,
            1.0,
        )
        self.assertEqual(
            summary.failure_type_counts,
            {"ServerError": 1},
        )

    def test_zero_successes_report_quality_as_unknown_not_zero(self):
        case = article_benchmark_case(
            "transfer-roundup-grades"
        )

        observations = (
            self._observation(
                case_id=case.case_id,
                resource_id="gemma-4-31b-it",
                article_type="transfer_roundup",
                bullets=[],
                success=False,
                failure_type="ServerError",
                failure_detail="500 INTERNAL",
            ),
            self._observation(
                case_id=case.case_id,
                resource_id="gemma-4-31b-it",
                article_type="transfer_roundup",
                bullets=[],
                success=False,
                failure_type="ServerError",
                failure_detail="503 UNAVAILABLE",
            ),
        )

        report = score_article_observations_with_reliability(
            observations,
            cases=(case,),
        )
        summary = report.resource_summaries[0]

        self.assertEqual(summary.success_rate, 0.0)
        self.assertIsNone(summary.successful_average_score)
        self.assertIsNone(
            summary.successful_classification_accuracy
        )
        self.assertIsNone(summary.successful_json_valid_rate)
        self.assertIsNone(
            summary.successful_average_required_fact_coverage
        )
        self.assertEqual(
            summary.reliability_adjusted_average_score,
            0.0,
        )
        self.assertEqual(
            summary.failure_type_counts,
            {"ServerError": 2},
        )

    def test_resource_order_prioritizes_reliability_before_quality(self):
        official = article_benchmark_case(
            "transfer-official-clear"
        )
        perfect_bullets = [
            "Mateo Silva joined Northbridge FC on a permanent transfer.",
            "Silva signed a four-year contract running until June 2030.",
            "Portside United separately confirmed the completed move.",
        ]
        partial_bullets = [
            "Mateo Silva joined Northbridge FC on a permanent transfer.",
            "Portside United separately confirmed the completed move.",
            "The move was announced by both clubs.",
        ]

        observations = (
            self._observation(
                case_id=official.case_id,
                resource_id="stable-model",
                article_type="transfer_official",
                bullets=partial_bullets,
            ),
            self._observation(
                case_id=official.case_id,
                resource_id="stable-model",
                article_type="transfer_official",
                bullets=partial_bullets,
            ),
            self._observation(
                case_id=official.case_id,
                resource_id="flaky-model",
                article_type="transfer_official",
                bullets=perfect_bullets,
            ),
            self._observation(
                case_id=official.case_id,
                resource_id="flaky-model",
                article_type="transfer_official",
                bullets=perfect_bullets,
                success=False,
                failure_type="ServerError",
            ),
        )

        report = score_article_observations_with_reliability(
            observations,
            cases=(official,),
        )

        self.assertEqual(
            tuple(
                summary.resource_id
                for summary in report.resource_summaries
            ),
            (
                "stable-model",
                "flaky-model",
            ),
        )

    def test_payload_round_trip_preserves_failure_metadata(self):
        payload = {
            "case_id": "transfer-roundup-grades",
            "task_id": ARTICLE_SINGLE_PASS,
            "resource_id": "gemma-4-31b-it",
            "success": False,
            "latency_ms": 41078,
            "prompt_tokens": 0,
            "output_tokens": 0,
            "thought_tokens": 0,
            "total_tokens": 0,
            "output": None,
            "failure_type": "ServerError",
            "failure_detail": "503 UNAVAILABLE",
        }

        observation = evaluation_observation_from_payload(payload)

        self.assertFalse(observation.success)
        self.assertEqual(
            observation.resource_id,
            "gemma-4-31b-it",
        )
        self.assertEqual(
            observation.failure_type,
            "ServerError",
        )
        self.assertEqual(
            observation.failure_detail,
            "503 UNAVAILABLE",
        )
        self.assertEqual(observation.latency_ms, 41078)


if __name__ == "__main__":
    unittest.main()
