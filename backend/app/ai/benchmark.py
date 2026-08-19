from __future__ import annotations

import json

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from app.ai.evaluation import (
    EvaluationBudget,
    EvaluationCase,
    EvaluationObservation,
    EvaluationPlan,
    EvaluationRun,
    build_generation_evaluation_plan,
)
from app.ai.tasks import ARTICLE_SINGLE_PASS
from app.application.config import MAX_ANALYZE_CHARS
from app.services.article_analysis import (
    extractive_fallback,
    gemini_article_single_pass_impl,
    normalize_article_bullets,
)
from app.services.article_rules import (
    AI_ARTICLE_TYPE_VALUES,
    normalize_ai_article_classification,
)


ARTICLE_BENCHMARK_VERSION = "sportabase-article-benchmark-v1"

DEFAULT_LIVE_BENCHMARK_CASE_IDS = (
    "transfer-official-clear",
    "transfer-rumor-hedged",
)

DEFAULT_CHALLENGER_RESOURCE_IDS = (
    "gemini-3.6-flash",
    "gemma-4-26b-a4b-it",
)


@dataclass(frozen=True)
class ArticleBenchmarkCase:
    case_id: str
    title: str
    text: str
    url: str
    expected_article_type: str
    required_facts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.case_id or "").strip():
            raise ValueError("Benchmark case ID is required.")
        if not str(self.title or "").strip():
            raise ValueError("Benchmark title is required.")
        if not str(self.text or "").strip():
            raise ValueError("Benchmark article text is required.")
        if self.expected_article_type not in AI_ARTICLE_TYPE_VALUES:
            raise ValueError(
                "Unsupported benchmark article type: "
                + str(self.expected_article_type)
            )


