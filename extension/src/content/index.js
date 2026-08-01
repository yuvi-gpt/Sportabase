import "../styles/sportabase.css";

import {
  openSportabaseShell,
} from "../ui/overlay-shell.js";

const config =
  globalThis.__SPORTABASE_BOOT_CONFIG__ || {};

const isYouTubeVideo =
  window.location.href.includes("youtube.com/watch") ||
  document.querySelector("ytd-watch-flexy") !== null;

openSportabaseShell({
  mode: isYouTubeVideo ? "video" : "article",
  preferences: config.preferences || {},
});

console.log(
  "[sportabase] Modular shell opened:",
  isYouTubeVideo ? "video" : "article"
);