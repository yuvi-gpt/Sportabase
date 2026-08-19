"""Compatibility alias for :mod:`app.analysis.correction_memory_history`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.correction_memory_history"
)

_sys.modules[__name__] = _implementation
