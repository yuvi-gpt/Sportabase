from __future__ import annotations

from typing import Sequence

from app.ai.benchmark import (
    ArticleBenchmarkCase,
    GOLDEN_ARTICLE_SINGLE_PASS_CASES,
)


ARTICLE_BENCHMARK_CORPUS_VERSION = "sportabase-article-corpus-v2"


EXPANDED_ARTICLE_SINGLE_PASS_CASES = (
    ArticleBenchmarkCase(
        case_id="injury-rumor-training-doubt",
        title="Northbridge sweating on Pavel Orlov fitness before derby",
        text=(
            "Northbridge FC midfielder Pavel Orlov is a doubt for Saturday's "
            "derby after missing part of Thursday training with what local "
            "reports describe as hamstring tightness. The club has not issued "
            "a medical update, no scan result has been announced, and head "
            "coach Daniel Reed said a late fitness test will decide whether "
            "Orlov is available."
        ),
        url="https://city-sport.example/northbridge/orlov-derby-doubt",
        expected_article_type="injury_rumor",
        required_facts=(
            "Pavel Orlov",
            "hamstring tightness",
            "late fitness test",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="match-report-late-winner",
        title="Harbor City beat Riverside 2-1 with stoppage-time winner",
        text=(
            "Harbor City defeated Riverside Athletic 2-1 on Sunday after "
            "Milan Kovac scored in the 93rd minute. Riverside had equalised "
            "through Luis Moreno after Harbor took a first-half lead. The "
            "victory moves Harbor City into third place after 12 league games."
        ),
        url="https://league-report.example/harbor-riverside-2-1",
        expected_article_type="match_report",
        required_facts=(
            "2-1",
            "Milan Kovac",
            "93rd minute",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="lineup-confirmed-cup-final",
        title="Confirmed XI: Portside name team for cup final",
        text=(
            "Portside United have confirmed their starting XI for tonight's "
            "cup final. Goalkeeper Aaron Bell starts behind a back four, while "
            "captain Marco Diaz returns in midfield. Teenage striker Eli Ward "
            "is named on the bench and veteran forward Roman Petrov starts."
        ),
        url="https://portside.example/team-news/cup-final-xi",
        expected_article_type="lineup_confirmed",
        required_facts=(
            "Marco Diaz",
            "Roman Petrov",
            "Eli Ward",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="lineup-predicted-derby",
        title="Predicted Northbridge XI for derby against Eastport",
        text=(
            "Our predicted lineup has Northbridge FC switching to a 4-3-3 for "
            "Saturday's derby. We expect Aaron Mills to start at right-back, "
            "with Pavel Orlov included only if he passes a late fitness test. "
            "The club has not announced its official starting XI."
        ),
        url="https://fan-analysis.example/northbridge/predicted-derby-xi",
        expected_article_type="lineup_predicted",
        required_facts=(
            "4-3-3",
            "Aaron Mills",
            "not announced",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="manager-interview-selection",
        title="Reed explains Northbridge selection decisions after win",
        text=(
            "Northbridge head coach Daniel Reed explained his team selection "
            "in a post-match interview. Reed said he rested Mateo Silva because "
            "of workload concerns and praised academy midfielder Noah Grant for "
            "his first league start. He also said the rotation was planned "
            "before the match rather than caused by injury."
        ),
        url="https://northbridge.example/interviews/reed-selection",
        expected_article_type="manager_interview",
        required_facts=(
            "Daniel Reed",
            "Mateo Silva",
            "Noah Grant",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="player-interview-contract-future",
        title="Keller says he is focused on Westhaven amid transfer talk",
        text=(
            "Jonas Keller told club media that he remains focused on Westhaven "
            "despite transfer speculation. The midfielder said he has two years "
            "left on his contract and has not asked to leave. Keller added that "
            "his priority is helping Westhaven qualify for Europe."
        ),
        url="https://westhaven.example/interviews/keller-future",
        expected_article_type="player_interview",
        required_facts=(
            "Jonas Keller",
            "two years",
            "has not asked to leave",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="press-conference-pre-match",
        title="Reed gives Moreno and Orlov updates before Eastport clash",
        text=(
            "At Friday's pre-match press conference, Daniel Reed said Luis "
            "Moreno will miss the Eastport match while Pavel Orlov will be "
            "assessed after training. Reed also confirmed that goalkeeper "
            "Aaron Bell is available again after serving a suspension."
        ),
        url="https://northbridge.example/press/reed-eastport",
        expected_article_type="press_conference",
        required_facts=(
            "Luis Moreno",
            "Pavel Orlov",
            "Aaron Bell",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="managerial-news-sacking",
        title="Westhaven dismiss head coach Adrian Cole",
        text=(
            "Westhaven FC announced that head coach Adrian Cole has left his "
            "position with immediate effect after six consecutive league "
            "defeats. Assistant coach Maya Chen will take charge on an interim "
            "basis while the club begins a search for a permanent successor."
        ),
        url="https://westhaven.example/club/adrian-cole-departs",
        expected_article_type="managerial_news",
        required_facts=(
            "Adrian Cole",
            "six consecutive league defeats",
            "Maya Chen",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="contract-news-renewal",
        title="Riverside extend captain Moreno contract through 2030",
        text=(
            "Riverside Athletic confirmed that captain Luis Moreno has signed "
            "a new three-year contract keeping him at the club through June "
            "2030. Moreno's previous deal was due to expire next summer. The "
            "club said the agreement contains an option for one additional year."
        ),
        url="https://riverside.example/news/moreno-contract-2030",
        expected_article_type="contract_news",
        required_facts=(
            "Luis Moreno",
            "three-year contract",
            "June 2030",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="tactical-analysis-pressing",
        title="How Harbor City's narrow press dismantled Portside buildup",
        text=(
            "This tactical analysis examines Harbor City's 4-2-3-1 pressing "
            "shape against Portside United. Harbor forced play toward the "
            "touchline, used winger Kenji Sato to jump onto the full-back, and "
            "kept midfielder Luca Moretti close to Portside's deepest midfielder. "
            "The piece focuses on structure and spacing rather than breaking news."
        ),
        url="https://tactics-board.example/harbor-portside-press",
        expected_article_type="tactical_analysis",
        required_facts=(
            "4-2-3-1",
            "Kenji Sato",
            "Luca Moretti",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="stats-data-shot-quality",
        title="Data report: Eastport creating fewer but better chances",
        text=(
            "Eastport United have attempted 18 percent fewer shots than last "
            "season but their average expected-goals value per shot has risen "
            "from 0.10 to 0.14. The dataset covers the club's first 15 league "
            "matches and also shows a six percent increase in touches inside "
            "the opposition penalty area."
        ),
        url="https://sports-data.example/eastport-shot-quality-report",
        expected_article_type="stats_data_report",
        required_facts=(
            "18 percent fewer shots",
            "0.14",
            "15 league matches",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="opinion-analysis-title-race",
        title="Why Harbor City should be considered genuine title contenders",
        text=(
            "In this opinion column, the author argues that Harbor City should "
            "now be treated as genuine title contenders. The case rests on their "
            "improved midfield depth, coach Elena Rossi's tactical flexibility "
            "and a favorable run of fixtures. It is an argument and assessment, "
            "not a report of a new official development."
        ),
        url="https://football-opinion.example/harbor-title-case",
        expected_article_type="opinion_analysis",
        required_facts=(
            "Harbor City",
            "Elena Rossi",
            "midfield depth",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="discipline-legal-suspension",
        title="League bans Marco Diaz for three matches after red card",
        text=(
            "The league disciplinary panel has suspended Portside United "
            "captain Marco Diaz for three matches following his red card against "
            "Harbor City. Portside may appeal the sanction within 48 hours. The "
            "panel said the punishment relates to serious foul play."
        ),
        url="https://league.example/discipline/marco-diaz-ban",
        expected_article_type="discipline_legal",
        required_facts=(
            "Marco Diaz",
            "three matches",
            "48 hours",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="fixture-schedule-cup-draw",
        title="Cup quarter-final draw sets Harbor City trip to Eastport",
        text=(
            "The national cup quarter-final draw has paired Eastport United "
            "with Harbor City. The tie will be played at Eastport Stadium on "
            "Wednesday 18 March at 19:45, while Riverside Athletic will host "
            "Portside United the following evening."
        ),
        url="https://cup.example/draw/quarter-finals",
        expected_article_type="fixture_schedule",
        required_facts=(
            "Eastport United",
            "Wednesday 18 March",
            "19:45",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="ownership-finance-investment",
        title="Harbor City owners approve 80 million training-ground project",
        text=(
            "Harbor City confirmed that its ownership group has approved an "
            "80 million dollar redevelopment of the club's training ground. "
            "Construction is scheduled to begin in October and the project will "
            "include a new academy building, medical centre and two indoor pitches."
        ),
        url="https://harbor.example/club/training-ground-investment",
        expected_article_type="ownership_finance",
        required_facts=(
            "80 million",
            "October",
            "two indoor pitches",
        ),
    ),
    ArticleBenchmarkCase(
        case_id="generic-news-community-award",
        title="Riverside goalkeeper Bell wins city community award",
        text=(
            "Riverside Athletic goalkeeper Aaron Bell received the city's annual "
            "community award for his work funding youth football sessions. Bell "
            "has supported the program for four years and will donate the award's "
            "10,000 dollar grant to three local sports charities."
        ),
        url="https://riverside.example/community/aaron-bell-award",
        expected_article_type="generic_news",
        required_facts=(
            "Aaron Bell",
            "four years",
            "10,000 dollar grant",
        ),
    ),
)


GOLDEN_ARTICLE_CORPUS = (
    *GOLDEN_ARTICLE_SINGLE_PASS_CASES,
    *EXPANDED_ARTICLE_SINGLE_PASS_CASES,
)


HIGH_INFORMATION_GENERATION_CASE_IDS = (
    "injury-rumor-training-doubt",
    "match-report-late-winner",
    "managerial-news-sacking",
    "tactical-analysis-pressing",
    "discipline-legal-suspension",
)


_CASES_BY_ID = {
    case.case_id: case
    for case in GOLDEN_ARTICLE_CORPUS
}


def golden_article_case(case_id: str) -> ArticleBenchmarkCase:
    normalized = str(case_id or "").strip()
    try:
        return _CASES_BY_ID[normalized]
    except KeyError as error:
        raise KeyError(
            "Unknown golden article benchmark case: " + normalized
        ) from error


def select_golden_article_cases(
    case_ids: Sequence[str] | None = None,
) -> tuple[ArticleBenchmarkCase, ...]:
    selected_ids = (
        tuple(case_ids)
        if case_ids is not None
        else HIGH_INFORMATION_GENERATION_CASE_IDS
    )
    if not selected_ids:
        raise ValueError("At least one golden benchmark case is required.")

    cases = tuple(
        golden_article_case(case_id)
        for case_id in selected_ids
    )

    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("Duplicate golden benchmark case IDs are not allowed.")

    return cases


def covered_article_types() -> tuple[str, ...]:
    seen: list[str] = []
    for case in GOLDEN_ARTICLE_CORPUS:
        if case.expected_article_type not in seen:
            seen.append(case.expected_article_type)
    return tuple(seen)


__all__ = [
    "ARTICLE_BENCHMARK_CORPUS_VERSION",
    "EXPANDED_ARTICLE_SINGLE_PASS_CASES",
    "GOLDEN_ARTICLE_CORPUS",
    "HIGH_INFORMATION_GENERATION_CASE_IDS",
    "golden_article_case",
    "select_golden_article_cases",
    "covered_article_types",
]
