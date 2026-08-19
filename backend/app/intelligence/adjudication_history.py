"""Compatibility alias for :mod:`app.analysis.adjudication_history`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.adjudication_history"
)

_sys.modules[__name__] = _implementation
