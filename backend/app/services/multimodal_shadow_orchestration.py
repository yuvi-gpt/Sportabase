"""Compatibility alias for :mod:`app.workflows.multimodal_shadow_orchestration`.

The service path preserves exact workflow-module identity while supplying the
structured-claim ingestion shadow adapter as the default lower-level runner.
Callers that explicitly inject ``shadow_runner`` keep their existing behavior.
"""

import functools as _functools
import importlib as _importlib
import sys as _sys

_implementation = _importlib.import_module(
    "app.workflows.multimodal_shadow_orchestration"
)
_enhanced_shadow_api = _importlib.import_module(
    "app.services.multimodal_shadow_api_enhanced"
)

if not getattr(
    _implementation,
    "_sportabase_structured_ingestion_wrapped",
    False,
):
    _original_execute = (
        _implementation
        .execute_multimodal_shadow_orchestration
    )

    @_functools.wraps(_original_execute)
    def _execute_with_structured_ingestion(*args, **kwargs):
        if "shadow_runner" not in kwargs:
            kwargs["shadow_runner"] = (
                _enhanced_shadow_api
                .execute_multimodal_shadow_api
            )
        return _original_execute(*args, **kwargs)

    _implementation.execute_multimodal_shadow_orchestration = (
        _execute_with_structured_ingestion
    )
    _implementation._sportabase_structured_ingestion_wrapped = True

_sys.modules[__name__] = _implementation
