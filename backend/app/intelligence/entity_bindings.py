"""Compatibility alias for :mod:`app.intelligence.records.entity_bindings`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.intelligence.records.entity_bindings"
)

_sys.modules[__name__] = _implementation
