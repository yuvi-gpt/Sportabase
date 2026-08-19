from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.ai.benchmark import (
    ArticleBenchmarkCase,
    ArticleBenchmarkObservationScore,
    score_article_single_pass_observation,
)
from app.ai.evaluation import EvaluationObservation


ARTICLE_BENCHMARK_REPORTING_VERSION = (
    "sportabase-article-benchmark-reporting-v2"
)


@dataclass(frozen=True)
class ArticleResourceQualityReliabilitySummary:
    resource_id: str
    observation_count: int
    success_count: int
    failure_count: int
    success_rate: float
    successful_average_score: float | None
    reliability_adjusted_average_score: float
    successful_classification_accuracy: float | None
    successful_json_valid_rate: float | None
    successful_bullet_contract_rate: float | None
    successful_average_required_fact_coverage: float | None
    successful_average_latency_ms: float | None
    successful_average_total_tokens: float | None
    failure_type_counts: Mapping[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "observation_count": self.observation_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "successful_average_score": self.successful_average_score,
            "reliability_adjusted_average_score": (
                self.reliability_adjusted_average_score
            ),
            "successful_classification_accuracy": (
                self.successful_classification_accuracy
            ),
            "successful_json_valid_rate": self.successful_json_valid_rate,
            "successful_bullet_contract_rate": (
                self.successful_bullet_contract_rate
            ),
            "successful_average_required_fact_coverage": (
                self.successful_average_required_fact_coverage
            ),
            "successful_average_latency_ms": (
                self.successful_average_latency_ms
            ),
            "successful_average_total_tokens": (
                self.successful_average_total_tokens
            ),
            "failure_type_counts": dict(self.failure_type_counts),
        }


@dataclass(frozen=True)
class ArticleQualityReliabilityReport:
    version: str
    observation_scores: tuple[ArticleBenchmarkObservationScore, ...]
    resource_summaries: tuple[
        ArticleResourceQualityReliabilitySummary,
        ...,
    ]

    def as_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "observation_scores": [
                score.as_dict()
                for score in self.observation_scores
            ],
            "resource_summaries": [
                summary.as_dict()
                for summary in self.resource_summaries
            ],
        }


def _average(values: Sequence[float]) -> float:
    return (
        sum(float(value) for value in values) / len(values)
        if values
        else 0.0
    )


def _average_or_none(
    values: Sequence[float],
    *,
    digits: int = 6,
) -> float | None:
    if not values:
        return None
    return round(_average(values), digits)


def _failure_type_counts(
    observations: Sequence[EvaluationObservation],
) -> dict[str, int]:
    counts: dict[str, int] = {}

    for observation in observations:
        if observation.success:
            continue

        failure_type = str(
            observation.failure_type or "unknown"
        ).strip() or "unknown"

        counts[failure_type] = counts.get(failure_type, 0) + 1

    return dict(sorted(counts.items()))


