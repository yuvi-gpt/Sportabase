export function trustedUserAction(handler) {
  if (typeof handler !== "function") {
    throw new TypeError("Trusted user action requires a function.");
  }

  return function handleTrustedUserAction(event, ...args) {
    if (!event?.isTrusted) {
      return undefined;
    }

    return handler.call(this, event, ...args);
  };
}
