import json
from pathlib import Path

import pytest

from evals.golden_v1.errors import ReplayError
from evals.golden_v1.loader import LoadedCase, load_corpus
from evals.golden_v1.replay import replay_case


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"


def test_final_output_and_provider_raw_replay():
    corpus = load_corpus(CORPUS)
    final = next(case for case in corpus.cases if case.data["case_id"].startswith("article.transfer.official"))
    raw = next(case for case in corpus.cases if case.data["case_id"].startswith("video.captions.low"))
    assert replay_case(final)["article_type"] == "transfer_official"
    assert replay_case(raw)["verdict"] == "weakly_supported"


def test_low_confidence_replay_transforms_strong_provider_output():
    corpus = load_corpus(CORPUS)
    case = next(case for case in corpus.cases if "low-confidence" in case.data["tags"])
    frozen = json.loads((case.directory / "provider-output.json").read_text(encoding="utf-8"))
    before = json.loads(frozen["text"])
    after = replay_case(case)
    assert before["transcript_confidence"] == 0.96
    assert before["evidence_score"] == 92
    assert before["logic_score"] == 91
    assert before["verdict"] == "well_supported_report"
    assert before["localized_verdict"]
    assert after["transcript_confidence"] == 0.42
    assert after["evidence_score"] == 55
    assert after["logic_score"] == 91
    assert after["verdict"] == "weakly_supported"
    assert after["localized_verdict"] == ""


def test_malformed_provider_artifact(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps({"text": "not json"}), encoding="utf-8")
    data = {"replay": {"kind": "provider_raw", "artifact": "bad.json", "normalization_contract": "video-output-v1"}}
    with pytest.raises(ReplayError, match="Malformed provider"):
        replay_case(LoadedCase(data=data, directory=tmp_path))


def test_unknown_normalization_contract(tmp_path):
    (tmp_path / "raw.json").write_text(json.dumps({"text": "{}"}), encoding="utf-8")
    data = {"replay": {"kind": "provider_raw", "artifact": "raw.json", "normalization_contract": "mystery"}}
    with pytest.raises(ReplayError, match="Unknown normalization"):
        replay_case(LoadedCase(data=data, directory=tmp_path))
