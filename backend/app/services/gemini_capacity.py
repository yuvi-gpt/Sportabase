"""Compatibility alias for the Sportabase AI Execution Platform."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module("app.ai.quota")
_sys.modules[__name__] = _implementation