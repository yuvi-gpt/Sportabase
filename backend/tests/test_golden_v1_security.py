import json
import shutil
from pathlib import Path

import pytest

from evals.golden_v1.errors import CorpusError
from evals.golden_v1.loader import CASE_DIRECTORY_LIMIT, CASE_JSON_LIMIT, JSON_ARTIFACT_LIMIT, TEXT_ARTIFACT_LIMIT, LoadedCase, load_corpus, read_json, read_text_artifact, safe_path


CORPUS = Path(__file__).parents[1] / "evals/golden_v1/corpus"


def test_oversized_case_and_text_are_rejected(tmp_path):
    oversized = tmp_path / "case.json"; oversized.write_bytes(b" " * (CASE_JSON_LIMIT + 1))
    with pytest.raises(CorpusError, match="size limit"): read_json(oversized, CASE_JSON_LIMIT)
    text = tmp_path / "article.txt"; text.write_bytes(b"x" * (TEXT_ARTIFACT_LIMIT + 1))
    with pytest.raises(CorpusError, match="size limit"): read_text_artifact(LoadedCase(data={}, directory=tmp_path), "article.txt")


def test_deep_json_nonfinite_and_malformed_utf8(tmp_path):
    deep = "0"
    for _ in range(22): deep = "[" + deep + "]"
    path = tmp_path / "deep.json"; path.write_text(deep, encoding="utf-8")
    with pytest.raises(CorpusError, match="nesting"): read_json(path, CASE_JSON_LIMIT)
    for raw in (b'{"x": NaN}', b"\xff"):
        path.write_bytes(raw)
        with pytest.raises(CorpusError, match="Malformed"): read_json(path, CASE_JSON_LIMIT)


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_each_non_finite_json_constant_is_rejected(tmp_path, constant):
    path = tmp_path / "number.json"
    path.write_text('{"value": ' + constant + '}', encoding="utf-8")
    with pytest.raises(CorpusError, match="Malformed"):
        read_json(path, CASE_JSON_LIMIT)


def test_json_artifact_and_collection_limits(tmp_path):
    artifact = tmp_path / "candidate.json"
    artifact.write_bytes(b" " * (JSON_ARTIFACT_LIMIT + 1))
    with pytest.raises(CorpusError, match="size limit"):
        read_json(artifact, JSON_ARTIFACT_LIMIT)
    artifact.write_text(json.dumps(list(range(1001))), encoding="utf-8")
    with pytest.raises(CorpusError, match="collection limit"):
        read_json(artifact, JSON_ARTIFACT_LIMIT)


def test_case_directory_total_limit(tmp_path):
    shutil.copytree(CORPUS, tmp_path, dirs_exist_ok=True)
    entry = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["cases"][0]
    case_directory = (tmp_path / entry["path"]).parent
    (case_directory / "unused-padding.bin").write_bytes(b"x" * (CASE_DIRECTORY_LIMIT + 1))
    with pytest.raises(CorpusError, match="directory exceeds"):
        load_corpus(tmp_path)


def test_intermediate_directory_symlink_rejected_where_supported(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "case.json").write_text("{}", encoding="utf-8")
    link = tmp_path / "linked"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    with pytest.raises(CorpusError, match="symlink"):
        safe_path(tmp_path, "linked/case.json", label="case")


def test_symlink_rejected_where_supported(tmp_path):
    target = tmp_path / "target.json"; target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    try: link.symlink_to(target)
    except OSError: pytest.skip("symlink creation unavailable")
    with pytest.raises(CorpusError, match="symlink"): read_json(link, CASE_JSON_LIMIT)
