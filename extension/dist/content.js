(() => {
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __commonJS = (cb, mod) => function __require() {
    try {
      return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
    } catch (e) {
      throw mod = 0, e;
    }
  };

  // src/content/index.js
  var require_index = __commonJS({
    "src/content/index.js"() {
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
              status: "modular-content-ready"
            });
          }
        );
      }
    }
  });
  require_index();
})();
//# sourceMappingURL=content.js.map
