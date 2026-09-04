import {
  mediaItemIdForUrl,
} from "./persistent-intelligence-core.mjs";

const REQUEST_TIMEOUT_MS = 22000;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatTime(value) {
  const text = String(value || "").trim();
  if (!text) return "Not recorded";
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime())
    ? text
    : parsed.toLocaleString();
}

async function requestJson(apiBase, path) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS
  );

  try {
    const response = await fetch(`${apiBase}${path}`, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = null;
    }
    if (!response.ok) {
      const error = new Error(
        String(payload?.detail || text || `HTTP ${response.status}`)
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
      title:
        String(source.display_name || source.canonical_domain || "Persisted source"),
      subtitle: [source.source_type, source.canonical_domain]
        .filter(Boolean)
        .join(" · "),
      firstSeenAt: source.first_seen_at,
      lastSeenAt: source.last_seen_at,
    };
  }

  const reporter = data?.reporter || {};
  return {
    title: String(reporter.display_name || "Persisted reporter"),
    subtitle: String(reporter.identity_key || "Persisted reporter"),
    firstSeenAt: reporter.first_seen_at,
    lastSeenAt: reporter.last_seen_at,
  };
}

const POLICY_COPY = {
  chronology_is_not_truth:
    "Chronology is descriptive activity, not a truth or credibility score.",
  reporting_volume_is_not_reliability:
    "Reporting volume is not a reliability rating.",
  source_count_is_not_independence:
    "Multiple sources do not automatically represent independent corroboration.",
  dependency_is_not_falsehood:
    "A persisted dependency relationship does not mean the reporting is false.",
  absence_of_verified_independence_is_not_dependence:
    "Missing verified independence evidence is not evidence of dependence.",
  evidence_quantity_is_not_probability:
    "More evidence records do not automatically increase truth probability.",
};

function policyMarkup(policy) {
  return Object.entries(policy || {})
    .filter(([, enabled]) => Boolean(enabled))
    .map(
      ([key]) => `
        <p>
          <i></i>
          ${escapeHtml(POLICY_COPY[key] || key.replaceAll("_", " "))}
        </p>
      `
    )
    .join("");
}

function eventMarkup(event) {
  const detail =
    event?.claim_summary ||
    event?.canonical_text ||
    event?.title ||
    event?.relationship_type ||
    event?.verification_status ||
    "Persisted reporting activity";

  return `
    <article class="sb-rp-event">
      <div>
        <strong>${escapeHtml(humanize(event?.type || "event"))}</strong>
        <small>${escapeHtml(formatTime(event?.occurred_at))}</small>
      </div>
      <p>${escapeHtml(detail)}</p>
    </article>
  `;
}

function countsMarkup(counts) {
  return Object.entries(counts || {})
    .map(
      ([key, value]) => `
        <div class="sb-rp-count">
          <strong>${escapeHtml(value)}</strong>
          <span>${escapeHtml(humanize(key))}</span>
        </div>
      `
    )
    .join("");
}

function relationMarkup(kind, item) {
  const title =
    item?.display_name ||
    item?.canonical_title ||
    item?.canonical_text ||
    item?.title ||
    item?.canonical_domain ||
    `${humanize(kind)} ${item?.id || ""}`;
  const subtitle =
    item?.source_type ||
    item?.identity_key ||
    item?.status ||
    item?.claim_type ||
    item?.mode ||
    "";
  const navigable = kind === "source" || kind === "reporter";

  return `
    <${navigable ? "button" : "div"}
      class="sb-rp-relation"
      ${
        navigable
          ? `type="button" data-sb-rp-kind="${kind}" data-sb-rp-id="${escapeHtml(item?.id)}"`
          : ""
      }
    >
      <span>${escapeHtml(kind.toUpperCase())}</span>
      <strong>${escapeHtml(title)}</strong>
      ${subtitle ? `<small>${escapeHtml(subtitle)}</small>` : ""}
    </${navigable ? "button" : "div"}>
  `;
}

function profileRelations(kind, data) {
  const groups = [
    ["media", data?.media || []],
    ["story", data?.stories || []],
    ["claim", data?.claims || []],
  ];
  if (kind === "source") {
    groups.push(["reporter", data?.reporters || []]);
  } else {
    groups.push(["source", data?.sources || []]);
  }
  return groups
    .flatMap(([relationKind, items]) =>
      items.slice(0, 8).map((item) => relationMarkup(relationKind, item))
    )
    .join("");
}

