export const WATCHABLE_TARGET_KINDS = Object.freeze([
  "entity", "story", "claim", "media",
]);

export function isSafeTargetKind(value) {
  return WATCHABLE_TARGET_KINDS.includes(String(value || ""));
}

export function urlBase64ToUint8Array(value) {
  const normalized = String(value || "").trim().replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - normalized.length % 4) % 4);
  const binary = globalThis.atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export function canonicalTargetUrl(appBase, targetKind, targetId) {
  if (!isSafeTargetKind(targetKind) || !String(targetId || "").trim()) return null;
  const url = new URL("./", appBase);
  url.searchParams.set("target_kind", targetKind);
  url.searchParams.set("target_id", String(targetId).trim().slice(0, 256));
  return url.href;
}

export function safeNotificationUrl(appBase, payload) {
  const canonical = canonicalTargetUrl(appBase, payload?.target_kind, payload?.target_id);
  if (!canonical) return new URL("./", appBase).href;
  if (!payload?.url) return canonical;
  try {
    const candidate = new URL(payload.url, appBase);
    return candidate.origin === new URL(appBase).origin ? canonical : canonical;
  } catch (_) {
    return canonical;
  }
}

export function serializePushSubscription(subscription) {
  const json = subscription?.toJSON?.();
  return {
    endpoint: String(json?.endpoint || subscription?.endpoint || ""),
    expirationTime: json?.expirationTime ?? subscription?.expirationTime ?? null,
    keys: {
      p256dh: String(json?.keys?.p256dh || ""),
      auth: String(json?.keys?.auth || ""),
    },
  };
}

export function persistentClientId(storage, cryptoObject = globalThis.crypto) {
  const key = "sportabaseWebClientId";
  try {
    const existing = String(storage.getItem(key) || "").trim();
    if (existing) return existing;
    if (typeof cryptoObject?.randomUUID !== "function") return null;
    const created = cryptoObject.randomUUID();
    storage.setItem(key, created);
    return String(storage.getItem(key) || "").trim() === created ? created : null;
  } catch (_) {
    return null;
  }
}

export function notificationCapability(environment) {
  if (!environment?.isSecureContext) return "insecure";
  if (!("Notification" in environment) || !("serviceWorker" in environment.navigator) || !("PushManager" in environment)) return "unsupported";
  if (environment.Notification.permission === "denied") return "denied";
  return "available";
}
