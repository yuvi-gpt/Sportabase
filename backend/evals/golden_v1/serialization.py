from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def reject_non_finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite JSON numbers are forbidden.")
    if isinstance(value, dict):
        for item in value.values():
            reject_non_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_non_finite(item)


def deterministic_json(value: Any, *, pretty: bool = False) -> str:
    reject_non_finite(value)
    options = {
        "ensure_ascii": False,
        "sort_keys": True,
        "allow_nan": False,
    }
    if pretty:
        options["indent"] = 2
    else:
        options["separators"] = (",", ":")
    return json.dumps(value, **options) + "\n"


def digest(value: Any) -> str:
    return hashlib.sha256(
        deterministic_json(value).encode("utf-8")
    ).hexdigest()
