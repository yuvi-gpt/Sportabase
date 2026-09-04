from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import CaseValidationError, CorpusError, ExpectationValidationError
from .schema import validate_case, validate_manifest
from .serialization import reject_non_finite

CASE_JSON_LIMIT = 256 * 1024
JSON_ARTIFACT_LIMIT = 512 * 1024
TEXT_ARTIFACT_LIMIT = 256 * 1024
CASE_DIRECTORY_LIMIT = 1024 * 1024
MAX_JSON_DEPTH = 20
MAX_COLLECTION = 1000


@dataclass(frozen=True)
class LoadedCase:
    data: dict
    directory: Path
    validation_error: str | None = None


@dataclass(frozen=True)
class LoadedCorpus:
    root: Path
    manifest: dict
    cases: tuple[LoadedCase, ...]


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_path(root: Path, relative: str, *, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise CorpusError(label + " must be a relative path without '..'.")
    root_resolved = root.resolve()
    unresolved = root_resolved / candidate
    cursor = root_resolved
    for component in candidate.parts:
        cursor = cursor / component
        if cursor.is_symlink():
            raise CorpusError(label + " may not traverse a symlink.")
    target = unresolved.resolve()
    if not _inside(target, root_resolved):
        raise CorpusError(label + " escapes its permitted directory.")
    return target


def _shape(value: Any, depth: int = 0) -> None:
    if depth > MAX_JSON_DEPTH:
        raise CorpusError("JSON nesting limit exceeded.")
    if isinstance(value, dict):
        if len(value) > MAX_COLLECTION:
            raise CorpusError("JSON object collection limit exceeded.")
        for item in value.values():
            _shape(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > MAX_COLLECTION:
            raise CorpusError("JSON array collection limit exceeded.")
        for item in value:
            _shape(item, depth + 1)


def read_json(path: Path, limit: int) -> Any:
    try:
        if path.is_symlink() or not path.is_file():
            raise CorpusError("JSON artifact must be a regular non-symlink file.")
        if path.stat().st_size > limit:
            raise CorpusError("JSON artifact exceeds size limit: " + path.name)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        value = json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
        reject_non_finite(value)
        _shape(value)
        return value
    except CorpusError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise CorpusError("Malformed JSON artifact: " + path.name) from error


def read_text_artifact(case: LoadedCase, relative: str) -> str:
    path = safe_path(case.directory, relative, label="Text artifact")
    try:
        if not path.is_file() or path.is_symlink():
            raise CorpusError("Text artifact must be a regular non-symlink file.")
        if path.stat().st_size > TEXT_ARTIFACT_LIMIT:
            raise CorpusError("Text artifact exceeds size limit.")
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CorpusError("Unable to read UTF-8 text artifact.") from error


def read_case_json_artifact(case: LoadedCase, relative: str) -> Any:
    return read_json(
        safe_path(case.directory, relative, label="JSON artifact"),
        JSON_ARTIFACT_LIMIT,
    )


def _directory_size(directory: Path) -> int:
    total = 0
    for base, directories, files in os.walk(directory, followlinks=False):
        for name in directories:
            if (Path(base) / name).is_symlink():
                raise CorpusError("Case directories may not contain symlinks.")
        for name in files:
            path = Path(base) / name
            if path.is_symlink():
                raise CorpusError("Case directories may not contain symlinks.")
            total += path.stat().st_size
            if total > CASE_DIRECTORY_LIMIT:
                raise CorpusError("Case directory exceeds size limit.")
    return total


def load_corpus(root: Path | str) -> LoadedCorpus:
    supplied_root = Path(root)
    if supplied_root.is_symlink():
        raise CorpusError("Corpus root may not be a symlink.")
    corpus_root = supplied_root.resolve()
    if not corpus_root.is_dir():
        raise CorpusError("Corpus root must be a regular directory.")
    manifest = validate_manifest(read_json(corpus_root / "manifest.json", CASE_JSON_LIMIT))
    cases = []
    seen_ids = set()
    for entry in manifest["cases"]:
        case_file = safe_path(corpus_root, entry["path"], label="Manifest case path")
        if case_file.name != "case.json":
            raise CorpusError("Manifest entries must point to case.json.")
        _directory_size(case_file.parent)
        raw_case = read_json(case_file, CASE_JSON_LIMIT)
        validation_error = None
        try:
            data = validate_case(raw_case)
        except ExpectationValidationError as error:
            data = raw_case
            validation_error = str(error)
        except CaseValidationError as error:
            raise CorpusError(str(error)) from error
        if data["case_id"] != entry["case_id"]:
            raise CorpusError("Manifest and case IDs differ.")
        if data["case_id"] in seen_ids:
            raise CorpusError("Duplicate case ID.")
        seen_ids.add(data["case_id"])
        loaded_case = LoadedCase(
            data=data,
            directory=case_file.parent,
            validation_error=validation_error,
        )
        artifact = safe_path(case_file.parent, data["replay"]["artifact"], label="Replay artifact")
        read_json(artifact, JSON_ARTIFACT_LIMIT)
        for key in ("article_text", "transcript"):
            if key in data["input"]:
                if not isinstance(data["input"][key], str):
                    raise CorpusError(key + " artifact reference must be a string.")
                read_text_artifact(loaded_case, data["input"][key])
        cases.append(loaded_case)
    return LoadedCorpus(root=corpus_root, manifest=manifest, cases=tuple(cases))
