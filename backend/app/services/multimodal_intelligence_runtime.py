"""Compatibility alias for :mod:`app.workflows.multimodal_intelligence_runtime`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.workflows.multimodal_intelligence_runtime"
)

_sys.modules[__name__] = _implementation