function createReportingProfilesPanel({ host, apiBase, sourceUrl }) {
  let destroyed = false;
  let attribution = null;

  function renderLoading() {
    host.innerHTML = `
      <section class="sb-rp-card">
        <div class="sb-rp-eyebrow">REPORTING PROFILES</div>
        <p class="sb-rp-muted">Resolving persisted source and reporter attribution…</p>
      </section>
    `;
  }

  function renderSummary() {
    if (destroyed || !attribution) return;
    const items = [
      attribution.sourceId
        ? { kind: "source", id: attribution.sourceId, label: "Source profile" }
        : null,
      attribution.reporterId
        ? { kind: "reporter", id: attribution.reporterId, label: "Reporter profile" }
        : null,
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
          ${items
            .map(
              (item) => `
                <button
                  type="button"
                  class="sb-rp-profile-button"
                  data-sb-rp-kind="${item.kind}"
                  data-sb-rp-id="${escapeHtml(item.id)}"
                >
                  <span>${escapeHtml(item.kind.toUpperCase())}</span>
                  <strong>${escapeHtml(item.label)}</strong>
                  <small>Open persisted history →</small>
                </button>
              `
            )
            .join("")}
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
        <div class="sb-rp-eyebrow">REPORTING PROFILE · ${kind.toUpperCase()}</div>
        <p class="sb-rp-muted">Loading persisted profile…</p>
      </section>
    `;

    try {
      const segment = kind === "source" ? "sources" : "reporters";
      const data = await requestJson(
        apiBase,
        `/intelligence/${segment}/${encodeURIComponent(id)}/history?limit=30`
      );
      if (destroyed) return;
      const identity = profileIdentity(kind, data);
      const relations = profileRelations(kind, data);

      host.innerHTML = `
        <section class="sb-rp-card">
          <button type="button" class="sb-rp-back" data-sb-rp-back>← Reporting profiles</button>
          <div class="sb-rp-head sb-rp-profile-head">
            <div>
              <div class="sb-rp-eyebrow">PERSISTED ${kind.toUpperCase()} PROFILE</div>
              <h3>${escapeHtml(identity.title)}</h3>
              <p class="sb-rp-muted">${escapeHtml(identity.subtitle)}</p>
            </div>
          </div>
          <div class="sb-rp-time-grid">
            <div><span>FIRST SEEN</span><strong>${escapeHtml(formatTime(identity.firstSeenAt))}</strong></div>
            <div><span>LAST SEEN</span><strong>${escapeHtml(formatTime(identity.lastSeenAt))}</strong></div>
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
              ${(data?.events || []).map(eventMarkup).join("") || '<p class="sb-rp-muted">No persisted profile events yet.</p>'}
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
          <button type="button" class="sb-rp-back" data-sb-rp-back>← Reporting profiles</button>
          <div class="sb-rp-eyebrow">REPORTING PROFILE</div>
          <h3>Profile temporarily unavailable</h3>
          <p class="sb-rp-copy">${escapeHtml(error?.message || error)}</p>
        </section>
      `;
      host.querySelector("[data-sb-rp-back]")?.addEventListener("click", renderSummary);
    }
  }

  async function initialize() {
    renderLoading();
    try {
      const mediaId = await mediaItemIdForUrl(sourceUrl);
      const mediaHistory = await requestJson(
        apiBase,
        `/intelligence/media/${encodeURIComponent(mediaId)}/history?limit=1`
      );
      if (destroyed) return;
      attribution = {
        sourceId: String(mediaHistory?.media?.source_id || "").trim(),
        reporterId: String(mediaHistory?.media?.reporter_id || "").trim(),
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
          <p class="sb-rp-copy">${escapeHtml(error?.message || error)}</p>
        </section>
      `;
    }
  }

  void initialize();

  return {
    destroy() {
      destroyed = true;
      host.innerHTML = "";
    },
  };
}

export function createReportingProfilesIntegration({
  root,
  apiBase,
  sourceUrl,
} = {}) {
  if (!root) return { destroy() {} };
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
    if (
      results === activeResults &&
      results.querySelector("[data-sb-reporting-profiles-host]")
    ) {
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
      sourceUrl: sourceUrl || window.location.href,
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
    },
  };
}
