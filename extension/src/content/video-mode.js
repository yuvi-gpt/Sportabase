import {
  extractYouTubeTranscript,
} from "./youtube-transcript.js";

import {
  postJson,
  SportabaseApiError,
} from "./api.js";

import {
  createAnalysisLoader,
} from "../ui/loader.js";

const ANALYSIS_STEPS = [
  {
    message: "Identifying the video's central claim…",
    progress: 52,
  },
  {
    message: "Tracing the supporting evidence…",
    progress: 64,
  },
  {
    message: "Testing the argument for gaps…",
    progress: 76,
  },
  {
    message: "Separating substance from presentation…",
    progress: 86,
  },
  {
    message: "Distilling the final assessment…",
    progress: 93,
  },
];

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function wait(milliseconds) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds);
  });
}

function clampScore(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(100, Math.round(numericValue))
  );
}

function humanizeLabel(value) {
  const normalized = String(
    value || "Video analysis"
  )
    .trim()
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ");

  return normalized.replace(
    /\b\w/g,
    (character) => character.toUpperCase()
  );
}

function getVideoTitle() {
  return (
    document
      .querySelector("h1 yt-formatted-string")
      ?.textContent?.trim() ||
    document.title.replace(" - YouTube", "") ||
    "YouTube video"
  );
}

function getScoreColor(score) {
  if (score < 35) return "#ef4444";
  if (score < 50) return "#f59e0b";
  if (score < 65) return "#3b82f6";
  if (score < 80) return "#8b5cf6";
  if (score < 90) return "#14b8a6";

  return "#22c55e";
}

function getAnalyzeButtonMarkup(label) {
  return `
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3v18"></path>
      <path d="m17 8-5-5-5 5"></path>
    </svg>

    <span>${escapeHtml(label)}</span>
  `;
}

function validateVideoResponse(data) {
  if (
    !data ||
    typeof data !== "object"
  ) {
    throw new SportabaseApiError(
      "Sportabase returned an empty video analysis."
    );
  }

  const verdict = String(
    data.verdict || ""
  ).toLowerCase();

  const claim = String(
    data.claim || ""
  ).toLowerCase();

  if (
    verdict === "analysis_failed" ||
    claim.includes("analysis failed")
  ) {
    const backendError = String(
      data.debug?.error ||
      data.evidence_used?.[0] ||
      "The AI analysis could not be completed."
    );

    throw new SportabaseApiError(
      backendError
    );
  }

  return data;
}

function getFriendlyErrorMessage(error) {
  if (
    error instanceof SportabaseApiError
  ) {
    return error.message;
  }

  const message = String(
    error?.message || error || ""
  );

  if (
    message.toLowerCase().includes(
      "transcript"
    )
  ) {
    return message;
  }

  return (
    "Sportabase could not analyze this video " +
    "right now. Please try again."
  );
}

