import config from "./product-config.mjs";
import { auth } from "./auth-provider.mjs";
import contract from "./preferences-contract.json" with { type: "json" };

export { contract };
export let accountState = null;
const LEGACY_MIGRATION_KEY = "sportabase:legacy-migration:v1";
export function deviceId() {
  let value = localStorage.getItem("sportabase:device:v1");
  if (!value) { value = crypto.randomUUID(); localStorage.setItem("sportabase:device:v1", value); }
  return value;
}
export function isPrivatePath(path) {
  return /^(\/account(?:\/|$)|\/watchlists(?:\/|$)|\/notifications(?:\/|$)|\/analyze(?:\/|$)|\/resolve-content$|\/content\/browser-capture$)/.test(path);
}
export async function authHeaders() {
  const token = await auth.token();
  if (!token) { document.dispatchEvent(new Event("sportabase:auth-required")); throw new Error("Sign in to use Sportabase."); }
  return { Authorization: `Bearer ${token}`, "X-Sportabase-Device-ID": deviceId() };
}
export async function accountRequest(path, { method = "GET", body, signal } = {}) {
  const response = await fetch(`${config.apiBase}${path}`, {
    method, headers: { ...await authHeaders(), "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  });
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === "string" ? data.detail : `Request failed (${response.status}).`); }
  return response.status === 204 ? null : response.json();
}
export function applyAppearance(prefs) {
  const root = document.documentElement;
  root.dataset.appearance = prefs.appearance;
  root.dataset.theme = prefs.appearance === "system" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : prefs.appearance;
  root.dataset.contrast = prefs.contrast; root.dataset.textSize = prefs.text_size;
  root.dataset.density = prefs.density; root.dataset.detail = prefs.analysis_detail;
  root.dataset.motion = prefs.motion === "system" ? (matchMedia("(prefers-reduced-motion: reduce)").matches ? "reduce" : "full") : prefs.motion;
}
export function cachedAppearance() {
  try { return { ...contract.defaults, ...JSON.parse(localStorage.getItem("sportabase:appearance:v1") || "{}") }; }
  catch { return contract.defaults; }
}
export function acceptState(state) {
  accountState = state;
  // Cache presentation only. Activity, identity, privacy and notification credentials stay out.
  const keys = [...contract.sections.Appearance, "analysis_detail", "date_format", "language"];
  try { localStorage.setItem("sportabase:appearance:v1", JSON.stringify(Object.fromEntries(keys.map(key => [key, state.effective[key]])))); } catch { /* Server sync remains usable. */ }
  applyAppearance(state.effective);
  return state;
}
export function clearAccountState() { accountState = null; }
export async function bootstrap(legacyClientId, { isCurrent = () => true } = {}) {
  let migrationComplete = false;
  try { migrationComplete = localStorage.getItem(LEGACY_MIGRATION_KEY) === "complete"; } catch {}
  const state = await accountRequest("/account/bootstrap", { method: "POST", body: {
    platform: "web", name: "Web browser", ...(!migrationComplete && legacyClientId ? { legacy_client_id: legacyClientId } : {}),
  } });
  if (state.legacy_migration?.status && state.legacy_migration.status !== "not_requested") {
    try { localStorage.setItem(LEGACY_MIGRATION_KEY, "complete"); } catch {}
  }
  if (!isCurrent()) return null;
  return acceptState(state);
}
export async function signOutCurrentDevice() {
  // Backend revocation is the security boundary. Do not end the Clerk session if
  // it fails, because that would strand account-owned delivery on a shared device.
  await accountRequest("/account/device/sign-out", { method: "POST" });
  let browserCleanupFailed = false;
  try {
    const registration = await navigator.serviceWorker?.getRegistration?.("./");
    const subscription = await registration?.pushManager?.getSubscription?.();
    if (subscription && !await subscription.unsubscribe()) browserCleanupFailed = true;
  } catch (error) {
    browserCleanupFailed = true;
    console.warn("[sportabase] Backend push was revoked, but browser subscription cleanup failed:", error);
  }
  await auth.signOut();
  clearAccountState();
  return { browserCleanupFailed };
}
applyAppearance(cachedAppearance());
for (const media of ["(prefers-color-scheme: dark)", "(prefers-reduced-motion: reduce)"]) {
  matchMedia(media).addEventListener("change", () => applyAppearance(accountState?.effective || cachedAppearance()));
}
