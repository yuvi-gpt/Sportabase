from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.operations.persistent_store import (
    PersistentOperationsStoreUnavailable,
    initialize_persistent_operations_store,
)


PERSISTENT_OPERATIONS_RUNTIME_VERSION = (
    "sportabase-persistent-operations-runtime-v1"
)
PERSISTENT_OPERATIONS_STATE_ATTRIBUTE = (
    "_sportabase_persistent_operations_store_status"
)


def build_persistent_operations_startup_handler(
    *,
    app: Any,
    database_url: str,
    timeout_seconds: int | float,
    initializer: Callable[..., bool] = initialize_persistent_operations_store,
) -> Callable[[], str]:
    """Build a startup hook that never makes telemetry a product outage.

    An empty database URL keeps the store disabled. A transient PostgreSQL
    availability failure marks the runtime unavailable but does not prevent the
    API from starting. Configuration errors still propagate so a deliberately
    enabled but invalid store cannot fail silently.
    """

    def startup() -> str:
        try:
            initialized = initializer(
                database_url=database_url,
                timeout_seconds=timeout_seconds,
            )
        except PersistentOperationsStoreUnavailable:
            status = "unavailable"
        else:
            status = "ready" if initialized else "disabled"

        setattr(
            app.state,
            PERSISTENT_OPERATIONS_STATE_ATTRIBUTE,
            status,
        )
        return status

    return startup


__all__ = [
    "PERSISTENT_OPERATIONS_RUNTIME_VERSION",
    "PERSISTENT_OPERATIONS_STATE_ATTRIBUTE",
    "build_persistent_operations_startup_handler",
]
