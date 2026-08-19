from __future__ import annotations

from typing import Callable

from app.ai.benchmark import (
    ArticleBenchmarkCase,
    compile_article_single_pass_evaluation_cases,
)
from app.ai.benchmark_corpus import (
    ARTICLE_BENCHMARK_CORPUS_VERSION,
    HIGH_INFORMATION_GENERATION_CASE_IDS,
    select_golden_article_cases,
)
from app.ai.evaluation import (
    EvaluationBudget,
    EvaluationPlan,
    build_generation_evaluation_plan,
)
from app.ai.routed_generation import project_capacity_configured


GENERATION_BENCHMARK_CAMPAIGN_VERSION = (
    "sportabase-google-generation-campaign-v1"
)

HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS = (
    "gemini-3.6-flash",
    "gemma-4-26b-a4b-it",
)

HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS = 15
HIGH_INFORMATION_CAMPAIGN_MAX_ESTIMATED_INPUT_TOKENS = 100_000


def build_high_information_generation_campaign(
    *,
    capacity_configured_resolver: Callable[[object], bool] = (
        project_capacity_configured
    ),
) -> tuple[tuple[ArticleBenchmarkCase, ...], EvaluationPlan]:
    cases = select_golden_article_cases(
        HIGH_INFORMATION_GENERATION_CASE_IDS
    )
    evaluation_cases = compile_article_single_pass_evaluation_cases(
        cases
    )

    plan = build_generation_evaluation_plan(
        evaluation_cases,
        candidate_resource_ids=(
            HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS
        ),
        include_primary=True,
        budget=EvaluationBudget(
            max_provider_calls=(
                HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS
            ),
            max_estimated_input_tokens=(
                HIGH_INFORMATION_CAMPAIGN_MAX_ESTIMATED_INPUT_TOKENS
            ),
        ),
        capacity_configured_resolver=(
            capacity_configured_resolver
        ),
    )

    expected_calls = (
        len(cases)
        * (1 + len(HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS))
    )

    if expected_calls != HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS:
        raise RuntimeError(
            "High-information campaign definition drifted from its "
            "provider-call budget."
        )

    if plan.planned_provider_calls != expected_calls:
        raise RuntimeError(
            "High-information campaign plan has an unexpected call count."
        )

    return cases, plan


def high_information_campaign_manifest(
    *,
    capacity_configured_resolver: Callable[[object], bool] = (
        project_capacity_configured
    ),
) -> dict[str, object]:
    cases, plan = build_high_information_generation_campaign(
        capacity_configured_resolver=(
            capacity_configured_resolver
        )
    )

    resources: list[str] = []
    for item in plan.items:
        if item.resource_id not in resources:
            resources.append(item.resource_id)

    return {
        "version": GENERATION_BENCHMARK_CAMPAIGN_VERSION,
        "corpus_version": ARTICLE_BENCHMARK_CORPUS_VERSION,
        "execution": "disabled",
        "provider_calls_made": 0,
        "case_ids": [
            case.case_id
            for case in cases
        ],
        "article_types": [
            case.expected_article_type
            for case in cases
        ],
        "resource_ids": resources,
        "challenger_resource_ids": list(
            HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS
        ),
        "plan": plan.as_dict(),
    }


__all__ = [
    "GENERATION_BENCHMARK_CAMPAIGN_VERSION",
    "HIGH_INFORMATION_CHALLENGER_RESOURCE_IDS",
    "HIGH_INFORMATION_CAMPAIGN_MAX_PROVIDER_CALLS",
    "HIGH_INFORMATION_CAMPAIGN_MAX_ESTIMATED_INPUT_TOKENS",
    "build_high_information_generation_campaign",
    "high_information_campaign_manifest",
]
