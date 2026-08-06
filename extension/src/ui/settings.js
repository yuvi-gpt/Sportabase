import {
  applyPreferences,
  DEFAULT_PREFERENCES,
  resolvePreferences,
  savePreferences,
  SPORTABASE_VIEWPORT_GUTTER,
} from "./preferences.js";

export function installSettingsDrawer({
  overlay,
  preferences = {},
} = {}) {
  if (!overlay) {
    return {
      open() {},
      close() {},
    };
  }

  let currentPreferences =
    resolvePreferences(
      preferences
    );

  let closeTimer = null;

  const layer =
    document.createElement("div");

  layer.className =
    "sb-settings-layer";

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

              <option
                value="custom"
                disabled
              >
                Custom
              </option>
            </select>
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
          Changes are saved automatically.
        </div>
      </div>
    </section>
  `;

  overlay.appendChild(layer);

  const settingsButton =
    overlay.querySelector(
      "[data-sb-settings]"
    );

  const panel =
    layer.querySelector(
      ".sb-settings-panel"
    );

  function syncControls() {
    layer
      .querySelectorAll(
        "[data-sb-setting]"
      )
      .forEach((control) => {
        const key =
          control.dataset.sbSetting;

        const value =
          currentPreferences[key];

        if (
          control.type ===
          "checkbox"
        ) {
          control.checked =
            Boolean(value);

          return;
        }

        control.value =
          value ?? "";
      });
  }

  async function persist(
    payload
  ) {
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
    currentPreferences =
      applyPreferences(
        overlay,
        currentPreferences
      );

    syncControls();
  }

  function resetLayout() {
    const resetPreferences = {
      sportabasePanelPosition:
        "top-right",

      sportabaseSizeMode:
        "comfort",

      sportabaseCustomWidth:
        null,

      sportabaseCustomHeight:
        null,

      sportabaseLeft:
        null,

      sportabaseTop:
        null,

      sportabaseHorizontalAnchor:
        "right",

      sportabaseEdgeOffset:
        SPORTABASE_VIEWPORT_GUTTER,

      sportabaseRememberPosition:
        true,
    };

    currentPreferences = {
      ...currentPreferences,
      ...resetPreferences,
    };

    applyCurrentPreferences();

    persist(
      resetPreferences
    );
  }

  function resetAllSettings() {
    currentPreferences = {
      ...DEFAULT_PREFERENCES,
    };

    applyCurrentPreferences();

    persist({
      ...DEFAULT_PREFERENCES,
    });
  }

  overlay.addEventListener(
    "sportabase:geometry-changed",
    (event) => {
      currentPreferences =
        resolvePreferences({
          ...currentPreferences,
          ...(event.detail || {}),
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

    closeTimer =
      window.setTimeout(() => {
        layer.hidden = true;
        closeTimer = null;
      }, 170);
  }

  layer
    .querySelectorAll(
      "[data-sb-settings-close]"
    )
    .forEach((button) => {
      button.addEventListener(
        "click",
        close
      );
    });

  settingsButton?.addEventListener(
    "click",
    open
  );

  layer
    .querySelectorAll(
      "[data-sb-setting]"
    )
    .forEach((control) => {
      control.addEventListener(
        "change",
        () => {
          const key =
            control.dataset.sbSetting;

          const value =
            control.type ===
            "checkbox"
              ? control.checked
              : control.value;

          const payload = {
            [key]: value,
          };

          currentPreferences = {
            ...currentPreferences,
            [key]: value,
          };

          if (
            key ===
            "sportabasePanelPosition"
          ) {
            const anchor =
              value === "top-left"
                ? "left"
                : "right";

            currentPreferences = {
              ...currentPreferences,

              sportabaseLeft:
                null,

              sportabaseTop:
                null,

              sportabaseHorizontalAnchor:
                anchor,

              sportabaseEdgeOffset:
        SPORTABASE_VIEWPORT_GUTTER,

              sportabaseRememberPosition:
                true,
            };

            payload.sportabaseLeft =
              null;

            payload.sportabaseTop =
              null;

            payload
              .sportabaseHorizontalAnchor =
                anchor;

            payload
              .sportabaseEdgeOffset =
                8;

            payload
              .sportabaseRememberPosition =
                true;
          }

          if (
            key ===
            "sportabaseSizeMode"
          ) {
            currentPreferences = {
              ...currentPreferences,

              sportabaseCustomWidth:
                null,

              sportabaseCustomHeight:
                null,
            };

            payload
              .sportabaseCustomWidth =
                null;

            payload
              .sportabaseCustomHeight =
                null;
          }

          applyCurrentPreferences();

          persist(payload);
        }
      );
    });

  layer
    .querySelector(
      "[data-sb-reset-layout]"
    )
    ?.addEventListener(
      "click",
      resetLayout
    );

  layer
    .querySelector(
      "[data-sb-reset-all]"
    )
    ?.addEventListener(
      "click",
      resetAllSettings
    );

  overlay.addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Escape" &&
        !layer.hidden
      ) {
        close();
      }
    }
  );

  settingsButton?.setAttribute(
    "aria-expanded",
    "false"
  );

  applyCurrentPreferences();

  return {
    open,
    close,
  };
}
