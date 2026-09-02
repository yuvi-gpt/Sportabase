import json
import shutil
import copy
from pathlib import Path

from evals.golden_v1.loader import LoadedCase, LoadedCorpus, load_corpus
from evals.golden_v1.reporting import evaluate_corpus
from evals.golden_v1.serialization import deterministic_json


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"


def test_status_counts_metrics_digest_and_byte_stability():
    first = evaluate_corpus(CORPUS)
    second = evaluate_corpus(CORPUS)
    assert first["totals"] == {"cases": 6, "passed": 6, "warned": 0, "failed": 0, "invalid": 0, "skipped": 0}
    assert first["metrics"]["required_facts"]["required"] == 4
    assert first["deterministic_digest"] == second["deterministic_digest"]
    assert deterministic_json(first, pretty=True).encode() == deterministic_json(second, pretty=True).encode()


def test_per_case_failure_survives_aggregates(tmp_path):
    corpus = load_corpus(CORPUS)
    for case in corpus.cases:
        if case.data["replay"]["kind"] == "final_output":
            target = tmp_path / case.data["case_id"]
            target.mkdir()
            shutil.copyfile(case.directory / "candidate.json", target / "candidate.json")
    broken_path = tmp_path / "article.transfer.official.synthetic-001/candidate.json"
    broken = json.loads(broken_path.read_text(encoding="utf-8"))
    broken["article_type"] = "transfer_rumor"
    broken_path.write_text(json.dumps(broken), encoding="utf-8")
    report = evaluate_corpus(CORPUS, candidate_root=tmp_path)
    row = next(item for item in report["case_results"] if item["case_id"] == "article.transfer.official.synthetic-001")
    assert row["status"] == "FAIL"
    assert report["totals"]["failed"] == 1


def test_invalid_expectation_is_invalid_case_but_bad_candidate_fails():
    corpus = load_corpus(CORPUS)
    source = corpus.cases[0]
    invalid = LoadedCase(source.data, source.directory, "Unknown evaluator: made_up_evaluator")
    invalid_report = evaluate_corpus(LoadedCorpus(corpus.root, corpus.manifest, (invalid,)))
    assert invalid_report["case_results"][0]["status"] == "INVALID_CASE"
    assert invalid_report["totals"]["invalid"] == 1

    data = copy.deepcopy(source.data)
    data["expected"]["checks"] = [{"evaluator": "exact", "path": "article_type", "value": "wrong"}]
    valid = LoadedCase(data, source.directory)
    failed_report = evaluate_corpus(LoadedCorpus(corpus.root, corpus.manifest, (valid,)))
    assert failed_report["case_results"][0]["status"] == "FAIL"


def test_review_statuses_and_deterministic_ordering():
    corpus = load_corpus(CORPUS)
    cases = []
    for status, source in zip(("needs_review", "draft", "approved"), reversed(corpus.cases[:3])):
        data = copy.deepcopy(source.data)
        data["annotation"]["review_status"] = status
        data["expected"]["checks"] = list(reversed(data["expected"]["checks"]))
        cases.append(LoadedCase(data, source.directory))
    mixed = LoadedCorpus(corpus.root, corpus.manifest, tuple(cases))
    first = evaluate_corpus(mixed)
    second = evaluate_corpus(mixed)
    assert [row["case_id"] for row in first["case_results"]] == sorted(row["case_id"] for row in first["case_results"])
    assert [row["status"] for row in first["case_results"]].count("SKIPPED") == 2
    assert first["case_results"] == second["case_results"]
    assert first["deterministic_digest"] == second["deterministic_digest"]
    assert deterministic_json(first, pretty=True).encode() == deterministic_json(second, pretty=True).encode()
