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

  // src/styles/account-settings.css
  var init_account_settings = __esm({
    "src/styles/account-settings.css"() {
    }
  });

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

  // src/styles/persistent-intelligence.css
  var init_persistent_intelligence = __esm({
    "src/styles/persistent-intelligence.css"() {
    }
  });

  // src/styles/reporting-profiles.css
  var init_reporting_profiles = __esm({
    "src/styles/reporting-profiles.css"() {
    }
  });

  // src/ui/logo.js
  function getSportabaseLogoMarkup({
    className = ""
  } = {}) {
    const logoUrl = chrome.runtime.getURL(
      "assets/sportabase-logo.png"
    );
    const extraClass = String(className || "").trim();
    return `
    <div
      class="
        sb-logo
        sb-logo-image
        ${extraClass}
      "
      style="
        --sb-logo-art:
          url('${logoUrl}')
      "
      aria-hidden="true"
    >
      <span class="sb-logo-glow"></span>
      <span class="sb-logo-mark"></span>
    </div>
  `;
  }
  var init_logo = __esm({
    "src/ui/logo.js"() {
    }
  });

  // src/ui/preferences.js
  function getViewportWidth() {
    return Math.max(
      1,
      document.documentElement?.clientWidth || globalThis.innerWidth || 1
    );
  }
  function getViewportHeight() {
    return Math.max(
      1,
      document.documentElement?.clientHeight || globalThis.innerHeight || 1
    );
  }
  function clamp(value, minimum, maximum) {
    return Math.max(
      minimum,
      Math.min(maximum, value)
    );
  }
  function finiteNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }
  function fitDimension(desired, available, minimum) {
    if (available <= minimum) {
      return Math.max(
        1,
        available
      );
    }
    return clamp(
      desired,
      minimum,
      available
    );
  }
  function resolvePreferences(input = {}) {
    const merged = {
      ...DEFAULT_PREFERENCES,
      ...input || {}
    };
    const panelPosition = [
      "top-right",
      "top-left"
    ].includes(
      merged.sportabasePanelPosition
    ) ? merged.sportabasePanelPosition : "top-right";
    const sizeMode = [
      "compact",
      "comfort",
      "large",
      "custom"
    ].includes(
      merged.sportabaseSizeMode
    ) ? merged.sportabaseSizeMode : "comfort";
    const horizontalAnchor = merged.sportabaseHorizontalAnchor === "left" ? "left" : "right";
    const detailLevel = merged.sportabaseDetailLevel === "essential" ? "essential" : "full";
    return {
      ...merged,
      sportabasePanelPosition: panelPosition,
      sportabaseSizeMode: sizeMode,
      sportabaseCustomWidth: finiteNumber(
        merged.sportabaseCustomWidth
      ),
      sportabaseCustomHeight: finiteNumber(
        merged.sportabaseCustomHeight
      ),
      sportabaseLeft: finiteNumber(
        merged.sportabaseLeft
      ),
      sportabaseTop: finiteNumber(
        merged.sportabaseTop
      ),
      sportabaseHorizontalAnchor: horizontalAnchor,
      sportabaseEdgeOffset: finiteNumber(
        merged.sportabaseEdgeOffset
      ) ?? EDGE_MARGIN,
      sportabaseRememberPosition: merged.sportabaseRememberPosition !== false,
      sportabaseDetailLevel: detailLevel
    };
  }
  function applyPanelLayout(overlay, inputPreferences = {}) {
    if (!overlay) return;
    const preferences = resolvePreferences(
      inputPreferences
    );
    const preset = SIZE_PRESETS[preferences.sportabaseSizeMode] || SIZE_PRESETS.comfort;
    const customSizeAvailable = preferences.sportabaseSizeMode === "custom" && preferences.sportabaseCustomWidth !== null && preferences.sportabaseCustomHeight !== null;
    const availableWidth = Math.max(
      1,
      getViewportWidth() - EDGE_MARGIN * 2
    );
    const availableHeight = Math.max(
      1,
      getViewportHeight() - EDGE_MARGIN * 2
    );
    const desiredWidth = customSizeAvailable ? preferences.sportabaseCustomWidth : preset.width;
    const desiredHeight = customSizeAvailable ? preferences.sportabaseCustomHeight : availableHeight;
    const width = fitDimension(
      desiredWidth,
      availableWidth,
      MIN_PANEL_WIDTH
    );
    const height = fitDimension(
      desiredHeight,
      availableHeight,
      MIN_PANEL_HEIGHT
    );
    const hasSavedPosition = preferences.sportabaseRememberPosition && preferences.sportabaseLeft !== null && preferences.sportabaseTop !== null;
    let left;
    let top;
    if (hasSavedPosition) {
      const maximumEdgeOffset = Math.max(
        EDGE_MARGIN,
        getViewportWidth() - width - EDGE_MARGIN
      );
      const edgeOffset = clamp(
        preferences.sportabaseEdgeOffset,
        EDGE_MARGIN,
        maximumEdgeOffset
      );
      left = preferences.sportabaseHorizontalAnchor === "right" ? getViewportWidth() - width - edgeOffset : edgeOffset;
      top = clamp(
        preferences.sportabaseTop,
        EDGE_MARGIN,
        Math.max(
          EDGE_MARGIN,
          getViewportHeight() - height - EDGE_MARGIN
        )
      );
    } else {
      top = EDGE_MARGIN;
      left = preferences.sportabasePanelPosition === "top-left" ? EDGE_MARGIN : getViewportWidth() - width - EDGE_MARGIN;
    }
    left = clamp(
      left,
      EDGE_MARGIN,
      Math.max(
        EDGE_MARGIN,
        getViewportWidth() - width - EDGE_MARGIN
      )
    );
    overlay.dataset.sbPosition = preferences.sportabasePanelPosition;
    overlay.dataset.sbSize = preferences.sportabaseSizeMode;
    overlay.style.left = `${Math.round(left)}px`;
    overlay.style.right = "auto";
    overlay.style.top = `${Math.round(top)}px`;
    overlay.style.bottom = "auto";
    overlay.style.width = `${Math.round(width)}px`;
    overlay.style.height = `${Math.round(height)}px`;
  }
  function applyPreferences(overlay, inputPreferences = {}) {
    const preferences = resolvePreferences(
      inputPreferences
    );
    if (!overlay) {
      return preferences;
    }
    const systemPrefersLight = window.matchMedia?.(
      "(prefers-color-scheme: light)"
    )?.matches || false;
    const appearance = preferences.sportabaseAppearance === "system" ? systemPrefersLight ? "light" : "dark" : preferences.sportabaseAppearance;
    const palette = PALETTES[appearance] || PALETTES.dark;
    overlay.dataset.sbText = preferences.sportabaseTextScale;
    overlay.dataset.sbDensity = preferences.sportabaseDensity;
    overlay.dataset.sbMotion = preferences.sportabaseMotionLevel === "system" ? matchMedia("(prefers-reduced-motion: reduce)").matches ? "reduce" : "full" : preferences.sportabaseMotionLevel;
    overlay.dataset.sbAppearance = appearance;
    overlay.dataset.sbDetail = preferences.sportabaseDetailLevel;
    overlay.classList.toggle(
      "sb-high-contrast",
      Boolean(
        preferences.sportabaseHighContrast
      )
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
    const resultPaletteActive = overlay.classList.contains(
      "sb-has-analysis-accent"
    );
    if (!resultPaletteActive) {
      overlay.style.setProperty(
        "--sb-accent",
        appearance === "light" ? "#246b16" : "#78f54a"
      );
      overlay.style.setProperty(
        "--sb-accent-bright",
        "#9cff38"
      );
    }
    applyPanelLayout(
      overlay,
      preferences
    );
    overlay.style.colorScheme = appearance;
    overlay.dispatchEvent(
      new CustomEvent(
        "sportabase:preferences-changed",
        {
          detail: preferences
        }
      )
    );
    return preferences;
  }
  async function savePreferences(payload = {}) {
    return chrome.runtime.sendMessage({
      type: "SPORTABASE_SAVE_OVERLAY_PREFS",
      payload
    });
  }
  var SPORTABASE_VIEWPORT_GUTTER, DEFAULT_PREFERENCES, PALETTES, SIZE_PRESETS, EDGE_MARGIN, MIN_PANEL_WIDTH, MIN_PANEL_HEIGHT;
  var init_preferences = __esm({
    "src/ui/preferences.js"() {
      SPORTABASE_VIEWPORT_GUTTER = 8;
      DEFAULT_PREFERENCES = {
        sportabaseAppearance: "system",
        sportabaseTextScale: "system",
        sportabaseDensity: "comfortable",
        sportabaseMotionLevel: "system",
        sportabaseHighContrast: false,
        /*
         * New users start comfortable and
         * pinned to the top-right corner.
         */
        sportabasePanelPosition: "top-right",
        sportabaseSizeMode: "comfort",
        /*
         * These values are populated after the
         * user manually drags or resizes.
         */
        sportabaseCustomWidth: null,
        sportabaseCustomHeight: null,
        sportabaseLeft: null,
        sportabaseTop: null,
        sportabaseHorizontalAnchor: "right",
        sportabaseEdgeOffset: SPORTABASE_VIEWPORT_GUTTER,
        sportabaseRememberPosition: true,
        sportabaseDetailLevel: "full"
      };
      PALETTES = {
        dark: {
          panelTop: "#101012",
          panelBottom: "#09090b",
          header: "rgba(14, 14, 16, 0.96)",
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
          header: "rgba(255, 255, 255, 0.97)",
          surface: "#ffffff",
          raised: "#eef0f4",
          text: "#15161a",
          muted: "#666a73",
          border: "rgba(15, 23, 42, 0.13)",
          divider: "rgba(15, 23, 42, 0.09)",
          shadow: "rgba(15, 23, 42, 0.20)"
        }
      };
      SIZE_PRESETS = {
        compact: {
          width: 430,
          height: 580
        },
        comfort: {
          width: 520,
          height: 680
        },
        large: {
          width: 650,
          height: 790
        }
      };
      EDGE_MARGIN = SPORTABASE_VIEWPORT_GUTTER;
      MIN_PANEL_WIDTH = 300;
      MIN_PANEL_HEIGHT = 320;
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
    let currentPreferences = resolvePreferences(
      preferences
    );
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
      tabindex="-1"
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
            Configure your Sportabase workspace
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
            Display
          </div>

          <label class="sb-setting-row">
            <span>
              <strong>Theme</strong>

              <small>
                Follow your system or force
                a light or dark interface.
              </small>
            </span>

            <select
              data-sb-setting=
                "sportabaseAppearance"
            >
              <option value="system">
                System
              </option>

              <option value="dark">
                Dark
              </option>

              <option value="light">
                Light
              </option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Panel position</strong>

              <small>
                Pin Sportabase to your preferred
                top corner.
              </small>
            </span>

            <select
              data-sb-setting=
                "sportabasePanelPosition"
            >
              <option value="top-right">
                Top right
              </option>

              <option value="top-left">
                Top left
              </option>
            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Panel size</strong>

              <small>
                Save a consistent extension
                size that remains on screen.
              </small>
            </span>

            <select
              data-sb-setting=
                "sportabaseSizeMode"
            >
              <option value="compact">
                Compact
              </option>

              <option value="comfort">
                Comfortable
              </option>

              <option value="large">
                Large
              </option>

            </select>
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>Remember position</strong>
              <small>Keep the panel where you place it.</small>
            </span>
            <input type="checkbox" data-sb-setting="sportabaseRememberPosition" />
          </label>

          <label class="sb-setting-row">
            <span>
              <strong>High contrast</strong>

              <small>
                Strengthen panel and card
                boundaries.
              </small>
            </span>

            <input
              type="checkbox"
              data-sb-setting=
                "sportabaseHighContrast"
            />
          </label>
        </section>

        <section class="sb-settings-group">
          <div class="sb-settings-group-title">
            Analysis
          </div>

          <label class="sb-setting-row">
            <span>
              <strong>Result detail</strong>

              <small>
                Essential shows the key result.
                Full includes supporting detail.
              </small>
            </span>

            <select
              data-sb-setting=
                "sportabaseDetailLevel"
            >
              <option value="essential">
                Essential
              </option>

              <option value="full">
                Full
              </option>
            </select>
          </label>
        </section>

        <section class="sb-settings-group">
          <div class="sb-settings-group-title">
            Reset
          </div>

          <button
            class="sb-settings-action"
            type="button"
            data-sb-reset-layout
          >
            Reset to comfortable top right
          </button>

          <button
            class="
              sb-settings-action
              sb-settings-action-danger
            "
            type="button"
            data-sb-reset-all
          >
            Reset all settings
          </button>
        </section>

        <div class="sb-settings-footer">
          Extension layout saves automatically. Account preferences use Save changes.
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
    function syncControls() {
      layer.querySelectorAll(
        "[data-sb-setting]"
      ).forEach((control) => {
        const key = control.dataset.sbSetting;
        const value = currentPreferences[key];
        if (control.type === "checkbox") {
          control.checked = Boolean(value);
          return;
        }
        control.value = value ?? "";
      });
    }
    async function persist(payload) {
      try {
        await savePreferences(
          payload
        );
      } catch (error) {
        console.error(
          "[sportabase] Could not save setting:",
          error
        );
      }
    }
    function applyCurrentPreferences() {
      currentPreferences = applyPreferences(
        overlay,
        currentPreferences
      );
      syncControls();
    }
    function resetLayout() {
      const resetPreferences = {
        sportabasePanelPosition: "top-right",
        sportabaseSizeMode: "comfort",
        sportabaseCustomWidth: null,
        sportabaseCustomHeight: null,
        sportabaseLeft: null,
        sportabaseTop: null,
        sportabaseHorizontalAnchor: "right",
        sportabaseEdgeOffset: SPORTABASE_VIEWPORT_GUTTER,
        sportabaseRememberPosition: true
      };
      currentPreferences = {
        ...currentPreferences,
        ...resetPreferences
      };
      applyCurrentPreferences();
      persist(
        resetPreferences
      );
    }
    function resetAllSettings() {
      currentPreferences = {
        ...DEFAULT_PREFERENCES
      };
      applyCurrentPreferences();
      persist({
        ...DEFAULT_PREFERENCES
      });
    }
    overlay.addEventListener(
      "sportabase:geometry-changed",
      (event) => {
        currentPreferences = resolvePreferences({
          ...currentPreferences,
          ...event.detail || {}
        });
        syncControls();
      }
    );
    function open() {
      if (closeTimer) {
        window.clearTimeout(
          closeTimer
        );
        closeTimer = null;
      }
      syncControls();
      layer.hidden = false;
      settingsButton?.setAttribute(
        "aria-expanded",
        "true"
      );
      requestAnimationFrame(() => {
        layer.classList.add(
          "sb-settings-open"
        );
        panel?.focus?.();
      });
    }
    function close() {
      layer.classList.remove(
        "sb-settings-open"
      );
      settingsButton?.setAttribute(
        "aria-expanded",
        "false"
      );
      closeTimer = window.setTimeout(() => {
        layer.hidden = true;
        closeTimer = null;
        settingsButton?.focus();
      }, currentPreferences.sportabaseMotionLevel === "reduce" ? 0 : 170);
    }
    layer.querySelectorAll(
      "[data-sb-settings-close]"
    ).forEach((button) => {
      button.addEventListener(
        "click",
        close
      );
    });
    settingsButton?.addEventListener(
      "click",
      open
    );
    layer.querySelectorAll(
      "[data-sb-setting]"
    ).forEach((control) => {
      control.addEventListener(
        "change",
        () => {
          const key = control.dataset.sbSetting;
          const value = control.type === "checkbox" ? control.checked : control.value;
          const payload = {
            [key]: value
          };
          currentPreferences = {
            ...currentPreferences,
            [key]: value
          };
          if (key === "sportabasePanelPosition") {
            const anchor = value === "top-left" ? "left" : "right";
            currentPreferences = {
              ...currentPreferences,
              sportabaseLeft: null,
              sportabaseTop: null,
              sportabaseHorizontalAnchor: anchor,
              sportabaseEdgeOffset: SPORTABASE_VIEWPORT_GUTTER,
              sportabaseRememberPosition: true
            };
            payload.sportabaseLeft = null;
            payload.sportabaseTop = null;
            payload.sportabaseHorizontalAnchor = anchor;
            payload.sportabaseEdgeOffset = 8;
            payload.sportabaseRememberPosition = true;
          }
          if (key === "sportabaseSizeMode") {
            currentPreferences = {
              ...currentPreferences,
              sportabaseCustomWidth: null,
              sportabaseCustomHeight: null
            };
            payload.sportabaseCustomWidth = null;
            payload.sportabaseCustomHeight = null;
          }
          applyCurrentPreferences();
          persist(payload);
        }
      );
    });
    layer.querySelector(
      "[data-sb-reset-layout]"
    )?.addEventListener(
      "click",
      resetLayout
    );
    const resetAllButton = layer.querySelector("[data-sb-reset-all]");
    let resetAllTimer = null;
    resetAllButton?.addEventListener("click", () => {
      if (resetAllButton.dataset.confirmed === "true") {
        window.clearTimeout(resetAllTimer);
        resetAllButton.dataset.confirmed = "false";
        resetAllButton.textContent = "Reset all settings";
        resetAllSettings();
        return;
      }
      resetAllButton.dataset.confirmed = "true";
      resetAllButton.textContent = "Confirm reset all settings";
      resetAllTimer = window.setTimeout(() => {
        resetAllButton.dataset.confirmed = "false";
        resetAllButton.textContent = "Reset all settings";
      }, 5e3);
    });
    overlay.addEventListener(
      "keydown",
      (event) => {
        if (event.key === "Escape" && !layer.hidden) {
          close();
        }
      }
    );
    settingsButton?.setAttribute(
      "aria-expanded",
      "false"
    );
    for (const key of ["sportabaseAppearance", "sportabaseHighContrast", "sportabaseDetailLevel"]) {
      layer.querySelector(`[data-sb-setting="${key}"]`)?.closest("label")?.remove();
    }
    for (const group of layer.querySelectorAll(".sb-settings-group")) {
      if (!group.querySelector(".sb-setting-row, .sb-settings-action")) group.remove();
    }
    const layoutTitle = layer.querySelector(".sb-settings-group-title");
    if (layoutTitle) layoutTitle.textContent = "Layout (this extension only)";
    const accountGroup = document.createElement("section");
    accountGroup.className = "sb-settings-group";
    const accountTitle = document.createElement("div");
    accountTitle.className = "sb-settings-group-title";
    accountTitle.textContent = "Account settings";
    const accountCopy = document.createElement("p");
    accountCopy.textContent = "Open the extension-owned Settings page to manage account defaults, notifications, privacy and sign-out.";
    const accountButton = document.createElement("button");
    accountButton.type = "button";
    accountButton.className = "sb-settings-action";
    accountButton.textContent = "Open account settings";
    accountButton.addEventListener("click", () => {
      void chrome.runtime.sendMessage({ type: "SPORTABASE_OPEN_EXTENSION_SETTINGS" }).catch((error) => console.error("[sportabase] Could not open account settings:", error));
    });
    accountGroup.append(accountTitle, accountCopy, accountButton);
    layer.querySelector(".sb-settings-content")?.prepend(accountGroup);
    layer.addEventListener("keydown", (event) => {
      if (event.key !== "Tab") return;
      const items = [...layer.querySelectorAll('button:not(:disabled),select:not(:disabled),input:not(:disabled),summary,[tabindex="0"]')].filter((el) => el.getClientRects().length);
      const first = items[0], last = items.at(-1);
      if (!items.includes(document.activeElement)) {
        event.preventDefault();
        (event.shiftKey ? last : first)?.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    });
    applyCurrentPreferences();
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
  function getViewportWidth2() {
    return Math.max(
      1,
      document.documentElement?.clientWidth || globalThis.innerWidth || 1
    );
  }
  function getViewportHeight2() {
    return Math.max(
      1,
      document.documentElement?.clientHeight || globalThis.innerHeight || 1
    );
  }
  function clamp2(value, minimum, maximum) {
    return Math.max(
      minimum,
      Math.min(maximum, value)
    );
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
  function clampGeometry({
    left,
    top,
    width,
    height
  }) {
    const maximumWidth = Math.max(
      1,
      getViewportWidth2() - EDGE_MARGIN2 * 2
    );
    const maximumHeight = Math.max(
      1,
      getViewportHeight2() - EDGE_MARGIN2 * 2
    );
    const safeWidth = clamp2(
      width,
      Math.min(
        MIN_WIDTH,
        maximumWidth
      ),
      maximumWidth
    );
    const safeHeight = clamp2(
      height,
      Math.min(
        MIN_HEIGHT,
        maximumHeight
      ),
      maximumHeight
    );
    const safeLeft = clamp2(
      left,
      EDGE_MARGIN2,
      Math.max(
        EDGE_MARGIN2,
        getViewportWidth2() - safeWidth - EDGE_MARGIN2
      )
    );
    const safeTop = clamp2(
      top,
      EDGE_MARGIN2,
      Math.max(
        EDGE_MARGIN2,
        getViewportHeight2() - safeHeight - EDGE_MARGIN2
      )
    );
    return {
      left: safeLeft,
      top: safeTop,
      width: safeWidth,
      height: safeHeight
    };
  }
  function applyGeometry(overlay, geometry) {
    const safeGeometry = clampGeometry(
      geometry
    );
    overlay.style.left = `${Math.round(
      safeGeometry.left
    )}px`;
    overlay.style.right = "auto";
    overlay.style.top = `${Math.round(
      safeGeometry.top
    )}px`;
    overlay.style.width = `${Math.round(
      safeGeometry.width
    )}px`;
    overlay.style.height = `${Math.round(
      safeGeometry.height
    )}px`;
    return safeGeometry;
  }
  function installWindowControls({
    overlay,
    preferences = {}
  } = {}) {
    if (!overlay) return;
    let currentPreferences = resolvePreferences(
      preferences
    );
    applyPanelLayout(
      overlay,
      currentPreferences
    );
    const dragHandles = overlay.querySelectorAll(
      ".sb-header, .sb-settings-header"
    );
    function saveManualGeometry(geometry, resized) {
      const anchor = geometry.left + geometry.width / 2 >= getViewportWidth2() / 2 ? "right" : "left";
      const edgeOffset = anchor === "right" ? getViewportWidth2() - geometry.left - geometry.width : geometry.left;
      const payload = {
        sportabasePanelPosition: anchor === "right" ? "top-right" : "top-left",
        sportabaseLeft: Math.round(
          geometry.left
        ),
        sportabaseTop: Math.round(
          geometry.top
        ),
        sportabaseHorizontalAnchor: anchor,
        sportabaseEdgeOffset: Math.max(
          EDGE_MARGIN2,
          Math.round(
            edgeOffset
          )
        ),
        sportabaseRememberPosition: true
      };
      if (resized) {
        payload.sportabaseSizeMode = "custom";
        payload.sportabaseCustomWidth = Math.round(
          geometry.width
        );
        payload.sportabaseCustomHeight = Math.round(
          geometry.height
        );
      }
      currentPreferences = resolvePreferences({
        ...currentPreferences,
        ...payload
      });
      overlay.dispatchEvent(
        new CustomEvent(
          "sportabase:geometry-changed",
          {
            detail: payload
          }
        )
      );
      applyPanelLayout(
        overlay,
        currentPreferences
      );
      savePreferences(
        payload
      ).catch((error) => {
        console.error(
          "[sportabase] Could not save panel geometry:",
          error
        );
      });
    }
    function beginInteraction({
      event,
      direction = null
    }) {
      if (event.button !== 0) {
        return;
      }
      event.preventDefault();
      const startGeometry = readGeometry(
        overlay
      );
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
        applyGeometry(
          overlay,
          {
            left,
            top,
            width,
            height
          }
        );
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
        saveManualGeometry(
          readGeometry(
            overlay
          ),
          Boolean(direction)
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
    dragHandles.forEach(
      (dragHandle) => {
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
      }
    );
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
      const handle = document.createElement(
        "div"
      );
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
      overlay.appendChild(
        handle
      );
    });
    function handlePreferencesChanged(event) {
      currentPreferences = resolvePreferences({
        ...currentPreferences,
        ...event.detail || {}
      });
      applyPanelLayout(
        overlay,
        currentPreferences
      );
    }
    function keepInsideViewport() {
      if (!overlay.isConnected) {
        window.removeEventListener(
          "resize",
          keepInsideViewport
        );
        return;
      }
      applyPanelLayout(
        overlay,
        currentPreferences
      );
    }
    overlay.addEventListener(
      "sportabase:preferences-changed",
      handlePreferencesChanged
    );
    window.addEventListener(
      "resize",
      keepInsideViewport
    );
    overlay.addEventListener(
      "sportabase:before-close",
      () => {
        overlay.removeEventListener(
          "sportabase:preferences-changed",
          handlePreferencesChanged
        );
        window.removeEventListener(
          "resize",
          keepInsideViewport
        );
      },
      {
        once: true
      }
    );
  }
  var EDGE_MARGIN2, MIN_WIDTH, MIN_HEIGHT;
  var init_window_controls = __esm({
    "src/ui/window-controls.js"() {
      init_preferences();
      EDGE_MARGIN2 = SPORTABASE_VIEWPORT_GUTTER;
      MIN_WIDTH = 300;
      MIN_HEIGHT = 320;
    }
  });

  // src/ui/overlay-shell.js
  function notifySportabaseShellClosing(overlay) {
    if (!overlay || overlay.dataset.closeNotified === "true") {
      return;
    }
    overlay.dataset.closeNotified = "true";
    overlay.dispatchEvent(
      new CustomEvent(
        SHELL_CLOSE_EVENT
      )
    );
  }
  function closeSportabaseShell(overlay) {
    if (!overlay || overlay.dataset.closing === "true") {
      return;
    }
    notifySportabaseShellClosing(
      overlay
    );
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
    const existingOverlay = document.getElementById(
      OVERLAY_ID
    );
    if (existingOverlay) {
      notifySportabaseShellClosing(
        existingOverlay
      );
      existingOverlay.remove();
    }
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
      onClose(callback) {
        if (typeof callback !== "function") {
          return () => {
          };
        }
        const listener = () => {
          callback();
        };
        overlay.addEventListener(
          SHELL_CLOSE_EVENT,
          listener,
          {
            once: true
          }
        );
        return () => {
          overlay.removeEventListener(
            SHELL_CLOSE_EVENT,
            listener
          );
        };
      },
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
  var OVERLAY_ID, SHELL_CLOSE_EVENT;
  var init_overlay_shell = __esm({
    "src/ui/overlay-shell.js"() {
      init_logo();
      init_preferences();
      init_settings();
      init_window_controls();
      OVERLAY_ID = "sportabase-root";
      SHELL_CLOSE_EVENT = "sportabase:before-close";
    }
  });

  // src/content/article-extractor.js
  function normalizeText(value) {
    return String(value || "").replace(/\u00a0/g, " ").replace(/[ \t]+/g, " ").replace(/\n[ \t]+/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  function getNodeText(node) {
    return normalizeText(
      node?.innerText || node?.textContent || ""
    );
  }
  function getLinkDensity(element, text2) {
    if (!element || !text2) return 1;
    const linkTextLength = Array.from(
      element.querySelectorAll("a")
    ).reduce(
      (total, link) => total + getNodeText(link).length,
      0
    );
    return Math.min(
      1,
      linkTextLength / Math.max(1, text2.length)
    );
  }
  function countMatches(text2, pattern) {
    return (String(text2 || "").match(pattern) || []).length;
  }
  function looksLikeFeedDump(text2) {
    const dateHits = countMatches(
      text2,
      /\b\d{1,2}\s+[A-Za-z?-?]{3,10}\s+\d{4}\b/gi
    );
    const timeHits = countMatches(
      text2,
      /\b\d{1,2}:\d{2}\b/g
    );
    const pipeHits = countMatches(
      text2,
      /\|/g
    );
    return dateHits >= 2 || timeHits >= 4 || timeHits >= 2 && pipeHits >= 2;
  }
  function looksPromotional(text2) {
    const matches = PROMOTIONAL_PATTERNS.filter(
      (pattern) => pattern.test(text2)
    ).length;
    return matches >= 2 || matches >= 1 && text2.length <= 260;
  }
  function looksLikeBoilerplate(text2) {
    return text2.length <= 240 && BOILERPLATE_PATTERNS.some(
      (pattern) => pattern.test(text2)
    );
  }
  function isUsefulContentBlock(node, text2) {
    if (!text2) return false;
    const tagName = String(node.tagName || "").toLowerCase();
    const minimumLength = tagName === "h2" || tagName === "h3" ? 30 : 45;
    if (text2.length < minimumLength) {
      return false;
    }
    if (looksLikeFeedDump(text2)) {
      return false;
    }
    if (looksPromotional(text2)) {
      return false;
    }
    if (looksLikeBoilerplate(text2)) {
      return false;
    }
    const linkDensity = getLinkDensity(node, text2);
    if (linkDensity >= 0.65 && text2.length < 500) {
      return false;
    }
    return true;
  }
  function cloneAndClean(element) {
    const clone = element.cloneNode(true);
    for (const selector of NOISE_SELECTORS) {
      clone.querySelectorAll(selector).forEach(
        (node) => node.remove()
      );
    }
    clone.querySelectorAll(
      "[class], [id]"
    ).forEach((node) => {
      const signature = [
        node.getAttribute("class"),
        node.getAttribute("id")
      ].filter(Boolean).join(" ");
      if (NOISE_TOKEN_PATTERN.test(
        signature
      )) {
        node.remove();
      }
    });
    return clone;
  }
  function collectContentBlocks(element) {
    if (!element) return [];
    const clone = cloneAndClean(element);
    const blocks = [];
    const seen = /* @__PURE__ */ new Set();
    const addBlock = (node) => {
      const text2 = getNodeText(node);
      if (!isUsefulContentBlock(
        node,
        text2
      )) {
        return;
      }
      const duplicateKey = text2.toLowerCase();
      if (seen.has(duplicateKey)) {
        return;
      }
      seen.add(duplicateKey);
      blocks.push(text2);
    };
    clone.querySelectorAll(
      "p, h2, h3, blockquote"
    ).forEach(addBlock);
    if (blocks.length < 2) {
      clone.querySelectorAll("div").forEach((node) => {
        if (node.querySelector(
          "p, div, section, article"
        )) {
          return;
        }
        addBlock(node);
      });
    }
    return blocks;
  }
  function buildCandidate(element, selector, priorityBonus = 0) {
    const blocks = collectContentBlocks(element);
    const text2 = normalizeText(
      blocks.join("\n\n")
    );
    if (text2.length < 250 || blocks.length < 2) {
      return null;
    }
    const blockCount = blocks.length;
    const averageBlockLength = text2.length / blockCount;
    const shortBlockCount = blocks.filter(
      (block) => block.length < 80
    ).length;
    const longBlockCount = blocks.filter(
      (block) => block.length >= 140
    ).length;
    const shortBlockRatio = shortBlockCount / Math.max(1, blockCount);
    const linkDensity = getLinkDensity(
      element,
      text2
    );
    const tooManyBlocks = blockCount > 90;
    const heavilyFragmented = blockCount > 35 && averageBlockLength < 95;
    const mostlyTinyBlocks = blockCount > 15 && shortBlockRatio > 0.72;
    const linkHeavy = linkDensity > 0.55;
    const suspicious = tooManyBlocks || heavilyFragmented || mostlyTinyBlocks || linkHeavy;
    const fragmentationPenalty = Math.max(
      0,
      blockCount - 35
    ) * 240;
    const score = priorityBonus + Math.min(text2.length, 14e3) + blockCount * 115 + longBlockCount * 170 + Math.min(
      averageBlockLength,
      260
    ) * 4 - shortBlockRatio * 2200 - linkDensity * 6500 - fragmentationPenalty - (suspicious ? 8500 : 0);
    return {
      selector,
      element,
      blocks,
      text: text2,
      score,
      suspicious,
      metrics: {
        blockCount,
        averageBlockLength: Math.round(
          averageBlockLength
        ),
        linkDensity: Number(
          linkDensity.toFixed(3)
        ),
        shortBlockRatio: Number(
          shortBlockRatio.toFixed(3)
        )
      }
    };
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
  function findTitleAnchoredCandidates() {
    const heading = document.querySelector(
      [
        "article h1",
        "[role='article'] h1",
        "main h1",
        "[role='main'] h1",
        "h1"
      ].join(", ")
    );
    if (!heading) return [];
    const candidates = [];
    let current = heading.parentElement;
    let previousCandidate = null;
    for (let depth = 0; current && current !== document.body && depth < 9; depth += 1) {
      const candidate = buildCandidate(
        current,
        "title-anchored",
        Math.max(
          1200,
          4200 - depth * 350
        )
      );
      if (candidate) {
        if (previousCandidate && candidate.metrics.blockCount > previousCandidate.metrics.blockCount * 2.2 && candidate.text.length > previousCandidate.text.length * 2.1) {
          break;
        }
        candidates.push(candidate);
        previousCandidate = candidate;
      }
      if (current.matches(
        [
          ...PRIMARY_ARTICLE_SELECTORS,
          ...STRUCTURAL_ARTICLE_SELECTORS
        ].join(", ")
      )) {
        break;
      }
      current = current.parentElement;
    }
    return candidates;
  }
  function addSelectorCandidates(candidates, seenElements, selectors, priorityBonus) {
    for (const selector of selectors) {
      const elements = document.querySelectorAll(
        selector
      );
      for (const element of elements) {
        if (!element || seenElements.has(element)) {
          continue;
        }
        seenElements.add(element);
        const candidate = buildCandidate(
          element,
          selector,
          priorityBonus
        );
        if (candidate) {
          candidates.push(
            candidate
          );
        }
      }
    }
  }
  function truncateBlocks(blocks, maximumCharacters) {
    const selected = [];
    let usedCharacters = 0;
    for (const block of blocks) {
      const separatorLength = selected.length ? 2 : 0;
      const available = maximumCharacters - usedCharacters - separatorLength;
      if (available <= 0) break;
      if (block.length <= available) {
        selected.push(block);
        usedCharacters += separatorLength + block.length;
        continue;
      }
      if (available >= 140) {
        let partial = block.slice(0, available);
        const finalBoundary = Math.max(
          partial.lastIndexOf(". "),
          partial.lastIndexOf("! "),
          partial.lastIndexOf("? "),
          partial.lastIndexOf("?"),
          partial.lastIndexOf("?"),
          partial.lastIndexOf("?")
        );
        if (finalBoundary >= available * 0.55) {
          partial = partial.slice(
            0,
            finalBoundary + 1
          );
        } else {
          const lastSpace = partial.lastIndexOf(" ");
          if (lastSpace >= available * 0.7) {
            partial = partial.slice(
              0,
              lastSpace
            );
          }
        }
        partial = partial.trim();
        if (partial.length >= 100) {
          selected.push(partial);
        }
      }
      break;
    }
    return {
      text: normalizeText(
        selected.join("\n\n")
      ),
      blockCount: selected.length
    };
  }
  function extractArticlePage({
    maxCharacters = 6e3
  } = {}) {
    const candidates = [];
    const seenElements = /* @__PURE__ */ new Set();
    for (const candidate of findTitleAnchoredCandidates()) {
      if (seenElements.has(
        candidate.element
      )) {
        continue;
      }
      seenElements.add(
        candidate.element
      );
      candidates.push(candidate);
    }
    addSelectorCandidates(
      candidates,
      seenElements,
      PRIMARY_ARTICLE_SELECTORS,
      5200
    );
    addSelectorCandidates(
      candidates,
      seenElements,
      STRUCTURAL_ARTICLE_SELECTORS,
      3e3
    );
    addSelectorCandidates(
      candidates,
      seenElements,
      FALLBACK_ARTICLE_SELECTORS,
      0
    );
    if (!candidates.length && document.body) {
      const bodyCandidate = buildCandidate(
        document.body,
        "body-fallback",
        -5e3
      );
      if (bodyCandidate) {
        candidates.push(
          bodyCandidate
        );
      }
    }
    const cleanCandidates = candidates.filter(
      (candidate) => !candidate.suspicious
    );
    const candidatePool = cleanCandidates.length ? cleanCandidates : candidates;
    candidatePool.sort(
      (left, right) => right.score - left.score
    );
    const bestCandidate = candidatePool[0] || null;
    const safeLimit = Math.max(
      1e3,
      Number(maxCharacters) || 6e3
    );
    const truncated = truncateBlocks(
      bestCandidate?.blocks || [],
      safeLimit
    );
    return {
      title: getArticleTitle(),
      url: window.location.href,
      hostname: window.location.hostname,
      text: truncated.text,
      fullCharacterCount: bestCandidate?.text.length || 0,
      characterCount: truncated.text.length,
      paragraphCount: truncated.blockCount,
      selector: bestCandidate?.selector || null,
      extractionMetrics: bestCandidate?.metrics || null,
      candidateCount: candidates.length
    };
  }
  var PRIMARY_ARTICLE_SELECTORS, STRUCTURAL_ARTICLE_SELECTORS, FALLBACK_ARTICLE_SELECTORS, NOISE_SELECTORS, NOISE_TOKEN_PATTERN, PROMOTIONAL_PATTERNS, BOILERPLATE_PATTERNS;
  var init_article_extractor = __esm({
    "src/content/article-extractor.js"() {
      PRIMARY_ARTICLE_SELECTORS = [
        "[itemprop='articleBody']",
        "[data-testid='article-body']",
        "[data-testid='Body']",
        "[data-module='ArticleBody']",
        ".article-body",
        ".article__body",
        ".article-content",
        ".article__content",
        ".Article__Content",
        ".entry-content",
        ".post-content",
        ".post__content",
        ".story-body",
        ".story__body",
        ".Story__Body",
        ".RichTextContainer"
      ];
      STRUCTURAL_ARTICLE_SELECTORS = [
        "article",
        "[role='article']",
        "main article",
        "[role='main'] article",
        "section article"
      ];
      FALLBACK_ARTICLE_SELECTORS = [
        "main",
        "[role='main']"
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
        "figure",
        "figcaption",
        "[aria-hidden='true']",
        "[hidden]",
        "[role='navigation']",
        "[role='banner']",
        "[role='complementary']",
        "[role='dialog']",
        ".advertisement",
        ".advert",
        ".ads",
        ".ad",
        ".banner",
        ".social-share",
        ".share-tools",
        ".newsletter",
        ".related-content",
        ".recommended-content",
        ".comments",
        ".sidebar",
        ".widget",
        ".promo",
        ".sponsored"
      ];
      NOISE_TOKEN_PATTERN = /(?:^|[\s_-])(?:ad|ads|advert|advertisement|banner|betting|bookmaker|comments?|cookie|footer|latest|menu|newsletter|odds|promo|recommended|related|share|sidebar|social|sponsor|subscription|trending|widget)(?:$|[\s_-])/i;
      PROMOTIONAL_PATTERNS = [
        /\b(?:advertisement|advertising|sponsored|paid content)\b/i,
        /\b(?:publicidad|contenido patrocinado|patrocinado)\b/i,
        /\b(?:publicidade|conte?do patrocinado)\b/i,
        /\b(?:publicit?|contenu sponsoris?)\b/i,
        /\b(?:werbung|gesponsert)\b/i,
        /\b(?:pubblicit?|contenuto sponsorizzato)\b/i,
        /\b(?:register|sign up|subscribe|join now)\b/i,
        /\b(?:reg[i?]strate|suscr[i?]bete|inicia sesi[o?]n)\b/i,
        /\b(?:cadastre-se|inscreva-se)\b/i,
        /\b(?:inscrivez-vous|abonnez-vous)\b/i,
        /\b(?:bet365|sportsbook|bookmaker|betting odds|casino bonus)\b/i,
        /\b(?:apuestas?|cuotas?|juego seguro|bono de apuesta)\b/i,
        /\b(?:apostas?|cota??es|b?nus de aposta)\b/i,
        /\b(?:paris sportifs|cotes|bonus de pari)\b/i,
        /\b(?:scommesse|quote|bonus scommessa)\b/i,
        /\b(?:sportwetten|quoten|wettbonus)\b/i
      ];
      BOILERPLATE_PATTERNS = [
        /\b(?:follow us|share this|read more|recommended for you)\b/i,
        /\b(?:s[i?]guenos|compartir|leer tambi[e?]n|te puede interesar)\b/i,
        /\b(?:siga-nos|compartilhar|leia tamb[e?]m)\b/i,
        /\b(?:suivez-nous|partager|lire aussi)\b/i,
        /\b(?:folgen sie uns|teilen|auch lesen)\b/i,
        /\b(?:seguici|condividi|leggi anche)\b/i
      ];
    }
  });

  // src/content/api.js
  function createRandomClientId() {
    if (typeof crypto?.randomUUID === "function") {
      return crypto.randomUUID();
    }
    if (typeof crypto?.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      crypto.getRandomValues(bytes);
      bytes[6] = bytes[6] & 15 | 64;
      bytes[8] = bytes[8] & 63 | 128;
      const hex = Array.from(
        bytes,
        (value) => value.toString(16).padStart(2, "0")
      );
      return [
        hex.slice(0, 4).join(""),
        hex.slice(4, 6).join(""),
        hex.slice(6, 8).join(""),
        hex.slice(8, 10).join(""),
        hex.slice(10, 16).join("")
      ].join("-");
    }
    throw new SportabaseApiError(
      "Sportabase could not create a private installation identity."
    );
  }
  async function loadClientIdentity() {
    const generatedId = createRandomClientId();
    try {
      const stored = await chrome.storage.local.get(
        CLIENT_ID_STORAGE_KEY
      );
      const existing = String(
        stored?.[CLIENT_ID_STORAGE_KEY] || ""
      ).trim();
      if (existing) {
        return {
          id: existing,
          persisted: true
        };
      }
      await chrome.storage.local.set({
        [CLIENT_ID_STORAGE_KEY]: generatedId
      });
      return {
        id: generatedId,
        persisted: true
      };
    } catch (error) {
      console.warn(
        "[sportabase] Persistent client identity unavailable:",
        error
      );
      return {
        id: generatedId,
        persisted: false
      };
    }
  }
  async function getSportabaseClientId({
    requirePersistent = false
  } = {}) {
    if (!clientIdentityPromise) {
      clientIdentityPromise = loadClientIdentity().catch(
        (error) => {
          clientIdentityPromise = null;
          throw error;
        }
      );
    }
    const identity = await clientIdentityPromise;
    if (requirePersistent && !identity.persisted) {
      throw new SportabaseApiError(
        "Watchlists and alerts require Chrome extension storage. Persistent storage is unavailable in this browser session."
      );
    }
    return identity.id;
  }
  async function postJson(url, payload, {
    timeoutMs = 12e4,
    signal = null
  } = {}) {
    const controller = new AbortController();
    const callerSignal = signal && typeof signal.addEventListener === "function" ? signal : null;
    let timedOut = false;
    const abortFromCaller = () => {
      controller.abort(
        callerSignal?.reason
      );
    };
    if (callerSignal?.aborted) {
      abortFromCaller();
    } else {
      callerSignal?.addEventListener(
        "abort",
        abortFromCaller,
        {
          once: true
        }
      );
    }
    const timeoutId = window.setTimeout(
      () => {
        timedOut = true;
        controller.abort();
      },
      timeoutMs
    );
    try {
      const clientId = await getSportabaseClientId();
      if (controller.signal.aborted) {
        const abortError = new Error("Request aborted.");
        abortError.name = "AbortError";
        throw abortError;
      }
      const response = await mediatedFetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Sportabase-Client-ID": clientId
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
        if (timedOut) {
          throw new SportabaseApiError(
            "The analysis took too long and was stopped. Try again once.",
            {
              status: 408
            }
          );
        }
        throw new SportabaseApiError(
          "The analysis was cancelled.",
          {
            status: 499,
            details: "cancelled",
            cancelled: true
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
      callerSignal?.removeEventListener(
        "abort",
        abortFromCaller
      );
    }
  }
  async function mediatedFetch(url, options = {}) {
    const parsed = new URL(url);
    const requestId = crypto.randomUUID();
    const signal = options.signal;
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    return new Promise((resolve, reject) => {
      const abort = () => {
        void chrome.runtime.sendMessage({ type: "SPORTABASE_API_CANCEL", requestId }).catch(() => {
        });
        reject(new DOMException("Cancelled", "AbortError"));
      };
      signal?.addEventListener("abort", abort, { once: true });
      chrome.runtime.sendMessage({ type: "SPORTABASE_API_REQUEST", requestId, path: parsed.pathname + parsed.search, method: options.method || "GET", ...options.body ? { body: JSON.parse(options.body) } : {} }).then((result) => {
        if (!result?.ok) throw new SportabaseApiError(result?.error || "Sign in to Sportabase to continue.", { status: 401 });
        resolve(new Response(result.status === 204 ? null : result.body, { status: result.status }));
      }).catch(reject).finally(() => signal?.removeEventListener("abort", abort));
    });
  }
  var SportabaseApiError, CLIENT_ID_STORAGE_KEY, clientIdentityPromise;
  var init_api = __esm({
    "src/content/api.js"() {
      SportabaseApiError = class extends Error {
        constructor(message, {
          status = 0,
          details = "",
          cancelled = false
        } = {}) {
          super(message);
          this.name = "SportabaseApiError";
          this.status = status;
          this.details = details;
          this.cancelled = Boolean(cancelled);
        }
      };
      CLIENT_ID_STORAGE_KEY = "sportabaseClientId";
      clientIdentityPromise = null;
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
    progress = 12,
    neutral = false,
    sourceTitle = "",
    sourceDomain = "",
    languageCode = ""
  } = {}) {
    if (!container) {
      return {
        update() {
        },
        destroy() {
        }
      };
    }
    const neutralMode = Boolean(neutral);
    const safeTitle = String(
      sourceTitle || message || ""
    ).trim();
    const safeDomain = String(
      sourceDomain || modeLabel || ""
    ).trim();
    const safeLanguageCode = String(
      languageCode || "SB"
    ).trim().slice(0, 5).toUpperCase();
    const visibleModeLabel = neutralMode && safeDomain ? safeDomain : modeLabel;
    const visibleMessage = neutralMode && safeTitle ? safeTitle : message;
    const liveLabel = neutralMode ? safeLanguageCode : "LIVE";
    const analyzingLabel = neutralMode ? safeDomain : "ANALYZING";
    const firstStageCount = neutralMode ? `${Math.round(progress)}%` : "Stage 1 of 3";
    const stageLabels = neutralMode ? ["1", "2", "3"] : [
      "Read",
      "Evaluate",
      "Distill"
    ];
    const progressAriaLabel = neutralMode && safeTitle ? safeTitle : "Sportabase analysis progress";
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
            <div
              class="
                sb-loader-orbit
                sb-loader-orbit-outer
              "
            ></div>

            <div
              class="
                sb-loader-orbit
                sb-loader-orbit-inner
              "
            ></div>

            <div
              class="sb-loader-scan-wave"
            ></div>

            <span
              class="
                sb-loader-signal
                sb-loader-signal-a
              "
            ></span>

            <span
              class="
                sb-loader-signal
                sb-loader-signal-b
              "
            ></span>

            ${getSportabaseLogoMarkup({
      className: "sb-loader-logo"
    })}
          </div>

          <div class="sb-loader-brand-copy">
            <div class="sb-loader-title">
              Sportabase
            </div>

            <div class="sb-loader-mode">
              ${escapeHtml(
      visibleModeLabel
    )}
            </div>
          </div>

          <div class="sb-loader-live-pill">
            <span></span>

            ${escapeHtml(
      liveLabel
    )}
          </div>
        </div>

        <div class="sb-loader-message-area">
          <div
            class="sb-loader-message"
            data-sb-loader-message
          >
            ${escapeHtml(
      visibleMessage
    )}
          </div>

          <div class="sb-loader-progress-row">
            <div class="sb-loader-analyzing">
              <span></span>

              ${escapeHtml(
      analyzingLabel
    )}
            </div>

            <div
              class="sb-loader-stage-count"
              data-sb-loader-stage-count
            >
              ${escapeHtml(
      firstStageCount
    )}
            </div>
          </div>

          <div
            class="sb-loader-track"
            role="progressbar"
            aria-label="${escapeHtml(
      progressAriaLabel
    )}"
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
            ${stageLabels.map(
      (stageLabel, index) => `
                  <div
                    class="sb-loader-stage"
                    data-sb-loader-stage="${index}"
                  >
                    <span></span>

                    ${escapeHtml(
        stageLabel
      )}
                  </div>
                `
    ).join("")}
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
      const safeProgress = Number.isFinite(
        numericProgress
      ) ? Math.max(
        5,
        Math.min(
          95,
          Math.round(
            numericProgress
          )
        )
      ) : 12;
      if (!neutralMode && nextMessage !== void 0 && messageElement) {
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
      const activeStage = getStageIndex(
        safeProgress
      );
      if (stageCountElement) {
        stageCountElement.textContent = neutralMode ? `${safeProgress}%` : `Stage ${activeStage + 1} of 3`;
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
      init_logo();
    }
  });

  // src/content/request-lifecycle.js
  function createRequestLifecycle() {
    let activeController = null;
    let sequence = 0;
    function cancel(reason = "cancelled") {
      sequence += 1;
      const controller = activeController;
      activeController = null;
      if (controller && !controller.signal.aborted) {
        controller.abort(reason);
      }
    }
    function begin() {
      cancel("superseded");
      const controller = new AbortController();
      const requestSequence = sequence;
      activeController = controller;
      return {
        controller,
        signal: controller.signal,
        isCurrent() {
          return activeController === controller && sequence === requestSequence && !controller.signal.aborted;
        },
        finish() {
          if (activeController === controller) {
            activeController = null;
          }
        }
      };
    }
    function hasActive() {
      return Boolean(
        activeController && !activeController.signal.aborted
      );
    }
    return {
      begin,
      cancel,
      hasActive
    };
  }
  var init_request_lifecycle = __esm({
    "src/content/request-lifecycle.js"() {
    }
  });

  // src/content/article-intelligence.mjs
  function clean(value) {
    return String(
      value ?? ""
    ).trim().replace(/\s+/g, " ");
  }
  function count(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return 0;
    }
    return Math.max(
      0,
      Math.trunc(numeric)
    );
  }
  function humanize(value) {
    const normalized = clean(
      value
    ).replaceAll("_", " ").replaceAll("-", " ");
    if (!normalized) {
      return "Unknown";
    }
    return normalized.replace(
      /\b\w/g,
      (character) => character.toUpperCase()
    );
  }
  function normalizeArticleIntelligence(value) {
    if (!value || typeof value !== "object") {
      return null;
    }
    const version = clean(
      value.version
    );
    if (version !== ARTICLE_INTELLIGENCE_PUBLIC_VERSION) {
      return null;
    }
    const status = clean(
      value.status
    ).toLowerCase();
    if (status !== "available" && status !== "unavailable") {
      return null;
    }
    const independenceStatus = clean(
      value.independence_status
    ).toLowerCase() || "unknown";
    const corroborationStatus = clean(
      value.corroboration_status
    ).toLowerCase() || "unknown";
    return {
      status,
      label: clean(
        value.label
      ) || (status === "available" ? "Evidence intelligence" : "Evidence check unavailable"),
      detail: clean(
        value.detail
      ),
      signal: clean(
        value.signal
      ).toLowerCase(),
      candidateCount: count(
        value.candidate_count
      ),
      verificationPairs: count(
        value.verification_pairs
      ),
      independenceStatus,
      independenceLabel: humanize(
        independenceStatus
      ),
      corroborationStatus,
      corroborationLabel: humanize(
        corroborationStatus
      ),
      contested: Boolean(
        value.contested
      ),
      provisional: value.provisional !== false,
      affectsMeritScore: value.affects_merit_score === true
    };
  }
  var ARTICLE_INTELLIGENCE_PUBLIC_VERSION;
  var init_article_intelligence = __esm({
    "src/content/article-intelligence.mjs"() {
      ARTICLE_INTELLIGENCE_PUBLIC_VERSION = "article-intelligence-public-v1";
    }
  });

  // src/ui/accent-theme.js
  function getScorePalette(score) {
    const normalizedScore = Math.max(
      0,
      Math.min(100, Number(score) || 0)
    );
    if (normalizedScore < 35) {
      return {
        accent: "#dc2626",
        bright: "#fb7185"
      };
    }
    if (normalizedScore < 50) {
      return {
        accent: "#ea580c",
        bright: "#facc15"
      };
    }
    if (normalizedScore < 65) {
      return {
        accent: "#2563eb",
        bright: "#22d3ee"
      };
    }
    if (normalizedScore < 80) {
      return {
        accent: "#6d28d9",
        bright: "#d946ef"
      };
    }
    if (normalizedScore < 90) {
      return {
        accent: "#0f766e",
        bright: "#22d3ee"
      };
    }
    return {
      accent: "#16a34a",
      bright: "#bef264"
    };
  }
  function createAccentTheme(overlay) {
    const baseAccent = SPORTABASE_BRAND_PALETTE.accent;
    const baseAccentBright = SPORTABASE_BRAND_PALETTE.bright;
    function apply(palette = {}) {
      const accent = palette.accent || baseAccent;
      const bright = palette.bright || accent;
      overlay.style.setProperty(
        "--sb-accent",
        accent
      );
      overlay.style.setProperty(
        "--sb-accent-bright",
        bright
      );
      overlay.style.setProperty(
        "--sb-score-color",
        accent
      );
      overlay.style.setProperty(
        "--sb-score-color-bright",
        bright
      );
      overlay.style.setProperty(
        "--sb-analysis-accent",
        accent
      );
      overlay.style.setProperty(
        "--sb-analysis-accent-bright",
        bright
      );
      overlay.classList.add(
        "sb-has-analysis-accent"
      );
    }
    function clear() {
      overlay.style.setProperty(
        "--sb-accent",
        baseAccent
      );
      overlay.style.setProperty(
        "--sb-accent-bright",
        baseAccentBright
      );
      overlay.style.removeProperty(
        "--sb-score-color"
      );
      overlay.style.removeProperty(
        "--sb-score-color-bright"
      );
      overlay.style.removeProperty(
        "--sb-analysis-accent"
      );
      overlay.style.removeProperty(
        "--sb-analysis-accent-bright"
      );
      overlay.classList.remove(
        "sb-has-analysis-accent"
      );
    }
    return {
      apply,
      clear
    };
  }
  var SPORTABASE_BRAND_PALETTE;
  var init_accent_theme = __esm({
    "src/ui/accent-theme.js"() {
      SPORTABASE_BRAND_PALETTE = Object.freeze({
        accent: "#06b6d4",
        bright: "#9cff38"
      });
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
      data.localized_reasons,
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
    const localizedLabel = String(
      data.localized_article_type || data.article_type_label || ""
    ).trim();
    if (localizedLabel) {
      return localizedLabel;
    }
    return humanizeLabel(
      data.article_type || data.content_type || data.category || data.story_type || "Article analysis"
    );
  }
  function getArticleUiLabels(data) {
    const labels = {
      ...DEFAULT_ARTICLE_UI_LABELS
    };
    const responseLabels = data?.ui_labels;
    if (!responseLabels || typeof responseLabels !== "object") {
      return labels;
    }
    for (const key of Object.keys(labels)) {
      const localizedValue = String(
        responseLabels[key] || ""
      ).trim();
      if (localizedValue) {
        labels[key] = localizedValue;
      }
    }
    return labels;
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
  function getPageLanguageCode(article) {
    const candidates = [
      document.documentElement?.lang,
      document.querySelector(
        'meta[property="og:locale"]'
      )?.getAttribute(
        "content"
      ),
      document.querySelector(
        'meta[name="language"]'
      )?.getAttribute(
        "content"
      ),
      document.querySelector(
        'meta[http-equiv="content-language"]'
      )?.getAttribute(
        "content"
      )
    ];
    for (const candidate of candidates) {
      const normalized = String(
        candidate || ""
      ).trim().toLowerCase().replaceAll(
        "_",
        "-"
      );
      const languageCode = normalized.split("-")[0];
      if (/^[a-z]{2,3}$/.test(
        languageCode
      )) {
        return languageCode.toUpperCase();
      }
    }
    const sample = String(
      article?.text || ""
    ).slice(
      0,
      4e3
    );
    const scriptLanguages = [
      [
        /[\u0900-\u097f]/,
        "HI"
      ],
      [
        /[\u0980-\u09ff]/,
        "BN"
      ],
      [
        /[\u3040-\u30ff]/,
        "JA"
      ],
      [
        /[\uac00-\ud7af]/,
        "KO"
      ],
      [
        /[\u4e00-\u9fff]/,
        "ZH"
      ],
      [
        /[\u0600-\u06ff]/,
        "AR"
      ],
      [
        /[\u0400-\u04ff]/,
        "RU"
      ],
      [
        /[\u0370-\u03ff]/,
        "EL"
      ],
      [
        /[\u0590-\u05ff]/,
        "HE"
      ],
      [
        /[\u0e00-\u0e7f]/,
        "TH"
      ]
    ];
    for (const [
      pattern,
      languageCode
    ] of scriptLanguages) {
      if (pattern.test(sample)) {
        return languageCode;
      }
    }
    return "SB";
  }
  function openArticleMode({
    shell,
    config = {}
  } = {}) {
    if (!shell?.content) return;
    let analysisRunning = false;
    let loadingTicker = null;
    const analysisRequests = createRequestLifecycle();
    const accentTheme = createAccentTheme(shell.overlay);
    function stopLoadingTicker() {
      if (!loadingTicker) return;
      window.clearInterval(
        loadingTicker
      );
      loadingTicker = null;
    }
    function cancelActiveAnalysis() {
      stopLoadingTicker();
      analysisRequests.cancel(
        "article mode closed"
      );
      analysisRunning = false;
    }
    shell.onClose?.(
      cancelActiveAnalysis
    );
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
      accentTheme.clear();
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

          <p class="sb-data-disclosure">
            By analyzing, the page URL, title, and readable
            article text are sent to Sportabase and Google
            Gemini for analysis.
            <a
              href="https://yuvi-gpt.github.io/Sportabase/privacy.html"
              target="_blank"
              rel="noopener noreferrer"
            >
              Privacy policy
            </a>
          </p>

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
      accentTheme.clear();
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
      const scorePalette = getScorePalette(meritScore);
      const articleType = getArticleType(data);
      const uiLabels = getArticleUiLabels(data);
      const summaryItems = getSummaryItems(data);
      const tags = getTags(data);
      const reasonItems = getReasonItems(data);
      const intelligence = normalizeArticleIntelligence(
        data.intelligence
      );
      const intelligenceMarkup = intelligence ? `
          <section
            class="sb-article-intelligence-card ${intelligence.status === "available" ? "is-available" : "is-unavailable"}"
          >
            <div class="sb-article-intelligence-head">
              <div>
                <div class="sb-article-section-label">
                  EVIDENCE INTELLIGENCE
                </div>

                <h3>
                  ${escapeHtml2(
        intelligence.label
      )}
                </h3>
              </div>

              <div
                class="sb-article-intelligence-status"
              >
                ${intelligence.status === "available" ? "ASSESSED" : "LIMITED"}
              </div>
            </div>

            ${intelligence.detail ? `
                  <p
                    class="sb-article-intelligence-detail"
                  >
                    ${escapeHtml2(
        intelligence.detail
      )}
                  </p>
                ` : ""}

            ${intelligence.status === "available" ? `
                  <div
                    class="sb-article-intelligence-grid"
                  >
                    <div>
                      <span>
                        CORROBORATION
                      </span>

                      <strong>
                        ${escapeHtml2(
        intelligence.corroborationLabel
      )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        INDEPENDENCE
                      </span>

                      <strong>
                        ${escapeHtml2(
        intelligence.independenceLabel
      )}
                      </strong>
                    </div>

                    <div>
                      <span>
                        SOURCES FOUND
                      </span>

                      <strong>
                        ${intelligence.candidateCount}
                      </strong>
                    </div>

                    <div>
                      <span>
                        PAIRS CHECKED
                      </span>

                      <strong>
                        ${intelligence.verificationPairs}
                      </strong>
                    </div>
                  </div>
                ` : ""}

            <div
              class="sb-article-intelligence-note"
            >
              ${intelligence.affectsMeritScore ? "Included in the displayed Merit Score." : "Evidence signal is informational while Sportabase validation remains active; it does not alter the displayed Merit Score."}
            </div>
          </section>
        ` : "";
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
      accentTheme.apply(scorePalette);
      shell.setModeLabel(
        `${uiLabels.article_intelligence} ? ${articleType}`
      );
      shell.content.innerHTML = `
      <div class="sb-article-results">
        <section class="sb-article-score-card">
          <div class="sb-article-score-top">
            <div>
              <div class="sb-article-result-eyebrow">
                ${escapeHtml2(
        uiLabels.merit_score
      )}
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
            ${escapeHtml2(
        uiLabels.characters_analyzed
      )} &middot;
            ${article.paragraphCount}
            ${escapeHtml2(
        uiLabels.content_blocks
      )}
          </div>
        </section>

        <section class="sb-article-summary-card">
          <div class="sb-article-section-label">
            ${escapeHtml2(
        uiLabels.summary
      )}
          </div>

          <ul>
            ${summaryMarkup}
          </ul>
        </section>

        <section class="sb-article-reason-card">
          <div class="sb-article-section-label">
            ${escapeHtml2(
        uiLabels.why_scored
      )}
          </div>

          <ul>
            ${reasonMarkup}
          </ul>
        </section>

        ${intelligenceMarkup}

        ${tagsMarkup}

        <section class="sb-article-source-card">
          <div class="sb-article-section-label">
            ${escapeHtml2(
        uiLabels.analyzed_story
      )}
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
            ${escapeHtml2(
        uiLabels.article_overview
      )}
          </button>

          <button
            class="sb-primary-button"
            type="button"
            data-sb-article-reanalyze
          >
            ${getAnalyzeButtonMarkup(
        uiLabels.analyze_again
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
      accentTheme.clear();
      const article = getCurrentArticle();
      if (article.characterCount < 300) {
        renderError(
          new SportabaseApiError(
            "Sportabase could not find enough readable article text on this page."
          )
        );
        return;
      }
      const pageLanguageCode = getPageLanguageCode(
        article
      );
      const sourceDomain = article.hostname || window.location.hostname || "Sportabase";
      shell.setModeLabel(
        `${sourceDomain} \xB7 ${pageLanguageCode}`
      );
      const loader = createAnalysisLoader({
        container: shell.content,
        modeLabel: sourceDomain,
        message: article.title,
        progress: 18,
        neutral: true,
        sourceTitle: article.title,
        sourceDomain,
        languageCode: pageLanguageCode
      });
      const loaderStartedAt = performance.now();
      const analysisRequest = analysisRequests.begin();
      try {
        await waitForNextPaint();
        if (!analysisRequest.isCurrent()) {
          return;
        }
        loader.update({
          message: "Article text found. Preparing the intelligence pass\u2026",
          progress: 28
        });
        await wait(320);
        if (!analysisRequest.isCurrent()) {
          return;
        }
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
        if (typeof config.captureCurrentPage === "function") {
          void config.captureCurrentPage({
            articleExtraction: article,
            signal: analysisRequest.signal
          }).catch(
            (captureError) => {
              if (!captureError?.cancelled) {
                console.warn(
                  "[sportabase] Browser capture shadow failed:",
                  captureError
                );
              }
            }
          );
        }
        const response = await postJson(
          `${apiBase}/analyze`,
          {
            title: article.title,
            url: article.url,
            text: article.text,
            max_bullets: 4
          },
          {
            timeoutMs: 12e4,
            signal: analysisRequest.signal
          }
        );
        if (!analysisRequest.isCurrent()) {
          return;
        }
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
        if (!analysisRequest.isCurrent()) {
          return;
        }
        loader.update({
          message: "Analysis complete. Opening your intelligence brief\u2026",
          progress: 95
        });
        await wait(420);
        if (!analysisRequest.isCurrent()) {
          return;
        }
        renderResults(
          validatedResponse,
          article
        );
      } catch (error) {
        if (error?.cancelled || !analysisRequest.isCurrent()) {
          return;
        }
        console.error(
          "[sportabase] Article analysis failed:",
          error
        );
        renderError(error);
      } finally {
        analysisRequest.finish();
        if (!analysisRequests.hasActive()) {
          analysisRunning = false;
        }
      }
    }
    renderLanding();
  }
  var ANALYSIS_STEPS, MINIMUM_LOADER_DURATION, DEFAULT_ARTICLE_UI_LABELS;
  var init_article_mode2 = __esm({
    "src/content/article-mode.js"() {
      init_article_extractor();
      init_api();
      init_loader2();
      init_request_lifecycle();
      init_article_intelligence();
      init_accent_theme();
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
      DEFAULT_ARTICLE_UI_LABELS = Object.freeze({
        article_intelligence: "ARTICLE INTELLIGENCE",
        merit_score: "MERIT SCORE",
        summary: "TL;DR",
        why_scored: "Why it scored this way",
        analyzed_story: "Analyzed story",
        article_overview: "Article overview",
        analyze_again: "Analyze again",
        characters_analyzed: "characters analyzed",
        content_blocks: "content blocks",
        analyzing: "ANALYZING",
        ready: "READY",
        limited: "LIMITED",
        unavailable: "UNAVAILABLE",
        retry_analysis: "Retry analysis",
        return_to_overview: "Return to article overview"
      });
    }
  });

  // src/content/youtube-transcript.js
  function normalizeTranscriptSegments(rawSegments) {
    const normalizedSegments = [];
    const seenAdjacent = [];
    let rawSegmentCount = 0;
    let emptySegmentCount = 0;
    let duplicateSegmentCount = 0;
    for (const rawSegment of rawSegments || []) {
      rawSegmentCount += 1;
      const text2 = String(
        rawSegment?.text ?? rawSegment ?? ""
      ).replace(/\u00a0/g, " ").replace(/\s+/g, " ").trim();
      if (!text2) {
        emptySegmentCount += 1;
        continue;
      }
      const duplicateKey = text2.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, " ").trim();
      const previousKey = seenAdjacent[seenAdjacent.length - 1];
      if (duplicateKey && duplicateKey === previousKey) {
        duplicateSegmentCount += 1;
        continue;
      }
      seenAdjacent.push(duplicateKey);
      normalizedSegments.push({
        text: text2,
        timestamp: String(
          rawSegment?.timestamp || ""
        ).trim()
      });
    }
    const transcript = normalizedSegments.map((segment) => segment.text).join("\n").trim();
    const characterCount = transcript.length;
    const segmentCount = normalizedSegments.length;
    const duplicateRatio = rawSegmentCount > 0 ? duplicateSegmentCount / rawSegmentCount : 0;
    const averageSegmentLength = segmentCount > 0 ? characterCount / segmentCount : 0;
    const warnings = [];
    if (segmentCount < 3) {
      warnings.push(
        "very_few_segments"
      );
    }
    if (characterCount < 120) {
      warnings.push(
        "very_short_transcript"
      );
    }
    if (duplicateRatio >= 0.25) {
      warnings.push(
        "high_duplicate_ratio"
      );
    }
    if (segmentCount >= 5 && averageSegmentLength < 8) {
      warnings.push(
        "fragmented_captions"
      );
    }
    let extractionConfidence = 1;
    extractionConfidence -= Math.min(
      0.35,
      duplicateRatio
    );
    if (segmentCount < 3) {
      extractionConfidence -= 0.35;
    } else if (segmentCount < 8) {
      extractionConfidence -= 0.12;
    }
    if (characterCount < 120) {
      extractionConfidence -= 0.3;
    } else if (characterCount < 400) {
      extractionConfidence -= 0.1;
    }
    if (averageSegmentLength > 0 && averageSegmentLength < 8) {
      extractionConfidence -= 0.15;
    }
    extractionConfidence = Math.max(
      0,
      Math.min(
        1,
        Number(
          extractionConfidence.toFixed(2)
        )
      )
    );
    return {
      transcript,
      segments: normalizedSegments,
      rawSegmentCount,
      segmentCount,
      characterCount,
      emptySegmentCount,
      duplicateSegmentCount,
      duplicateRatio: Number(
        duplicateRatio.toFixed(3)
      ),
      averageSegmentLength: Number(
        averageSegmentLength.toFixed(1)
      ),
      extractionConfidence,
      warnings
    };
  }
  function getTranscriptTimestamp(element) {
    const container = element.closest(
      [
        "transcript-segment-view-model",
        "ytd-transcript-segment-renderer"
      ].join(", ")
    );
    return container?.querySelector(
      [
        ".segment-timestamp",
        "[class*='timestamp']",
        "[aria-label*='minute' i]",
        "[aria-label*='second' i]"
      ].join(", ")
    )?.textContent?.replace(/\s+/g, " ").trim() || "";
  }
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
    const rawSegments = transcriptElements.map(
      (element) => {
        return {
          text: element.textContent || "",
          timestamp: getTranscriptTimestamp(element)
        };
      }
    );
    const normalized = normalizeTranscriptSegments(
      rawSegments
    );
    if (!normalized.transcript) {
      throw new Error(
        "The transcript panel opened, but no transcript text was found."
      );
    }
    return {
      transcript: normalized.transcript,
      segmentCount: normalized.segmentCount,
      characterCount: normalized.characterCount,
      extractionConfidence: normalized.extractionConfidence,
      extractionWarnings: normalized.warnings,
      duplicateSegmentCount: normalized.duplicateSegmentCount,
      duplicateRatio: normalized.duplicateRatio,
      averageSegmentLength: normalized.averageSegmentLength,
      timestampsAvailable: normalized.segments.some(
        (segment) => Boolean(segment.timestamp)
      )
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
    const analysisRequests = createRequestLifecycle();
    shell.setModeLabel(
      "VIDEO INTELLIGENCE \xB7 YOUTUBE"
    );
    const accentTheme = createAccentTheme(shell.overlay);
    function stopLoadingTicker() {
      if (!loadingTicker) return;
      window.clearInterval(
        loadingTicker
      );
      loadingTicker = null;
    }
    function cancelActiveAnalysis() {
      stopLoadingTicker();
      analysisRequests.cancel(
        "video mode closed"
      );
      analysisRunning = false;
    }
    shell.onClose?.(
      cancelActiveAnalysis
    );
    function renderLanding() {
      stopLoadingTicker();
      analysisRunning = false;
      accentTheme.clear();
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
      accentTheme.clear();
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
      const uiLabels = data.ui_labels && typeof data.ui_labels === "object" ? data.ui_labels : {};
      const verdictLabel = String(
        data.localized_verdict || ""
      ).trim() || humanizeLabel2(
        data.verdict || "Assessment complete"
      );
      const contentTypeLabel = String(
        data.localized_content_type || ""
      ).trim() || humanizeLabel2(
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
      accentTheme.clear();
      shell.setModeLabel(
        `VIDEO INTELLIGENCE \xB7 ${contentTypeLabel.toUpperCase()}`
      );
      shell.content.innerHTML = `
      <div class="sb-video-results">
        <section class="sb-result-score-card">
          <div class="sb-result-score-top">
            <div>
              <div class="sb-result-eyebrow">
                VERDICT
              </div>

              <div class="sb-result-verdict">
                ${escapeHtml3(verdictLabel)}
              </div>
            </div>
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
            ${escapeHtml3(
        uiLabels.main_claim || "Main claim"
      )}
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
            ${escapeHtml3(
        uiLabels.evidence_used || "Evidence used"
      )}
          </div>

          <ul>
            ${evidenceItems}
          </ul>
        </section>

        <section class="sb-result-detail-card">
          <div class="sb-result-section-label">
            ${escapeHtml3(
        uiLabels.logic_check || "Logic check"
      )}
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
            ${escapeHtml3(
        uiLabels.hype_check || "Hype check"
      )}
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

            <span>${escapeHtml3(uiLabels.analyze_again || "Analyze again")}</span>
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
      const analysisRequest = analysisRequests.begin();
      try {
        const transcriptResult = await extractYouTubeTranscript();
        if (!analysisRequest.isCurrent()) {
          return;
        }
        loader.update({
          message: "Transcript found. Preparing the video analysis\u2026",
          progress: 38
        });
        await wait3(320);
        if (!analysisRequest.isCurrent()) {
          return;
        }
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
        if (typeof config.captureCurrentPage === "function") {
          void config.captureCurrentPage({
            youtubeTranscript: transcriptResult,
            signal: analysisRequest.signal
          }).catch(
            (captureError) => {
              if (!captureError?.cancelled) {
                console.warn(
                  "[sportabase] Browser capture shadow failed:",
                  captureError
                );
              }
            }
          );
        }
        const response = await postJson(
          `${apiBase}/analyze/video`,
          {
            title: videoTitle,
            transcript: transcriptResult.transcript,
            url: window.location.href,
            transcript_metadata: {
              extraction_confidence: transcriptResult.extractionConfidence,
              extraction_warnings: transcriptResult.extractionWarnings,
              segment_count: transcriptResult.segmentCount,
              character_count: transcriptResult.characterCount,
              duplicate_segment_count: transcriptResult.duplicateSegmentCount,
              duplicate_ratio: transcriptResult.duplicateRatio,
              average_segment_length: transcriptResult.averageSegmentLength,
              timestamps_available: transcriptResult.timestampsAvailable
            }
          },
          {
            timeoutMs: 12e4,
            signal: analysisRequest.signal
          }
        );
        if (!analysisRequest.isCurrent()) {
          return;
        }
        stopLoadingTicker();
        loader.update({
          message: "Finalizing your Sportabase video readout\u2026",
          progress: 95
        });
        const validatedResponse = validateVideoResponse(response);
        await wait3(380);
        if (!analysisRequest.isCurrent()) {
          return;
        }
        renderResults(
          validatedResponse,
          transcriptResult
        );
      } catch (error) {
        if (error?.cancelled || !analysisRequest.isCurrent()) {
          return;
        }
        console.error(
          "[sportabase] Video analysis failed:",
          error
        );
        renderError(error);
      } finally {
        analysisRequest.finish();
        if (!analysisRequests.hasActive()) {
          analysisRunning = false;
        }
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
      init_request_lifecycle();
      init_accent_theme();
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

  // src/content/platform-acquisition.mjs
  function cleanText(value) {
    return String(
      value ?? ""
    ).replace(/\u00a0/g, " ").replace(/[ \t]+/g, " ").replace(/\n[ \t]+/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  }
  function truncateText(value, limit) {
    const text2 = cleanText(value);
    const safeLimit = Math.max(
      500,
      Number(limit) || 12e3
    );
    if (text2.length <= safeLimit) {
      return text2;
    }
    return text2.slice(
      0,
      safeLimit
    ).trim();
  }
  function hostMatches(hostname, expected) {
    return hostname === expected || hostname.endsWith(
      `.${expected}`
    );
  }
  function parseHttpUrl(value, base = void 0) {
    try {
      const parsed = new URL(
        String(
          value || ""
        ),
        base
      );
      if (![
        "http:",
        "https:"
      ].includes(
        parsed.protocol
      )) {
        return null;
      }
      return parsed;
    } catch (_) {
      return null;
    }
  }
  function absoluteUrl(value, baseUrl) {
    const parsed = parseHttpUrl(
      value,
      baseUrl
    );
    return parsed ? parsed.href : "";
  }
  function queryFirst(root, selectors) {
    if (!root || typeof root.querySelector !== "function") {
      return null;
    }
    for (const selector of selectors) {
      try {
        const node = root.querySelector(
          selector
        );
        if (node) {
          return node;
        }
      } catch (_) {
      }
    }
    return null;
  }
  function queryAll(root, selectors) {
    if (!root || typeof root.querySelectorAll !== "function") {
      return [];
    }
    const nodes = [];
    const seen = /* @__PURE__ */ new Set();
    for (const selector of selectors) {
      try {
        const selected = Array.from(
          root.querySelectorAll(
            selector
          ) || []
        );
        for (const node of selected) {
          if (!node || seen.has(node)) {
            continue;
          }
          seen.add(node);
          nodes.push({
            node,
            selector
          });
        }
      } catch (_) {
      }
    }
    return nodes;
  }
  function nodeText(node) {
    return cleanText(
      node?.innerText || node?.textContent || ""
    );
  }
  function firstText(root, selectors) {
    for (const selector of selectors) {
      const node = queryFirst(
        root,
        [
          selector
        ]
      );
      const text2 = nodeText(node);
      if (text2) {
        return text2;
      }
    }
    return "";
  }
  function firstAttr(root, selectors, attribute) {
    for (const selector of selectors) {
      const node = queryFirst(
        root,
        [
          selector
        ]
      );
      const value = cleanText(
        node?.getAttribute?.(attribute) || ""
      );
      if (value) {
        return value;
      }
    }
    return "";
  }
  function firstMeta(documentRef, selectors) {
    return firstAttr(
      documentRef,
      selectors,
      "content"
    );
  }
  function canonicalUrl(documentRef, sourceUrl) {
    const raw = firstAttr(
      documentRef,
      [
        "link[rel='canonical']",
        'link[rel="canonical"]'
      ],
      "href"
    ) || firstMeta(
      documentRef,
      [
        "meta[property='og:url']",
        'meta[property="og:url"]'
      ]
    );
    return absoluteUrl(
      raw,
      sourceUrl
    ) || sourceUrl;
  }
  function titleFromDocument(documentRef) {
    return firstMeta(
      documentRef,
      [
        "meta[property='og:title']",
        'meta[property="og:title"]',
        "meta[name='twitter:title']",
        'meta[name="twitter:title"]'
      ]
    ) || firstText(
      documentRef,
      [
        "h1"
      ]
    ) || cleanText(
      documentRef?.title || ""
    );
  }
  function descriptionFromDocument(documentRef) {
    return firstMeta(
      documentRef,
      [
        "meta[property='og:description']",
        'meta[property="og:description"]',
        "meta[name='twitter:description']",
        'meta[name="twitter:description"]',
        "meta[name='description']",
        'meta[name="description"]'
      ]
    );
  }
  function publishedFromDocument(documentRef, scope = documentRef) {
    return firstAttr(
      scope,
      [
        "time[datetime]"
      ],
      "datetime"
    ) || firstMeta(
      documentRef,
      [
        "meta[property='article:published_time']",
        'meta[property="article:published_time"]',
        "meta[name='date']",
        'meta[name="date"]'
      ]
    );
  }
  function actorFromLink(linkValue, sourceUrl, displayName = "") {
    const profileUrl = absoluteUrl(
      linkValue,
      sourceUrl
    );
    let handle = "";
    if (profileUrl) {
      const parsed = parseHttpUrl(
        profileUrl
      );
      const parts = parsed?.pathname.split("/").filter(Boolean) || [];
      if (parts.length) {
        handle = parts[0].replace(
          /^@/,
          ""
        );
      }
    }
    return {
      platform_actor_id: "",
      handle,
      display_name: cleanText(
        displayName
      ),
      profile_url: profileUrl,
      canonical_entity_id: "",
      metadata: {}
    };
  }
  function actorFromHandle(handle, displayName = "") {
    return {
      platform_actor_id: "",
      handle: cleanText(handle).replace(
        /^@/,
        ""
      ),
      display_name: cleanText(
        displayName
      ),
      profile_url: "",
      canonical_entity_id: "",
      metadata: {}
    };
  }
  function hasActor(actor) {
    return Boolean(
      actor && (actor.platform_actor_id || actor.handle || actor.display_name || actor.profile_url)
    );
  }
  function mediaUrlForNode(node, sourceUrl) {
    const raw = node?.currentSrc || node?.src || node?.getAttribute?.("src") || node?.getAttribute?.("href") || "";
    return absoluteUrl(
      raw,
      sourceUrl
    );
  }
  function collectMedia(documentRef, scope, sourceUrl, descriptors = []) {
    const media = [];
    const seen = /* @__PURE__ */ new Set();
    const add = (kind, url, node = null, selector = "metadata") => {
      const normalizedUrl = absoluteUrl(
        url,
        sourceUrl
      );
      if (!normalizedUrl) {
        return;
      }
      const identity = `${kind}|${normalizedUrl}`;
      if (seen.has(
        identity
      )) {
        return;
      }
      seen.add(
        identity
      );
      const item = {
        component_id: `${kind}:${media.length}`,
        media_kind: kind,
        media_url: normalizedUrl,
        metadata: {
          capture_selector: selector
        }
      };
      if (kind === "video") {
        const duration = Number(
          node?.duration
        );
        if (Number.isFinite(
          duration
        ) && duration >= 0) {
          item.duration_seconds = duration;
        }
      }
      media.push(
        item
      );
    };
    for (const descriptor of descriptors) {
      for (const {
        node,
        selector
      } of queryAll(
        scope,
        descriptor.selectors || []
      )) {
        add(
          descriptor.kind,
          mediaUrlForNode(
            node,
            sourceUrl
          ),
          node,
          selector
        );
      }
    }
    const ogVideo = firstMeta(
      documentRef,
      [
        "meta[property='og:video']",
        'meta[property="og:video"]',
        "meta[property='og:video:url']",
        'meta[property="og:video:url"]'
      ]
    );
    const ogImage = firstMeta(
      documentRef,
      [
        "meta[property='og:image']",
        'meta[property="og:image"]'
      ]
    );
    if (ogVideo) {
      add(
        "video",
        ogVideo,
        null,
        "og:video"
      );
    }
    if (ogImage) {
      add(
        "image",
        ogImage,
        null,
        "og:image"
      );
    }
    return media;
  }
  function basePayload({
    platform,
    surface,
    containerKind,
    canonical,
    title,
    publishedAt,
    metadata = {}
  }) {
    const payload = {
      platform,
      surface,
      container_kind: containerKind,
      canonical_url: canonical,
      metadata: {
        browser_acquisition_version: PLATFORM_ACQUISITION_VERSION,
        adapter: platform,
        ...metadata
      }
    };
    if (title) {
      payload.title = title;
    }
    if (publishedAt) {
      payload.published_at = publishedAt;
    }
    return payload;
  }
  function surfaceForUrl(platform, sourceUrl) {
    const parsed = parseHttpUrl(
      sourceUrl
    );
    const parts = parsed?.pathname.split("/").filter(Boolean).map(
      (part) => part.toLowerCase()
    ) || [];
    if (platform === "instagram") {
      if (parts[0] === "stories") {
        return "story";
      }
      if ([
        "reel",
        "reels"
      ].includes(
        parts[0]
      )) {
        return "reel";
      }
      if (parts[0] === "tv") {
        return "video";
      }
      return "post";
    }
    if (platform === "youtube") {
      if (parts[0] === "shorts") {
        return "short";
      }
      if (parts[0] === "post") {
        return "community_post";
      }
      return "video";
    }
    if (platform === "reddit") {
      return parts.includes(
        "comments"
      ) && parts.length >= 6 ? "comment" : "post";
    }
    if (platform === "facebook") {
      if (parts[0] === "reel") {
        return "reel";
      }
      if (parts[0] === "watch") {
        return "video";
      }
      return "post";
    }
    if (platform === "tiktok") {
      return parts.includes(
        "photo"
      ) ? "photo" : "video";
    }
    if (platform === "x") {
      return "post";
    }
    return "article";
  }
  function detectBrowserPlatform(url) {
    const parsed = parseHttpUrl(
      url
    );
    if (!parsed) {
      return "web";
    }
    const hostname = parsed.hostname.toLowerCase().replace(
      /^www\./,
      ""
    );
    for (const [
      platform,
      hosts
    ] of Object.entries(
      PLATFORM_HOSTS
    )) {
      if (hosts.some(
        (host) => hostMatches(
          hostname,
          host
        )
      )) {
        return platform;
      }
    }
    return "web";
  }
  function acquireX(documentRef, sourceUrl, limit) {
    const scope = queryFirst(
      documentRef,
      [
        "article[data-testid='tweet']",
        "article"
      ]
    ) || documentRef;
    const body = truncateText(
      firstText(
        scope,
        [
          "[data-testid='tweetText']"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const actorLink = firstAttr(
      scope,
      [
        "[data-testid='User-Name'] a[href^='/']"
      ],
      "href"
    );
    const actorName = firstText(
      scope,
      [
        "[data-testid='User-Name']"
      ]
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "image",
          selectors: [
            "[data-testid='tweetPhoto'] img"
          ]
        },
        {
          kind: "video",
          selectors: [
            "video"
          ]
        }
      ]
    );
    const payload = basePayload({
      platform: "x",
      surface: "post",
      containerKind: "post",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title: titleFromDocument(
        documentRef
      ),
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (body) {
      payload.body = body;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      )
    };
  }
  function acquireInstagram(documentRef, sourceUrl, limit) {
    const scope = queryFirst(
      documentRef,
      [
        "article"
      ]
    ) || documentRef;
    const surface = surfaceForUrl(
      "instagram",
      sourceUrl
    );
    const caption = truncateText(
      firstText(
        scope,
        [
          "h1",
          "[data-testid='post-comment-root']"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const actorLink = firstAttr(
      scope,
      [
        "header a[href^='/']",
        "a[href^='/']"
      ],
      "href"
    );
    const actorName = firstText(
      scope,
      [
        "header a[href^='/']"
      ]
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        },
        {
          kind: "image",
          selectors: [
            "img[src]"
          ]
        }
      ]
    );
    const payload = basePayload({
      platform: "instagram",
      surface,
      containerKind: surface === "story" ? "story" : "post",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title: titleFromDocument(
        documentRef
      ),
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (caption) {
      payload.caption = caption;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      )
    };
  }
  function acquireTikTok(documentRef, sourceUrl, limit) {
    const scope = queryFirst(
      documentRef,
      [
        "[data-e2e='browse-video-container']",
        "main"
      ]
    ) || documentRef;
    const caption = truncateText(
      firstText(
        scope,
        [
          "[data-e2e='browse-video-desc']"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const username = firstText(
      scope,
      [
        "[data-e2e='browse-username']",
        "[data-e2e='video-author-uniqueid']"
      ]
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        },
        {
          kind: "image",
          selectors: [
            "[data-e2e='photo-mode-canvas'] img",
            "img[src]"
          ]
        }
      ]
    );
    const payload = basePayload({
      platform: "tiktok",
      surface: surfaceForUrl(
        "tiktok",
        sourceUrl
      ),
      containerKind: "post",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title: titleFromDocument(
        documentRef
      ),
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (caption) {
      payload.caption = caption;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromHandle(
        username
      )
    };
  }
  function acquireReddit(documentRef, sourceUrl, limit) {
    const scope = queryFirst(
      documentRef,
      [
        "shreddit-post",
        "article"
      ]
    ) || documentRef;
    const title = firstText(
      scope,
      [
        "[slot='title']",
        "h1"
      ]
    ) || titleFromDocument(
      documentRef
    );
    const body = truncateText(
      firstText(
        scope,
        [
          "[slot='text-body']",
          "[data-post-click-location='text-body']",
          "div[slot='text-body']"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const author = cleanText(
      scope?.getAttribute?.("author") || firstText(
        scope,
        [
          "[data-testid='post_author_link']"
        ]
      )
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        },
        {
          kind: "image",
          selectors: [
            "img[src]"
          ]
        }
      ]
    );
    const surface = surfaceForUrl(
      "reddit",
      sourceUrl
    );
    const payload = basePayload({
      platform: "reddit",
      surface,
      containerKind: surface === "comment" ? "comment" : "post",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title,
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (body) {
      payload.body = body;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromHandle(
        author
      )
    };
  }
  function acquireFacebook(documentRef, sourceUrl, limit) {
    const scope = queryFirst(
      documentRef,
      [
        "[role='article']"
      ]
    ) || documentRef;
    const body = truncateText(
      firstText(
        scope,
        [
          "[data-ad-preview='message']",
          "[data-testid='post_message']"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const actorLink = firstAttr(
      scope,
      [
        "h2 a[href]",
        "h3 a[href]"
      ],
      "href"
    );
    const actorName = firstText(
      scope,
      [
        "h2 a[href]",
        "h3 a[href]"
      ]
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        },
        {
          kind: "image",
          selectors: [
            "img[src]"
          ]
        }
      ]
    );
    const surface = surfaceForUrl(
      "facebook",
      sourceUrl
    );
    const payload = basePayload({
      platform: "facebook",
      surface,
      containerKind: "post",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title: titleFromDocument(
        documentRef
      ),
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (body) {
      payload.body = body;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      )
    };
  }
  function acquireYouTube(documentRef, sourceUrl, limit, youtubeTranscript) {
    const surface = surfaceForUrl(
      "youtube",
      sourceUrl
    );
    const isCommunity = surface === "community_post";
    const scope = isCommunity ? queryFirst(
      documentRef,
      [
        "ytd-backstage-post-thread-renderer",
        "ytd-post-renderer"
      ]
    ) || documentRef : documentRef;
    const title = isCommunity ? titleFromDocument(
      documentRef
    ) : firstText(
      documentRef,
      [
        "h1 yt-formatted-string",
        "h1"
      ]
    ) || titleFromDocument(
      documentRef
    );
    const description = truncateText(
      isCommunity ? firstText(
        scope,
        [
          "#content-text",
          "yt-formatted-string#content-text"
        ]
      ) : firstText(
        documentRef,
        [
          "#description-inline-expander yt-attributed-string",
          "#description"
        ]
      ) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const actorLink = isCommunity ? firstAttr(
      scope,
      [
        "#author-text[href]",
        "a#author-text"
      ],
      "href"
    ) : firstAttr(
      documentRef,
      [
        "#channel-name a[href]",
        "ytd-channel-name a[href]"
      ],
      "href"
    );
    const actorName = isCommunity ? firstText(
      scope,
      [
        "#author-text",
        "a#author-text"
      ]
    ) : firstText(
      documentRef,
      [
        "#channel-name",
        "ytd-channel-name"
      ]
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      isCommunity ? [
        {
          kind: "image",
          selectors: [
            "img[src]"
          ]
        }
      ] : [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        }
      ]
    );
    const payload = basePayload({
      platform: "youtube",
      surface,
      containerKind: isCommunity ? "post" : "media",
      canonical: canonicalUrl(
        documentRef,
        sourceUrl
      ),
      title,
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      )
    });
    if (description) {
      if (isCommunity) {
        payload.body = description;
      } else {
        payload.description = description;
      }
    }
    const transcript = cleanText(
      youtubeTranscript?.transcript || ""
    );
    if (transcript) {
      payload.transcript = truncateText(
        transcript,
        Math.max(
          limit,
          2e4
        )
      );
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: actorFromLink(
        actorLink,
        sourceUrl,
        actorName
      )
    };
  }
  function acquireWeb(documentRef, sourceUrl, limit, articleExtraction) {
    const article = articleExtraction && typeof articleExtraction === "object" ? articleExtraction : null;
    const scope = queryFirst(
      documentRef,
      [
        "article",
        "main",
        "[role='main']"
      ]
    ) || documentRef?.body || documentRef;
    const title = cleanText(
      article?.title || titleFromDocument(
        documentRef
      )
    );
    const body = truncateText(
      article?.text || nodeText(scope) || descriptionFromDocument(
        documentRef
      ),
      limit
    );
    const media = collectMedia(
      documentRef,
      scope,
      sourceUrl,
      [
        {
          kind: "video",
          selectors: [
            "video"
          ]
        },
        {
          kind: "image",
          selectors: [
            "article img[src]",
            "main img[src]"
          ]
        }
      ]
    );
    const articleUrl = cleanText(
      article?.url || sourceUrl
    ) || sourceUrl;
    const payload = basePayload({
      platform: "web",
      surface: "article",
      containerKind: "article",
      canonical: canonicalUrl(
        documentRef,
        articleUrl
      ),
      title,
      publishedAt: publishedFromDocument(
        documentRef,
        scope
      ),
      metadata: article ? {
        legacy_article_extractor: true,
        article_selector: cleanText(
          article.selector || ""
        ),
        article_candidate_count: Number(
          article.candidateCount || 0
        )
      } : {}
    });
    if (body) {
      payload.body = body;
    }
    if (media.length) {
      payload.media = media;
    }
    return {
      payload,
      actor: {}
    };
  }
  function acquirePageSnapshot({
    documentRef = globalThis.document,
    sourceUrl = globalThis.location?.href || "",
    observedAt = (/* @__PURE__ */ new Date()).toISOString(),
    maxTextCharacters = 12e3,
    articleExtraction = null,
    youtubeTranscript = null
  } = {}) {
    const parsed = parseHttpUrl(
      sourceUrl
    );
    if (!parsed) {
      throw new Error(
        "Browser acquisition requires an HTTP or HTTPS page URL."
      );
    }
    if (!documentRef || typeof documentRef.querySelector !== "function") {
      throw new Error(
        "Browser acquisition requires a document-like object."
      );
    }
    const timestamp = cleanText(
      observedAt
    );
    if (!timestamp) {
      throw new Error(
        "Browser acquisition requires observedAt."
      );
    }
    const platform = detectBrowserPlatform(
      sourceUrl
    );
    const adapter = {
      instagram: () => acquireInstagram(
        documentRef,
        sourceUrl,
        maxTextCharacters
      ),
      x: () => acquireX(
        documentRef,
        sourceUrl,
        maxTextCharacters
      ),
      tiktok: () => acquireTikTok(
        documentRef,
        sourceUrl,
        maxTextCharacters
      ),
      reddit: () => acquireReddit(
        documentRef,
        sourceUrl,
        maxTextCharacters
      ),
      facebook: () => acquireFacebook(
        documentRef,
        sourceUrl,
        maxTextCharacters
      ),
      youtube: () => acquireYouTube(
        documentRef,
        sourceUrl,
        maxTextCharacters,
        youtubeTranscript
      ),
      web: () => acquireWeb(
        documentRef,
        sourceUrl,
        maxTextCharacters,
        articleExtraction
      )
    }[platform];
    const {
      payload,
      actor
    } = adapter();
    const hasText = [
      "title",
      "body",
      "caption",
      "description",
      "transcript"
    ].some(
      (key) => cleanText(
        payload[key] || ""
      )
    );
    const hasMedia = Array.isArray(
      payload.media
    ) && payload.media.length > 0;
    if (!hasText && !hasMedia) {
      throw new Error(
        "No usable content was captured from the current page."
      );
    }
    let extractionMethod = "browser_dom";
    if (platform === "web" && articleExtraction) {
      extractionMethod = "browser_dom+article_extractor";
    }
    if (platform === "youtube" && cleanText(
      youtubeTranscript?.transcript || ""
    )) {
      extractionMethod = "browser_dom+youtube_transcript";
    }
    return {
      version: BROWSER_CAPTURE_VERSION,
      source_url: sourceUrl,
      observed_at: timestamp,
      extraction_method: extractionMethod,
      payload,
      actor: hasActor(actor) ? actor : {}
    };
  }
  var BROWSER_CAPTURE_VERSION, PLATFORM_ACQUISITION_VERSION, PLATFORM_HOSTS;
  var init_platform_acquisition = __esm({
    "src/content/platform-acquisition.mjs"() {
      BROWSER_CAPTURE_VERSION = "browser-capture-v1";
      PLATFORM_ACQUISITION_VERSION = "platform-acquisition-v1";
      PLATFORM_HOSTS = Object.freeze({
        instagram: [
          "instagram.com"
        ],
        x: [
          "x.com",
          "twitter.com"
        ],
        tiktok: [
          "tiktok.com"
        ],
        reddit: [
          "reddit.com",
          "redd.it"
        ],
        facebook: [
          "facebook.com",
          "fb.watch"
        ],
        youtube: [
          "youtube.com",
          "youtu.be",
          "youtube-nocookie.com"
        ]
      });
    }
  });

  // src/content/browser-capture-session.mjs
  function cleanText2(value) {
    return String(
      value ?? ""
    ).trim();
  }
  function youtubeTranscriptEligible(sourceUrl) {
    try {
      const parsed = new URL(
        String(
          sourceUrl || ""
        )
      );
      const path = parsed.pathname.toLowerCase();
      return path === "/watch" || path.startsWith(
        "/shorts/"
      );
    } catch (_) {
      return false;
    }
  }
  function transcriptMetadata(transcriptResult) {
    if (!transcriptResult || typeof transcriptResult !== "object") {
      return {};
    }
    const metadata = {};
    const confidence = Number(
      transcriptResult.extractionConfidence
    );
    if (Number.isFinite(
      confidence
    )) {
      metadata.extraction_confidence = confidence;
    }
    const segmentCount = Number(
      transcriptResult.segmentCount
    );
    if (Number.isFinite(
      segmentCount
    )) {
      metadata.segment_count = segmentCount;
    }
    const characterCount = Number(
      transcriptResult.characterCount
    );
    if (Number.isFinite(
      characterCount
    )) {
      metadata.character_count = characterCount;
    }
    if (Array.isArray(
      transcriptResult.extractionWarnings
    )) {
      metadata.extraction_warnings = transcriptResult.extractionWarnings.map(
        (value) => cleanText2(value)
      ).filter(Boolean);
    }
    return metadata;
  }
  function createBrowserCaptureSession({
    config = {},
    documentRef = globalThis.document,
    sourceUrlResolver = () => globalThis.location?.href || "",
    now = () => (/* @__PURE__ */ new Date()).toISOString(),
    acquirePageSnapshotImpl = acquirePageSnapshot,
    detectBrowserPlatformImpl = detectBrowserPlatform,
    extractArticlePageImpl = null,
    extractYouTubeTranscriptImpl = null,
    postJsonImpl = null
  } = {}) {
    return async function captureCurrentPage({
      articleExtraction = null,
      youtubeTranscript = null,
      signal = null
    } = {}) {
      const sourceUrl = cleanText2(
        sourceUrlResolver()
      );
      if (!sourceUrl) {
        throw new Error(
          "Current page URL is unavailable."
        );
      }
      const platform = detectBrowserPlatformImpl(
        sourceUrl
      );
      let articleResult = articleExtraction;
      let transcriptResult = youtubeTranscript;
      let articleExtractorStatus = articleResult ? "provided" : "not_required";
      let transcriptStatus = transcriptResult && cleanText2(
        transcriptResult.transcript
      ) ? "provided" : "not_required";
      if (platform === "web" && !articleResult) {
        try {
          const configuredLimit = Number(
            config.maxAnalyzeChars || config.maxArticleChars || config.max_analyze_chars || 12e3
          );
          articleResult = extractArticlePageImpl({
            maxCharacters: Number.isFinite(
              configuredLimit
            ) ? configuredLimit : 12e3
          });
          articleExtractorStatus = "available";
        } catch (_) {
          articleResult = null;
          articleExtractorStatus = "unavailable";
        }
      }
      if (platform === "youtube" && youtubeTranscriptEligible(
        sourceUrl
      ) && !(transcriptResult && cleanText2(
        transcriptResult.transcript
      ))) {
        try {
          transcriptResult = await extractYouTubeTranscriptImpl();
          transcriptStatus = cleanText2(
            transcriptResult?.transcript
          ) ? "available" : "unavailable";
        } catch (_) {
          transcriptResult = null;
          transcriptStatus = "unavailable";
        }
      }
      const capture = acquirePageSnapshotImpl({
        documentRef,
        sourceUrl,
        observedAt: now(),
        maxTextCharacters: Number(
          config.maxCaptureChars || config.maxAnalyzeChars || config.maxArticleChars || 12e3
        ) || 12e3,
        articleExtraction: articleResult,
        youtubeTranscript: transcriptResult
      });
      if (!capture.payload.metadata || typeof capture.payload.metadata !== "object") {
        capture.payload.metadata = {};
      }
      capture.payload.metadata["browser_capture_session_version"] = BROWSER_CAPTURE_SESSION_VERSION;
      if (platform === "web") {
        capture.payload.metadata["article_extractor_capture"] = {
          status: articleExtractorStatus
        };
      }
      if (platform === "youtube" && youtubeTranscriptEligible(
        sourceUrl
      )) {
        capture.payload.metadata["youtube_transcript_capture"] = {
          status: transcriptStatus,
          ...transcriptMetadata(
            transcriptResult
          )
        };
      }
      const apiBase = String(
        config.api || "https://sportabase-api.onrender.com"
      ).replace(
        /\/+$/,
        ""
      );
      const timeoutMs = Math.max(
        1e3,
        Number(
          config.captureTimeoutMs || 2e4
        ) || 2e4
      );
      if (typeof postJsonImpl !== "function") {
        throw new Error(
          "Browser capture transport is unavailable."
        );
      }
      const response = await postJsonImpl(
        `${apiBase}/content/browser-capture`,
        {
          capture
        },
        {
          timeoutMs,
          signal
        }
      );
      return {
        capture,
        response
      };
    };
  }
  var BROWSER_CAPTURE_SESSION_VERSION;
  var init_browser_capture_session = __esm({
    "src/content/browser-capture-session.mjs"() {
      init_platform_acquisition();
      BROWSER_CAPTURE_SESSION_VERSION = "browser-capture-session-v1";
    }
  });

  // src/content/persistent-intelligence-core.mjs
  function clean2(value) {
    return String(value ?? "").trim();
  }
  function text(value) {
    return typeof value === "string" ? value.trim() : "";
  }
  function isTrackingQueryParameter(name) {
    const normalized = clean2(name).toLowerCase();
    return normalized.startsWith("utm_") || TRACKING_QUERY_PARAMETERS.has(normalized);
  }
  function youtubeVideoId(url) {
    const hostname = clean2(
      url.hostname
    ).toLowerCase();
    const pathParts = url.pathname.split("/").filter(Boolean);
    let candidate = "";
    if (hostname === "youtu.be" || hostname === "www.youtu.be") {
      candidate = pathParts[0] || "";
    } else if (YOUTUBE_HOSTS.has(hostname)) {
      const first = clean2(pathParts[0]).toLowerCase();
      if (["embed", "live", "shorts", "v"].includes(first) && pathParts.length >= 2) {
        candidate = pathParts[1];
      } else if (!pathParts.length || first === "watch") {
        candidate = clean2(
          url.searchParams.get("v")
        );
      }
    }
    candidate = candidate.replace(
      /[^A-Za-z0-9_-]/g,
      ""
    );
    return /^[A-Za-z0-9_-]{6,20}$/.test(candidate) ? candidate : "";
  }
  function normalizeCanonicalAnalysisUrl(value) {
    let rawUrl = clean2(value);
    if (!rawUrl) {
      return "";
    }
    rawUrl = rawUrl.split("#", 1)[0].trim();
    try {
      if (/^\/\//.test(rawUrl)) {
        rawUrl = `https:${rawUrl}`;
      } else if (!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(rawUrl) && /^[A-Za-z0-9.-]+\//.test(rawUrl)) {
        rawUrl = `https://${rawUrl}`;
      }
      const parsed = new URL(rawUrl);
      const scheme = parsed.protocol.replace(/:$/, "").toLowerCase();
      const hostname = parsed.hostname.trim().toLowerCase();
      if (!scheme || !hostname) {
        return rawUrl;
      }
      const videoId = youtubeVideoId(parsed);
      if (videoId) {
        return `https://youtube.com/watch?v=${videoId}`;
      }
      let authority = hostname;
      if (parsed.port) {
        authority = `${authority}:${parsed.port}`;
      }
      let path = parsed.pathname || "/";
      path = path.replace(/\/{2,}/g, "/");
      if (path !== "/") {
        path = path.replace(/\/+$/, "");
      }
      const retained = [];
      for (const [key, queryValue] of parsed.searchParams.entries()) {
        if (isTrackingQueryParameter(key)) {
          continue;
        }
        retained.push([key, queryValue]);
      }
      retained.sort((left, right) => {
        const leftKey = left[0].toLowerCase();
        const rightKey = right[0].toLowerCase();
        if (leftKey < rightKey) return -1;
        if (leftKey > rightKey) return 1;
        if (left[1] < right[1]) return -1;
        if (left[1] > right[1]) return 1;
        return 0;
      });
      const query = new URLSearchParams();
      for (const [key, queryValue] of retained) {
        query.append(key, queryValue);
      }
      const encoded = query.toString();
      return `${scheme}://${authority}${path}${encoded ? `?${encoded}` : ""}`;
    } catch {
      return rawUrl;
    }
  }
  async function mediaItemIdForUrl(value) {
    const canonicalUrl2 = normalizeCanonicalAnalysisUrl(value);
    if (!canonicalUrl2) {
      throw new Error("Media item URL is required.");
    }
    const payload = new TextEncoder().encode(
      `media|${canonicalUrl2}`
    );
    const digest = await crypto.subtle.digest(
      "SHA-256",
      payload
    );
    return Array.from(
      new Uint8Array(digest),
      (byte) => byte.toString(16).padStart(2, "0")
    ).join("");
  }
  function isWatchableKind(value) {
    return WATCHABLE_KINDS.includes(
      clean2(value)
    );
  }
  function historyPathFor(kind, id, {
    limit = 30,
    cursor = ""
  } = {}) {
    if (!isWatchableKind(kind)) {
      throw new Error(
        "Unsupported Sportabase intelligence kind."
      );
    }
    const targetId = clean2(id);
    if (!targetId) {
      throw new Error(
        "Sportabase intelligence ID is required."
      );
    }
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (cursor) {
      params.set("cursor", cursor);
    }
    return `/intelligence/${HISTORY_PATH_SEGMENTS[kind]}/${encodeURIComponent(targetId)}/history?${params.toString()}`;
  }
  function historyIdentity(kind, response) {
    if (kind === "entity") {
      const entity = response?.entity || {};
      return {
        kind,
        id: clean2(entity.id),
        title: clean2(entity.canonical_name) || "Persisted entity",
        subtitle: [
          clean2(entity.entity_type),
          clean2(entity.sport_key)
        ].filter(Boolean).join(" \xB7 "),
        firstSeenAt: clean2(entity.first_seen_at),
        lastSeenAt: clean2(entity.last_seen_at),
        canonicalUrl: ""
      };
    }
    if (kind === "story") {
      const story = response?.story || {};
      return {
        kind,
        id: clean2(story.id),
        title: clean2(story.canonical_title) || "Persisted story",
        subtitle: clean2(story.status) || "Persisted story",
        firstSeenAt: clean2(story.first_seen_at),
        lastSeenAt: clean2(story.last_seen_at),
        canonicalUrl: ""
      };
    }
    if (kind === "claim") {
      const claim = response?.claim || {};
      return {
        kind,
        id: clean2(claim.id),
        title: clean2(claim.canonical_text) || "Persisted claim",
        subtitle: [
          clean2(claim.claim_type),
          clean2(claim.subject_key)
        ].filter(Boolean).join(" \xB7 "),
        firstSeenAt: clean2(claim.first_seen_at),
        lastSeenAt: clean2(claim.last_seen_at),
        canonicalUrl: ""
      };
    }
    const media = response?.media || {};
    return {
      kind: "media",
      id: clean2(media.id),
      title: clean2(media.title) || "Persisted media",
      subtitle: clean2(media.mode) || "Persisted media",
      firstSeenAt: clean2(media.first_seen_at),
      lastSeenAt: clean2(media.last_seen_at),
      canonicalUrl: clean2(media.canonical_url)
    };
  }
  function historyRelations(kind, response) {
    const relations = [];
    const add = (relation) => {
      if (!relation?.id || !isWatchableKind(relation.kind)) {
        return;
      }
      if (relations.some(
        (item) => item.kind === relation.kind && item.id === relation.id
      )) {
        return;
      }
      relations.push(relation);
    };
    if (kind === "media") {
      for (const event of response?.events || []) {
        const storyId = text(event?.story_id);
        if (storyId) {
          add({
            kind: "story",
            id: storyId,
            title: `Story ${storyId}`,
            subtitle: "Persisted media relationship"
          });
        }
      }
    }
    if (kind === "story") {
      for (const claim of response?.claims || []) {
        add({
          kind: "claim",
          id: clean2(claim?.id),
          title: clean2(claim?.canonical_text) || `Claim ${clean2(claim?.id)}`,
          subtitle: clean2(claim?.claim_type)
        });
      }
      for (const media of response?.media || []) {
        add({
          kind: "media",
          id: clean2(media?.id),
          title: clean2(media?.title) || `Media ${clean2(media?.id)}`,
          subtitle: clean2(media?.mode)
        });
      }
    }
    if (kind === "claim") {
      for (const story of response?.stories || []) {
        add({
          kind: "story",
          id: clean2(story?.id),
          title: clean2(story?.canonical_title) || `Story ${clean2(story?.id)}`,
          subtitle: clean2(story?.status)
        });
      }
      for (const participant of response?.verified_participants || []) {
        const entityId = clean2(
          participant?.entity_id
        );
        add({
          kind: "entity",
          id: entityId,
          title: clean2(participant?.canonical_name) || `Entity ${entityId}`,
          subtitle: clean2(participant?.entity_type)
        });
      }
    }
    if (kind === "entity") {
      for (const story of response?.stories || []) {
        add({
          kind: "story",
          id: clean2(story?.id),
          title: clean2(story?.canonical_title) || `Story ${clean2(story?.id)}`,
          subtitle: clean2(story?.status)
        });
      }
      for (const media of response?.media || []) {
        add({
          kind: "media",
          id: clean2(media?.id),
          title: clean2(media?.title) || `Media ${clean2(media?.id)}`,
          subtitle: clean2(media?.mode)
        });
      }
      for (const event of response?.events || []) {
        const claimId = text(event?.claim_id);
        if (claimId) {
          add({
            kind: "claim",
            id: claimId,
            title: text(event?.claim_text) || `Claim ${claimId}`,
            subtitle: "Verified claim participation"
          });
        }
      }
    }
    return relations;
  }
  function historyPolicyNotes(policy) {
    return Object.entries(
      policy && typeof policy === "object" ? policy : {}
    ).filter(([, enabled]) => Boolean(enabled)).map(
      ([key]) => POLICY_COPY[key] || key.replace(/_/g, " ")
    );
  }
  function historyEventDetails(event) {
    const details = [];
    for (const [field, label] of EVENT_DETAIL_FIELDS) {
      const value = event?.[field];
      if (typeof value === "string" || typeof value === "number") {
        const rendered = clean2(value);
        if (rendered) {
          details.push({ label, value: rendered });
        }
      }
    }
    if (Array.isArray(event?.reasons)) {
      const reasons = event.reasons.filter(
        (value) => typeof value === "string" && value.trim()
      ).map((value) => value.trim()).join(" \xB7 ");
      if (reasons) {
        details.push({
          label: "Reasons",
          value: reasons
        });
      }
    }
    return details;
  }
  function filterAlertsForTarget(alerts, target) {
    return (Array.isArray(alerts) ? alerts : []).filter(
      (item) => clean2(item?.target_kind) === clean2(target?.kind) && clean2(item?.target_id) === clean2(target?.id)
    );
  }
  var TRACKING_QUERY_PARAMETERS, YOUTUBE_HOSTS, WATCHABLE_KINDS, HISTORY_PATH_SEGMENTS, POLICY_COPY, EVENT_DETAIL_FIELDS;
  var init_persistent_intelligence_core = __esm({
    "src/content/persistent-intelligence-core.mjs"() {
      TRACKING_QUERY_PARAMETERS = /* @__PURE__ */ new Set([
        "dclid",
        "fbclid",
        "gclid",
        "gbraid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref_src",
        "s_cid",
        "vero_conv",
        "vero_id",
        "wbraid"
      ]);
      YOUTUBE_HOSTS = /* @__PURE__ */ new Set([
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtu.be",
        "www.youtu.be",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com"
      ]);
      WATCHABLE_KINDS = Object.freeze([
        "entity",
        "story",
        "claim",
        "media"
      ]);
      HISTORY_PATH_SEGMENTS = Object.freeze({
        entity: "entities",
        story: "stories",
        claim: "claims",
        media: "media"
      });
      POLICY_COPY = Object.freeze({
        verified_relationships_only: "Entity relationships shown here come from verified persisted relationships.",
        chronology_is_not_truth: "Chronology records when intelligence occurred; it is not a truth or credibility score.",
        relationships_are_persisted: "Story relationships shown here are persisted graph relationships, not temporary text matches.",
        evidence_quantity_is_not_probability: "More evidence records do not automatically mean a claim is more likely to be true.",
        dependencies_remain_distinct: "Repeated or dependent reporting remains distinct from independent corroboration.",
        article_merit_is_reporting_quality_not_truth: "Article Merit measures reporting and informational quality, not truth probability.",
        video_scores_are_not_combined: "Video Evidence Score, Logic Score and Verdict remain separate; there is no composite credibility score.",
        versions_are_not_assumed_comparable: "Analysis versions are not assumed to be directly comparable across time."
      });
      EVENT_DETAIL_FIELDS = Object.freeze([
        ["claim_text", "Claim"],
        ["canonical_name", "Entity"],
        ["participant_role", "Participant role"],
        ["verification_status", "Verification status"],
        ["relationship_type", "Relationship"],
        ["link_basis", "Link basis"],
        ["claim_summary", "Observation"],
        ["trigger_type", "Revision trigger"],
        ["field", "Field"],
        ["kind", "Transition"],
        ["mode", "Mode"],
        ["badge", "Article badge"],
        ["article_type", "Article type"],
        ["merit_score", "Merit \xB7 reporting quality"],
        ["evidence_score", "Video evidence score"],
        ["logic_score", "Video logic score"],
        ["verdict", "Video verdict"],
        ["analysis_version", "Analysis version"],
        ["scoring_version", "Scoring version"]
      ]);
    }
  });

  // src/content/persistent-intelligence.js
  function escapeHtml4(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function formatTime(value) {
    const text2 = String(value || "").trim();
    if (!text2) return "Not recorded";
    const parsed = new Date(text2);
    if (Number.isNaN(parsed.getTime())) {
      return text2;
    }
    return parsed.toLocaleString();
  }
  function humanize2(value) {
    return String(value || "").replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim().replace(
      /\b\w/g,
      (letter) => letter.toUpperCase()
    );
  }
  function errorMessage(error) {
    if (error instanceof SportabaseApiError) {
      return error.message;
    }
    return String(error?.message || error || "").trim() || "Sportabase could not load persistent intelligence.";
  }
  async function requestJson(apiBase, path, {
    method = "GET",
    body = void 0,
    privateRequest = false
  } = {}) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS
    );
    try {
      const headers = {
        Accept: "application/json"
      };
      if (body !== void 0) {
        headers["Content-Type"] = "application/json";
      }
      if (privateRequest) {
        headers["x-sportabase-client-id"] = await getSportabaseClientId({
          requirePersistent: true
        });
      }
      const response = await (privateRequest ? mediatedFetch : fetch)(
        `${apiBase}${path}`,
        {
          method,
          headers,
          body: body === void 0 ? void 0 : JSON.stringify(body),
          signal: controller.signal
        }
      );
      const responseText = await response.text();
      let payload = null;
      try {
        payload = responseText ? JSON.parse(responseText) : null;
      } catch {
        payload = null;
      }
      if (!response.ok) {
        const detail = String(
          payload?.detail || payload?.message || responseText || ""
        ).trim();
        throw new SportabaseApiError(
          detail || `Sportabase returned HTTP ${response.status}.`,
          {
            status: response.status,
            details: detail
          }
        );
      }
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new SportabaseApiError(
          "Persistent intelligence request timed out.",
          { status: 408 }
        );
      }
      if (error instanceof SportabaseApiError) {
        throw error;
      }
      throw new SportabaseApiError(
        "Sportabase could not reach the persistent intelligence service.",
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
  function eventMarkup(event, index) {
    const details = historyEventDetails(event);
    return `
    <article class="sb-pi-event">
      <div class="sb-pi-event-head">
        <span class="sb-pi-event-index">
          ${String(index + 1).padStart(2, "0")}
        </span>

        <div>
          <strong>
            ${escapeHtml4(
      humanize2(event?.type || "Persisted event")
    )}
          </strong>

          <small>
            ${escapeHtml4(
      formatTime(event?.occurred_at)
    )}
          </small>
        </div>
      </div>

      ${details.length ? `
            <dl class="sb-pi-event-details">
              ${details.map(
      (detail) => `
                    <div>
                      <dt>${escapeHtml4(detail.label)}</dt>
                      <dd>${escapeHtml4(detail.value)}</dd>
                    </div>
                  `
    ).join("")}
            </dl>
          ` : `
            <p class="sb-pi-event-empty">
              Persisted relationship or analysis event.
            </p>
          `}
    </article>
  `;
  }
  function relationMarkup(relation) {
    return `
    <button
      class="sb-pi-relation"
      type="button"
      data-sb-pi-open-kind="${escapeHtml4(relation.kind)}"
      data-sb-pi-open-id="${escapeHtml4(relation.id)}"
    >
      <span>
        ${escapeHtml4(relation.kind.toUpperCase())}
      </span>

      <strong>
        ${escapeHtml4(relation.title)}
      </strong>

      ${relation.subtitle ? `<small>${escapeHtml4(relation.subtitle)}</small>` : ""}
    </button>
  `;
  }
  function activityMarkup(activity) {
    if (!activity) return "";
    const alerts = activity.alerts || [];
    return `
    <section class="sb-pi-section sb-pi-activity-section">
      <div class="sb-pi-section-head">
        <div>
          <span>WATCH ACTIVITY</span>
          <h4>Recent persisted changes</h4>
        </div>

        <strong>
          ${alerts.length}
        </strong>
      </div>

      <p class="sb-pi-note">
        Reconciliation read the persisted discovery ledger only.
        It did not call Gemini or a notification provider.
      </p>

      ${alerts.length ? `
            <div class="sb-pi-alert-list">
              ${alerts.slice(0, 10).map(
      (alert) => `
                    <article class="sb-pi-alert ${alert.read_at ? "" : "is-unread"}">
                      <div>
                        <span>
                          ${escapeHtml4(
        humanize2(alert.event_type)
      )}
                        </span>
                        ${alert.read_at ? "" : "<b>UNREAD</b>"}
                      </div>

                      <p>
                        ${escapeHtml4(alert.summary)}
                      </p>

                      <small>
                        Occurred ${escapeHtml4(
        formatTime(alert.occurred_at)
      )}
                        \xB7 detected ${escapeHtml4(
        formatTime(alert.detected_at)
      )}
                      </small>
                    </article>
                  `
    ).join("")}
            </div>
          ` : `
            <div class="sb-pi-empty-inline">
              ${activity.truncated ? `No matching activity was found in the first ${activity.pagesScanned * ALERT_PAGE_LIMIT} recent inbox records.` : "No alert activity has been persisted for this watched object yet."}
            </div>
          `}

      <div class="sb-pi-reconcile-meta">
        Reconcile result \xB7 ${activity.newAlerts} new alert${activity.newAlerts === 1 ? "" : "s"} across ${activity.watchesChecked} watch${activity.watchesChecked === 1 ? "" : "es"} checked.
      </div>
    </section>
  `;
  }
  function createPanel({
    host,
    apiBase,
    sourceUrl,
    mode
  }) {
    let destroyed = false;
    let loading = false;
    let current = null;
    let watchedKeys = /* @__PURE__ */ new Set();
    let privateStateError = "";
    function targetKey(target) {
      return `${target.kind}:${target.id}`;
    }
    function isWatching(target) {
      return watchedKeys.has(
        targetKey(target)
      );
    }
    function renderLoading(label) {
      if (destroyed) return;
      host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-loading">
          <span class="sb-pi-spinner"></span>
          <div>
            <strong>${escapeHtml4(label)}</strong>
            <small>
              Reading only persisted Sportabase intelligence.
            </small>
          </div>
        </div>
      </section>
    `;
    }
    function renderMissing(message) {
      if (destroyed) return;
      host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-eyebrow">
          PERSISTENT INTELLIGENCE
        </div>

        <h3>Canonical history is not ready yet</h3>

        <p class="sb-pi-copy">
          ${escapeHtml4(message)}
        </p>

        <button
          class="sb-pi-button sb-pi-button-secondary"
          type="button"
          data-sb-pi-retry
        >
          Check persisted record again
        </button>
      </section>
    `;
      host.querySelector("[data-sb-pi-retry]")?.addEventListener("click", () => {
        void openInitialMedia();
      });
    }
    function renderError(message) {
      if (destroyed) return;
      host.innerHTML = `
      <section class="sb-pi-card is-error">
        <div class="sb-pi-eyebrow">
          PERSISTENT INTELLIGENCE
        </div>

        <h3>History temporarily unavailable</h3>

        <p class="sb-pi-copy">
          ${escapeHtml4(message)}
        </p>

        <button
          class="sb-pi-button sb-pi-button-secondary"
          type="button"
          data-sb-pi-retry
        >
          Retry
        </button>
      </section>
    `;
      host.querySelector("[data-sb-pi-retry]")?.addEventListener("click", () => {
        void openInitialMedia();
      });
    }
    function bindActions() {
      if (!current || destroyed) return;
      host.querySelectorAll("[data-sb-pi-open-kind]").forEach((button) => {
        button.addEventListener("click", () => {
          const kind = button.getAttribute(
            "data-sb-pi-open-kind"
          );
          const id = button.getAttribute(
            "data-sb-pi-open-id"
          );
          if (kind && id) {
            void openTarget(kind, id);
          }
        });
      });
      host.querySelector("[data-sb-pi-watch]")?.addEventListener("click", () => {
        void addWatch();
      });
      host.querySelector("[data-sb-pi-activity]")?.addEventListener("click", () => {
        void checkActivity();
      });
      host.querySelector("[data-sb-pi-more]")?.addEventListener("click", () => {
        void loadMoreHistory();
      });
      host.querySelector("[data-sb-pi-back-media]")?.addEventListener("click", () => {
        void openInitialMedia();
      });
      host.querySelector("[data-sb-pi-original]")?.addEventListener("click", () => {
        const url = current?.identity?.canonicalUrl;
        if (url) {
          window.open(
            url,
            "_blank",
            "noopener,noreferrer"
          );
        }
      });
    }
    function renderCurrent() {
      if (!current || destroyed) return;
      const {
        target,
        history,
        identity,
        relations,
        activity
      } = current;
      const watching = isWatching(target);
      const policyNotes = historyPolicyNotes(history.policy);
      host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-head">
          <div>
            <div class="sb-pi-eyebrow">
              PERSISTENT INTELLIGENCE
            </div>

            <h3>${escapeHtml4(identity.title)}</h3>

            <p class="sb-pi-subtitle">
              ${escapeHtml4(
        identity.subtitle || humanize2(target.kind)
      )}
            </p>
          </div>

          <span class="sb-pi-kind">
            ${escapeHtml4(target.kind.toUpperCase())}
          </span>
        </div>

        <div class="sb-pi-time-grid">
          <div>
            <span>FIRST SEEN</span>
            <strong>${escapeHtml4(
        formatTime(identity.firstSeenAt)
      )}</strong>
          </div>

          <div>
            <span>LAST SEEN</span>
            <strong>${escapeHtml4(
        formatTime(identity.lastSeenAt)
      )}</strong>
          </div>
        </div>

        <div class="sb-pi-actions">
          <button
            class="sb-pi-button ${watching ? "sb-pi-button-active" : "sb-pi-button-primary"}"
            type="button"
            data-sb-pi-watch
            ${watching ? "disabled" : ""}
          >
            ${watching ? "Watching future changes" : "Watch future changes"}
          </button>

          <button
            class="sb-pi-button sb-pi-button-secondary"
            type="button"
            data-sb-pi-activity
            ${watching ? "" : "disabled"}
          >
            Check watch activity
          </button>

          ${identity.canonicalUrl ? `
                <button
                  class="sb-pi-button sb-pi-button-secondary"
                  type="button"
                  data-sb-pi-original
                >
                  Open original \u2197
                </button>
              ` : ""}

          ${target.kind !== "media" ? `
                <button
                  class="sb-pi-button sb-pi-button-quiet"
                  type="button"
                  data-sb-pi-back-media
                >
                  Back to analyzed media
                </button>
              ` : ""}
        </div>

        ${privateStateError ? `
              <p class="sb-pi-private-warning">
                History remains public, but watch controls are unavailable: ${escapeHtml4(
        privateStateError
      )}
              </p>
            ` : ""}

        <section class="sb-pi-policy">
          <span>INTERPRETATION BOUNDARIES</span>
          ${policyNotes.length ? policyNotes.map(
        (note) => `
                      <p>
                        <i></i>
                        ${escapeHtml4(note)}
                      </p>
                    `
      ).join("") : `
                <p>
                  <i></i>
                  Persisted chronology is descriptive context, not a truth score.
                </p>
              `}
        </section>

        <section class="sb-pi-section">
          <div class="sb-pi-section-head">
            <div>
              <span>PERSISTED GRAPH</span>
              <h4>Related intelligence</h4>
            </div>
            <strong>${relations.length}</strong>
          </div>

          ${relations.length ? `
                <div class="sb-pi-relations">
                  ${relations.map(relationMarkup).join("")}
                </div>
              ` : `
                <div class="sb-pi-empty-inline">
                  No related canonical objects are exposed by this history response yet.
                </div>
              `}
        </section>

        <section class="sb-pi-section">
          <div class="sb-pi-section-head">
            <div>
              <span>DOMAIN CHRONOLOGY</span>
              <h4>Persisted history</h4>
            </div>
            <strong>${history.events?.length || 0}</strong>
          </div>

          <p class="sb-pi-note">
            Ordering reflects domain occurrence time. It does not imply truth, credibility, novelty, or independent corroboration.
          </p>

          ${history.events?.length ? `
                <div class="sb-pi-events">
                  ${history.events.map(eventMarkup).join("")}
                </div>
              ` : `
                <div class="sb-pi-empty-inline">
                  No persisted history events are exposed for this object yet.
                </div>
              `}

          ${history.pagination?.next_cursor ? `
                <button
                  class="sb-pi-button sb-pi-button-secondary sb-pi-more"
                  type="button"
                  data-sb-pi-more
                >
                  Load more history
                </button>
              ` : ""}
        </section>

        ${activityMarkup(activity)}
      </section>
    `;
      bindActions();
    }
    async function loadWatchState() {
      privateStateError = "";
      try {
        const response = await requestJson(
          apiBase,
          "/watchlists",
          { privateRequest: true }
        );
        watchedKeys = new Set(
          (response?.items || []).map(
            (item) => `${item.target_kind}:${item.target_id}`
          )
        );
      } catch (error) {
        privateStateError = errorMessage(error);
        watchedKeys = /* @__PURE__ */ new Set();
      }
    }
    async function openTarget(kind, id) {
      if (loading || destroyed) return;
      loading = true;
      renderLoading(
        `Loading ${humanize2(kind)} history\u2026`
      );
      try {
        const history = await requestJson(
          apiBase,
          historyPathFor(kind, id, {
            limit: 30
          })
        );
        if (destroyed) return;
        const target = { kind, id };
        current = {
          target,
          history,
          identity: historyIdentity(
            kind,
            history
          ),
          relations: historyRelations(
            kind,
            history
          ),
          activity: null
        };
        renderCurrent();
      } catch (error) {
        if (destroyed) return;
        if (error?.status === 404) {
          const modeCopy = mode === "video" ? "The video readout is available, but its canonical media history has not been persisted yet. Browser-capture persistence may still be processing." : "The article readout is available, but Sportabase does not currently expose a canonical media-history record for this URL.";
          renderMissing(modeCopy);
        } else {
          renderError(errorMessage(error));
        }
      } finally {
        loading = false;
      }
    }
    async function openInitialMedia() {
      if (loading || destroyed) return;
      try {
        const mediaId = await mediaItemIdForUrl(sourceUrl);
        await openTarget("media", mediaId);
      } catch (error) {
        renderError(errorMessage(error));
      }
    }
    async function addWatch() {
      if (!current || loading || isWatching(current.target)) {
        return;
      }
      loading = true;
      try {
        const response = await requestJson(
          apiBase,
          "/watchlists",
          {
            method: "POST",
            privateRequest: true,
            body: {
              target_kind: current.target.kind,
              target_id: current.target.id
            }
          }
        );
        watchedKeys.add(
          targetKey(current.target)
        );
        if (response?.created === false) {
          watchedKeys.add(
            targetKey(current.target)
          );
        }
        privateStateError = "";
        renderCurrent();
      } catch (error) {
        privateStateError = errorMessage(error);
        renderCurrent();
      } finally {
        loading = false;
      }
    }
    async function loadMoreHistory() {
      if (!current || loading || !current.history?.pagination?.next_cursor) {
        return;
      }
      loading = true;
      try {
        const next = await requestJson(
          apiBase,
          historyPathFor(
            current.target.kind,
            current.target.id,
            {
              limit: 30,
              cursor: current.history.pagination.next_cursor
            }
          )
        );
        current.history = {
          ...current.history,
          events: [
            ...current.history.events || [],
            ...next?.events || []
          ],
          pagination: next?.pagination || current.history.pagination
        };
        current.relations = historyRelations(
          current.target.kind,
          current.history
        );
        renderCurrent();
      } catch (error) {
        privateStateError = errorMessage(error);
        renderCurrent();
      } finally {
        loading = false;
      }
    }
    async function checkActivity() {
      if (!current || loading || !isWatching(current.target)) {
        return;
      }
      loading = true;
      try {
        const reconcile = await requestJson(
          apiBase,
          "/watchlists/alerts/reconcile",
          {
            method: "POST",
            privateRequest: true
          }
        );
        let cursor = "";
        let pagesScanned = 0;
        let truncated = false;
        const alerts = [];
        while (pagesScanned < MAX_ALERT_PAGES) {
          const params = new URLSearchParams();
          params.set(
            "unread_only",
            "false"
          );
          params.set(
            "limit",
            String(ALERT_PAGE_LIMIT)
          );
          if (cursor) {
            params.set("cursor", cursor);
          }
          const page = await requestJson(
            apiBase,
            `/watchlists/alerts?${params.toString()}`,
            { privateRequest: true }
          );
          alerts.push(
            ...page?.items || []
          );
          pagesScanned += 1;
          cursor = String(
            page?.pagination?.next_cursor || ""
          );
          if (!cursor) {
            break;
          }
        }
        truncated = Boolean(cursor);
        current.activity = {
          alerts: filterAlertsForTarget(
            alerts,
            current.target
          ),
          pagesScanned,
          truncated,
          newAlerts: Number(
            reconcile?.new_alerts || 0
          ),
          watchesChecked: Number(
            reconcile?.watches_checked || 0
          )
        };
        privateStateError = "";
        renderCurrent();
      } catch (error) {
        privateStateError = errorMessage(error);
        renderCurrent();
      } finally {
        loading = false;
      }
    }
    void loadWatchState().finally(() => {
      if (!destroyed) {
        void openInitialMedia();
      }
    });
    return {
      destroy() {
        destroyed = true;
        host.innerHTML = "";
      }
    };
  }
  function createPersistentIntelligenceIntegration({
    root,
    apiBase,
    sourceUrl,
    mode
  } = {}) {
    if (!root) {
      return {
        destroy() {
        }
      };
    }
    const normalizedApiBase = String(
      apiBase || "https://sportabase-api.onrender.com"
    ).replace(/\/+$/, "");
    let activePanel = null;
    let activeResults = null;
    function sync() {
      const results = root.querySelector(
        ".sb-article-results, .sb-video-results"
      );
      if (!results) {
        if (activePanel) {
          activePanel.destroy();
          activePanel = null;
          activeResults = null;
        }
        return;
      }
      if (results === activeResults && results.querySelector(
        "[data-sb-persistent-intelligence-host]"
      )) {
        return;
      }
      activePanel?.destroy();
      const host = document.createElement("div");
      host.setAttribute(
        "data-sb-persistent-intelligence-host",
        ""
      );
      const actions = results.querySelector(
        ".sb-article-result-actions, .sb-result-actions"
      );
      if (actions?.parentNode === results) {
        results.insertBefore(
          host,
          actions
        );
      } else {
        results.append(host);
      }
      activeResults = results;
      activePanel = createPanel({
        host,
        apiBase: normalizedApiBase,
        sourceUrl: sourceUrl || window.location.href,
        mode
      });
    }
    const observer = new MutationObserver(sync);
    observer.observe(root, {
      childList: true,
      subtree: true
    });
    sync();
    return {
      destroy() {
        observer.disconnect();
        activePanel?.destroy();
        activePanel = null;
        activeResults = null;
      }
    };
  }
  var REQUEST_TIMEOUT_MS, MAX_ALERT_PAGES, ALERT_PAGE_LIMIT;
  var init_persistent_intelligence2 = __esm({
    "src/content/persistent-intelligence.js"() {
      init_api();
      init_persistent_intelligence_core();
      REQUEST_TIMEOUT_MS = 22e3;
      MAX_ALERT_PAGES = 3;
      ALERT_PAGE_LIMIT = 100;
    }
  });

  // src/content/reporting-profiles.js
  function escapeHtml5(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }
  function humanize3(value) {
    return String(value || "").replaceAll("_", " ").replaceAll("-", " ").replace(/\s+/g, " ").trim().replace(/\b\w/g, (letter) => letter.toUpperCase());
  }
  function formatTime2(value) {
    const text2 = String(value || "").trim();
    if (!text2) return "Not recorded";
    const parsed = new Date(text2);
    return Number.isNaN(parsed.getTime()) ? text2 : parsed.toLocaleString();
  }
  async function requestJson2(apiBase, path) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS2
    );
    try {
      const response = await fetch(`${apiBase}${path}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal
      });
      const text2 = await response.text();
      let payload = null;
      try {
        payload = text2 ? JSON.parse(text2) : null;
      } catch {
        payload = null;
      }
      if (!response.ok) {
        const error = new Error(
          String(payload?.detail || text2 || `HTTP ${response.status}`)
        );
        error.status = response.status;
        throw error;
      }
      return payload;
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new Error("Reporting profile request timed out.");
      }
      throw error;
    } finally {
      window.clearTimeout(timeoutId);
    }
  }
  function profileIdentity(kind, data) {
    if (kind === "source") {
      const source = data?.source || {};
      return {
        title: String(source.display_name || source.canonical_domain || "Persisted source"),
        subtitle: [source.source_type, source.canonical_domain].filter(Boolean).join(" \xB7 "),
        firstSeenAt: source.first_seen_at,
        lastSeenAt: source.last_seen_at
      };
    }
    const reporter = data?.reporter || {};
    return {
      title: String(reporter.display_name || "Persisted reporter"),
      subtitle: String(reporter.identity_key || "Persisted reporter"),
      firstSeenAt: reporter.first_seen_at,
      lastSeenAt: reporter.last_seen_at
    };
  }
  function policyMarkup(policy) {
    return Object.entries(policy || {}).filter(([, enabled]) => Boolean(enabled)).map(
      ([key]) => `
        <p>
          <i></i>
          ${escapeHtml5(POLICY_COPY2[key] || key.replaceAll("_", " "))}
        </p>
      `
    ).join("");
  }
  function eventMarkup2(event) {
    const detail = event?.claim_summary || event?.canonical_text || event?.title || event?.relationship_type || event?.verification_status || "Persisted reporting activity";
    return `
    <article class="sb-rp-event">
      <div>
        <strong>${escapeHtml5(humanize3(event?.type || "event"))}</strong>
        <small>${escapeHtml5(formatTime2(event?.occurred_at))}</small>
      </div>
      <p>${escapeHtml5(detail)}</p>
    </article>
  `;
  }
  function countsMarkup(counts) {
    return Object.entries(counts || {}).map(
      ([key, value]) => `
        <div class="sb-rp-count">
          <strong>${escapeHtml5(value)}</strong>
          <span>${escapeHtml5(humanize3(key))}</span>
        </div>
      `
    ).join("");
  }
  function relationMarkup2(kind, item) {
    const title = item?.display_name || item?.canonical_title || item?.canonical_text || item?.title || item?.canonical_domain || `${humanize3(kind)} ${item?.id || ""}`;
    const subtitle = item?.source_type || item?.identity_key || item?.status || item?.claim_type || item?.mode || "";
    const navigable = kind === "source" || kind === "reporter";
    return `
    <${navigable ? "button" : "div"}
      class="sb-rp-relation"
      ${navigable ? `type="button" data-sb-rp-kind="${kind}" data-sb-rp-id="${escapeHtml5(item?.id)}"` : ""}
    >
      <span>${escapeHtml5(kind.toUpperCase())}</span>
      <strong>${escapeHtml5(title)}</strong>
      ${subtitle ? `<small>${escapeHtml5(subtitle)}</small>` : ""}
    </${navigable ? "button" : "div"}>
  `;
  }
  function profileRelations(kind, data) {
    const groups = [
      ["media", data?.media || []],
      ["story", data?.stories || []],
      ["claim", data?.claims || []]
    ];
    if (kind === "source") {
      groups.push(["reporter", data?.reporters || []]);
    } else {
      groups.push(["source", data?.sources || []]);
    }
    return groups.flatMap(
      ([relationKind, items]) => items.slice(0, 8).map((item) => relationMarkup2(relationKind, item))
    ).join("");
  }
  function createReportingProfilesPanel({ host, apiBase, sourceUrl }) {
    let destroyed = false;
    let attribution = null;
    function renderLoading() {
      host.innerHTML = `
      <section class="sb-rp-card">
        <div class="sb-rp-eyebrow">REPORTING PROFILES</div>
        <p class="sb-rp-muted">Resolving persisted source and reporter attribution\u2026</p>
      </section>
    `;
    }
    function renderSummary() {
      if (destroyed || !attribution) return;
      const items = [
        attribution.sourceId ? { kind: "source", id: attribution.sourceId, label: "Source profile" } : null,
        attribution.reporterId ? { kind: "reporter", id: attribution.reporterId, label: "Reporter profile" } : null
      ].filter(Boolean);
      if (!items.length) {
        host.innerHTML = "";
        return;
      }
      host.innerHTML = `
      <section class="sb-rp-card">
        <div class="sb-rp-head">
          <div>
            <div class="sb-rp-eyebrow">REPORTING PROFILES</div>
            <h3>Who produced this reporting?</h3>
          </div>
          <span>${items.length}</span>
        </div>
        <p class="sb-rp-copy">
          Open persisted source/reporter history. These profiles describe recorded activity and relationships; they do not assign a reliability score.
        </p>
        <div class="sb-rp-profile-buttons">
          ${items.map(
        (item) => `
                <button
                  type="button"
                  class="sb-rp-profile-button"
                  data-sb-rp-kind="${item.kind}"
                  data-sb-rp-id="${escapeHtml5(item.id)}"
                >
                  <span>${escapeHtml5(item.kind.toUpperCase())}</span>
                  <strong>${escapeHtml5(item.label)}</strong>
                  <small>Open persisted history \u2192</small>
                </button>
              `
      ).join("")}
        </div>
      </section>
    `;
      bindProfileLinks();
    }
    function bindProfileLinks() {
      host.querySelectorAll("[data-sb-rp-kind]").forEach((button) => {
        button.addEventListener("click", () => {
          const kind = button.getAttribute("data-sb-rp-kind");
          const id = button.getAttribute("data-sb-rp-id");
          if ((kind === "source" || kind === "reporter") && id) {
            void openProfile(kind, id);
          }
        });
      });
    }
    async function openProfile(kind, id) {
      if (destroyed) return;
      host.innerHTML = `
      <section class="sb-rp-card">
        <div class="sb-rp-eyebrow">REPORTING PROFILE \xB7 ${kind.toUpperCase()}</div>
        <p class="sb-rp-muted">Loading persisted profile\u2026</p>
      </section>
    `;
      try {
        const segment = kind === "source" ? "sources" : "reporters";
        const data = await requestJson2(
          apiBase,
          `/intelligence/${segment}/${encodeURIComponent(id)}/history?limit=30`
        );
        if (destroyed) return;
        const identity = profileIdentity(kind, data);
        const relations = profileRelations(kind, data);
        host.innerHTML = `
        <section class="sb-rp-card">
          <button type="button" class="sb-rp-back" data-sb-rp-back>\u2190 Reporting profiles</button>
          <div class="sb-rp-head sb-rp-profile-head">
            <div>
              <div class="sb-rp-eyebrow">PERSISTED ${kind.toUpperCase()} PROFILE</div>
              <h3>${escapeHtml5(identity.title)}</h3>
              <p class="sb-rp-muted">${escapeHtml5(identity.subtitle)}</p>
            </div>
          </div>
          <div class="sb-rp-time-grid">
            <div><span>FIRST SEEN</span><strong>${escapeHtml5(formatTime2(identity.firstSeenAt))}</strong></div>
            <div><span>LAST SEEN</span><strong>${escapeHtml5(formatTime2(identity.lastSeenAt))}</strong></div>
          </div>
          <div class="sb-rp-boundary">
            <strong>NO RELIABILITY SCORE</strong>
            <p>This profile exposes persisted observations, relationships, dependencies, independence assertions and evidence links as separate facts.</p>
          </div>
          <div class="sb-rp-count-grid">${countsMarkup(data?.counts)}</div>
          <section class="sb-rp-policy">
            <span>INTERPRETATION BOUNDARIES</span>
            ${policyMarkup(data?.policy)}
          </section>
          <section class="sb-rp-section">
            <div class="sb-rp-section-head"><h4>Related intelligence</h4></div>
            <div class="sb-rp-relations">${relations || '<p class="sb-rp-muted">No related objects exposed yet.</p>'}</div>
          </section>
          <section class="sb-rp-section">
            <div class="sb-rp-section-head"><h4>Persisted chronology</h4><span>${data?.events?.length || 0}</span></div>
            <p class="sb-rp-muted">Ordering is descriptive. It does not imply truth, reliability, novelty or independent corroboration.</p>
            <div class="sb-rp-events">
              ${(data?.events || []).map(eventMarkup2).join("") || '<p class="sb-rp-muted">No persisted profile events yet.</p>'}
            </div>
          </section>
        </section>
      `;
        host.querySelector("[data-sb-rp-back]")?.addEventListener("click", renderSummary);
        bindProfileLinks();
      } catch (error) {
        if (destroyed) return;
        host.innerHTML = `
        <section class="sb-rp-card is-error">
          <button type="button" class="sb-rp-back" data-sb-rp-back>\u2190 Reporting profiles</button>
          <div class="sb-rp-eyebrow">REPORTING PROFILE</div>
          <h3>Profile temporarily unavailable</h3>
          <p class="sb-rp-copy">${escapeHtml5(error?.message || error)}</p>
        </section>
      `;
        host.querySelector("[data-sb-rp-back]")?.addEventListener("click", renderSummary);
      }
    }
    async function initialize() {
      renderLoading();
      try {
        const mediaId = await mediaItemIdForUrl(sourceUrl);
        const mediaHistory = await requestJson2(
          apiBase,
          `/intelligence/media/${encodeURIComponent(mediaId)}/history?limit=1`
        );
        if (destroyed) return;
        attribution = {
          sourceId: String(mediaHistory?.media?.source_id || "").trim(),
          reporterId: String(mediaHistory?.media?.reporter_id || "").trim()
        };
        renderSummary();
      } catch (error) {
        if (destroyed) return;
        if (error?.status === 404) {
          host.innerHTML = "";
          return;
        }
        host.innerHTML = `
        <section class="sb-rp-card is-error">
          <div class="sb-rp-eyebrow">REPORTING PROFILES</div>
          <p class="sb-rp-copy">${escapeHtml5(error?.message || error)}</p>
        </section>
      `;
      }
    }
    void initialize();
    return {
      destroy() {
        destroyed = true;
        host.innerHTML = "";
      }
    };
  }
  function createReportingProfilesIntegration({
    root,
    apiBase,
    sourceUrl
  } = {}) {
    if (!root) return { destroy() {
    } };
    const normalizedApiBase = String(
      apiBase || "https://sportabase-api.onrender.com"
    ).replace(/\/+$/, "");
    let activePanel = null;
    let activeResults = null;
    function sync() {
      const results = root.querySelector(
        ".sb-article-results, .sb-video-results"
      );
      if (!results) {
        activePanel?.destroy();
        activePanel = null;
        activeResults = null;
        return;
      }
      if (results === activeResults && results.querySelector("[data-sb-reporting-profiles-host]")) {
        return;
      }
      activePanel?.destroy();
      const host = document.createElement("div");
      host.setAttribute("data-sb-reporting-profiles-host", "");
      const actions = results.querySelector(
        ".sb-article-result-actions, .sb-result-actions"
      );
      if (actions?.parentNode === results) {
        results.insertBefore(host, actions);
      } else {
        results.append(host);
      }
      activeResults = results;
      activePanel = createReportingProfilesPanel({
        host,
        apiBase: normalizedApiBase,
        sourceUrl: sourceUrl || window.location.href
      });
    }
    const observer = new MutationObserver(sync);
    observer.observe(root, { childList: true, subtree: true });
    sync();
    return {
      destroy() {
        observer.disconnect();
        activePanel?.destroy();
        activePanel = null;
        activeResults = null;
      }
    };
  }
  var REQUEST_TIMEOUT_MS2, POLICY_COPY2;
  var init_reporting_profiles2 = __esm({
    "src/content/reporting-profiles.js"() {
      init_persistent_intelligence_core();
      REQUEST_TIMEOUT_MS2 = 22e3;
      POLICY_COPY2 = {
        chronology_is_not_truth: "Chronology is descriptive activity, not a truth or credibility score.",
        reporting_volume_is_not_reliability: "Reporting volume is not a reliability rating.",
        source_count_is_not_independence: "Multiple sources do not automatically represent independent corroboration.",
        dependency_is_not_falsehood: "A persisted dependency relationship does not mean the reporting is false.",
        absence_of_verified_independence_is_not_dependence: "Missing verified independence evidence is not evidence of dependence.",
        evidence_quantity_is_not_probability: "More evidence records do not automatically increase truth probability."
      };
    }
  });

  // src/content/index.js
  var require_index = __commonJS({
    "src/content/index.js"() {
      init_account_settings();
      init_sportabase();
      init_loader();
      init_video_results();
      init_article_mode();
      init_persistent_intelligence();
      init_reporting_profiles();
      init_overlay_shell();
      init_article_mode2();
      init_video_mode();
      init_browser_capture_session();
      init_persistent_intelligence2();
      init_reporting_profiles2();
      init_article_extractor();
      init_youtube_transcript();
      init_api();
      var config = globalThis.__SPORTABASE_BOOT_CONFIG__ || {};
      var captureCurrentPage = createBrowserCaptureSession({
        config,
        extractArticlePageImpl: extractArticlePage,
        extractYouTubeTranscriptImpl: extractYouTubeTranscript,
        postJsonImpl: postJson
      });
      var runtimeConfig = {
        ...config,
        captureCurrentPage
      };
      var isYouTubeVideo = window.location.href.includes(
        "youtube.com/watch"
      ) || window.location.href.includes(
        "youtube.com/shorts/"
      ) || document.querySelector(
        "ytd-watch-flexy"
      ) !== null;
      var shell = openSportabaseShell({
        mode: isYouTubeVideo ? "video" : "article",
        preferences: runtimeConfig.preferences || {}
      });
      var apiBase = String(
        runtimeConfig.api || "https://sportabase-api.onrender.com"
      ).replace(/\/+$/, "");
      var persistentIntelligence = createPersistentIntelligenceIntegration({
        root: shell.content,
        apiBase,
        sourceUrl: window.location.href,
        mode: isYouTubeVideo ? "video" : "article"
      });
      var reportingProfiles = createReportingProfilesIntegration({
        root: shell.content,
        apiBase,
        sourceUrl: window.location.href
      });
      shell.onClose?.(() => {
        persistentIntelligence.destroy();
        reportingProfiles.destroy();
      });
      if (isYouTubeVideo) {
        openVideoMode({
          shell,
          config: runtimeConfig
        });
      } else {
        openArticleMode({
          shell,
          config: runtimeConfig
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
