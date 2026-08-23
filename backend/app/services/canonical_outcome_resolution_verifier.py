"""Compatibility alias for canonical outcome resolution verification."""

import importlib as _importlib
import sys as _sys


_implementation = _importlib.import_module(
    "app.analysis.verification.canonical_outcome_resolution_verifier"
)

_sys.modules[__name__] = _implementation
