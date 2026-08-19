"""Compatibility alias for :mod:`app.analysis.verification.direct_stakeholder_independence_verifier`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.verification.direct_stakeholder_independence_verifier"
)

_sys.modules[__name__] = _implementation
