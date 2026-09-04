import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  canonicalTargetUrl,
  notificationCapability,
  persistentClientId,
  safeNotificationUrl,
  serializePushSubscription,
  urlBase64ToUint8Array,
} from "../web-push-helpers.mjs";


test("VAPID base64url conversion produces the original bytes", () => {
  const bytes = urlBase64ToUint8Array("AQID-vs");
  assert.deepEqual([...bytes], [1, 2, 3, 250, 251]);
});


test("canonical targets accept exactly the four watchable kinds", () => {
  for (const kind of ["entity", "story", "claim", "media"]) {
    const url = new URL(canonicalTargetUrl("https://sportabase.example/app/", kind, "id 1"));
    assert.equal(url.origin, "https://sportabase.example");
    assert.equal(url.searchParams.get("target_kind"), kind);
  }
  assert.equal(canonicalTargetUrl("https://sportabase.example/", "source", "source-1"), null);
  assert.equal(canonicalTargetUrl("https://sportabase.example/", "reporter", "reporter-1"), null);
});


test("canonical targets preserve root and subpath application scope", () => {
  const root = new URL(canonicalTargetUrl("https://sportabase.example/index.html", "claim", "claim-1"));
  assert.equal(root.pathname, "/");
  const subpath = new URL(canonicalTargetUrl("https://sportabase.example/apps/sportabase/index.html", "claim", "claim-1"));
  assert.equal(subpath.pathname, "/apps/sportabase/");
  assert.equal(subpath.origin, "https://sportabase.example");
});


test("notification URLs cannot navigate off site", () => {
  const url = new URL(safeNotificationUrl("https://sportabase.example/", {
    target_kind: "story", target_id: "story-1", url: "https://evil.example/steal",
  }));
  assert.equal(url.origin, "https://sportabase.example");
  assert.equal(url.searchParams.get("target_id"), "story-1");
});


test("persistent identity has no shared anonymous fallback", () => {
  const broken = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.equal(persistentClientId(broken, { randomUUID() { return "unique"; } }), null);
  const memory = new Map();
  const storage = { getItem: (key) => memory.get(key), setItem: (key, value) => memory.set(key, value) };
  assert.equal(persistentClientId(storage, { randomUUID() { return "unique-id"; } }), "unique-id");
  assert.equal(persistentClientId(storage, { randomUUID() { return "different"; } }), "unique-id");
});


test("PushSubscription serialization matches the backend contract", () => {
  const serialized = serializePushSubscription({ toJSON() { return {
    endpoint: "https://push.example/sub", expirationTime: 123,
    keys: { p256dh: "public", auth: "secret" },
  }; } });
  assert.deepEqual(serialized, {
    endpoint: "https://push.example/sub", expirationTime: 123,
    keys: { p256dh: "public", auth: "secret" },
  });
});


test("unsupported, insecure, and denied capability states are graceful", () => {
  assert.equal(notificationCapability({ isSecureContext: false }), "insecure");
  assert.equal(notificationCapability({ isSecureContext: true, navigator: {} }), "unsupported");
  assert.equal(notificationCapability({
    isSecureContext: true, navigator: { serviceWorker: {} }, PushManager() {},
    Notification: { permission: "denied" },
  }), "denied");
});


test("frontend source never uses the shared web-anonymous identity", () => {
  const source = fs.readFileSync(new URL("../app.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("web-anonymous"), false);
});
