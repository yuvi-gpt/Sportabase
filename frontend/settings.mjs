import { auth, initializeAuth } from "./auth-provider.mjs";
import { contract, accountState, acceptState, accountRequest, applyAppearance, bootstrap, clearAccountState, signOutCurrentDevice } from "./account-client.mjs";
import { persistentClientId } from "./web-push-helpers.mjs";

const names = ["Account", "Appearance", "Notifications", "Analysis", "My Activity", "Language & Region", "Privacy & Data", "Devices/Sessions", "Support/About"];
const dialog = document.getElementById("settings-dialog");
const content = document.getElementById("settings-content");
const status = document.getElementById("settings-status");
let section = "Account", scope = "device", busy = false, generation = 0, accountSyncEpoch = 0;
const narrow = () => matchMedia("(max-width: 600px)").matches;
const label = value => ({ en: "English", iso: "YYYY-MM-DD", system: "Use system setting" })[value] || value[0].toUpperCase() + value.slice(1);
function node(tag, text, props = {}) { const element = document.createElement(tag); if (text) element.textContent = text; Object.assign(element, props); return element; }
function message(text, tone = "neutral") { status.textContent = text; status.hidden = !text; status.dataset.tone = tone; }
function action(text, fn, className = "secondary-button") {
  const button = node("button", text, { type: "button", className });
  button.addEventListener("click", async () => { button.disabled = true; try { await fn(); } catch (error) { message(error.message); } finally { button.disabled = false; } });
  return button;
}
function showSettings(name = "Account") {
  section = names.includes(name) ? name : "Account";
  dialog.dataset.mobileView = narrow() ? "index" : "section";
  if (!dialog.open) dialog.showModal();
  render();
  void accountRequest("/account/events", { method: "POST", body: { event: "settings_opened" } }).catch(() => {});
}
document.getElementById("open-settings").addEventListener("click", () => showSettings());
document.getElementById("close-settings").addEventListener("click", () => dialog.close());
dialog.addEventListener("close", () => document.getElementById("open-settings").focus());
dialog.addEventListener("keydown", event => {
  if (event.key !== "Tab") return;
  const controls = [...dialog.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])")]
    .filter(control => control.getClientRects().length && control.getAttribute("aria-hidden") !== "true");
  if (!controls.length) return;
  const first = controls[0], last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
document.addEventListener("sportabase:auth-required", () => { if (!dialog.open) { section = "Account"; dialog.dataset.mobileView = "section"; dialog.showModal(); render(); } });
for (const name of names) {
  const button = action(name, () => { section = name; dialog.dataset.mobileView = "section"; message(""); render(); });
  button.dataset.section = name;
  document.getElementById("settings-nav").append(button);
}

function render() {
  generation++;
  const notifications = document.getElementById("browser-notification-controls");
  if (notifications) document.getElementById("notification-parking").append(notifications);
  content.replaceChildren();
  if (narrow()) content.append(action("Back to Settings", () => { dialog.dataset.mobileView = "index"; message(""); }, "settings-back"));
  content.append(node("h2", section));
  for (const button of document.querySelectorAll("[data-section]")) {
    if (button.dataset.section === section) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  if (section === "Support/About") {
    content.append(node("p", "Sportabase · Account product lab v1"), node("p", "Evidence-first sports intelligence."));
    content.append(node("a", "Privacy and data policy", { href: "./privacy.html" }));
    return;
  }
  if (!auth.state.signedIn) {
    content.append(node("h3", auth.state.loaded ? "Your Sportabase account" : "Loading account…"), node("p", "Sign in to analyze, save activity, manage watches and sync settings."));
    if (auth.state.error) content.append(node("p", auth.state.error, { role: "status" }));
    content.append(action("Sign in", () => auth.signIn(), "primary-button"), action("Create account", () => auth.signUp()));
    return;
  }
  if (!accountState) {
    content.append(node("p", "Connect this device to your account."), action("Connect / retry", synchronize));
    return;
  }
  if (section === "Account") {
    content.append(node("h3", auth.state.label), node("p", "Signed in · This browser is connected."));
    content.append(action("Manage account and sessions", () => auth.manage()), action("Sign out", async () => {
      const result = await signOutCurrentDevice();
      if (result.browserCleanupFailed) message("Signed out. Backend push was revoked; browser cleanup can be retried from site settings.");
    }));
  } else if (section === "My Activity") renderActivity();
  else if (section === "Devices/Sessions") {
    content.append(node("p", "Installations have their own preferences. Manage active sign-in sessions through your account."), action("Manage sessions", () => auth.manage()));
    const list = node("ul", "", { className: "settings-list" }); content.append(list);
    const turn = generation;
    void accountRequest("/account/devices").then(data => {
      if (turn !== generation) return;
      for (const device of data.items) list.append(node("li", `${device.name} · ${device.platform}${device.current ? " · This device" : ""} · ${device.follows_defaults ? "Account defaults" : "Device overrides"}`));
    }).catch(error => message(error.message));
  } else renderPreferences();
}

function renderPreferences() {
  const privacy = section === "Privacy & Data";
  const scopeLabel = node("label", "Change settings for", { className: "setting-row" });
  const select = node("select", "", { ariaLabel: "Settings scope" });
  for (const [value, text] of [["device", "This device"], ["account", "Account defaults"]]) select.append(node("option", text, { value }));
  select.value = privacy ? "account" : scope; select.disabled = privacy;
  select.addEventListener("change", () => { scope = select.value; render(); });
  scopeLabel.append(select); content.append(scopeLabel);
  if (!privacy && scope === "device") {
    content.append(node("p", "Your device can follow account defaults or keep its own settings.", { className: "muted" }));
    const row = node("label", "Use account defaults on this device", { className: "setting-row" });
    const follow = node("input", "", { type: "checkbox", checked: accountState.follows_defaults });
    follow.addEventListener("change", () => save({}, follow.checked)); row.append(follow); content.append(row);
  }
  const values = (privacy || scope === "account") ? accountState.defaults : accountState.effective;
  const form = node("form");
  const pending = {};
  for (const key of contract.sections[section] || []) {
    const field = contract.fields[key];
    const row = node("label", field.label, { className: "setting-row" });
    let control;
    if (field.options) {
      control = node("select");
      for (const value of field.options) control.append(node("option", label(value), { value }));
      control.value = values[key];
    } else if (typeof values[key] === "boolean") control = node("input", "", { type: "checkbox", checked: values[key] });
    else control = node("input", "", { type: field.type || "text", value: values[key], maxLength: 80 });
    control.name = key;
    row.dataset.preference = key;
    control.disabled = busy || (!privacy && scope === "device" && accountState.follows_defaults);
    control.addEventListener("change", () => {
      pending[key] = control.type === "checkbox" ? control.checked : control.value;
      if (section === "Appearance" || section === "Analysis") applyAppearance({ ...accountState.effective, ...pending });
      if (section === "Notifications") updateNotificationDependencies();
      saveButton.disabled = false;
      message("Unsaved changes");
    });
    row.append(control); form.append(row);
  }
  const saveButton = node("button", "Save changes", { type: "submit", disabled: true, className: "primary-button" });
  form.append(saveButton);
  function updateNotificationDependencies() {
    if (section !== "Notifications") return;
    const inherited = busy || (!privacy && scope === "device" && accountState.follows_defaults);
    const enabled = form.elements.notifications_enabled?.checked;
    const quiet = form.elements.quiet_hours_enabled?.checked;
    for (const key of ["entity_alerts", "story_alerts", "claim_alerts", "media_alerts"])
      if (form.elements[key]) form.elements[key].disabled = inherited || !enabled;
    for (const key of ["quiet_hours_enabled", "quiet_hours_start", "quiet_hours_end", "timezone"]) {
      const control = form.elements[key]; if (!control) continue;
      control.disabled = inherited || !enabled || (key !== "quiet_hours_enabled" && !quiet);
      if (key !== "quiet_hours_enabled") control.closest(".setting-row").hidden = !quiet;
    }
  }
  updateNotificationDependencies();
  form.addEventListener("submit", async event => { event.preventDefault(); await save(pending, undefined, privacy ? "account" : scope); });
  content.append(form);
  if (section === "Notifications") {
    content.append(node("p", "These delivery rules keep in-app Alerts available. Quiet hours postpone push until the window ends.", { className: "muted" }));
    content.append(document.getElementById("browser-notification-controls"));
  }
  if (section === "Analysis") content.append(node("p", "Essential detail collapses supporting explanation. Score definitions and evidence qualifications stay visible."));
  if (section === "Language & Region") content.append(node("p", "The interface currently supports English. System uses English until more interface translations are available. Analysis retains its existing language support."));
  if (privacy) {
    content.append(node("p", "Optional usage sharing stores narrow product event counts. Turning it off removes retained optional events. Necessary account, device, watch ownership, lifecycle and notification registration records remain while your account is active. Activity stores titles and sanitized revisit links until cleared."));
    content.append(action("Export personal data", exportData), action("Clear My Activity", () => confirmAction("Clear My Activity", "Remove your personal activity on every device? Canonical intelligence remains available.", "CLEAR MY ACTIVITY", "/account/activity"), "danger-button"), action("Delete account", () => confirmAction("Delete account", "Permanently delete your Sportabase account, watches, alerts, settings and activity. A recent account verification is required.", "DELETE MY ACCOUNT", "/account"), "danger-button"));
  }
}

async function save(preferences, follows, selectedScope = scope) {
  if (busy) return;
  busy = true; message("Saving…");
  try {
    const state = await accountRequest("/account/preferences", { method: "PATCH", body: {
      version: contract.version, scope: selectedScope, revision: selectedScope === "account" ? accountState.account_revision : accountState.device_revision,
      preferences, ...(follows === undefined ? {} : { follows_defaults: follows }),
    } });
    acceptState(state); busy = false; message(selectedScope === "account" ? "Saved to account defaults" : state.follows_defaults ? "This device now follows account defaults" : "Saved on this device", "success"); render();
  } catch (error) { applyAppearance(accountState.effective); message(`${error.message} Your changes have not been saved.`, "error"); }
  finally { busy = false; }
}
function renderActivity() {
  const form = node("form", "", { className: "activity-filters" });
  const search = node("input", "", { type: "search", placeholder: "Search titles", ariaLabel: "Search My Activity", maxLength: 120 });
  const filter = node("select", "", { ariaLabel: "Activity type" });
  for (const [value, text] of [["", "All analyses"], ["article", "Articles"], ["video", "Videos"]]) filter.append(node("option", text, { value }));
  form.append(search, filter, node("button", "Search", { type: "submit" })); content.append(form);
  const list = node("ul", "", { className: "settings-list" }); content.append(list);
  let next = null;
  const more = action("Load more", () => load(true)); more.hidden = true; content.append(more);
  const turn = generation;
  async function load(append = false) {
    message("Loading activity…");
    const params = new URLSearchParams({ q: search.value, kind: filter.value, ...(append && next ? next : {}) });
    try {
      const result = await accountRequest(`/account/activity?${params}`);
      if (turn !== generation) return;
      if (!append) list.replaceChildren();
      for (const item of result.items) {
        const row = node("li");
        let url = ""; try { const parsed = new URL(item.url); if (["https:", "http:"].includes(parsed.protocol)) url = parsed.href; } catch {}
        row.append(url ? node("a", item.title, { href: url, target: "_blank", rel: "noopener noreferrer" }) : node("strong", item.title));
        const date = new Date(item.created_at * 1000);
        row.append(node("small", `${label(item.kind)} · ${item.platform} · ${accountState.effective.date_format === "iso" ? date.toISOString().slice(0, 10) : date.toLocaleString()}`));
        list.append(row);
      }
      next = result.next; more.hidden = !next;
      message(result.items.length || append ? "Activity loaded" : "No activity found. Your completed analyses appear here when activity saving is enabled.");
    } catch (error) { message(error.message); }
  }
  form.addEventListener("submit", event => { event.preventDefault(); void load(); });
  void load();
}
async function exportData() {
  const data = await accountRequest("/account/export");
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = node("a", "", { href: url, download: "sportabase-personal-data.json" }); link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  message("Export downloaded");
}
function confirmAction(title, copy, confirmation, path) {
  const confirm = document.getElementById("data-confirmation");
  const trigger = document.activeElement;
  confirm.replaceChildren(node("h2", title), node("p", copy));
  confirm.append(action("Cancel", () => confirm.close()), action(title, async () => {
    await accountRequest(path, { method: "DELETE", body: { confirmation } });
    confirm.close(); message(path === "/account" ? "Account deleted" : "My Activity cleared");
    if (path === "/account") await auth.signOut();
  }, "danger-button"));
  confirm.addEventListener("close", () => trigger?.focus(), { once: true });
  confirm.showModal(); confirm.querySelector("button").focus();
}
document.getElementById("data-confirmation").addEventListener("keydown", event => {
  if (event.key !== "Tab") return;
  const controls = [...event.currentTarget.querySelectorAll("button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href]")];
  if (!controls.length) return;
  if (event.shiftKey && document.activeElement === controls[0]) { event.preventDefault(); controls.at(-1).focus(); }
  else if (!event.shiftKey && document.activeElement === controls.at(-1)) { event.preventDefault(); controls[0].focus(); }
});
async function synchronize(epoch = ++accountSyncEpoch) {
  const expectedUserId = auth.state.userId;
  const isCurrent = () => epoch === accountSyncEpoch && auth.state.signedIn && auth.state.userId === expectedUserId;
  message("Syncing account…");
  try {
    const state = await bootstrap(persistentClientId(localStorage, crypto), { isCurrent });
    if (!state || !isCurrent()) return;
    message("Account connected"); render(); document.dispatchEvent(new Event("sportabase:account-ready"));
  } catch (error) { if (isCurrent()) { message(error.message); render(); } }
}
auth.subscribe(state => {
  const epoch = ++accountSyncEpoch;
  document.getElementById("account-label").textContent = state.signedIn ? "Account" : "Sign in";
  if (state.signedIn) void synchronize(epoch);
  else { clearAccountState(); render(); }
});
void initializeAuth();
if (location.hash === "#settings") showSettings();
