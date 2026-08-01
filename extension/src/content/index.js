import "../styles/sportabase.css";

import "../styles/loader.css";

import {
  openSportabaseShell,
} from "../ui/overlay-shell.js";

import {
  openArticleMode,
} from "./article-mode.js";

import {
  openVideoMode,
} from "./video-mode.js";

const config =
  globalThis.__SPORTABASE_BOOT_CONFIG__ || {};

const isYouTubeVideo =
  window.location.href.includes(
    "youtube.com/watch"
  ) ||
  document.querySelector(
    "ytd-watch-flexy"
  ) !== null;

const shell = openSportabaseShell({
  mode: isYouTubeVideo
    ? "video"
    : "article",

  preferences:
    config.preferences || {},
});

if (isYouTubeVideo) {
  openVideoMode({
    shell,
    config,
  });
} else {
  openArticleMode({
    shell,
    config,
  });
}

console.log(
  "[sportabase] Modular mode opened:",
  isYouTubeVideo
    ? "video"
    : "article"
);
