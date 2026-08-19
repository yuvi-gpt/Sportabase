"""Compatibility alias for :mod:`app.workflows.multimodal_inbox_shadow_orchestration`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.workflows.multimodal_inbox_shadow_orchestration"
)

_sys.modules[__name__] = _implementation