GOLDEN_ARTICLE_SINGLE_PASS_CASES = (
    ArticleBenchmarkCase(
        case_id="transfer-official-clear",
        title="Northbridge FC complete signing of Mateo Silva",
        text=(
            "Northbridge FC announced on its official website that midfielder "
            "Mateo Silva has joined from Portside United on a permanent "
            "transfer. Silva signed a four-year contract running until June "
            "2030, and the club published photographs of him signing the deal "
            "and holding the Northbridge shirt. Portside United separately "
            "confirmed the permanent transfer and thanked Silva for his time "
            "at the club. No transfer fee was disclosed."
        ),
        url="https://northbridge.example/news/mateo-silva-signing",
        expected_article_type="transfer_official",
        required_facts=(
            "Mateo Silva",
            "Northbridge FC",
            "four-year contract",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="transfer-rumor-hedged",
        title=(
            "Eastport United monitoring Jonas Keller "
            "ahead of summer window"
        ),
        text=(
            "Eastport United are monitoring Westhaven midfielder Jonas "
            "Keller ahead of the summer transfer window, according to two "
            "reports. Keller is said to be one of several names on the club's "
            "shortlist, but Eastport have not submitted a bid and Westhaven "
            "have received no formal offer. There is no agreement with the "
            "player or his club, and neither side has announced negotiations."
        ),
        url=(
            "https://daily-sport.example/transfers/"
            "eastport-jonas-keller-interest"
        ),
        expected_article_type="transfer_rumor",
        required_facts=(
            "Jonas Keller",
            "Eastport United",
            "no formal offer",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="transfer-roundup-grades",
        title="Summer transfer grades: ranking Harbor City's five signings",
        text=(
            "Harbor City completed five first-team signings during the summer "
            "window. This review grades each deal from A to F, comparing fee, "
            "squad fit and expected role. Defender Amir Haddad receives an A, "
            "midfielder Luca Moretti a B+, winger Kenji Sato a B, goalkeeper "
            "Milan Vukovic a C+, and forward Tomas Reyes a B-. The article is "
            "a retrospective assessment of multiple completed transfers rather "
            "than a report of a new deal."
        ),
        url=(
            "https://football-review.example/harbor-city/"
            "summer-transfer-grades"
        ),
        expected_article_type="transfer_roundup",
        required_facts=(
            "five",
            "Harbor City",
            "Amir Haddad",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="injury-confirmed-club-statement",
        title=(
            "Riverside confirms Luis Moreno out for six months after ACL surgery"
        ),
        text=(
            "Riverside Athletic confirmed in a club statement that captain "
            "Luis Moreno underwent successful surgery after suffering an ACL "
            "injury in Saturday's league match. The club's medical department "
            "expects Moreno to miss approximately six months while completing "
            "rehabilitation. Riverside said the timetable will be reviewed "
            "during recovery and wished the player well."
        ),
        url="https://riverside.example/medical-update/luis-moreno-acl",
        expected_article_type="injury_confirmed",
        required_facts=(
            "Luis Moreno",
            "ACL",
            "six months",
        ),
    ),
)

_CASES_BY_ID = {
    case.case_id: case
    for case in GOLDEN_ARTICLE_SINGLE_PASS_CASES
}


@dataclass(frozen=True)
class ArticleBenchmarkObservationScore:
    case_id: str
    resource_id: str
    success: bool
    json_valid: bool
    classification_correct: bool
    bullet_contract_met: bool
    required_fact_hits: int
    required_fact_count: int
    required_fact_coverage: float
    overall_score: float
    latency_ms: int
    total_tokens: int

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ArticleBenchmarkResourceSummary:
    resource_id: str
    observation_count: int
    success_count: int
    average_score: float
    classification_accuracy: float
    json_valid_rate: float
    bullet_contract_rate: float
    average_required_fact_coverage: float
    average_latency_ms: float
    average_total_tokens: float

    def as_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ArticleBenchmarkReport:
    version: str
    observation_scores: tuple[ArticleBenchmarkObservationScore, ...]
    resource_summaries: tuple[ArticleBenchmarkResourceSummary, ...]

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


def article_benchmark_case(case_id: str) -> ArticleBenchmarkCase:
    normalized = str(case_id or "").strip()
    try:
        return _CASES_BY_ID[normalized]
    except KeyError as error:
        raise KeyError(
            "Unknown article benchmark case: " + normalized
        ) from error


def select_article_benchmark_cases(
    case_ids: Sequence[str] | None = None,
) -> tuple[ArticleBenchmarkCase, ...]:
    selected_ids = (
        tuple(case_ids)
        if case_ids is not None
        else DEFAULT_LIVE_BENCHMARK_CASE_IDS
    )
    if not selected_ids:
        raise ValueError("At least one benchmark case is required.")

    cases = tuple(
        article_benchmark_case(case_id)
        for case_id in selected_ids
    )
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate benchmark case IDs are not allowed.")
    return cases


def _captured_article_single_pass_prompt(
    case: ArticleBenchmarkCase,
) -> str:
    captured: dict[str, Any] = {}

    def capture_generator(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "article_type": case.expected_article_type,
                    "article_subtype": "benchmark_capture",
                    "confidence": 0.9,
                    "reason": "Benchmark prompt capture.",
                    "bullets": [
                        "Benchmark capture sentence one.",
                        "Benchmark capture sentence two.",
                        "Benchmark capture sentence three.",
                    ],
                    "ui_labels": {},
                }
            )
        )

    gemini_article_single_pass_impl(
        title=case.title,
        text=case.text,
        url=case.url,
        max_bullets=3,
        language_info={
            "detected_language": "English",
            "mixed_language": False,
        },
        client_key="benchmark-prompt-capture",
        client_factory=lambda: object(),
        generator=capture_generator,
        fallback_resolver=extractive_fallback,
        bullet_normalizer=normalize_article_bullets,
        classification_normalizer=normalize_ai_article_classification,
        max_analyze_chars=MAX_ANALYZE_CHARS,
    )

    mode = str(captured.get("mode", "")).strip()
    model = str(captured.get("model", "")).strip()
    prompt = captured.get("contents")

    if mode != ARTICLE_SINGLE_PASS:
        raise RuntimeError(
            "Production article prompt capture returned unexpected task mode."
        )
    if model != "gemini-3.5-flash":
        raise RuntimeError(
            "Production article prompt capture returned unexpected baseline model."
        )
    if not isinstance(prompt, str) or not prompt.strip():
        raise RuntimeError("Production article prompt capture returned no prompt.")
    return prompt


def compile_article_single_pass_evaluation_cases(
    cases: Sequence[ArticleBenchmarkCase],
) -> tuple[EvaluationCase, ...]:
    return tuple(
        EvaluationCase(
            case_id=case.case_id,
            task_id=ARTICLE_SINGLE_PASS,
            contents=_captured_article_single_pass_prompt(case),
        )
        for case in tuple(cases)
    )


def build_article_single_pass_benchmark_plan(
    *,
    case_ids: Sequence[str] | None = None,
    candidate_resource_ids: Sequence[str] = DEFAULT_CHALLENGER_RESOURCE_IDS,
    budget: EvaluationBudget | None = None,
    capacity_configured_resolver=None,
) -> tuple[tuple[ArticleBenchmarkCase, ...], EvaluationPlan]:
    cases = select_article_benchmark_cases(case_ids)
    evaluation_cases = compile_article_single_pass_evaluation_cases(cases)

    kwargs: dict[str, Any] = {
        "candidate_resource_ids": tuple(candidate_resource_ids),
        "include_primary": True,
        "budget": budget or EvaluationBudget(),
    }
    if capacity_configured_resolver is not None:
        kwargs["capacity_configured_resolver"] = (
            capacity_configured_resolver
        )

    plan = build_generation_evaluation_plan(
        evaluation_cases,
        **kwargs,
    )
    return cases, plan


def _output_text(output: Any) -> str:
    value = (
        output.get("text", "")
        if isinstance(output, Mapping)
        else getattr(output, "text", "")
    )
    return str(value or "").strip()


def _parsed_json_payload(output: Any) -> tuple[bool, dict[str, Any]]:
    raw = _output_text(output)
    if not raw:
        return False, {}

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]

    try:
        parsed = json.loads(raw)
    except Exception:
        return False, {}
    return (
        (True, parsed)
        if isinstance(parsed, dict)
        else (False, {})
    )


