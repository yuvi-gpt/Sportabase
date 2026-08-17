from __future__ import annotations

import json

from pathlib import Path
from typing import Any, Mapping

from .golden_dataset import (
    MultimodalGoldenDatasetError,
    build_golden_cases,
    golden_dataset_descriptor,
    validate_golden_cases,
)
from .golden_observed import (
    MULTIMODAL_GOLDEN_OBSERVED_VERSION,
    MultimodalGoldenObservedError,
    evaluate_observed_artifact,
    observed_template,
)
from .golden_runtime import (
    MULTIMODAL_GOLDEN_EVAL_VERSION,
    evaluate_deterministic_golden_set,
    evaluate_golden_case,
)


class MultimodalGoldenEvalError(RuntimeError):
    pass


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = [
    "MULTIMODAL_GOLDEN_EVAL_VERSION",
    "MULTIMODAL_GOLDEN_OBSERVED_VERSION",
    "MultimodalGoldenDatasetError",
    "MultimodalGoldenEvalError",
    "MultimodalGoldenObservedError",
    "build_golden_cases",
    "evaluate_deterministic_golden_set",
    "evaluate_golden_case",
    "evaluate_observed_artifact",
    "golden_dataset_descriptor",
    "observed_template",
    "validate_golden_cases",
    "write_json",
]
