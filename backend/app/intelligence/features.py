"""Compatibility alias for :mod:`app.analysis.features`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.features"
)

_sys.modules[__name__] = _implementation
