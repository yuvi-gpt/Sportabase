"""Compatibility alias for the Sportabase Content Engine."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module("app.content.browser_ingestion")
_sys.modules[__name__] = _implementation