(() => {
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __esm = (fn, res, err) => function __init() {
    if (err) throw err[0];
    try {
      return fn && (res = (0, fn[__getOwnPropNames(fn)[0]])(fn = 0)), res;
    } catch (e) {
      throw err = [e], e;
    }
  };
  var __commonJS = (cb, mod) => function __require() {
    try {
      return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
    } catch (e) {
      throw mod = 0, e;
    }
  };

  // src/styles/sportabase.css
  var init_sportabase = __esm({
    "src/styles/sportabase.css"() {
    }
  });

  // src/ui/logo.js
  function getSportabaseLogoMarkup() {
    return `
    <div class="sb-logo" aria-hidden="true">
      <span>SB</span>
    </div>
  `;
  }
  var init_logo = __esm({
    "src/ui/logo.js"() {
    }
  });

  // src/ui/preferences.js
  function resolvePreferences(input = {}) {
    return {
      ...DEFAULT_PREFERENCES,
      ...input || {}
    };
  }
  function applyPreferences(overlay, inputPreferences = {}) {
    if (!overlay) return resolvePreferences(inputPreferences);
    const preferences = resolvePreferences(inputPreferences);
    const systemPrefersLight = window.matchMedia?.(
      "(prefers-color-scheme: light)"
    )?.matches || false;
    const appearance = preferences.sportabaseAppearance === "system" ? systemPrefersLight ? "light" : "dark" : preferences.sportabaseAppearance;
    const palette = PALETTES[appearance] || PALETTES.dark;
    const accent = preferences.sportabaseAccentMode === "fixed" ? preferences.sportabaseAccentColor || "#7c3aed" : "#7c3aed";
    const textScaleMap = {
      small: 0.94,
      medium: 1,
      large: 1.08
    };
    const densityMap = {
      compact: 0.88,
      comfortable: 1,
      spacious: 1.12
    };
    const glowMap = {
      off: 0,
      reduced: 0.55,
      full: 1
    };
    overlay.dataset.sbAppearance = appearance;
    overlay.dataset.sbMotion = preferences.sportabaseMotionLevel;
    overlay.dataset.sbGlow = preferences.sportabaseGlowLevel;
    overlay.classList.toggle(
      "sb-high-contrast",
      Boolean(preferences.sportabaseHighContrast)
    );
    overlay.style.setProperty(
      "--sb-panel-top",
      palette.panelTop
    );
    overlay.style.setProperty(
      "--sb-panel-bottom",
      palette.panelBottom
    );
    overlay.style.setProperty(
      "--sb-header-background",
      palette.header
    );
    overlay.style.setProperty(
      "--sb-surface",
      palette.surface
    );
    overlay.style.setProperty(
      "--sb-raised",
      palette.raised
    );
    overlay.style.setProperty(
      "--sb-text",
      palette.text
    );
    overlay.style.setProperty(
      "--sb-muted",
      palette.muted
    );
    overlay.style.setProperty(
      "--sb-border",
      palette.border
    );
    overlay.style.setProperty(
      "--sb-divider",
      palette.divider
    );
    overlay.style.setProperty(
      "--sb-shadow",
      palette.shadow
    );
    overlay.style.setProperty(
      "--sb-accent",
      accent
    );
    overlay.style.setProperty(
      "--sb-accent-bright",
      `color-mix(in srgb, ${accent} 72%, white 28%)`
    );
    overlay.style.setProperty(
      "--sb-text-scale",
      String(
        textScaleMap[preferences.sportabaseTextScale] || 1
      )
    );
    overlay.style.setProperty(
      "--sb-density",
      String(
        densityMap[preferences.sportabaseDensity] || 1
      )
    );
    overlay.style.setProperty(
      "--sb-glow-strength",
      String(
        glowMap[preferences.sportabaseGlowLevel] ?? 0.55
      )
    );
    overlay.style.colorScheme = appearance;
    return preferences;
  }
  var DEFAULT_PREFERENCES, PALETTES;
  var init_preferences = __esm({
    "src/ui/preferences.js"() {
      DEFAULT_PREFERENCES = {
        sportabaseAppearance: "system",
        sportabaseAccentMode: "dynamic",
        sportabaseAccentColor: "#7c3aed",
        sportabaseGlowLevel: "reduced",
        sportabaseMotionLevel: "full",
        sportabaseHighContrast: false,
        sportabaseTextScale: "medium",
        sportabaseDensity: "comfortable",
        sportabaseSizeMode: "comfort",
        sportabaseRememberPosition: true
      };
      PALETTES = {
        dark: {
          panelTop: "#121214",
          panelBottom: "#0c0c0e",
          header: "rgba(16, 16, 18, 0.92)",
          surface: "#19191c",
          raised: "#222226",
          text: "#f8f8fa",
          muted: "#9d9da5",
          border: "rgba(255, 255, 255, 0.10)",
          divider: "rgba(255, 255, 255, 0.08)",
          shadow: "rgba(0, 0, 0, 0.50)"
        },
        light: {
          panelTop: "#ffffff",
          panelBottom: "#f3f4f7",
          header: "rgba(255, 255, 255, 0.94)",
          surface: "#ffffff",
          raised: "#eef0f4",
          text: "#15161a",
          muted: "#666a73",
          border: "rgba(15, 23, 42, 0.13)",
          divider: "rgba(15, 23, 42, 0.09)",
          shadow: "rgba(15, 23, 42, 0.20)"
        }
      };
    }
  });

  // src/ui/overlay-shell.js
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
  function openSportabaseShell({
    mode = "article",
    preferences = {}
  } = {}) {
    document.getElementById(OVERLAY_ID)?.remove();
    const isVideo = mode === "video";
    const modeLabel = isVideo ? "VIDEO INTELLIGENCE \xB7 YOUTUBE" : "ARTICLE INTELLIGENCE";
    const pageTitle = isVideo ? document.querySelector("h1 yt-formatted-string")?.textContent?.trim() || document.title.replace(" - YouTube", "") : document.title;
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
    applyPreferences(overlay, preferences);
    overlay.querySelector("[data-sb-close]")?.addEventListener("click", () => {
      closeSportabaseShell(overlay);
    });
    requestAnimationFrame(() => {
      overlay.classList.add("sb-is-open");
    });
    return overlay;
  }
  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  var OVERLAY_ID;
  var init_overlay_shell = __esm({
    "src/ui/overlay-shell.js"() {
      init_logo();
      init_preferences();
      OVERLAY_ID = "sportabase-root";
    }
  });

  // src/content/index.js
  var require_index = __commonJS({
    "src/content/index.js"() {
      init_sportabase();
      init_overlay_shell();
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
            const isYouTubeVideo = window.location.href.includes(
              "youtube.com/watch"
            ) || document.querySelector("ytd-watch-flexy") !== null;
            openSportabaseShell({
              mode: isYouTubeVideo ? "video" : "article",
              preferences: message.config?.preferences || {}
            });
            sendResponse({
              ok: true,
              status: "modular-shell-open",
              mode: isYouTubeVideo ? "video" : "article"
            });
          }
        );
      }
    }
  });
  require_index();
})();
//# sourceMappingURL=content.js.map