def score_article_single_pass_observation(
    observation: EvaluationObservation,
    *,
    case: ArticleBenchmarkCase,
) -> ArticleBenchmarkObservationScore:
    if observation.case_id != case.case_id:
        raise ValueError("Observation/case ID mismatch.")

    json_valid, payload = _parsed_json_payload(observation.output)
    article_type = str(payload.get("article_type", "")).strip()
    classification_correct = bool(
        observation.success
        and json_valid
        and article_type == case.expected_article_type
    )

    raw_bullets = payload.get("bullets", [])
    bullets = (
        [
            str(item).strip()
            for item in raw_bullets
            if isinstance(item, str) and str(item).strip()
        ]
        if isinstance(raw_bullets, list)
        else []
    )
    bullet_contract_met = bool(
        observation.success
        and json_valid
        and len(bullets) == 3
        and len({item.lower() for item in bullets}) == 3
    )

    searchable = " ".join(
        [
            article_type,
            *bullets,
            str(payload.get("reason", "")),
        ]
    ).lower()
    required_fact_hits = sum(
        1
        for fact in case.required_facts
        if str(fact).lower() in searchable
    )
    required_fact_count = len(case.required_facts)
    required_fact_coverage = (
        required_fact_hits / required_fact_count
        if required_fact_count
        else 1.0
    )

    overall_score = (
        (0.15 if json_valid else 0.0)
        + (0.45 if classification_correct else 0.0)
        + (0.15 if bullet_contract_met else 0.0)
        + (0.25 * required_fact_coverage)
    )
    if not observation.success:
        overall_score = 0.0

    return ArticleBenchmarkObservationScore(
        case_id=case.case_id,
        resource_id=observation.resource_id,
        success=observation.success,
        json_valid=json_valid,
        classification_correct=classification_correct,
        bullet_contract_met=bullet_contract_met,
        required_fact_hits=required_fact_hits,
        required_fact_count=required_fact_count,
        required_fact_coverage=round(required_fact_coverage, 6),
        overall_score=round(overall_score, 6),
        latency_ms=int(observation.latency_ms),
        total_tokens=int(observation.total_tokens),
    )


def _average(values: Sequence[float]) -> float:
    return (
        sum(float(value) for value in values) / len(values)
        if values
        else 0.0
    )


def score_article_single_pass_run(
    run: EvaluationRun,
    *,
    cases: Sequence[ArticleBenchmarkCase],
) -> ArticleBenchmarkReport:
    cases_by_id = {
        case.case_id: case
        for case in cases
    }
    scores = []

    for observation in run.observations:
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

    resource_ids = []
    for score in scores:
        if score.resource_id not in resource_ids:
            resource_ids.append(score.resource_id)

    summaries = []
    for resource_id in resource_ids:
        resource_scores = [
            score
            for score in scores
            if score.resource_id == resource_id
        ]
        summaries.append(
            ArticleBenchmarkResourceSummary(
                resource_id=resource_id,
                observation_count=len(resource_scores),
                success_count=sum(
                    1 for score in resource_scores if score.success
                ),
                average_score=round(
                    _average([s.overall_score for s in resource_scores]), 6
                ),
                classification_accuracy=round(
                    _average([
                        1.0 if s.classification_correct else 0.0
                        for s in resource_scores
                    ]),
                    6,
                ),
                json_valid_rate=round(
                    _average([
                        1.0 if s.json_valid else 0.0
                        for s in resource_scores
                    ]),
                    6,
                ),
                bullet_contract_rate=round(
                    _average([
                        1.0 if s.bullet_contract_met else 0.0
                        for s in resource_scores
                    ]),
                    6,
                ),
                average_required_fact_coverage=round(
                    _average([
                        s.required_fact_coverage
                        for s in resource_scores
                    ]),
                    6,
                ),
                average_latency_ms=round(
                    _average([
                        float(s.latency_ms)
                        for s in resource_scores
                    ]),
                    3,
                ),
                average_total_tokens=round(
                    _average([
                        float(s.total_tokens)
                        for s in resource_scores
                    ]),
                    3,
                ),
            )
        )

    summaries.sort(
        key=lambda summary: (
            -summary.average_score,
            summary.average_latency_ms,
            summary.resource_id,
        )
    )
    return ArticleBenchmarkReport(
        version=ARTICLE_BENCHMARK_VERSION,
        observation_scores=tuple(scores),
        resource_summaries=tuple(summaries),
    )


__all__ = [
    "ARTICLE_BENCHMARK_VERSION",
    "DEFAULT_LIVE_BENCHMARK_CASE_IDS",
    "DEFAULT_CHALLENGER_RESOURCE_IDS",
    "ArticleBenchmarkCase",
    "ArticleBenchmarkObservationScore",
    "ArticleBenchmarkResourceSummary",
    "ArticleBenchmarkReport",
    "GOLDEN_ARTICLE_SINGLE_PASS_CASES",
    "article_benchmark_case",
    "select_article_benchmark_cases",
    "compile_article_single_pass_evaluation_cases",
    "build_article_single_pass_benchmark_plan",
    "score_article_single_pass_observation",
    "score_article_single_pass_run",
]
