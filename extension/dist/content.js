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
  async function savePreferences(payload = {}) {
    return chrome.runtime.sendMessage({
      type: "SPORTABASE_SAVE_OVERLAY_PREFS",
      payload
    });
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
        sportabaseCustomWidth: null,
        sportabaseCustomHeight: null,
        sportabaseLeft: null,
        sportabaseTop: null,
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

  // src/ui/settings.js
  function installSettingsDrawer({
    overlay,
    preferences = {}
  } = {}) {
    if (!overlay) {
      return {
        open() {
        },
        close() {
        }
      };
    }
    let currentPreferences = {
      ...preferences
    };
    let closeTimer = null;
    const layer = document.createElement("div");
    layer.className = "sb-settings-layer";
    layer.hidden = true;
    layer.innerHTML = `
    <button
      class="sb-settings-backdrop"
      type="button"
      aria-label="Close settings"
      data-sb-settings-close
    ></button>

    <section
      class="sb-settings-panel"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sb-settings-title"
    >
      <header class="sb-settings-header">
        <div>
          <div
            id="sb-settings-title"
            class="sb-settings-title"
          >
            Settings
          </div>

          <div class="sb-settings-subtitle">
            Personalize your Sportabase experience
          </div>
        </div>

        <button
          class="sb-icon-button"
          type="button"
          aria-label="Close settings"
          title="Close settings"
          data-sb-settings-close
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

      <div class="sb-settings-content">
        <section class="sb-settings-group">
          <div class="sb-settings-group-title">
            Appearance
          </div>

          <label class="sb-setting-row">
            <span>
              <strong>Theme</strong>
              <small>Choose light, dark, or follow your system.</small>
            </span>

            <select data-sb-setting="sportabaseAppearance">
              <option value="system">System</option>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Accent</strong>
              <small>Use Sportabase purple or your own color.</small>
            </span>

            <select data-sb-setting="sportabaseAccentMode">
              <option value="dynamic">Sportabase</option>
              <option value="fixed">Custom</option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Accent color</strong>
              <small>Used when the accent mode is Custom.</small>
            </span>

            <input
              type="color"
              data-sb-setting="sportabaseAccentColor"
            />
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Glow</strong>
              <small>Control decorative lighting effects.</small>
            </span>

            <select data-sb-setting="sportabaseGlowLevel">
              <option value="off">Off</option>
              <option value="reduced">Reduced</option>
              <option value="full">Full</option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Motion</strong>
              <small>Control transitions and animations.</small>
            </span>

            <select data-sb-setting="sportabaseMotionLevel">
              <option value="full">Full</option>
              <option value="reduced">Reduced</option>
              <option value="none">None</option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>High contrast</strong>
              <small>Add a stronger boundary around the panel.</small>
            </span>

            <input
              type="checkbox"
              data-sb-setting="sportabaseHighContrast"
            />
          </label>
        </section>

        <section class="sb-settings-group">
          <div class="sb-settings-group-title">
            Reading
          </div>

          <label class="sb-setting-row">
            <span>
              <strong>Text size</strong>
              <small>Adjust the interface typography.</small>
            </span>

            <select data-sb-setting="sportabaseTextScale">
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Density</strong>
              <small>Control spacing between interface elements.</small>
            </span>

            <select data-sb-setting="sportabaseDensity">
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
              <option value="spacious">Spacious</option>
            </select>
          </label>
        </section>

        <div class="sb-settings-footer">
          Changes are saved automatically.
        </div>
      </div>
    </section>
  `;
    overlay.appendChild(layer);
    const settingsButton = overlay.querySelector(
      "[data-sb-settings]"
    );
    const panel = layer.querySelector(
      ".sb-settings-panel"
    );
    const accentModeControl = layer.querySelector(
      '[data-sb-setting="sportabaseAccentMode"]'
    );
    const accentColorControl = layer.querySelector(
      '[data-sb-setting="sportabaseAccentColor"]'
    );
    function updateAccentControlState() {
      if (!accentColorControl) return;
      const customAccent = currentPreferences.sportabaseAccentMode === "fixed";
      accentColorControl.disabled = !customAccent;
      accentColorControl.closest(".sb-setting-row")?.classList.toggle(
        "sb-setting-disabled",
        !customAccent
      );
    }
    function syncControls() {
      layer.querySelectorAll("[data-sb-setting]").forEach((control) => {
        const key = control.dataset.sbSetting;
        const value = currentPreferences[key];
        if (control.type === "checkbox") {
          control.checked = Boolean(value);
          return;
        }
        control.value = value ?? "";
      });
      updateAccentControlState();
    }
    function open() {
      if (closeTimer) {
        window.clearTimeout(closeTimer);
        closeTimer = null;
      }
      syncControls();
      layer.hidden = false;
      settingsButton?.setAttribute(
        "aria-expanded",
        "true"
      );
      requestAnimationFrame(() => {
        layer.classList.add("sb-settings-open");
        panel?.focus?.();
      });
    }
    function close() {
      layer.classList.remove("sb-settings-open");
      settingsButton?.setAttribute(
        "aria-expanded",
        "false"
      );
      closeTimer = window.setTimeout(() => {
        layer.hidden = true;
        closeTimer = null;
      }, 170);
    }
    layer.querySelectorAll("[data-sb-settings-close]").forEach((button) => {
      button.addEventListener("click", close);
    });
    settingsButton?.addEventListener("click", open);
    layer.querySelectorAll("[data-sb-setting]").forEach((control) => {
      const eventName = control.type === "color" ? "input" : "change";
      control.addEventListener(eventName, () => {
        const key = control.dataset.sbSetting;
        const value = control.type === "checkbox" ? control.checked : control.value;
        currentPreferences = {
          ...currentPreferences,
          [key]: value
        };
        if (control === accentModeControl) {
          updateAccentControlState();
        }
        applyPreferences(
          overlay,
          currentPreferences
        );
        savePreferences({
          [key]: value
        }).catch((error) => {
          console.error(
            "[sportabase] Could not save setting:",
            error
          );
        });
      });
    });
    overlay.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !layer.hidden) {
        close();
      }
    });
    settingsButton?.setAttribute(
      "aria-expanded",
      "false"
    );
    syncControls();
    return {
      open,
      close
    };
  }
  var init_settings = __esm({
    "src/ui/settings.js"() {
      init_preferences();
    }
  });

  // src/ui/window-controls.js
  function clamp(value, minimum, maximum) {
    return Math.max(
      minimum,
      Math.min(maximum, value)
    );
  }
  function getViewportLimits() {
    return {
      maxWidth: Math.max(
        MIN_WIDTH,
        Math.min(820, window.innerWidth - EDGE_MARGIN * 2)
      ),
      maxHeight: Math.max(
        MIN_HEIGHT,
        Math.min(900, window.innerHeight - EDGE_MARGIN * 2)
      )
    };
  }
  function clampGeometry({
    left,
    top,
    width,
    height
  }) {
    const {
      maxWidth,
      maxHeight
    } = getViewportLimits();
    const safeWidth = clamp(
      width,
      MIN_WIDTH,
      maxWidth
    );
    const safeHeight = clamp(
      height,
      MIN_HEIGHT,
      maxHeight
    );
    const safeLeft = clamp(
      left,
      EDGE_MARGIN,
      Math.max(
        EDGE_MARGIN,
        window.innerWidth - safeWidth - EDGE_MARGIN
      )
    );
    const safeTop = clamp(
      top,
      EDGE_MARGIN,
      Math.max(
        EDGE_MARGIN,
        window.innerHeight - safeHeight - EDGE_MARGIN
      )
    );
    return {
      left: safeLeft,
      top: safeTop,
      width: safeWidth,
      height: safeHeight
    };
  }
  function readGeometry(overlay) {
    const rect = overlay.getBoundingClientRect();
    return {
      left: rect.left,
      top: rect.top,
      width: rect.width,
      height: rect.height
    };
  }
  function applyGeometry(overlay, geometry) {
    const safeGeometry = clampGeometry(geometry);
    overlay.style.left = `${Math.round(safeGeometry.left)}px`;
    overlay.style.top = `${Math.round(safeGeometry.top)}px`;
    overlay.style.right = "auto";
    overlay.style.width = `${Math.round(safeGeometry.width)}px`;
    overlay.style.height = `${Math.round(safeGeometry.height)}px`;
    return safeGeometry;
  }
  function saveGeometry(geometry, preferences) {
    if (preferences.sportabaseRememberPosition === false) {
      return;
    }
    savePreferences({
      sportabaseSizeMode: "custom",
      sportabaseCustomWidth: Math.round(geometry.width),
      sportabaseCustomHeight: Math.round(geometry.height),
      sportabaseLeft: Math.round(geometry.left),
      sportabaseTop: Math.round(geometry.top)
    }).catch((error) => {
      console.error(
        "[sportabase] Could not save panel geometry:",
        error
      );
    });
  }
  function restoreGeometry(overlay, preferences) {
    if (preferences.sportabaseRememberPosition === false) {
      return;
    }
    const current = readGeometry(overlay);
    const width = Number(
      preferences.sportabaseCustomWidth
    );
    const height = Number(
      preferences.sportabaseCustomHeight
    );
    const left = Number(
      preferences.sportabaseLeft
    );
    const top = Number(
      preferences.sportabaseTop
    );
    const hasSavedSize = Number.isFinite(width) && Number.isFinite(height);
    const hasSavedPosition = Number.isFinite(left) && Number.isFinite(top);
    if (!hasSavedSize && !hasSavedPosition) {
      return;
    }
    applyGeometry(overlay, {
      left: hasSavedPosition ? left : current.left,
      top: hasSavedPosition ? top : current.top,
      width: hasSavedSize ? width : current.width,
      height: hasSavedSize ? height : current.height
    });
  }
  function installWindowControls({
    overlay,
    preferences = {}
  } = {}) {
    if (!overlay) return;
    const dragHandles = overlay.querySelectorAll(
      ".sb-header, .sb-settings-header"
    );
    restoreGeometry(
      overlay,
      preferences
    );
    function beginInteraction({
      event,
      direction = null
    }) {
      if (event.button !== 0) return;
      event.preventDefault();
      const startGeometry = readGeometry(overlay);
      const startX = event.clientX;
      const startY = event.clientY;
      overlay.classList.add(
        direction ? "sb-is-resizing" : "sb-is-dragging"
      );
      document.documentElement.classList.add(
        "sb-window-interaction-active"
      );
      function handlePointerMove(moveEvent) {
        const deltaX = moveEvent.clientX - startX;
        const deltaY = moveEvent.clientY - startY;
        let {
          left,
          top,
          width,
          height
        } = startGeometry;
        if (!direction) {
          left += deltaX;
          top += deltaY;
        } else {
          if (direction.includes("e")) {
            width += deltaX;
          }
          if (direction.includes("s")) {
            height += deltaY;
          }
          if (direction.includes("w")) {
            width -= deltaX;
            left += deltaX;
          }
          if (direction.includes("n")) {
            height -= deltaY;
            top += deltaY;
          }
        }
        applyGeometry(overlay, {
          left,
          top,
          width,
          height
        });
      }
      function finishInteraction() {
        document.removeEventListener(
          "pointermove",
          handlePointerMove
        );
        document.removeEventListener(
          "pointerup",
          finishInteraction
        );
        document.removeEventListener(
          "pointercancel",
          finishInteraction
        );
        overlay.classList.remove(
          "sb-is-dragging",
          "sb-is-resizing"
        );
        document.documentElement.classList.remove(
          "sb-window-interaction-active"
        );
        saveGeometry(
          readGeometry(overlay),
          preferences
        );
      }
      document.addEventListener(
        "pointermove",
        handlePointerMove
      );
      document.addEventListener(
        "pointerup",
        finishInteraction
      );
      document.addEventListener(
        "pointercancel",
        finishInteraction
      );
    }
    dragHandles.forEach((dragHandle) => {
      dragHandle.addEventListener(
        "pointerdown",
        (event) => {
          if (event.target.closest(
            "button, a, input, select, textarea"
          )) {
            return;
          }
          beginInteraction({
            event
          });
        }
      );
    });
    [
      "n",
      "s",
      "e",
      "w",
      "ne",
      "nw",
      "se",
      "sw"
    ].forEach((direction) => {
      const handle = document.createElement("div");
      handle.className = "sb-resize-handle";
      handle.dataset.direction = direction;
      handle.setAttribute(
        "aria-hidden",
        "true"
      );
      handle.addEventListener(
        "pointerdown",
        (event) => {
          event.stopPropagation();
          beginInteraction({
            event,
            direction
          });
        }
      );
      overlay.appendChild(handle);
    });
  }
  var MIN_WIDTH, MIN_HEIGHT, EDGE_MARGIN;
  var init_window_controls = __esm({
    "src/ui/window-controls.js"() {
      init_preferences();
      MIN_WIDTH = 360;
      MIN_HEIGHT = 320;
      EDGE_MARGIN = 8;
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
    const modeLabel = mode === "video" ? "VIDEO INTELLIGENCE \xB7 YOUTUBE" : "ARTICLE INTELLIGENCE";
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

          <div
            class="sb-brand-mode"
            data-sb-mode-label
          >
            ${modeLabel}
          </div>
        </div>
      </div>

      <div class="sb-header-actions">
        <button
          class="sb-icon-button"
          type="button"
          data-sb-settings
          aria-label="Open settings"
          aria-expanded="false"
          title="Settings"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.8"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M4 7h10"></path>
            <path d="M18 7h2"></path>
            <circle cx="16" cy="7" r="2"></circle>

            <path d="M4 17h2"></path>
            <path d="M10 17h10"></path>
            <circle cx="8" cy="17" r="2"></circle>
          </svg>
        </button>

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
      </div>
    </header>

    <main
      class="sb-content"
      data-sb-content
    ></main>
  `;
    const mountTarget = document.body || document.documentElement;
    mountTarget.appendChild(overlay);
    const resolvedPreferences = applyPreferences(
      overlay,
      preferences
    );
    installSettingsDrawer({
      overlay,
      preferences: resolvedPreferences
    });
    installWindowControls({
      overlay,
      preferences: resolvedPreferences
    });
    overlay.querySelector("[data-sb-close]")?.addEventListener("click", () => {
      closeSportabaseShell(overlay);
    });
    requestAnimationFrame(() => {
      overlay.classList.add("sb-is-open");
    });
    const content = overlay.querySelector(
      "[data-sb-content]"
    );
    const modeLabelElement = overlay.querySelector(
      "[data-sb-mode-label]"
    );
    return {
      overlay,
      content,
      close() {
        closeSportabaseShell(overlay);
      },
      setModeLabel(value) {
        if (modeLabelElement) {
          modeLabelElement.textContent = String(value || "");
        }
      }
    };
  }
  var OVERLAY_ID;
  var init_overlay_shell = __esm({
    "src/ui/overlay-shell.js"() {
      init_logo();
      init_preferences();
      init_settings();
      init_window_controls();
      OVERLAY_ID = "sportabase-root";
    }
  });

  // src/content/article-mode.js
  function openArticleMode({
    shell
  } = {}) {
    if (!shell?.content) return;
    shell.setModeLabel(
      "ARTICLE INTELLIGENCE"
    );
    shell.content.innerHTML = `
    <section class="sb-welcome-card">
      <div class="sb-card-eyebrow">
        ARTICLE MODE
      </div>

      <h2 class="sb-card-title">
        Article migration is next
      </h2>

      <p class="sb-card-description">
        The modular article extractor and analysis
        screen will be connected after Video Mode.
      </p>
    </section>
  `;
  }
  var init_article_mode = __esm({
    "src/content/article-mode.js"() {
    }
  });

  // src/content/youtube-transcript.js
  function wait(milliseconds) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, milliseconds);
    });
  }
  function getTranscriptElements() {
    for (const selector of TRANSCRIPT_SELECTORS) {
      const elements = Array.from(
        document.querySelectorAll(selector)
      ).filter((element) => {
        return element.textContent?.trim();
      });
      if (elements.length) {
        return elements;
      }
    }
    return [];
  }
  function findTranscriptButton() {
    const directButton = document.querySelector(
      [
        "ytd-video-description-transcript-section-renderer button",
        'button[aria-label*="transcript" i]',
        'button[title*="transcript" i]'
      ].join(", ")
    );
    if (directButton) {
      return directButton;
    }
    return Array.from(
      document.querySelectorAll(
        [
          "button",
          "tp-yt-paper-button",
          "ytd-button-renderer button",
          "yt-button-shape button"
        ].join(", ")
      )
    ).find((element) => {
      const searchableText = [
        element.textContent,
        element.getAttribute("aria-label"),
        element.getAttribute("title")
      ].filter(Boolean).join(" ").trim().toLowerCase();
      return searchableText.includes("show transcript") || searchableText === "transcript";
    });
  }
  async function expandVideoDescription() {
    const metadata = document.querySelector(
      "ytd-watch-metadata"
    );
    const expandButton = metadata?.querySelector(
      [
        "#expand",
        "tp-yt-paper-button#expand",
        "ytd-text-inline-expander #expand"
      ].join(", ")
    );
    if (!expandButton) return;
    expandButton.click();
    await wait(400);
  }
  async function extractYouTubeTranscript({
    timeoutMs = 8e3
  } = {}) {
    let transcriptElements = getTranscriptElements();
    if (!transcriptElements.length) {
      let transcriptButton = findTranscriptButton();
      if (!transcriptButton) {
        await expandVideoDescription();
        transcriptButton = findTranscriptButton();
      }
      if (!transcriptButton) {
        throw new Error(
          "No transcript button was found. Captions may be unavailable for this video."
        );
      }
      transcriptButton.click();
      const startedAt = Date.now();
      while (Date.now() - startedAt < timeoutMs) {
        transcriptElements = getTranscriptElements();
        if (transcriptElements.length) {
          break;
        }
        await wait(250);
      }
    }
    const segments = transcriptElements.map((element) => {
      return element.textContent?.replace(/\s+/g, " ").trim();
    }).filter(Boolean);
    const transcript = segments.join(" ").trim();
    if (!transcript) {
      throw new Error(
        "The transcript panel opened, but no transcript text was found."
      );
    }
    return {
      transcript,
      segmentCount: segments.length,
      characterCount: transcript.length
    };
  }
  var TRANSCRIPT_SELECTORS;
  var init_youtube_transcript = __esm({
    "src/content/youtube-transcript.js"() {
      TRANSCRIPT_SELECTORS = [
        'transcript-segment-view-model span[role="text"]',
        "ytd-transcript-segment-renderer .segment-text",
        "ytd-transcript-segment-renderer yt-formatted-string"
      ];
    }
  });

  // src/content/video-mode.js
  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function getVideoTitle() {
    return document.querySelector("h1 yt-formatted-string")?.textContent?.trim() || document.title.replace(" - YouTube", "") || "YouTube video";
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
  function openVideoMode({
    shell
  } = {}) {
    if (!shell?.content) return;
    shell.setModeLabel(
      "VIDEO INTELLIGENCE \xB7 YOUTUBE"
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
    const analyzeButton = shell.content.querySelector(
      "[data-sb-video-analyze]"
    );
    const status = shell.content.querySelector(
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
        status.className = "sb-video-status sb-video-status-loading";
        status.innerHTML = `
        <span class="sb-status-pulse"></span>

        <span>
          Opening and reading the YouTube transcript\u2026
        </span>
      `;
        try {
          const transcriptResult = await extractYouTubeTranscript();
          status.className = "sb-video-status sb-video-status-success";
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
              segments \xB7
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
          status.className = "sb-video-status sb-video-status-error";
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
            error?.message || "The transcript could not be read."
          )}
            </span>
          </div>
        `;
          analyzeButton.disabled = false;
          analyzeButton.classList.remove(
            "sb-button-loading"
          );
          analyzeButton.innerHTML = getAnalyzeButtonMarkup("Try again");
        }
      }
    );
  }
  var init_video_mode = __esm({
    "src/content/video-mode.js"() {
      init_youtube_transcript();
    }
  });

  // src/content/index.js
  var require_index = __commonJS({
    "src/content/index.js"() {
      init_sportabase();
      init_overlay_shell();
      init_article_mode();
      init_video_mode();
      var config = globalThis.__SPORTABASE_BOOT_CONFIG__ || {};
      var isYouTubeVideo = window.location.href.includes(
        "youtube.com/watch"
      ) || document.querySelector(
        "ytd-watch-flexy"
      ) !== null;
      var shell = openSportabaseShell({
        mode: isYouTubeVideo ? "video" : "article",
        preferences: config.preferences || {}
      });
      if (isYouTubeVideo) {
        openVideoMode({
          shell,
          config
        });
      } else {
        openArticleMode({
          shell,
          config
        });
      }
      console.log(
        "[sportabase] Modular mode opened:",
        isYouTubeVideo ? "video" : "article"
      );
    }
  });
  require_index();
})();
//# sourceMappingURL=content.js.map
