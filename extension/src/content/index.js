import "../styles/sportabase.css";

import {
  openSportabaseShell,
} from "../ui/overlay-shell.js";

if (!globalThis.__SPORTABASE_CONTENT_LOADED__) {
  globalThis.__SPORTABASE_CONTENT_LOADED__ = true;

  console.log(
    "[sportabase] Modular content bundle loaded."
  );

  chrome.runtime.onMessage.addListener(
    (message, _sender, sendResponse) => {
      if (message?.type !== "SPORTABASE_OPEN") {
        return;
      }

      const isYouTubeVideo =
        window.location.href.includes(
          "youtube.com/watch"
        ) ||
        document.querySelector("ytd-watch-flexy") !== null;

      openSportabaseShell({
        mode: isYouTubeVideo ? "video" : "article",
      });

      sendResponse({
        ok: true,
        status: "modular-shell-open",
        mode: isYouTubeVideo
          ? "video"
          : "article",
      });
    }
  );
}
