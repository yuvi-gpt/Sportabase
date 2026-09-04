const KINDS = new Set(["entity", "story", "claim", "media"]);
const bounded = (value, length) => String(value || "").trim().slice(0, length);

function targetUrl(data) {
  const kind = bounded(data?.target_kind, 16);
  const id = bounded(data?.target_id, 256);
  const url = new URL("./", self.registration.scope);
  if (KINDS.has(kind) && id) {
    url.searchParams.set("target_kind", kind);
    url.searchParams.set("target_id", id);
  }
  const alertId = bounded(data?.alert_id, 128);
  if (alertId) url.hash = `alert=${encodeURIComponent(alertId)}`;
  return url.href;
}

self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data?.json() || {}; } catch (_) { data = {}; }
  const kind = bounded(data.target_kind, 16);
  const safeData = {
    url: targetUrl(data),
    alert_id: bounded(data.alert_id, 128),
    target_kind: KINDS.has(kind) ? kind : "",
    target_id: bounded(data.target_id, 256),
  };
  event.waitUntil(self.registration.showNotification("Sportabase", {
    body: bounded(data.summary, 240) || "New intelligence is available.",
    tag: safeData.alert_id || undefined,
    data: safeData,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const destination = targetUrl(event.notification.data || {});
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    const wanted = new URL(destination);
    for (const client of windows) {
      const current = new URL(client.url);
      if (current.origin === wanted.origin && current.pathname === wanted.pathname) {
        if ("navigate" in client) await client.navigate(destination);
        return client.focus();
      }
    }
    return self.clients.openWindow(destination);
  })());
});
