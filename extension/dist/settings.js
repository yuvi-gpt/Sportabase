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

  // src/styles/extension-settings-page.css
  var init_extension_settings_page = __esm({
    "src/styles/extension-settings-page.css"() {
    }
  });

  // src/styles/account-settings.css
  var init_account_settings = __esm({
    "src/styles/account-settings.css"() {
    }
  });

  // ../frontend/preferences-contract.json
  var preferences_contract_default;
  var init_preferences_contract = __esm({
    "../frontend/preferences-contract.json"() {
      preferences_contract_default = {
        version: "sportabase-preferences-v1",
        defaults: {
          appearance: "system",
          contrast: "standard",
          text_size: "system",
          density: "comfortable",
          motion: "system",
          language: "system",
          date_format: "system",
          analysis_detail: "full",
          notifications_enabled: true,
          entity_alerts: true,
          story_alerts: true,
          claim_alerts: true,
          media_alerts: true,
          quiet_hours_enabled: false,
          quiet_hours_start: "22:00",
          quiet_hours_end: "07:00",
          timezone: "UTC",
          analytics_enabled: false,
          activity_enabled: true
        },
        sections: {
          Appearance: ["appearance", "contrast", "text_size", "density", "motion"],
          Notifications: ["notifications_enabled", "entity_alerts", "story_alerts", "claim_alerts", "media_alerts", "quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end", "timezone"],
          Analysis: ["analysis_detail"],
          "Language & Region": ["language", "date_format"],
          "Privacy & Data": ["analytics_enabled", "activity_enabled"]
        },
        fields: {
          appearance: { label: "Appearance", options: ["system", "light", "dark"] },
          contrast: { label: "Contrast", options: ["standard", "high"] },
          text_size: { label: "Text size", options: ["system", "small", "large"] },
          density: { label: "Density", options: ["comfortable", "compact"] },
          motion: { label: "Motion", options: ["system", "reduce", "full"] },
          language: { label: "Interface language", options: ["system", "en"] },
          date_format: { label: "Date display", options: ["system", "iso"] },
          analysis_detail: { label: "Analysis detail", options: ["full", "essential"] },
          notifications_enabled: { label: "Allow push delivery" },
          entity_alerts: { label: "Entity alerts" },
          story_alerts: { label: "Story alerts" },
          claim_alerts: { label: "Claim alerts" },
          media_alerts: { label: "Media alerts" },
          quiet_hours_enabled: { label: "Quiet hours" },
          quiet_hours_start: { label: "Quiet hours start", type: "time" },
          quiet_hours_end: { label: "Quiet hours end", type: "time" },
          timezone: { label: "Quiet hours timezone", type: "text" },
          analytics_enabled: { label: "Share product usage counts", accountOnly: true },
          activity_enabled: { label: "Save My Activity", accountOnly: true }
        }
      };
    }
  });

  // src/ui/account-settings.js
  function sharedToLocal(preferences) {
    return Object.fromEntries(Object.entries(mapping).map(([key, local]) => [local, key === "contrast" ? preferences[key] === "high" : preferences[key]]));
  }
  function installAccountSettings({ layer, applyShared }) {
    const container = layer.querySelector(".sb-settings-content");
    const host = document.createElement("div");
    host.className = "sb-account-settings";
    container.prepend(host);
    let state = null, scope = "device", busy = false;
    const openSections = /* @__PURE__ */ new Set(["Account"]);
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    function element(tag, text) {
      const el = document.createElement(tag);
      if (text) el.textContent = text;
      return el;
    }
    function setStatus(text, tone = "neutral") {
      status.textContent = text;
      status.dataset.tone = tone;
    }
    async function message(type, extra = {}) {
      const result = await chrome.runtime.sendMessage({ type, ...extra });
      if (!result?.ok) throw new Error(result?.error || "Account operation failed.");
      return result;
    }
    function button(label, fn) {
      const el = element("button", label);
      el.type = "button";
      el.className = "sb-account-button";
      el.addEventListener("click", async () => {
        el.disabled = true;
        try {
          await fn();
        } catch (error) {
          setStatus(error.message, "error");
        } finally {
          el.disabled = false;
        }
      });
      return el;
    }
    function group(name, initial = false) {
      const el = element("details");
      el.open = openSections.has(name) || initial;
      const summary = element("summary", name);
      el.append(summary);
      el.addEventListener("toggle", () => el.open ? openSections.add(name) : openSections.delete(name));
      host.append(el);
      return el;
    }
    function lock(value) {
      busy = value;
      for (const control of host.querySelectorAll("button,input,select")) {
        if (value) {
          control.dataset.wasDisabled = String(control.disabled);
          control.disabled = true;
        } else {
          control.disabled = control.dataset.wasDisabled === "true";
          delete control.dataset.wasDisabled;
        }
      }
    }
    async function refresh() {
      setStatus("Connecting account...");
      try {
        const result = await message("SPORTABASE_ACCOUNT_STATE");
        state = result.state;
        applyShared(sharedToLocal(state.effective));
        render("Account");
        setStatus(state.follows_defaults ? "Connected \xB7 Using account defaults" : "Connected \xB7 Device overrides enabled", "success");
      } catch (error) {
        state = null;
        render("Account");
        setStatus(error.message, "error");
      }
    }
    function render(focusSection = "") {
      host.replaceChildren(status);
      const account = group("Account", true);
      account.append(element("p", state ? "Connected account \xB7 Chrome extension" : "Sign in on Sportabase, then connect this extension."));
      account.append(button(state ? "Open account and sessions" : "Sign in on Sportabase", () => message("SPORTABASE_OPEN_ACCOUNT")), button(state ? "Refresh connection" : "Connect after signing in", refresh));
      if (state) account.append(button("Sign out of this extension", async () => {
        await message("SPORTABASE_SIGN_OUT");
        state = null;
        render("Account");
        setStatus("Signed out", "success");
      }));
      if (state) {
        const row = element("label", "Settings location");
        row.className = "sb-setting-row";
        const select = element("select");
        for (const [value, text] of [["device", "This extension"], ["account", "Account defaults"]]) {
          const option = element("option", text);
          option.value = value;
          select.append(option);
        }
        select.value = scope;
        select.addEventListener("change", () => {
          scope = select.value;
          render("Account");
        });
        row.append(select);
        account.append(row);
        if (scope === "device") {
          const follow = element("label", "Use account defaults on this extension");
          follow.className = "sb-setting-row";
          const input = element("input");
          input.type = "checkbox";
          input.checked = state.follows_defaults;
          input.addEventListener("change", () => save({}, input.checked, "device", "Account"));
          follow.append(input);
          account.append(follow);
        }
      }
      for (const name of ["Appearance", "Analysis", "Notifications", "Language & Region", "Privacy & Data"]) {
        const section = group(name);
        if (!state) {
          section.append(element("p", "Connect your account to manage these preferences."));
          continue;
        }
        const privacy = name === "Privacy & Data";
        const selected = privacy ? "account" : scope;
        const values = selected === "account" ? state.defaults : state.effective;
        const pending = {};
        let saveButton;
        const inherited = () => !privacy && selected === "device" && state.follows_defaults;
        const dependencies = () => {
          if (name !== "Notifications") return;
          const master = section.querySelector('[name="notifications_enabled"]')?.checked;
          const quiet = section.querySelector('[name="quiet_hours_enabled"]')?.checked;
          for (const key of ["entity_alerts", "story_alerts", "claim_alerts", "media_alerts", "quiet_hours_enabled"]) {
            const control = section.querySelector(`[name="${key}"]`);
            if (control) control.disabled = busy || inherited() || !master;
          }
          for (const key of ["quiet_hours_start", "quiet_hours_end", "timezone"]) {
            const control = section.querySelector(`[name="${key}"]`);
            if (!control) continue;
            control.disabled = busy || inherited() || !master || !quiet;
            control.closest(".sb-setting-row").hidden = !quiet;
          }
        };
        for (const key of preferences_contract_default.sections[name]) {
          const field = preferences_contract_default.fields[key];
          const row = element("label", field.label);
          row.className = "sb-setting-row";
          let input;
          if (field.options) {
            input = element("select");
            for (const value of field.options) {
              const option = element("option", labels[value] || value);
              option.value = value;
              input.append(option);
            }
            input.value = values[key];
          } else {
            input = element("input");
            input.type = typeof values[key] === "boolean" ? "checkbox" : field.type || "text";
            if (input.type === "checkbox") input.checked = values[key];
            else input.value = values[key];
            input.maxLength = 80;
          }
          input.name = key;
          input.disabled = busy || inherited();
          input.addEventListener("change", () => {
            pending[key] = input.type === "checkbox" ? input.checked : input.value;
            if (name === "Appearance" || name === "Analysis") applyShared(sharedToLocal({ ...state.effective, ...pending }));
            saveButton.disabled = false;
            dependencies();
            setStatus("Unsaved changes");
          });
          row.append(input);
          section.append(row);
        }
        saveButton = button("Save changes", () => save(pending, void 0, selected, name));
        saveButton.disabled = true;
        section.append(saveButton);
        dependencies();
        if (name === "Notifications") section.append(element("p", "Push delivery uses web or mobile registrations. Quiet hours postpone delivery; Alerts stay available."));
        if (privacy) section.append(element("p", "Optional usage sharing controls narrow event counts. Necessary account, device, watch and notification records remain while the account is active. Export and deletion open the configured Sportabase web app."), button("Manage personal data", () => message("SPORTABASE_OPEN_ACCOUNT")));
      }
      const activity = group("My Activity");
      activity.append(button("Open personal activity", () => message("SPORTABASE_OPEN_ACCOUNT")));
      const about = group("Support/About");
      about.append(element("p", `Sportabase ${chrome.runtime.getManifest().version}`), button("Account and privacy information", () => message("SPORTABASE_OPEN_ACCOUNT")));
      if (focusSection) queueMicrotask(() => [...host.querySelectorAll("summary")].find((summary) => summary.textContent === focusSection)?.focus());
    }
    async function save(preferences, follows, selected = scope, source = "Account") {
      if (busy) return;
      lock(true);
      setStatus("Saving...");
      try {
        const result = await message("SPORTABASE_ACCOUNT_UPDATE", { body: { version: preferences_contract_default.version, scope: selected, revision: selected === "account" ? state.account_revision : state.device_revision, preferences, ...follows === void 0 ? {} : { follows_defaults: follows } } });
        state = result.state;
        applyShared(sharedToLocal(state.effective));
        lock(false);
        render(source);
        setStatus(selected === "account" ? "Saved to account defaults" : state.follows_defaults ? "This extension now follows account defaults" : "Saved on this extension", "success");
      } catch (error) {
        applyShared(sharedToLocal(state.effective));
        lock(false);
        setStatus(error.message, "error");
      }
    }
    render();
    return { refresh };
  }
  var mapping, labels;
  var init_account_settings2 = __esm({
    "src/ui/account-settings.js"() {
      init_preferences_contract();
      mapping = { appearance: "sportabaseAppearance", contrast: "sportabaseHighContrast", text_size: "sportabaseTextScale", density: "sportabaseDensity", motion: "sportabaseMotionLevel", analysis_detail: "sportabaseDetailLevel" };
      labels = { system: "System setting", en: "English", full: "Full detail", essential: "Essential detail", comfortable: "Comfortable", compact: "Compact", standard: "Standard", high: "High contrast", reduce: "Reduce motion", light: "Light", dark: "Dark", small: "Smaller", large: "Larger", iso: "YYYY-MM-DD" };
    }
  });

  // src/extension-page/account-settings-page.js
  var require_account_settings_page = __commonJS({
    "src/extension-page/account-settings-page.js"() {
      init_extension_settings_page();
      init_account_settings();
      init_account_settings2();
      function applyPresentation(preferences) {
        const root = document.documentElement;
        root.dataset.appearance = preferences.sportabaseAppearance || "system";
        root.dataset.contrast = preferences.sportabaseHighContrast ? "high" : "standard";
        root.dataset.text = preferences.sportabaseTextScale || "medium";
        root.dataset.density = preferences.sportabaseDensity || "comfortable";
        root.dataset.motion = preferences.sportabaseMotionLevel || "system";
        root.dataset.detail = preferences.sportabaseDetailLevel || "full";
      }
      var settings = installAccountSettings({ layer: document, applyShared: applyPresentation });
      void settings.refresh();
    }
  });
  require_account_settings_page();
})();
