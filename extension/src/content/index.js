if (!globalThis.__SPORTABASE_CONTENT_LOADED__) {
  globalThis.__SPORTABASE_CONTENT_LOADED__ = true;

  console.log("[sportabase] Modular content bundle loaded.");

  chrome.runtime.onMessage.addListener(
    (message, _sender, sendResponse) => {
      if (message?.type !== "SPORTABASE_OPEN") {
        return;
      }

      console.log(
        "[sportabase] Open request received:",
        message.config
      );

      sendResponse({
        ok: true,
        status: "modular-content-ready",
      });
    }
  );
}