export function openVideoMode({
  shell,
  config = {},
} = {}) {
  if (!shell?.content) return;

  const videoTitle = getVideoTitle();

  let analysisRunning = false;
  let loadingTicker = null;

  shell.setModeLabel(
    "VIDEO INTELLIGENCE · YOUTUBE"
  );

    const baseAccent =
      getComputedStyle(shell.overlay)
        .getPropertyValue("--sb-accent")
        .trim() || "#7c3aed";

    const baseAccentBright =
      getComputedStyle(shell.overlay)
        .getPropertyValue("--sb-accent-bright")
        .trim() || baseAccent;

    function applyResultAccent(color) {
      shell.overlay.style.setProperty(
        "--sb-accent",
        color
      );

      shell.overlay.style.setProperty(
        "--sb-accent-bright",
        color
      );

      shell.overlay.style.setProperty(
        "--sb-score-color",
        color
      );

      shell.overlay.style.setProperty(
        "--sb-analysis-accent",
        color
      );

      shell.overlay.classList.add(
        "sb-has-analysis-accent"
      );
    }

    function clearResultAccent() {
      shell.overlay.style.setProperty(
        "--sb-accent",
        baseAccent
      );

      shell.overlay.style.setProperty(
        "--sb-accent-bright",
        baseAccentBright
      );

      shell.overlay.style.removeProperty(
        "--sb-score-color"
      );

      shell.overlay.style.removeProperty(
        "--sb-analysis-accent"
      );

      shell.overlay.classList.remove(
        "sb-has-analysis-accent"
      );
    }

  function stopLoadingTicker() {
    if (!loadingTicker) return;

    window.clearInterval(
      loadingTicker
    );

    loadingTicker = null;
  }

  function renderLanding() {
    stopLoadingTicker();
    analysisRunning = false;
    clearResultAccent();

    shell.setModeLabel(
      "VIDEO INTELLIGENCE · YOUTUBE"
    );

    shell.content.innerHTML = `
      <div class="sb-video-layout">
        <section class="sb-video-card">
          <div class="sb-video-card-header">
            <div class="sb-video-ready-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <rect
                  x="3"
                  y="5"
                  width="18"
                  height="14"
                  rx="3"
                ></rect>

                <path
                  d="m10 9 5 3-5 3V9Z"
                ></path>
              </svg>
            </div>

            <div class="sb-video-heading">
              <div class="sb-video-eyebrow">
                VIDEO READY
              </div>

              <h2>
                Transcript-based intelligence
              </h2>
            </div>

            <div class="sb-video-detected-pill">
              <span></span>
              DETECTED
            </div>
          </div>

          <div class="sb-video-context">
            <div class="sb-video-context-label">
              Current video
            </div>

            <div class="sb-video-title">
              ${escapeHtml(videoTitle)}
            </div>
          </div>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-video-analyze
          >
            ${getAnalyzeButtonMarkup(
              "Analyze video"
            )}
          </button>

          <p class="sb-data-disclosure">
            By analyzing, the video title, URL, and available
            transcript are sent to Sportabase and Google
            Gemini for analysis.
            <a
              href="https://yuvi-gpt.github.io/Sportabase/privacy.html"
              target="_blank"
              rel="noopener noreferrer"
            >
              Privacy policy
            </a>
          </p>

          <div class="sb-video-feature-grid">
            <div>
              <span>01</span>
              Transcript
            </div>

            <div>
              <span>02</span>
              Evidence
            </div>

            <div>
              <span>03</span>
              Logic
            </div>
          </div>
        </section>

        <div class="sb-video-status">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path
              d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"
            ></path>

            <path d="m9 12 2 2 4-4"></path>
          </svg>

          <span>
            Sportabase will locate the
            YouTube transcript automatically.
          </span>
        </div>
      </div>
    `;

    shell.content
      .querySelector(
        "[data-sb-video-analyze]"
      )
      ?.addEventListener(
        "click",
        runAnalysis
      );
  }

  function renderError(error) {
    stopLoadingTicker();
    analysisRunning = false;
    clearResultAccent();

    const friendlyMessage =
      getFriendlyErrorMessage(error);

    shell.setModeLabel(
      "VIDEO INTELLIGENCE · UNAVAILABLE"
    );

    shell.content.innerHTML = `
      <div class="sb-video-state-layout">
        <section class="sb-video-error-card">
          <div class="sb-video-state-icon">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="9"
              ></circle>

              <path d="M12 8v5"></path>
              <path d="M12 16h.01"></path>
            </svg>
          </div>

          <div class="sb-video-state-eyebrow">
            ANALYSIS UNAVAILABLE
          </div>

          <h2>
            Sportabase could not finish this readout
          </h2>

          <p>
            ${escapeHtml(friendlyMessage)}
          </p>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-video-retry
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6v5h-5"></path>
              <path d="M4 18v-5h5"></path>

              <path
                d="M18.5 9a7 7 0 0 0-11.7-2.6L4 9"
              ></path>

              <path
                d="M5.5 15a7 7 0 0 0 11.7 2.6L20 15"
              ></path>
            </svg>

            <span>Try again</span>
          </button>

          <button
            class="sb-secondary-button"
            type="button"
            data-sb-video-back
          >
            Return to video overview
          </button>
        </section>
      </div>
    `;

    shell.content
      .querySelector(
        "[data-sb-video-retry]"
      )
      ?.addEventListener(
        "click",
        runAnalysis
      );

    shell.content
      .querySelector(
        "[data-sb-video-back]"
      )
      ?.addEventListener(
        "click",
        renderLanding
      );
  }

  function renderResults(
    data,
    transcriptResult
  ) {
    stopLoadingTicker();
    analysisRunning = false;

    const evidenceScore =
      clampScore(data.evidence_score);

    const logicScore =
      clampScore(data.logic_score);

    const supportScore = Math.round(
      (evidenceScore + logicScore) / 2
    );

    const scoreColor =
      getScoreColor(supportScore);

    const uiLabels =
      data.ui_labels &&
      typeof data.ui_labels === "object"
        ? data.ui_labels
        : {};

    const verdictLabel =
      String(
        data.localized_verdict || ""
      ).trim() ||
      humanizeLabel(
        data.verdict || "Assessment complete"
      );

    const contentTypeLabel =
      String(
        data.localized_content_type || ""
      ).trim() ||
      humanizeLabel(
        data.content_type ||
        "Video analysis"
      );

    const evidenceItems =
      Array.isArray(data.evidence_used) &&
      data.evidence_used.length
        ? data.evidence_used
            .map(
              (item) => `
                <li>
                  ${escapeHtml(item)}
                </li>
              `
            )
            .join("")
        : `
            <li>
              No specific evidence details
              were returned.
            </li>
          `;

    applyResultAccent(scoreColor);

    shell.setModeLabel(
      `VIDEO INTELLIGENCE · ${contentTypeLabel.toUpperCase()}`
    );

    shell.content.innerHTML = `
      <div class="sb-video-results">
        <section class="sb-result-score-card">
          <div class="sb-result-score-top">
            <div>
              <div class="sb-result-eyebrow">
                OVERALL SUPPORT
              </div>

              <div class="sb-result-score">
                <strong>
                  ${supportScore}
                </strong>

                <span>/100</span>
              </div>
            </div>

            <div class="sb-result-verdict">
              ${escapeHtml(verdictLabel)}
            </div>
          </div>

          <div class="sb-result-score-track">
            <div
              style="
                width:${supportScore}%;
              "
            ></div>
          </div>

          <div class="sb-result-transcript-meta">
            ${transcriptResult.segmentCount}
            transcript segments ·
            ${transcriptResult.characterCount.toLocaleString()}
            characters analyzed
          </div>
        </section>

        <section class="sb-result-claim-card">
          <div class="sb-result-section-label">
            ${escapeHtml(
              uiLabels.main_claim ||
              "Main claim"
            )}
          </div>

          <p>
            ${escapeHtml(
              data.claim ||
              "No clear central claim was returned."
            )}
          </p>
        </section>

        <div class="sb-result-metrics">
          <section>
            <span>Evidence</span>

            <strong>
              ${evidenceScore}
            </strong>

            <small>/100</small>
          </section>

          <section>
            <span>Logic</span>

            <strong>
              ${logicScore}
            </strong>

            <small>/100</small>
          </section>
        </div>

        <section class="sb-result-detail-card">
          <div class="sb-result-section-label">
            ${escapeHtml(
              uiLabels.evidence_used ||
              "Evidence used"
            )}
          </div>

          <ul>
            ${evidenceItems}
          </ul>
        </section>

        <section class="sb-result-detail-card">
          <div class="sb-result-section-label">
            ${escapeHtml(
              uiLabels.logic_check ||
              "Logic check"
            )}
          </div>

          <p>
            ${escapeHtml(
              data.logic_check ||
              "No logic assessment was returned."
            )}
          </p>
        </section>

        <section
          class="
            sb-result-detail-card
            sb-result-hype-card
          "
        >
          <div class="sb-result-section-label">
            ${escapeHtml(
              uiLabels.hype_check ||
              "Hype check"
            )}
          </div>

          <p>
            ${escapeHtml(
              data.hype_check ||
              "No presentation assessment was returned."
            )}
          </p>
        </section>

        <div class="sb-result-actions">
          <button
            class="sb-secondary-button"
            type="button"
            data-sb-video-overview
          >
            Video overview
          </button>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-video-reanalyze
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6v5h-5"></path>
              <path d="M4 18v-5h5"></path>

              <path
                d="M18.5 9a7 7 0 0 0-11.7-2.6L4 9"
              ></path>

              <path
                d="M5.5 15a7 7 0 0 0 11.7 2.6L20 15"
              ></path>
            </svg>

            <span>${escapeHtml(uiLabels.analyze_again || "Analyze again")}</span>
          </button>
        </div>
      </div>
    `;

    shell.content
      .querySelector(
        "[data-sb-video-overview]"
      )
      ?.addEventListener(
        "click",
        renderLanding
      );

    shell.content
      .querySelector(
        "[data-sb-video-reanalyze]"
      )
      ?.addEventListener(
        "click",
        runAnalysis
      );
  }

  async function runAnalysis() {
    if (analysisRunning) return;

    analysisRunning = true;
    stopLoadingTicker();

    shell.setModeLabel(
      "VIDEO INTELLIGENCE · ANALYZING"
    );

    const loader =
      createAnalysisLoader({
        container: shell.content,
        modeLabel:
          "VIDEO INTELLIGENCE · YOUTUBE",
        message:
          "Opening and reading the YouTube transcript…",
        progress: 18,
      });

    try {
      const transcriptResult =
        await extractYouTubeTranscript();

      loader.update({
        message:
          "Transcript found. Preparing the video analysis…",
        progress: 38,
      });

      await wait(320);

      let loadingStepIndex = 0;

      loader.update(
        ANALYSIS_STEPS[loadingStepIndex]
      );

      loadingTicker =
        window.setInterval(() => {
          if (
            loadingStepIndex <
            ANALYSIS_STEPS.length - 1
          ) {
            loadingStepIndex += 1;
          }

          loader.update(
            ANALYSIS_STEPS[
              loadingStepIndex
            ]
          );
        }, 1900);

      const apiBase = String(
        config.api ||
        "https://sportabase-api.onrender.com"
      ).replace(/\/+$/, "");

      const response = await postJson(
        `${apiBase}/analyze/video`,
        {
          title: videoTitle,
          transcript:
            transcriptResult.transcript,
          url: window.location.href,
        },
        {
          timeoutMs: 120000,
        }
      );

      stopLoadingTicker();

      loader.update({
        message:
          "Finalizing your Sportabase video readout…",
        progress: 95,
      });

      const validatedResponse =
        validateVideoResponse(response);

      await wait(380);

      renderResults(
        validatedResponse,
        transcriptResult
      );
    } catch (error) {
      console.error(
        "[sportabase] Video analysis failed:",
        error
      );

      renderError(error);
    }
  }

  renderLanding();
}
