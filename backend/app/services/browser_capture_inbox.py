"""Compatibility alias for the Sportabase Content Engine."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module("app.content.capture_inbox")
_sys.modules[__name__] = _implementation