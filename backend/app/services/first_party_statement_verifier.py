"""Compatibility alias for :mod:`app.analysis.verification.first_party_statement_verifier`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.verification.first_party_statement_verifier"
)

_sys.modules[__name__] = _implementation
