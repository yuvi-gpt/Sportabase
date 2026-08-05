export function createRequestLifecycle() {
  let activeController = null;
  let sequence = 0;

  function cancel(
    reason = "cancelled"
  ) {
    sequence += 1;

    const controller =
      activeController;

    activeController = null;

    if (
      controller &&
      !controller.signal.aborted
    ) {
      controller.abort(reason);
    }
  }

  function begin() {
    cancel("superseded");

    const controller =
      new AbortController();

    const requestSequence =
      sequence;

    activeController =
      controller;

    return {
      controller,
      signal: controller.signal,

      isCurrent() {
        return (
          activeController ===
            controller &&
          sequence ===
            requestSequence &&
          !controller.signal.aborted
        );
      },

      finish() {
        if (
          activeController ===
          controller
        ) {
          activeController = null;
        }
      },
    };
  }

  function hasActive() {
    return Boolean(
      activeController &&
      !activeController.signal.aborted
    );
  }

  return {
    begin,
    cancel,
    hasActive,
  };
}
