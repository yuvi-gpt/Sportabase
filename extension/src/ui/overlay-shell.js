import { getSportabaseLogoMarkup } from "./logo.js";

const OVERLAY_ID = "sportabase-root";

function closeSportabaseShell(overlay) {
  if (!overlay || overlay.dataset.closing === "true") {
    return;
  }

  overlay.dataset.closing = "true";
  overlay.classList.remove("sb-is-open");
  overlay.classList.add("sb-is-closing");

  window.setTimeout(() => {
    overlay.remove();
  }, 180);
}

export function openSportabaseShell({
  mode = "article",
} = {}) {
  document.getElementById(OVERLAY_ID)?.remove();

  const isVideo = mode === "video";

  const modeLabel = isVideo
    ? "VIDEO INTELLIGENCE · YOUTUBE"
    : "ARTICLE INTELLIGENCE";

  const pageTitle = isVideo
    ? document
        .querySelector("h1 yt-formatted-string")
        ?.textContent?.trim() ||
      document.title.replace(" - YouTube", "")
    : document.title;

  const overlay = document.createElement("aside");

  overlay.id = OVERLAY_ID;
  overlay.className = "sb-overlay";
  overlay.setAttribute(
    "aria-label",
    "Sportabase intelligence panel"
  );

  overlay.innerHTML = `
    <header class="sb-header">
      <div class="sb-brand">
        ${getSportabaseLogoMarkup()}

        <div class="sb-brand-copy">
          <div class="sb-brand-title">
            Sportabase
          </div>

          <div class="sb-brand-mode">
            ${modeLabel}
          </div>
        </div>
      </div>

      <button
        class="sb-icon-button"
        type="button"
        data-sb-close
        aria-label="Close Sportabase"
        title="Close"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <path d="M6 6l12 12"></path>
          <path d="M18 6L6 18"></path>
        </svg>
      </button>
    </header>

    <main class="sb-content">
      <section class="sb-welcome-card">
        <div class="sb-status-row">
          <div class="sb-status-icon">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.9"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M12 3v18"></path>
              <path d="m17 8-5-5-5 5"></path>
            </svg>
          </div>

          <div>
            <div class="sb-card-eyebrow">
              NEW ARCHITECTURE
            </div>

            <h2 class="sb-card-title">
              Modular shell online
            </h2>
          </div>

          <div class="sb-ready-pill">
            <span></span>
            READY
          </div>
        </div>

        <div class="sb-page-context">
          <div class="sb-context-label">
            Current ${isVideo ? "video" : "page"}
          </div>

          <div class="sb-context-title">
            ${escapeHtml(pageTitle || "Untitled")}
          </div>
        </div>

        <p class="sb-card-description">
          The legacy interface has been disconnected.
          Sportabase is now running from the new modular
          content bundle.
        </p>
      </section>
    </main>
  `;

  document.documentElement.appendChild(overlay);

  overlay
    .querySelector("[data-sb-close]")
    ?.addEventListener("click", () => {
      closeSportabaseShell(overlay);
    });

  requestAnimationFrame(() => {
    overlay.classList.add("sb-is-open");
  });

  return overlay;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
