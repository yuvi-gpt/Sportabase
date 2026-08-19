"""Compatibility alias for :mod:`app.analysis.verification.machine_verified_revision_runtime`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.analysis.verification.machine_verified_revision_runtime"
)

_sys.modules[__name__] = _implementation
