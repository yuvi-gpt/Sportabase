export type CurrentRequest = () => boolean;

export function createAccountResyncCoordinator() {
  let generation = 0;
  let requestId = 0;
  let active: { id: number; key: string; promise: Promise<unknown> } | null = null;

  return {
    run<T>(key: string, operation: (isCurrent: CurrentRequest) => Promise<T>): Promise<T> {
      if (active?.key === key) return active.promise as Promise<T>;

      const currentGeneration = ++generation;
      const id = ++requestId;
      const isCurrent = () => generation === currentGeneration;
      const promise = Promise.resolve()
        .then(() => operation(isCurrent))
        .finally(() => {
          if (active?.id === id) active = null;
        });

      active = { id, key, promise };
      return promise;
    },
    invalidate() {
      generation += 1;
      active = null;
    },
  };
}

export function createWebAccountReturnTracker(reconcile: () => void) {
  let away = false;
  let accountManagementPending = false;

  return {
    beginAccountManagement() {
      accountManagementPending = true;
    },
    cancelAccountManagement() {
      accountManagementPending = false;
    },
    markAway() {
      away = true;
    },
    reconcileIfReturned(visible: boolean) {
      if (!visible || (!away && !accountManagementPending)) return false;
      away = false;
      accountManagementPending = false;
      reconcile();
      return true;
    },
    reset() {
      away = false;
      accountManagementPending = false;
    },
  };
}
