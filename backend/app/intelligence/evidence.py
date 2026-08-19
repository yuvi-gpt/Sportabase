"""Compatibility alias for Intelligence persisted records."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.intelligence.records.evidence"
)
_sys.modules[__name__] = _implementation
