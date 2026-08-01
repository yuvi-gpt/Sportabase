import {
  extractYouTubeTranscript,
} from "./youtube-transcript.js";

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

export function openVideoMode({
  shell,
} = {}) {
  if (!shell?.content) return;

  shell.setModeLabel(
    "VIDEO INTELLIGENCE · YOUTUBE"
  );

  const videoTitle = getVideoTitle();

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

              <path d="m10 9 5 3-5 3V9Z"></path>
            </svg>
          </div>

          <div class="sb-video-heading">
            <div class="sb-video-eyebrow">
              VIDEO READY
            </div>

            <h2>Transcript-based intelligence</h2>
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
          ${getAnalyzeButtonMarkup("Analyze video")}
        </button>

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

      <div
        class="sb-video-status"
        data-sb-video-status
      >
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
          Sportabase will locate the YouTube
          transcript automatically.
        </span>
      </div>
    </div>
  `;

  const analyzeButton =
    shell.content.querySelector(
      "[data-sb-video-analyze]"
    );

  const status =
    shell.content.querySelector(
      "[data-sb-video-status]"
    );

  analyzeButton?.addEventListener(
    "click",
    async () => {
      analyzeButton.disabled = true;
      analyzeButton.classList.add(
        "sb-button-loading"
      );

      analyzeButton.innerHTML = `
        <span class="sb-button-spinner"></span>
        <span>Finding transcript...</span>
      `;

      status.className =
        "sb-video-status sb-video-status-loading";

      status.innerHTML = `
        <span class="sb-status-pulse"></span>

        <span>
          Opening and reading the YouTube transcript…
        </span>
      `;

      try {
        const transcriptResult =
          await extractYouTubeTranscript();

        status.className =
          "sb-video-status sb-video-status-success";

        status.innerHTML = `
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6 9 17l-5-5"></path>
          </svg>

          <div>
            <strong>Transcript found</strong>

            <span>
              ${transcriptResult.segmentCount}
              segments ·
              ${transcriptResult.characterCount.toLocaleString()}
              characters
            </span>
          </div>
        `;

        analyzeButton.classList.remove(
          "sb-button-loading"
        );

        analyzeButton.innerHTML = `
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M20 6 9 17l-5-5"></path>
          </svg>

          <span>Transcript ready</span>
        `;

        console.log(
          "[sportabase] Transcript extracted:",
          transcriptResult
        );
      } catch (error) {
        console.error(
          "[sportabase] Transcript extraction failed:",
          error
        );

        status.className =
          "sb-video-status sb-video-status-error";

        status.innerHTML = `
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9"></circle>
            <path d="M12 8v5"></path>
            <path d="M12 16h.01"></path>
          </svg>

          <div>
            <strong>Transcript unavailable</strong>

            <span>
              ${escapeHtml(
                error?.message ||
                "The transcript could not be read."
              )}
            </span>
          </div>
        `;

        analyzeButton.disabled = false;
        analyzeButton.classList.remove(
          "sb-button-loading"
        );

        analyzeButton.innerHTML =
          getAnalyzeButtonMarkup("Try again");
      }
    }
  );
}
