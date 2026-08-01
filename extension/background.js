const API = "https://sportabase-api.onrender.com";
// const API = "http://127.0.0.1:8000";

const CONFIG = {
  maxArticleChars: 6000,
  cacheTtlMs: 1000 * 60 * 60 * 6,
  fetchTimeoutMs: 22000,
};

const DEFAULT_PREFERENCES = {
  sportabaseAppearance: "system",
  sportabaseAccentMode: "dynamic",
  sportabaseAccentColor: "#1ed760",
  sportabaseGlowLevel: "reduced",
  sportabaseMotionLevel: "full",
  sportabaseHighContrast: false,

  sportabaseTextScale: "medium",
  sportabaseDensity: "comfortable",

  sportabaseSizeMode: "comfort",
  sportabaseCustomWidth: null,
  sportabaseCustomHeight: null,
  sportabaseLeft: null,
  sportabaseTop: null,
  sportabaseRememberPosition: true,

  sportabaseDetailLevel: "full",
  sportabaseAutoTranscript: true,
  sportabaseRememberSections: true,
  sportabaseKeepOpenOnNavigation: false,
};

async function openSportabase(tabId) {
  const preferences = await chrome.storage.local.get(
    DEFAULT_PREFERENCES
  );

  const config = {
    api: API,
    preferences,
    ...CONFIG,
  };

  await chrome.scripting.executeScript({
    target: { tabId },
    func: (bootConfig) => {
      globalThis.__SPORTABASE_BOOT_CONFIG__ =
        bootConfig;
    },
    args: [config],
  });

  await chrome.scripting.insertCSS({
    target: { tabId },
    files: ["dist/content.css"],
  });

  await chrome.scripting.executeScript({
    target: { tabId },
    files: ["dist/content.js"],
  });

  return {
    ok: true,
    status: "modular-shell-opened",
  };
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab?.id) return;

  try {
    const response = await openSportabase(tab.id);

    console.log(
      "[sportabase] Modular extension response:",
      response
    );
  } catch (error) {
    const message = String(
      error?.message || error || ""
    );

    if (
      message.includes("Cannot access contents of url") ||
      message.includes("The extensions gallery cannot be scripted") ||
      message.includes("Missing host permission") ||
      message.includes("Frame with ID 0 was removed")
    ) {
      console.warn(
        "[sportabase] Page cannot be opened:",
        message
      );

      return;
    }

    console.error(
      "[sportabase] Failed to open modular extension:",
      error
    );
  }
});

chrome.runtime.onMessage.addListener(
  (message, _sender, sendResponse) => {
    if (
      message?.type !==
      "SPORTABASE_SAVE_OVERLAY_PREFS"
    ) {
      return;
    }

    chrome.storage.local
      .set(message.payload || {})
      .then(() => {
        sendResponse({ ok: true });
      })
      .catch((error) => {
        console.error(
          "[sportabase] Failed to save preferences:",
          error
        );

        sendResponse({
          ok: false,
          error: String(error?.message || error),
        });
      });

    return true;
  }
);
