from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .errors import GoldenV1Error
from .evaluators import evaluate_check
from .loader import LoadedCase, LoadedCorpus, load_corpus
from .replay import replay_case
from .schema import EVALUATION_VERSION
from .serialization import digest

STATUSES = ("PASS", "WARN", "FAIL", "INVALID_CASE", "SKIPPED")


def select_cases(corpus: LoadedCorpus, *, case_ids: Iterable[str] = (), tags: Iterable[str] = (), mode: str | None = None) -> tuple[LoadedCase, ...]:
    requested = set(case_ids)
    known = {case.data["case_id"] for case in corpus.cases}
    unknown = sorted(requested - known)
    if unknown:
        raise GoldenV1Error("Unknown requested case: " + ", ".join(unknown))
    required_tags = set(tags)
    return tuple(case for case in corpus.cases if (not requested or case.data["case_id"] in requested) and (not required_tags or required_tags.issubset(set(case.data["tags"]))) and (mode is None or case.data["mode"] == mode))


def _case_result(case: LoadedCase, *, candidate_root: Path | None = None) -> dict:
    data = case.data
    if data["annotation"]["review_status"] != "approved":
        return {"case_id": data["case_id"], "mode": data["mode"], "status": "SKIPPED", "checks": [], "diffs": ["case is not approved"]}
    if case.validation_error is not None:
        return {"case_id": data["case_id"], "mode": data["mode"], "status": "INVALID_CASE", "checks": [], "diffs": [case.validation_error]}
    try:
        candidate = replay_case(case, candidate_root=candidate_root)
        checks = [evaluate_check(candidate, check, index) for index, check in enumerate(data["expected"]["checks"], 1)]
        invalid_checks = [check for check in checks if check["status"] == "INVALID_CASE"]
        failures = [check for check in checks if check["status"] == "FAIL"]
        warnings = [check for check in checks if check["status"] == "WARN"]
        if invalid_checks: status = "INVALID_CASE"
        elif failures: status = "FAIL"
        elif warnings or data["expected"].get("human_review_required", False): status = "WARN"
        else: status = "PASS"
        diffs = [f"{row['path'] or '<root>'}: {row['evaluator']} {row['status']}" for row in checks if row["status"] != "PASS"]
        if data["expected"].get("human_review_required", False):
            diffs.append("human review required: " + str(data["expected"].get("review_focus", "")))
        return {"case_id": data["case_id"], "mode": data["mode"], "status": status, "checks": checks, "diffs": diffs}
    except GoldenV1Error as error:
        return {"case_id": data["case_id"], "mode": data["mode"], "status": "INVALID_CASE", "checks": [], "diffs": [str(error)]}


def _metrics(results: list[dict]) -> dict:
    classification = {"article": {"correct": 0, "evaluated": 0, "confusion_matrix": {}}, "video": {"correct": 0, "evaluated": 0, "confusion_matrix": {}}}
    facts = {"matched": 0, "required": 0}
    forbidden_violations = 0
    claims = {"matched": 0, "required": 0}
    localization = {"passed": 0, "evaluated": 0}
    video_ranges = {"passed": 0, "evaluated": 0}
    matrices: dict[str, dict[str, dict[str, int]]] = {"article": defaultdict(lambda: defaultdict(int)), "video": defaultdict(lambda: defaultdict(int))}
    for result in results:
        for check in result["checks"]:
            evaluator, dimension = check["evaluator"], check["dimension"]
            passed = check["status"] in {"PASS", "WARN"}
            if dimension == "classification" and result["mode"] in classification:
                section = classification[result["mode"]]; section["evaluated"] += 1; section["correct"] += int(passed)
                details = check.get("details", {}); actual = str(details.get("actual", "<candidate>")); expected = str(details.get("expected", "<expected>")); matrices[result["mode"]][expected][actual] += 1
            if evaluator == "required_facts":
                rows = check.get("details", {}).get("facts", []); facts["required"] += len(rows); facts["matched"] += sum(bool(row["passed"]) for row in rows)
            if evaluator == "forbidden_facts": forbidden_violations += sum(not row["passed"] for row in check.get("details", {}).get("facts", []))
            if evaluator == "canonical_claim": claims["required"] += 1; claims["matched"] += int(passed)
            if evaluator == "language": localization["evaluated"] += 1; localization["passed"] += int(passed)
            if result["mode"] == "video" and evaluator == "numeric_range": video_ranges["evaluated"] += 1; video_ranges["passed"] += int(passed)
    for mode in matrices:
        classification[mode]["confusion_matrix"] = {expected: dict(sorted(actuals.items())) for expected, actuals in sorted(matrices[mode].items())}
    return {"classification": classification, "required_facts": facts, "forbidden_fact_violations": forbidden_violations, "required_claims": claims, "localization": localization, "video_score_within_range": video_ranges}


def evaluate_corpus(corpus_or_root: LoadedCorpus | Path | str, *, candidate_label: str = "fixture", candidate_root: Path | None = None, case_ids: Iterable[str] = (), tags: Iterable[str] = (), mode: str | None = None) -> dict:
    corpus = corpus_or_root if isinstance(corpus_or_root, LoadedCorpus) else load_corpus(corpus_or_root)
    selected = select_cases(corpus, case_ids=case_ids, tags=tags, mode=mode)
    results = sorted((_case_result(case, candidate_root=candidate_root) for case in selected), key=lambda row: row["case_id"])
    counts = {status: sum(row["status"] == status for row in results) for status in STATUSES}
    report = {"evaluation_version": EVALUATION_VERSION, "golden_set_version": corpus.manifest["golden_set_version"], "mode": "offline", "candidate_label": candidate_label, "totals": {"cases": len(results), "passed": counts["PASS"], "warned": counts["WARN"], "failed": counts["FAIL"], "invalid": counts["INVALID_CASE"], "skipped": counts["SKIPPED"]}, "metrics": _metrics(results), "case_results": results}
    report["deterministic_digest"] = digest(report)
    return report


def text_report(report: dict) -> str:
    totals = report["totals"]
    lines = ["Sportabase Golden-Set Evaluation V1", "mode: offline", "candidate: " + report["candidate_label"], f"cases: {totals['cases']}  pass: {totals['passed']}  warn: {totals['warned']}  fail: {totals['failed']}  invalid: {totals['invalid']}  skipped: {totals['skipped']}"]
    if totals["cases"] == 0:
        lines.append("0 cases selected by filters.")
    lines.extend(f"{row['status']:12} {row['case_id']}" for row in report["case_results"])
    lines.append("digest: " + report["deterministic_digest"])
    return "\n".join(lines) + "\n"
