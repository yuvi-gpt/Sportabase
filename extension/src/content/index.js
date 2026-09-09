import "../styles/account-settings.css";
﻿import "../styles/sportabase.css";

import "../styles/loader.css";

import "../styles/video-results.css";

import "../styles/article-mode.css";

import "../styles/persistent-intelligence.css";

import "../styles/reporting-profiles.css";

import {
  openSportabaseShell,
} from "../ui/overlay-shell.js";

import {
  openArticleMode,
} from "./article-mode.js";

import {
  openVideoMode,
} from "./video-mode.js";

import {
  createBrowserCaptureSession,
} from "./browser-capture-session.mjs";

import {
  createPersistentIntelligenceIntegration,
} from "./persistent-intelligence.js";

import {
  createReportingProfilesIntegration,
} from "./reporting-profiles.js";

import {
  extractArticlePage,
} from "./article-extractor.js";

import {
  extractYouTubeTranscript,
} from "./youtube-transcript.js";

import {
  postJson,
} from "./api.js";

const config =
  globalThis.__SPORTABASE_BOOT_CONFIG__ || {};

const captureCurrentPage =
  createBrowserCaptureSession({
    config,

    extractArticlePageImpl:
      extractArticlePage,

    extractYouTubeTranscriptImpl:
      extractYouTubeTranscript,

    postJsonImpl:
      postJson,
  });

const runtimeConfig = {
  ...config,
  captureCurrentPage,
};

const isYouTubeVideo =
  window.location.href.includes(
    "youtube.com/watch"
  ) ||
  window.location.href.includes(
    "youtube.com/shorts/"
  ) ||
  document.querySelector(
    "ytd-watch-flexy"
  ) !== null;

const shell = openSportabaseShell({
  mode: isYouTubeVideo
    ? "video"
    : "article",

  preferences:
    runtimeConfig.preferences || {},
});

const apiBase = String(
  runtimeConfig.api ||
  "https://sportabase-api.onrender.com"
).replace(/\/+$/, "");

const persistentIntelligence =
  createPersistentIntelligenceIntegration({
    root: shell.content,
    apiBase,
    sourceUrl: window.location.href,
    mode: isYouTubeVideo
      ? "video"
      : "article",
  });

const reportingProfiles =
  createReportingProfilesIntegration({
    root: shell.content,
    apiBase,
    sourceUrl: window.location.href,
  });

shell.onClose?.(() => {
  persistentIntelligence.destroy();
  reportingProfiles.destroy();
});

if (isYouTubeVideo) {
  openVideoMode({
    shell,
    config:
      runtimeConfig,
  });
} else {
  openArticleMode({
    shell,
    config:
      runtimeConfig,
  });
}

console.log(
  "[sportabase] Modular mode opened:",
  isYouTubeVideo
    ? "video"
    : "article"
);
