"""Compatibility alias for :mod:`app.workflows.browser_capture_automation`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.workflows.browser_capture_automation"
)

_sys.modules[__name__] = _implementation
