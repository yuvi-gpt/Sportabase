"""Compatibility alias for :mod:`app.knowledge.sources`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.knowledge.sources"
)

_sys.modules[__name__] = _implementation
