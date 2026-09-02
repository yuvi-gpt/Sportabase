import socket
from pathlib import Path
from unittest.mock import patch

from evals.golden_v1.loader import load_corpus
from evals.golden_v1.reporting import evaluate_corpus


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"
EXPECTED = {"article": 12, "video": 8, "intelligence": 4}
SEED_CASES = {
    "article.transfer.official.synthetic-001",
    "article.transfer.rumor.synthetic-001",
    "video.captions.high-confidence.synthetic-001",
    "video.captions.low-confidence.synthetic-001",
    "intelligence.claim.transfer-equivalence.synthetic-001",
    "intelligence.dependency-blocks-independence.synthetic-001",
}


def test_curated_corpus_composition_and_seed_cases():
    corpus = load_corpus(CORPUS)
    assert len(corpus.cases) == 24
    for mode, count in EXPECTED.items():
        assert sum(case.data["mode"] == mode for case in corpus.cases) == count
    assert all(case.data["annotation"]["review_status"] == "approved" for case in corpus.cases)
    assert SEED_CASES <= {case.data["case_id"] for case in corpus.cases}


def test_smoke_evaluation_is_provider_network_database_and_whisper_free():
    def forbidden(*args, **kwargs):
        raise AssertionError("external runtime access attempted")
    with patch.object(socket, "create_connection", side_effect=forbidden), patch.object(socket.socket, "connect", side_effect=forbidden), patch("app.ai.generation.generate_gemini_content", side_effect=forbidden), patch("app.ai.generation.reserve_gemini_call", side_effect=forbidden):
        report = evaluate_corpus(CORPUS)
    assert report["totals"]["passed"] == 24
    assert report["totals"]["failed"] == 0
