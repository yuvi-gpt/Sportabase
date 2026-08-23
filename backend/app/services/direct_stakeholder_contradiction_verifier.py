"""Compatibility alias for direct stakeholder contradiction verification."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.verification.direct_stakeholder_contradiction_verifier"
)

_sys.modules[__name__] = _implementation
