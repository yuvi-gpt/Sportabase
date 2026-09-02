import socket
from pathlib import Path
from unittest.mock import patch

from evals.golden_v1.loader import load_corpus
from evals.golden_v1.reporting import evaluate_corpus


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"
EXPECTED = {"article": 2, "video": 2, "intelligence": 2}


def test_exactly_six_approved_representative_cases():
    corpus = load_corpus(CORPUS)
    assert len(corpus.cases) == 6
    for mode, count in EXPECTED.items():
        assert sum(case.data["mode"] == mode for case in corpus.cases) == count
    assert all(case.data["annotation"]["review_status"] == "approved" for case in corpus.cases)


def test_smoke_evaluation_is_provider_network_database_and_whisper_free():
    def forbidden(*args, **kwargs):
        raise AssertionError("external runtime access attempted")
    with patch.object(socket, "create_connection", side_effect=forbidden), patch.object(socket.socket, "connect", side_effect=forbidden), patch("app.ai.generation.generate_gemini_content", side_effect=forbidden), patch("app.ai.generation.reserve_gemini_call", side_effect=forbidden):
        report = evaluate_corpus(CORPUS)
    assert report["totals"]["passed"] == 6
    assert report["totals"]["failed"] == 0
