import json
import shutil
from pathlib import Path

import pytest

from evals.golden_v1.errors import CorpusError
from evals.golden_v1.loader import load_corpus


CORPUS = Path(__file__).parents[1] / "evals" / "golden_v1" / "corpus"


def test_valid_manifest_loads_curated_corpus():
    loaded = load_corpus(CORPUS)
    assert len(loaded.cases) == 24


def test_duplicate_case_id_and_path_are_rejected(tmp_path):
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    manifest["cases"].append(dict(manifest["cases"][0]))
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="duplicate"):
        load_corpus(tmp_path)


@pytest.mark.parametrize("path", ["../case.json", str(Path.cwd().anchor + "case.json")])
def test_unsafe_manifest_paths_are_rejected(tmp_path, path):
    manifest = {"golden_set_version": "sportabase-golden-set-v1", "case_schema_version": "golden-case-v1", "cases": [{"case_id": "safe.case", "path": path}]}
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError):
        load_corpus(tmp_path)


def test_unsupported_corpus_version(tmp_path):
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    manifest["golden_set_version"] = "future"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="Unsupported"):
        load_corpus(tmp_path)


def test_duplicate_manifest_path_with_different_ids(tmp_path):
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    duplicate = dict(manifest["cases"][0])
    duplicate["case_id"] = "different.case"
    manifest["cases"].append(duplicate)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="paths.*duplicate"):
        load_corpus(tmp_path)


def test_malformed_case_json_is_fatal(tmp_path):
    shutil.copytree(CORPUS, tmp_path, dirs_exist_ok=True)
    entry = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["cases"][0]
    (tmp_path / entry["path"]).write_text("{broken", encoding="utf-8")
    with pytest.raises(CorpusError, match="Malformed JSON"):
        load_corpus(tmp_path)


def test_unsupported_manifest_case_schema_version(tmp_path):
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    manifest["case_schema_version"] = "future"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(CorpusError, match="case schema"):
        load_corpus(tmp_path)
