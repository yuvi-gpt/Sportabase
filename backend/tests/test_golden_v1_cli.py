from pathlib import Path
import json
import shutil

from evals.golden_v1 import cli


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"


def test_cli_success_filters_list_validate_and_json(tmp_path, capsys):
    assert cli.main(["--corpus", str(CORPUS), "--case", "article.transfer.official.synthetic-001"]) == 0
    assert cli.main(["--corpus", str(CORPUS), "--tag", "transcript", "--mode", "video", "--list-cases"]) == 0
    assert "video.captions" in capsys.readouterr().out
    assert cli.main(["--corpus", str(CORPUS), "--validate-only"]) == 0
    output = tmp_path / "report.json"
    assert cli.main(["--corpus", str(CORPUS), "--format", "json", "--json-out", str(output)]) == 0
    assert output.is_file()


def test_cli_unknown_case_is_exit_two(capsys):
    assert cli.main(["--corpus", str(CORPUS), "--case", "missing.case"]) == 2
    assert "Unknown requested case" in capsys.readouterr().err


def test_cli_failure_and_warnings_as_errors(monkeypatch):
    base = {"totals": {"cases": 1, "passed": 0, "warned": 0, "failed": 1, "invalid": 0, "skipped": 0}, "case_results": [], "candidate_label": "x", "deterministic_digest": "d"}
    monkeypatch.setattr(cli, "evaluate_corpus", lambda *a, **k: base)
    assert cli.main(["--corpus", str(CORPUS)]) == 1
    warned = {**base, "totals": {"cases": 1, "passed": 0, "warned": 1, "failed": 0, "invalid": 0, "skipped": 0}}
    monkeypatch.setattr(cli, "evaluate_corpus", lambda *a, **k: warned)
    assert cli.main(["--corpus", str(CORPUS), "--warnings-as-errors"]) == 1


def copy_corpus(tmp_path):
    root = tmp_path / "corpus"
    shutil.copytree(CORPUS, root)
    return root


def test_real_cli_regression_invalid_case_and_malformed_manifest(tmp_path):
    case_id = "article.transfer.official.synthetic-001"
    candidates = tmp_path / "candidates"
    target = candidates / case_id
    target.mkdir(parents=True)
    source = CORPUS / "article" / case_id / "candidate.json"
    candidate = json.loads(source.read_text(encoding="utf-8"))
    candidate["article_type"] = "transfer_rumor"
    (target / "candidate.json").write_text(json.dumps(candidate), encoding="utf-8")
    assert cli.main(["--corpus", str(CORPUS), "--case", case_id, "--candidate-root", str(candidates)]) == 1

    invalid = copy_corpus(tmp_path / "invalid")
    case_path = invalid / "article" / case_id / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["expected"]["checks"] = [{"evaluator": "made_up_evaluator", "path": "x"}]
    case_path.write_text(json.dumps(case), encoding="utf-8")
    assert cli.main(["--corpus", str(invalid), "--case", case_id]) == 2

    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "manifest.json").write_text("{bad", encoding="utf-8")
    assert cli.main(["--corpus", str(malformed)]) == 2


def test_real_cli_warning_as_error(tmp_path):
    root = copy_corpus(tmp_path)
    case_id = "article.transfer.official.synthetic-001"
    case_path = root / "article" / case_id / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["expected"]["human_review_required"] = True
    case["expected"]["review_focus"] = "manual prose review"
    case_path.write_text(json.dumps(case), encoding="utf-8")
    assert cli.main(["--corpus", str(root), "--case", case_id]) == 0
    assert cli.main(["--corpus", str(root), "--case", case_id, "--warnings-as-errors"]) == 1


def test_external_candidate_root_does_not_change_goldens_or_report_identity(tmp_path, capsys):
    case_id = "article.transfer.official.synthetic-001"
    candidates = tmp_path / "private-location" / "candidates"
    target = candidates / case_id
    target.mkdir(parents=True)
    source = CORPUS / "article" / case_id / "candidate.json"
    shutil.copyfile(source, target / "candidate.json")
    golden_before = (CORPUS / "article" / case_id / "case.json").read_bytes()
    args = ["--corpus", str(CORPUS), "--case", case_id, "--candidate-root", str(candidates), "--format", "json"]
    assert cli.main(args) == 0
    first = capsys.readouterr().out
    assert str(candidates.resolve()) not in first
    assert cli.main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    assert golden_before == (CORPUS / "article" / case_id / "case.json").read_bytes()


def test_external_candidate_root_rejects_symlink_escape(tmp_path):
    root = tmp_path / "candidates"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    case_id = "article.transfer.official.synthetic-001"
    link = root / case_id
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("symlink creation unavailable")
    assert cli.main(["--corpus", str(CORPUS), "--case", case_id, "--candidate-root", str(root)]) == 2


def test_validate_only_reports_invalid_expectation_deterministically(tmp_path, capsys):
    root = copy_corpus(tmp_path)
    case_id = "article.transfer.official.synthetic-001"
    case_path = root / "article" / case_id / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["expected"]["checks"] = [{"evaluator": "made_up_evaluator", "path": "x"}]
    case_path.write_text(json.dumps(case), encoding="utf-8")
    args = ["--corpus", str(root), "--case", case_id, "--validate-only"]
    assert cli.main(args) == 2
    first = capsys.readouterr().out
    assert "selected cases: 1" in first
    assert "invalid cases: 1" in first
    assert f"INVALID_CASE {case_id}: Unknown evaluator" in first
    assert str(root.resolve()) not in first
    assert cli.main(args) == 2
    assert capsys.readouterr().out == first


def test_validate_only_malformed_manifest_and_unknown_case_exit_two(tmp_path):
    malformed = tmp_path / "malformed"
    malformed.mkdir()
    (malformed / "manifest.json").write_text("{bad", encoding="utf-8")
    assert cli.main(["--corpus", str(malformed), "--validate-only"]) == 2
    assert cli.main(["--corpus", str(CORPUS), "--case", "missing.case", "--validate-only"]) == 2


def test_validate_only_zero_filter_is_explicit(capsys):
    assert cli.main(["--corpus", str(CORPUS), "--tag", "does-not-exist", "--validate-only"]) == 0
    output = capsys.readouterr().out
    assert output.strip() == "0 cases selected"
    assert "passed" not in output.lower()
