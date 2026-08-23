"""Compatibility alias for machine-verified contradiction semantic verification."""

import importlib as _importlib
import sys as _sys


_implementation = _importlib.import_module(
    "app.analysis.verification.machine_verified_contradiction_semantics_verifier"
)

_sys.modules[__name__] = _implementation
