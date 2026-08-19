"""Compatibility alias for :mod:`app.story.stories`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.story.stories"
)

_sys.modules[__name__] = _implementation
