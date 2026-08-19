"""Compatibility alias for :mod:`app.analysis.context`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.context"
)

_sys.modules[__name__] = _implementation
