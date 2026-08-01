import {
  applyPreferences,
  savePreferences,
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

  let currentPreferences = {
    ...preferences,
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

    const customAccent =
      currentPreferences.sportabaseAccentMode ===
      "fixed";

    accentColorControl.disabled = !customAccent;
    accentColorControl.closest(".sb-setting-row")
      ?.classList.toggle(
        "sb-setting-disabled",
        !customAccent
      );
  }

  function syncControls() {
    layer
      .querySelectorAll("[data-sb-setting]")
      .forEach((control) => {
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

  layer
    .querySelectorAll("[data-sb-settings-close]")
    .forEach((button) => {
      button.addEventListener("click", close);
    });

  settingsButton?.addEventListener("click", open);

  layer
    .querySelectorAll("[data-sb-setting]")
    .forEach((control) => {
      const eventName =
        control.type === "color"
          ? "input"
          : "change";

      control.addEventListener(eventName, () => {
        const key = control.dataset.sbSetting;

        const value =
          control.type === "checkbox"
            ? control.checked
            : control.value;

        currentPreferences = {
          ...currentPreferences,
          [key]: value,
        };

        if (control === accentModeControl) {
          updateAccentControlState();
        }

        applyPreferences(
          overlay,
          currentPreferences
        );

        savePreferences({
          [key]: value,
        }).catch((error) => {
          console.error(
            "[sportabase] Could not save setting:",
            error
          );
        });
      });
    });

  overlay.addEventListener("keydown", (event) => {
    if (
      event.key === "Escape" &&
      !layer.hidden
    ) {
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
    close,
  };
}
