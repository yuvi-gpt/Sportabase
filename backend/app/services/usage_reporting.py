"""Compatibility alias for :mod:`app.operations.usage`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module("app.operations.usage")
_sys.modules[__name__] = _implementation
