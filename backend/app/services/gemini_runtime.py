"""Compatibility alias for the routed Sportabase AI execution facade."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.ai.routed_generation"
)

_sys.modules[__name__] = _implementation
