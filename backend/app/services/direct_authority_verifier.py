"""Compatibility alias for :mod:`app.analysis.verification.direct_authority_verifier`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.verification.direct_authority_verifier"
)

_sys.modules[__name__] = _implementation