def score_article_observations_with_reliability(
    observations: Sequence[EvaluationObservation],
    *,
    cases: Sequence[ArticleBenchmarkCase],
) -> ArticleQualityReliabilityReport:
    normalized_observations = tuple(observations)
    normalized_cases = tuple(cases)

    if not normalized_observations:
        raise ValueError("At least one benchmark observation is required.")

    cases_by_id = {
        case.case_id: case
        for case in normalized_cases
    }

    scores: list[ArticleBenchmarkObservationScore] = []

    for observation in normalized_observations:
        try:
            case = cases_by_id[observation.case_id]
        except KeyError as error:
            raise KeyError(
                "Evaluation observation has no benchmark case: "
                + observation.case_id
            ) from error

        scores.append(
            score_article_single_pass_observation(
                observation,
                case=case,
            )
        )

    resource_ids: list[str] = []

    for observation in normalized_observations:
        if observation.resource_id not in resource_ids:
            resource_ids.append(observation.resource_id)

    summaries: list[ArticleResourceQualityReliabilitySummary] = []

    for resource_id in resource_ids:
        resource_pairs = [
            (observation, score)
            for observation, score in zip(
                normalized_observations,
                scores,
            )
            if observation.resource_id == resource_id
        ]

        resource_observations = [
            observation
            for observation, _ in resource_pairs
        ]
        resource_scores = [
            score
            for _, score in resource_pairs
        ]
        successful_scores = [
            score
            for score in resource_scores
            if score.success
        ]

        observation_count = len(resource_scores)
        success_count = len(successful_scores)
        failure_count = observation_count - success_count

        summaries.append(
            ArticleResourceQualityReliabilitySummary(
                resource_id=resource_id,
                observation_count=observation_count,
                success_count=success_count,
                failure_count=failure_count,
                success_rate=round(
                    (
                        success_count / observation_count
                        if observation_count
                        else 0.0
                    ),
                    6,
                ),
                successful_average_score=_average_or_none(
                    [
                        score.overall_score
                        for score in successful_scores
                    ]
                ),
                reliability_adjusted_average_score=round(
                    _average(
                        [
                            score.overall_score
                            for score in resource_scores
                        ]
                    ),
                    6,
                ),
                successful_classification_accuracy=(
                    _average_or_none(
                        [
                            1.0
                            if score.classification_correct
                            else 0.0
                            for score in successful_scores
                        ]
                    )
                ),
                successful_json_valid_rate=_average_or_none(
                    [
                        1.0 if score.json_valid else 0.0
                        for score in successful_scores
                    ]
                ),
                successful_bullet_contract_rate=_average_or_none(
                    [
                        1.0
                        if score.bullet_contract_met
                        else 0.0
                        for score in successful_scores
                    ]
                ),
                successful_average_required_fact_coverage=(
                    _average_or_none(
                        [
                            score.required_fact_coverage
                            for score in successful_scores
                        ]
                    )
                ),
                successful_average_latency_ms=_average_or_none(
                    [
                        float(score.latency_ms)
                        for score in successful_scores
                    ],
                    digits=3,
                ),
                successful_average_total_tokens=_average_or_none(
                    [
                        float(score.total_tokens)
                        for score in successful_scores
                    ],
                    digits=3,
                ),
                failure_type_counts=_failure_type_counts(
                    resource_observations
                ),
            )
        )

    summaries.sort(
        key=lambda summary: (
            -summary.success_rate,
            -(
                summary.successful_average_score
                if summary.successful_average_score is not None
                else -1.0
            ),
            (
                summary.successful_average_latency_ms
                if summary.successful_average_latency_ms is not None
                else float("inf")
            ),
            summary.resource_id,
        )
    )

    return ArticleQualityReliabilityReport(
        version=ARTICLE_BENCHMARK_REPORTING_VERSION,
        observation_scores=tuple(scores),
        resource_summaries=tuple(summaries),
    )


def evaluation_observation_from_payload(
    payload: Mapping[str, Any],
) -> EvaluationObservation:
    return EvaluationObservation(
        case_id=str(payload.get("case_id", "")),
        task_id=str(payload.get("task_id", "")),
        resource_id=str(payload.get("resource_id", "")),
        success=bool(payload.get("success", False)),
        latency_ms=int(payload.get("latency_ms", 0) or 0),
        prompt_tokens=int(payload.get("prompt_tokens", 0) or 0),
        output_tokens=int(payload.get("output_tokens", 0) or 0),
        thought_tokens=int(payload.get("thought_tokens", 0) or 0),
        total_tokens=int(payload.get("total_tokens", 0) or 0),
        output=payload.get("output"),
        failure_type=str(payload.get("failure_type", "") or ""),
        failure_detail=str(payload.get("failure_detail", "") or ""),
    )


__all__ = [
    "ARTICLE_BENCHMARK_REPORTING_VERSION",
    "ArticleResourceQualityReliabilitySummary",
    "ArticleQualityReliabilityReport",
    "score_article_observations_with_reliability",
    "evaluation_observation_from_payload",
]
