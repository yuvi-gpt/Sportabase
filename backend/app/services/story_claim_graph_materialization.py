"""Compatibility alias for :mod:`app.story.story_claim_graph_materialization`."""

import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.story.story_claim_graph_materialization"
)

_sys.modules[__name__] = _implementation
