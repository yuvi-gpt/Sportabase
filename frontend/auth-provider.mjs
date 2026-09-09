import config from "./product-config.mjs";
import { assertBrowserDeployment } from "./deployment-config.mjs";

let clerk = null;
const listeners = new Set();
export const auth = {
  state: { loaded: false, signedIn: false, label: "Loading account…", error: "" },
  subscribe(fn) { listeners.add(fn); fn(this.state); return () => listeners.delete(fn); },
  async token() { return clerk?.session ? await clerk.session.getToken() : null; },
  async signIn() { if (!clerk) throw new Error(this.state.error || "Account sign-in is unavailable."); await clerk.redirectToSignIn({ signInFallbackRedirectUrl: location.href }); },
  async signUp() { if (!clerk) throw new Error(this.state.error || "Account sign-up is unavailable."); await clerk.redirectToSignUp({ signUpFallbackRedirectUrl: location.href }); },
  async signOut() { await clerk?.signOut(); },
  async manage() { if (clerk) await clerk.redirectToUserProfile(); },
};
function update(state) { auth.state = state; for (const fn of listeners) fn(state); }
function script(src, key) {
  return new Promise((resolve, reject) => {
    const element = document.createElement("script");
    element.src = src; element.async = true; element.crossOrigin = "anonymous";
    element.dataset.clerkPublishableKey = key;
    element.onload = resolve;
    element.onerror = () => reject(new Error("Sign-in could not load. Check your connection and retry."));
    document.head.append(element);
  });
}
export async function initializeAuth() {
  try {
    assertBrowserDeployment(config, location);
    const key = config.clerkPublishableKey;
    if (!/^pk_(test|live)_/.test(key)) throw new Error("Account sign-in is not configured for this installation.");
    const domain = atob(key.split("_")[2]).replace(/\$$/, "");
    if (!/^[a-z0-9.-]+$/i.test(domain)) throw new Error("Account configuration is invalid.");
    await script(`https://${domain}/npm/@clerk/clerk-js@6.31.0/dist/clerk.browser.js`, key);
    clerk = window.Clerk;
    await clerk.load();
    clerk.addListener(({ user, session }) => update({ loaded: true, signedIn: Boolean(session && user),
      userId: user?.id, label: user?.primaryEmailAddress?.emailAddress || user?.fullName || "Your account", error: "" }));
  } catch (error) {
    update({ loaded: true, signedIn: false, label: "Signed out", error: error.message });
  }
}
