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

  // src/styles/loader.css
  var init_loader = __esm({
    "src/styles/loader.css"() {
    }
  });

  // src/styles/video-results.css
  var init_video_results = __esm({
    "src/styles/video-results.css"() {
    }
  });

  // src/styles/article-mode.css
  var init_article_mode = __esm({
    "src/styles/article-mode.css"() {
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

  // src/content/article-extractor.js
  function normalizeText(value) {
    return String(value || "").replace(/\u00a0/g, " ").replace(/[ \t]+/g, " ").replace(/\n[ \t]+/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  function extractTextFromElement(element) {
    if (!element) return "";
    const clone = element.cloneNode(true);
    for (const selector of NOISE_SELECTORS) {
      clone.querySelectorAll(selector).forEach((node) => node.remove());
    }
    const paragraphs = Array.from(
      clone.querySelectorAll(
        "p, h2, h3, blockquote, li"
      )
    ).map(
      (node) => normalizeText(node.innerText || node.textContent)
    ).filter((text) => text.length >= 25);
    if (paragraphs.length >= 3) {
      return normalizeText(
        paragraphs.join("\n\n")
      );
    }
    return normalizeText(
      clone.innerText || clone.textContent
    );
  }
  function scoreCandidate(element, text) {
    if (!text) return -Infinity;
    const paragraphCount = element.querySelectorAll("p").length;
    const headingCount = element.querySelectorAll("h1, h2, h3").length;
    const linkTextLength = Array.from(
      element.querySelectorAll("a")
    ).reduce(
      (total, link) => total + normalizeText(
        link.innerText || link.textContent
      ).length,
      0
    );
    const linkDensity = text.length > 0 ? linkTextLength / text.length : 1;
    return text.length + paragraphCount * 140 + headingCount * 45 - linkDensity * 1200;
  }
  function getArticleTitle() {
    const candidates = [
      document.querySelector(
        'meta[property="og:title"]'
      )?.getAttribute("content"),
      document.querySelector(
        'meta[name="twitter:title"]'
      )?.getAttribute("content"),
      document.querySelector("article h1")?.textContent,
      document.querySelector("main h1")?.textContent,
      document.querySelector("h1")?.textContent,
      document.title
    ];
    return candidates.map(normalizeText).find(Boolean) || "Untitled sports article";
  }
  function findTitleAnchoredCandidate() {
    const heading = document.querySelector(
      "article h1, [role='article'] h1, main h1, [role='main'] h1, h1"
    );
    if (!heading) return null;
    let current = heading.parentElement;
    let candidate = null;
    for (let depth = 0; current && current !== document.body && depth < 10; depth += 1) {
      const text = extractTextFromElement(current);
      const paragraphCount = current.querySelectorAll("p").length;
      const isUsable = text.length >= 450 && paragraphCount >= 3;
      if (isUsable) {
        if (candidate && text.length > candidate.text.length * 2.4) {
          break;
        }
        candidate = {
          element: current,
          text
        };
        if (current.matches(
          "article, [role='article']"
        )) {
          break;
        }
      }
      current = current.parentElement;
    }
    return candidate;
  }
  function extractArticlePage({
    maxCharacters = 6e3
  } = {}) {
    const candidates = [];
    const seenElements = /* @__PURE__ */ new Set();
    const titleAnchoredCandidate = findTitleAnchoredCandidate();
    if (titleAnchoredCandidate) {
      seenElements.add(
        titleAnchoredCandidate.element
      );
      candidates.push({
        selector: "title-anchored",
        element: titleAnchoredCandidate.element,
        text: titleAnchoredCandidate.text,
        score: scoreCandidate(
          titleAnchoredCandidate.element,
          titleAnchoredCandidate.text
        ) + 1e4
      });
    }
    for (const selector of ARTICLE_SELECTORS) {
      const elements = document.querySelectorAll(selector);
      for (const element of elements) {
        if (!element || seenElements.has(element)) {
          continue;
        }
        seenElements.add(element);
        const text2 = extractTextFromElement(element);
        if (text2.length < 200) continue;
        candidates.push({
          selector,
          element,
          text: text2,
          score: scoreCandidate(
            element,
            text2
          )
        });
      }
    }
    if (!candidates.length && document.body) {
      const fallbackText = extractTextFromElement(document.body);
      if (fallbackText.length >= 200) {
        candidates.push({
          selector: "body",
          element: document.body,
          text: fallbackText,
          score: scoreCandidate(
            document.body,
            fallbackText
          )
        });
      }
    }
    candidates.sort(
      (left, right) => right.score - left.score
    );
    const bestCandidate = candidates[0] || null;
    const fullText = bestCandidate?.text || "";
    const safeLimit = Math.max(
      1e3,
      Number(maxCharacters) || 6e3
    );
    const text = fullText.slice(0, safeLimit).trim();
    return {
      title: getArticleTitle(),
      url: window.location.href,
      hostname: window.location.hostname,
      text,
      fullCharacterCount: fullText.length,
      characterCount: text.length,
      paragraphCount: text ? text.split(/\n{2,}/).length : 0,
      selector: bestCandidate?.selector || null
    };
  }
  var ARTICLE_SELECTORS, NOISE_SELECTORS;
  var init_article_extractor = __esm({
    "src/content/article-extractor.js"() {
      ARTICLE_SELECTORS = [
        "article",
        "main article",
        "[role='main'] article",
        "main",
        "section article",
        "div[data-testid='Body']",
        "div[data-testid='article-body']",
        ".Story__Body",
        ".story__body",
        ".article-body",
        ".article__body",
        ".RichTextContainer",
        ".Article__Content",
        ".article__content",
        "[data-module='ArticleBody']"
      ];
      NOISE_SELECTORS = [
        "script",
        "style",
        "noscript",
        "svg",
        "canvas",
        "iframe",
        "nav",
        "footer",
        "aside",
        "form",
        "button",
        "input",
        "textarea",
        "select",
        "[aria-hidden='true']",
        "[hidden]",
        "[role='navigation']",
        "[role='banner']",
        "[role='complementary']",
        ".advertisement",
        ".advert",
        ".ads",
        ".ad",
        ".social-share",
        ".share-tools",
        ".newsletter",
        ".related-content",
        ".recommended-content",
        ".comments"
      ];
    }
  });

  // src/content/api.js
  async function postJson(url, payload, {
    timeoutMs = 12e4
  } = {}) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      timeoutMs
    );
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });
      const responseText = await response.text();
      let data = null;
      try {
        data = responseText ? JSON.parse(responseText) : null;
      } catch (_) {
        data = null;
      }
      if (!response.ok) {
        const details = String(
          data?.detail || data?.message || responseText || ""
        );
        if (response.status === 429) {
          throw new SportabaseApiError(
            "The AI analysis quota is temporarily exhausted. Try again after it resets.",
            {
              status: response.status,
              details
            }
          );
        }
        if (response.status === 503) {
          throw new SportabaseApiError(
            "The AI analysis service is temporarily busy. Try again in a moment.",
            {
              status: response.status,
              details
            }
          );
        }
        throw new SportabaseApiError(
          details || `Sportabase returned HTTP ${response.status}.`,
          {
            status: response.status,
            details
          }
        );
      }
      return data;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new SportabaseApiError(
          "The analysis took too long and was stopped. Try again once.",
          {
            status: 408
          }
        );
      }
      if (error instanceof SportabaseApiError) {
        throw error;
      }
      throw new SportabaseApiError(
        "Sportabase could not reach the analysis service.",
        {
          details: String(
            error?.message || error || ""
          )
        }
      );
    } finally {
      window.clearTimeout(timeoutId);
    }
  }
  var SportabaseApiError;
  var init_api = __esm({
    "src/content/api.js"() {
      SportabaseApiError = class extends Error {
        constructor(message, {
          status = 0,
          details = ""
        } = {}) {
          super(message);
          this.name = "SportabaseApiError";
          this.status = status;
          this.details = details;
        }
      };
    }
  });

  // src/ui/loader.js
  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function getStageIndex(progress) {
    if (progress < 42) return 0;
    if (progress < 76) return 1;
    return 2;
  }
  function createAnalysisLoader({
    container,
    modeLabel = "VIDEO INTELLIGENCE",
    message = "Preparing the analysis\u2026",
    progress = 12
  } = {}) {
    if (!container) {
      return {
        update() {
        },
        destroy() {
        }
      };
    }
    container.innerHTML = `
    <div class="sb-analysis-loader">
      <div
        class="sb-loader-ambient"
        aria-hidden="true"
      ></div>

      <section
        class="sb-loader-card"
        role="status"
        aria-live="polite"
      >
        <div class="sb-loader-brand-row">
          <div
            class="sb-loader-symbol"
            aria-hidden="true"
          >
            <div class="sb-loader-orbit"></div>

            <div class="sb-loader-core">
              SB
            </div>
          </div>

          <div class="sb-loader-brand-copy">
            <div class="sb-loader-title">
              Sportabase
            </div>

            <div class="sb-loader-mode">
              ${escapeHtml(modeLabel)}
            </div>
          </div>

          <div class="sb-loader-live-pill">
            <span></span>
            LIVE
          </div>
        </div>

        <div class="sb-loader-message-area">
          <div
            class="sb-loader-message"
            data-sb-loader-message
          >
            ${escapeHtml(message)}
          </div>

          <div class="sb-loader-progress-row">
            <div class="sb-loader-analyzing">
              <span></span>
              ANALYZING
            </div>

            <div
              class="sb-loader-stage-count"
              data-sb-loader-stage-count
            >
              Stage 1 of 3
            </div>
          </div>

          <div
            class="sb-loader-track"
            role="progressbar"
            aria-label="Sportabase analysis progress"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow="${progress}"
            data-sb-loader-track
          >
            <div
              class="sb-loader-bar"
              data-sb-loader-bar
              style="width:${progress}%;"
            ></div>
          </div>

          <div class="sb-loader-stages">
            <div
              class="sb-loader-stage"
              data-sb-loader-stage="0"
            >
              <span></span>
              Read
            </div>

            <div
              class="sb-loader-stage"
              data-sb-loader-stage="1"
            >
              <span></span>
              Evaluate
            </div>

            <div
              class="sb-loader-stage"
              data-sb-loader-stage="2"
            >
              <span></span>
              Distill
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
    const messageElement = container.querySelector(
      "[data-sb-loader-message]"
    );
    const barElement = container.querySelector(
      "[data-sb-loader-bar]"
    );
    const trackElement = container.querySelector(
      "[data-sb-loader-track]"
    );
    const stageCountElement = container.querySelector(
      "[data-sb-loader-stage-count]"
    );
    const stageElements = Array.from(
      container.querySelectorAll(
        "[data-sb-loader-stage]"
      )
    );
    function update({
      message: nextMessage,
      progress: nextProgress
    } = {}) {
      const numericProgress = Number(nextProgress);
      const safeProgress = Number.isFinite(numericProgress) ? Math.max(
        5,
        Math.min(
          95,
          Math.round(numericProgress)
        )
      ) : 12;
      if (nextMessage !== void 0 && messageElement) {
        messageElement.textContent = String(nextMessage);
      }
      if (barElement) {
        barElement.style.width = `${safeProgress}%`;
      }
      if (trackElement) {
        trackElement.setAttribute(
          "aria-valuenow",
          String(safeProgress)
        );
      }
      const activeStage = getStageIndex(safeProgress);
      if (stageCountElement) {
        stageCountElement.textContent = `Stage ${activeStage + 1} of 3`;
      }
      stageElements.forEach(
        (stageElement, index) => {
          stageElement.classList.remove(
            "sb-loader-stage-active",
            "sb-loader-stage-complete"
          );
          if (index < activeStage) {
            stageElement.classList.add(
              "sb-loader-stage-complete"
            );
          }
          if (index === activeStage) {
            stageElement.classList.add(
              "sb-loader-stage-active"
            );
          }
        }
      );
    }
    update({
      message,
      progress
    });
    return {
      update,
      destroy() {
        container.innerHTML = "";
      }
    };
  }
  var init_loader2 = __esm({
    "src/ui/loader.js"() {
    }
  });

  // src/content/article-mode.js
  function escapeHtml2(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function wait(milliseconds) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, milliseconds);
    });
  }
  function waitForNextPaint() {
    return new Promise((resolve) => {
      window.requestAnimationFrame(() => {
        window.requestAnimationFrame(resolve);
      });
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
      value || "Article analysis"
    ).trim().replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ");
    return normalized.replace(
      /\b\w/g,
      (character) => character.toUpperCase()
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
  function normalizeStringList(value) {
    if (Array.isArray(value)) {
      return value.map((item) => {
        if (item && typeof item === "object") {
          return String(
            item.text || item.summary || item.point || item.claim || item.label || ""
          ).trim();
        }
        return String(item || "").trim();
      }).filter(Boolean);
    }
    if (typeof value === "string") {
      return value.split(/\n+|•|\u2022/).map(
        (item) => item.replace(/^[-*]\s*/, "").trim()
      ).filter(Boolean);
    }
    return [];
  }
  function getSummaryItems(data) {
    const candidates = [
      data.tldr,
      data.tl_dr,
      data.summary_bullets,
      data.bullets,
      data.key_points,
      data.summary
    ];
    for (const candidate of candidates) {
      const items = normalizeStringList(candidate);
      if (items.length) {
        return items.slice(0, 5);
      }
    }
    return [
      "No summary bullets were returned."
    ];
  }
  function getTags(data) {
    const candidates = [
      data.tags,
      data.entities,
      data.topics,
      data.teams
    ];
    for (const candidate of candidates) {
      const tags = normalizeStringList(candidate);
      if (tags.length) {
        return tags.slice(0, 8);
      }
    }
    return [];
  }
  function getMeritScore(data) {
    return clampScore(
      data.merit_score ?? data.score ?? data.overall_score ?? data.substance_score ?? 0
    );
  }
  function getReasonItems(data) {
    const candidates = [
      data.reasons,
      data.reason,
      data.merit_reasons,
      data.merit_reason,
      data.score_reason,
      data.explanation,
      data.why_it_matters
    ];
    for (const candidate of candidates) {
      const items = normalizeStringList(candidate);
      if (items.length) {
        return items.slice(0, 9);
      }
    }
    return [
      "No scoring explanation was returned."
    ];
  }
  function getArticleType(data) {
    return humanizeLabel(
      data.article_type || data.content_type || data.category || data.story_type || "Article analysis"
    );
  }
  function validateArticleResponse(data) {
    if (!data || typeof data !== "object") {
      throw new SportabaseApiError(
        "Sportabase returned an empty article analysis."
      );
    }
    const status = String(
      data.status || ""
    ).toLowerCase();
    const verdict = String(
      data.verdict || ""
    ).toLowerCase();
    if (status === "analysis_failed" || verdict === "analysis_failed") {
      throw new SportabaseApiError(
        String(
          data.debug?.error || data.error || data.message || "The AI analysis could not be completed."
        )
      );
    }
    return data;
  }
  function getFriendlyErrorMessage(error) {
    if (error instanceof SportabaseApiError) {
      return error.message;
    }
    return String(
      error?.message || error || ""
    ).trim() || "Sportabase could not analyze this article right now.";
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

    <span>${escapeHtml2(label)}</span>
  `;
  }
  function openArticleMode({
    shell,
    config = {}
  } = {}) {
    if (!shell?.content) return;
    let analysisRunning = false;
    let loadingTicker = null;
    const baseAccent = getComputedStyle(shell.overlay).getPropertyValue("--sb-accent").trim() || "#7c3aed";
    const baseAccentBright = getComputedStyle(shell.overlay).getPropertyValue(
      "--sb-accent-bright"
    ).trim() || baseAccent;
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
    function getCurrentArticle() {
      const configuredLimit = Number(
        config.maxAnalyzeChars || config.max_analyze_chars || 6e3
      );
      return extractArticlePage({
        maxCharacters: Number.isFinite(configuredLimit) ? configuredLimit : 6e3
      });
    }
    function renderLanding() {
      stopLoadingTicker();
      clearResultAccent();
      analysisRunning = false;
      const article = getCurrentArticle();
      const articleDetected = article.characterCount >= 300;
      shell.setModeLabel(
        articleDetected ? "ARTICLE INTELLIGENCE \xB7 READY" : "ARTICLE INTELLIGENCE \xB7 LIMITED"
      );
      shell.content.innerHTML = `
      <div class="sb-article-layout">
        <section class="sb-article-card">
          <div class="sb-article-card-header">
            <div class="sb-article-ready-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path
                  d="M6 3h9l4 4v14H6z"
                ></path>

                <path d="M14 3v5h5"></path>
                <path d="M9 13h6"></path>
                <path d="M9 17h6"></path>
              </svg>
            </div>

            <div class="sb-article-heading">
              <div class="sb-article-eyebrow">
                ${articleDetected ? "ARTICLE READY" : "LIMITED TEXT"}
              </div>

              <h2>
                Evidence-first article intelligence
              </h2>
            </div>

            <div class="sb-article-detected-pill">
              <span></span>

              ${articleDetected ? "DETECTED" : "CHECK PAGE"}
            </div>
          </div>

          <div class="sb-article-context">
            <div class="sb-article-context-label">
              Current story
            </div>

            <div class="sb-article-title">
              ${escapeHtml2(article.title)}
            </div>

            <div class="sb-article-source">
              ${escapeHtml2(article.hostname)}
              \xB7
              ${article.characterCount.toLocaleString()}
              characters
            </div>
          </div>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-analyze
            ${articleDetected ? "" : "disabled"}
          >
            ${getAnalyzeButtonMarkup(
        articleDetected ? "Analyze article" : "Article text unavailable"
      )}
          </button>

          <div class="sb-article-feature-grid">
            <div>
              <span>01</span>
              Summary
            </div>

            <div>
              <span>02</span>
              Merit
            </div>

            <div>
              <span>03</span>
              Evidence
            </div>
          </div>
        </section>

        <div class="sb-article-status">
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
            ${articleDetected ? "Sportabase found readable article text on this page." : "Open the full article page, then refresh and try again."}
          </span>
        </div>
      </div>
    `;
      if (articleDetected) {
        shell.content.querySelector(
          "[data-sb-article-analyze]"
        )?.addEventListener(
          "click",
          runAnalysis
        );
      }
    }
    function renderError(error) {
      stopLoadingTicker();
      clearResultAccent();
      analysisRunning = false;
      shell.setModeLabel(
        "ARTICLE INTELLIGENCE \xB7 UNAVAILABLE"
      );
      shell.content.innerHTML = `
      <div class="sb-article-state-layout">
        <section class="sb-article-error-card">
          <div class="sb-article-state-icon">
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

          <div class="sb-article-state-eyebrow">
            ANALYSIS UNAVAILABLE
          </div>

          <h2>
            Sportabase could not finish this readout
          </h2>

          <p>
            ${escapeHtml2(
        getFriendlyErrorMessage(error)
      )}
          </p>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-retry
          >
            ${getAnalyzeButtonMarkup(
        "Try again"
      )}
          </button>

          <button
            class="sb-secondary-button"
            type="button"
            data-sb-article-back
          >
            Return to article overview
          </button>
        </section>
      </div>
    `;
      shell.content.querySelector(
        "[data-sb-article-retry]"
      )?.addEventListener(
        "click",
        runAnalysis
      );
      shell.content.querySelector(
        "[data-sb-article-back]"
      )?.addEventListener(
        "click",
        renderLanding
      );
    }
    function renderResults(data, article) {
      stopLoadingTicker();
      analysisRunning = false;
      const meritScore = getMeritScore(data);
      const scoreColor = getScoreColor(meritScore);
      const articleType = getArticleType(data);
      const summaryItems = getSummaryItems(data);
      const tags = getTags(data);
      const reasonItems = getReasonItems(data);
      const summaryMarkup = summaryItems.map(
        (item) => `
            <li>
              ${escapeHtml2(item)}
            </li>
          `
      ).join("");
      const reasonMarkup = reasonItems.map(
        (item) => `
            <li>
              ${escapeHtml2(item)}
            </li>
          `
      ).join("");
      const tagsMarkup = tags.length ? `
            <div class="sb-article-tags">
              ${tags.map(
        (tag) => `
                    <span>
                      ${escapeHtml2(tag)}
                    </span>
                  `
      ).join("")}
            </div>
          ` : "";
      applyResultAccent(scoreColor);
      shell.setModeLabel(
        `ARTICLE INTELLIGENCE \xB7 ${articleType.toUpperCase()}`
      );
      shell.content.innerHTML = `
      <div class="sb-article-results">
        <section class="sb-article-score-card">
          <div class="sb-article-score-top">
            <div>
              <div class="sb-article-result-eyebrow">
                MERIT SCORE
              </div>

              <div class="sb-article-score">
                <strong>
                  ${meritScore}
                </strong>

                <span>/100</span>
              </div>
            </div>

            <div class="sb-article-type-pill">
              ${escapeHtml2(articleType)}
            </div>
          </div>

          <div class="sb-article-score-track">
            <div
              style="width:${meritScore}%;"
            ></div>
          </div>

          <div class="sb-article-analysis-meta">
            ${article.characterCount.toLocaleString()}
            characters analyzed \xB7
            ${article.paragraphCount}
            content blocks
          </div>
        </section>

        <section class="sb-article-summary-card">
          <div class="sb-article-section-label">
            TL;DR
          </div>

          <ul>
            ${summaryMarkup}
          </ul>
        </section>

        <section class="sb-article-reason-card">
          <div class="sb-article-section-label">
            Why it scored this way
          </div>

          <ul>
            ${reasonMarkup}
          </ul>
        </section>

        ${tagsMarkup}

        <section class="sb-article-source-card">
          <div class="sb-article-section-label">
            Analyzed story
          </div>

          <div class="sb-article-source-title">
            ${escapeHtml2(article.title)}
          </div>

          <div class="sb-article-source-domain">
            ${escapeHtml2(article.hostname)}
          </div>
        </section>

        <div class="sb-article-result-actions">
          <button
            class="sb-secondary-button"
            type="button"
            data-sb-article-overview
          >
            Article overview
          </button>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-reanalyze
          >
            ${getAnalyzeButtonMarkup(
        "Analyze again"
      )}
          </button>
        </div>
      </div>
    `;
      shell.content.querySelector(
        "[data-sb-article-overview]"
      )?.addEventListener(
        "click",
        renderLanding
      );
      shell.content.querySelector(
        "[data-sb-article-reanalyze]"
      )?.addEventListener(
        "click",
        runAnalysis
      );
    }
    async function runAnalysis() {
      if (analysisRunning) return;
      analysisRunning = true;
      stopLoadingTicker();
      clearResultAccent();
      const article = getCurrentArticle();
      if (article.characterCount < 300) {
        renderError(
          new SportabaseApiError(
            "Sportabase could not find enough readable article text on this page."
          )
        );
        return;
      }
      shell.setModeLabel(
        "ARTICLE INTELLIGENCE \xB7 ANALYZING"
      );
      const loader = createAnalysisLoader({
        container: shell.content,
        modeLabel: "ARTICLE INTELLIGENCE",
        message: "Reading the article and removing page noise\u2026",
        progress: 18
      });
      const loaderStartedAt = performance.now();
      try {
        await waitForNextPaint();
        loader.update({
          message: "Article text found. Preparing the intelligence pass\u2026",
          progress: 28
        });
        await wait(320);
        let smoothProgress = 28;
        let loadingStepIndex = 0;
        loader.update({
          message: ANALYSIS_STEPS[loadingStepIndex].message,
          progress: smoothProgress
        });
        loadingTicker = window.setInterval(() => {
          if (smoothProgress >= 92) {
            return;
          }
          const increment = smoothProgress < 58 ? 3 : smoothProgress < 78 ? 2 : 1;
          smoothProgress = Math.min(
            92,
            smoothProgress + increment
          );
          while (loadingStepIndex < ANALYSIS_STEPS.length - 1 && smoothProgress >= ANALYSIS_STEPS[loadingStepIndex + 1].progress) {
            loadingStepIndex += 1;
          }
          loader.update({
            message: ANALYSIS_STEPS[loadingStepIndex].message,
            progress: smoothProgress
          });
        }, 520);
        const apiBase = String(
          config.api || "https://sportabase-api.onrender.com"
        ).replace(/\/+$/, "");
        const response = await postJson(
          `${apiBase}/analyze`,
          {
            title: article.title,
            url: article.url,
            text: article.text,
            max_bullets: 4
          },
          {
            timeoutMs: 12e4
          }
        );
        stopLoadingTicker();
        loader.update({
          message: "Finalizing your Sportabase article brief\u2026",
          progress: 95
        });
        const validatedResponse = validateArticleResponse(response);
        const loaderElapsed = performance.now() - loaderStartedAt;
        const remainingLoaderTime = Math.max(
          0,
          MINIMUM_LOADER_DURATION - loaderElapsed
        );
        await wait(remainingLoaderTime);
        loader.update({
          message: "Analysis complete. Opening your intelligence brief\u2026",
          progress: 95
        });
        await wait(420);
        renderResults(
          validatedResponse,
          article
        );
      } catch (error) {
        console.error(
          "[sportabase] Article analysis failed:",
          error
        );
        renderError(error);
      }
    }
    renderLanding();
  }
  var ANALYSIS_STEPS, MINIMUM_LOADER_DURATION;
  var init_article_mode2 = __esm({
    "src/content/article-mode.js"() {
      init_article_extractor();
      init_api();
      init_loader2();
      ANALYSIS_STEPS = [
        {
          message: "Identifying the article's central story\u2026",
          progress: 50
        },
        {
          message: "Separating reporting from filler\u2026",
          progress: 62
        },
        {
          message: "Evaluating evidence and sourcing\u2026",
          progress: 74
        },
        {
          message: "Scoring substance and credibility\u2026",
          progress: 86
        },
        {
          message: "Distilling the final intelligence brief\u2026",
          progress: 93
        }
      ];
      MINIMUM_LOADER_DURATION = 3e3;
    }
  });

  // src/content/youtube-transcript.js
  function wait2(milliseconds) {
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
    await wait2(400);
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
        await wait2(250);
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
  function escapeHtml3(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function wait3(milliseconds) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, milliseconds);
    });
  }
  function clampScore2(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
      return 0;
    }
    return Math.max(
      0,
      Math.min(100, Math.round(numericValue))
    );
  }
  function humanizeLabel2(value) {
    const normalized = String(
      value || "Video analysis"
    ).trim().replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ");
    return normalized.replace(
      /\b\w/g,
      (character) => character.toUpperCase()
    );
  }
  function getVideoTitle() {
    return document.querySelector("h1 yt-formatted-string")?.textContent?.trim() || document.title.replace(" - YouTube", "") || "YouTube video";
  }
  function getScoreColor2(score) {
    if (score < 35) return "#ef4444";
    if (score < 50) return "#f59e0b";
    if (score < 65) return "#3b82f6";
    if (score < 80) return "#8b5cf6";
    if (score < 90) return "#14b8a6";
    return "#22c55e";
  }
  function getAnalyzeButtonMarkup2(label) {
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

    <span>${escapeHtml3(label)}</span>
  `;
  }
  function validateVideoResponse(data) {
    if (!data || typeof data !== "object") {
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
    if (verdict === "analysis_failed" || claim.includes("analysis failed")) {
      const backendError = String(
        data.debug?.error || data.evidence_used?.[0] || "The AI analysis could not be completed."
      );
      throw new SportabaseApiError(
        backendError
      );
    }
    return data;
  }
  function getFriendlyErrorMessage2(error) {
    if (error instanceof SportabaseApiError) {
      return error.message;
    }
    const message = String(
      error?.message || error || ""
    );
    if (message.toLowerCase().includes(
      "transcript"
    )) {
      return message;
    }
    return "Sportabase could not analyze this video right now. Please try again.";
  }
  function openVideoMode({
    shell,
    config = {}
  } = {}) {
    if (!shell?.content) return;
    const videoTitle = getVideoTitle();
    let analysisRunning = false;
    let loadingTicker = null;
    shell.setModeLabel(
      "VIDEO INTELLIGENCE \xB7 YOUTUBE"
    );
    const baseAccent = getComputedStyle(shell.overlay).getPropertyValue("--sb-accent").trim() || "#7c3aed";
    const baseAccentBright = getComputedStyle(shell.overlay).getPropertyValue("--sb-accent-bright").trim() || baseAccent;
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
        "VIDEO INTELLIGENCE \xB7 YOUTUBE"
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
              ${escapeHtml3(videoTitle)}
            </div>
          </div>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-video-analyze
          >
            ${getAnalyzeButtonMarkup2(
        "Analyze video"
      )}
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
      shell.content.querySelector(
        "[data-sb-video-analyze]"
      )?.addEventListener(
        "click",
        runAnalysis
      );
    }
    function renderError(error) {
      stopLoadingTicker();
      analysisRunning = false;
      clearResultAccent();
      const friendlyMessage = getFriendlyErrorMessage2(error);
      shell.setModeLabel(
        "VIDEO INTELLIGENCE \xB7 UNAVAILABLE"
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
            ${escapeHtml3(friendlyMessage)}
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
      shell.content.querySelector(
        "[data-sb-video-retry]"
      )?.addEventListener(
        "click",
        runAnalysis
      );
      shell.content.querySelector(
        "[data-sb-video-back]"
      )?.addEventListener(
        "click",
        renderLanding
      );
    }
    function renderResults(data, transcriptResult) {
      stopLoadingTicker();
      analysisRunning = false;
      const evidenceScore = clampScore2(data.evidence_score);
      const logicScore = clampScore2(data.logic_score);
      const supportScore = Math.round(
        (evidenceScore + logicScore) / 2
      );
      const scoreColor = getScoreColor2(supportScore);
      const verdictLabel = humanizeLabel2(
        data.verdict || "Assessment complete"
      );
      const contentTypeLabel = humanizeLabel2(
        data.content_type || "Video analysis"
      );
      const evidenceItems = Array.isArray(data.evidence_used) && data.evidence_used.length ? data.evidence_used.map(
        (item) => `
                <li>
                  ${escapeHtml3(item)}
                </li>
              `
      ).join("") : `
            <li>
              No specific evidence details
              were returned.
            </li>
          `;
      applyResultAccent(scoreColor);
      shell.setModeLabel(
        `VIDEO INTELLIGENCE \xB7 ${contentTypeLabel.toUpperCase()}`
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
              ${escapeHtml3(verdictLabel)}
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
            transcript segments \xB7
            ${transcriptResult.characterCount.toLocaleString()}
            characters analyzed
          </div>
        </section>

        <section class="sb-result-claim-card">
          <div class="sb-result-section-label">
            Main claim
          </div>

          <p>
            ${escapeHtml3(
        data.claim || "No clear central claim was returned."
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
            Evidence used
          </div>

          <ul>
            ${evidenceItems}
          </ul>
        </section>

        <section class="sb-result-detail-card">
          <div class="sb-result-section-label">
            Logic check
          </div>

          <p>
            ${escapeHtml3(
        data.logic_check || "No logic assessment was returned."
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
            Hype check
          </div>

          <p>
            ${escapeHtml3(
        data.hype_check || "No presentation assessment was returned."
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

            <span>Analyze again</span>
          </button>
        </div>
      </div>
    `;
      shell.content.querySelector(
        "[data-sb-video-overview]"
      )?.addEventListener(
        "click",
        renderLanding
      );
      shell.content.querySelector(
        "[data-sb-video-reanalyze]"
      )?.addEventListener(
        "click",
        runAnalysis
      );
    }
    async function runAnalysis() {
      if (analysisRunning) return;
      analysisRunning = true;
      stopLoadingTicker();
      shell.setModeLabel(
        "VIDEO INTELLIGENCE \xB7 ANALYZING"
      );
      const loader = createAnalysisLoader({
        container: shell.content,
        modeLabel: "VIDEO INTELLIGENCE \xB7 YOUTUBE",
        message: "Opening and reading the YouTube transcript\u2026",
        progress: 18
      });
      try {
        const transcriptResult = await extractYouTubeTranscript();
        loader.update({
          message: "Transcript found. Preparing the video analysis\u2026",
          progress: 38
        });
        await wait3(320);
        let loadingStepIndex = 0;
        loader.update(
          ANALYSIS_STEPS2[loadingStepIndex]
        );
        loadingTicker = window.setInterval(() => {
          if (loadingStepIndex < ANALYSIS_STEPS2.length - 1) {
            loadingStepIndex += 1;
          }
          loader.update(
            ANALYSIS_STEPS2[loadingStepIndex]
          );
        }, 1900);
        const apiBase = String(
          config.api || "https://sportabase-api.onrender.com"
        ).replace(/\/+$/, "");
        const response = await postJson(
          `${apiBase}/analyze/video`,
          {
            title: videoTitle,
            transcript: transcriptResult.transcript,
            url: window.location.href
          },
          {
            timeoutMs: 12e4
          }
        );
        stopLoadingTicker();
        loader.update({
          message: "Finalizing your Sportabase video readout\u2026",
          progress: 95
        });
        const validatedResponse = validateVideoResponse(response);
        await wait3(380);
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
  var ANALYSIS_STEPS2;
  var init_video_mode = __esm({
    "src/content/video-mode.js"() {
      init_youtube_transcript();
      init_api();
      init_loader2();
      ANALYSIS_STEPS2 = [
        {
          message: "Identifying the video's central claim\u2026",
          progress: 52
        },
        {
          message: "Tracing the supporting evidence\u2026",
          progress: 64
        },
        {
          message: "Testing the argument for gaps\u2026",
          progress: 76
        },
        {
          message: "Separating substance from presentation\u2026",
          progress: 86
        },
        {
          message: "Distilling the final assessment\u2026",
          progress: 93
        }
      ];
    }
  });

  // src/content/index.js
  var require_index = __commonJS({
    "src/content/index.js"() {
      init_sportabase();
      init_loader();
      init_video_results();
      init_article_mode();
      init_overlay_shell();
      init_article_mode2();
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
