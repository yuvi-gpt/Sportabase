import {
  getSportabaseClientId,
  mediatedFetch,
  SportabaseApiError,
} from "./api.js";

import {
  filterAlertsForTarget,
  historyEventDetails,
  historyIdentity,
  historyPathFor,
  historyPolicyNotes,
  historyRelations,
  mediaItemIdForUrl,
} from "./persistent-intelligence-core.mjs";

import {
  trustedUserAction,
} from "./trusted-events.mjs";

const REQUEST_TIMEOUT_MS = 22000;
const MAX_ALERT_PAGES = 3;
const ALERT_PAGE_LIMIT = 100;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  const text = String(value || "").trim();
  if (!text) return "Not recorded";

  const parsed = new Date(text);
  if (Number.isNaN(parsed.getTime())) {
    return text;
  }

  return parsed.toLocaleString();
}

function humanize(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) =>
      letter.toUpperCase()
    );
}

function errorMessage(error) {
  if (error instanceof SportabaseApiError) {
    return error.message;
  }

  return (
    String(error?.message || error || "").trim() ||
    "Sportabase could not load persistent intelligence."
  );
}

async function requestJson(
  apiBase,
  path,
  {
    method = "GET",
    body = undefined,
    privateRequest = false,
  } = {}
) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(
    () => controller.abort(),
    REQUEST_TIMEOUT_MS
  );

  try {
    const headers = {
      Accept: "application/json",
    };

    if (body !== undefined) {
      headers["Content-Type"] =
        "application/json";
    }

    if (privateRequest) {
      headers["x-sportabase-client-id"] =
        await getSportabaseClientId({
          requirePersistent: true,
        });
    }

    const response = await (privateRequest ? mediatedFetch : fetch)(
      `${apiBase}${path}`,
      {
        method,
        headers,
        body:
          body === undefined
            ? undefined
            : JSON.stringify(body),
        signal: controller.signal,
      }
    );

    const responseText =
      await response.text();

    let payload = null;
    try {
      payload = responseText
        ? JSON.parse(responseText)
        : null;
    } catch {
      payload = null;
    }

    if (!response.ok) {
      const detail = String(
        payload?.detail ||
        payload?.message ||
        responseText ||
        ""
      ).trim();

      throw new SportabaseApiError(
        detail ||
        `Sportabase returned HTTP ${response.status}.`,
        {
          status: response.status,
          details: detail,
        }
      );
    }

    return payload;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new SportabaseApiError(
        "Persistent intelligence request timed out.",
        { status: 408 }
      );
    }

    if (error instanceof SportabaseApiError) {
      throw error;
    }

    throw new SportabaseApiError(
      "Sportabase could not reach the persistent intelligence service.",
      {
        details: String(
          error?.message || error || ""
        ),
      }
    );
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function eventMarkup(event, index) {
  const details = historyEventDetails(event);

  return `
    <article class="sb-pi-event">
      <div class="sb-pi-event-head">
        <span class="sb-pi-event-index">
          ${String(index + 1).padStart(2, "0")}
        </span>

        <div>
          <strong>
            ${escapeHtml(
              humanize(event?.type || "Persisted event")
            )}
          </strong>

          <small>
            ${escapeHtml(
              formatTime(event?.occurred_at)
            )}
          </small>
        </div>
      </div>

      ${
        details.length
          ? `
            <dl class="sb-pi-event-details">
              ${details
                .map(
                  (detail) => `
                    <div>
                      <dt>${escapeHtml(detail.label)}</dt>
                      <dd>${escapeHtml(detail.value)}</dd>
                    </div>
                  `
                )
                .join("")}
            </dl>
          `
          : `
            <p class="sb-pi-event-empty">
              Persisted relationship or analysis event.
            </p>
          `
      }
    </article>
  `;
}

function relationMarkup(relation) {
  return `
    <button
      class="sb-pi-relation"
      type="button"
      data-sb-pi-open-kind="${escapeHtml(relation.kind)}"
      data-sb-pi-open-id="${escapeHtml(relation.id)}"
    >
      <span>
        ${escapeHtml(relation.kind.toUpperCase())}
      </span>

      <strong>
        ${escapeHtml(relation.title)}
      </strong>

      ${
        relation.subtitle
          ? `<small>${escapeHtml(relation.subtitle)}</small>`
          : ""
      }
    </button>
  `;
}

function activityMarkup(activity) {
  if (!activity) return "";

  const alerts = activity.alerts || [];

  return `
    <section class="sb-pi-section sb-pi-activity-section">
      <div class="sb-pi-section-head">
        <div>
          <span>WATCH ACTIVITY</span>
          <h4>Recent persisted changes</h4>
        </div>

        <strong>
          ${alerts.length}
        </strong>
      </div>

      <p class="sb-pi-note">
        Reconciliation read the persisted discovery ledger only.
        It did not call Gemini or a notification provider.
      </p>

      ${
        alerts.length
          ? `
            <div class="sb-pi-alert-list">
              ${alerts
                .slice(0, 10)
                .map(
                  (alert) => `
                    <article class="sb-pi-alert ${
                      alert.read_at ? "" : "is-unread"
                    }">
                      <div>
                        <span>
                          ${escapeHtml(
                            humanize(alert.event_type)
                          )}
                        </span>
                        ${
                          alert.read_at
                            ? ""
                            : "<b>UNREAD</b>"
                        }
                      </div>

                      <p>
                        ${escapeHtml(alert.summary)}
                      </p>

                      <small>
                        Occurred ${escapeHtml(
                          formatTime(alert.occurred_at)
                        )}
                        · detected ${escapeHtml(
                          formatTime(alert.detected_at)
                        )}
                      </small>
                    </article>
                  `
                )
                .join("")}
            </div>
          `
          : `
            <div class="sb-pi-empty-inline">
              ${
                activity.truncated
                  ? `No matching activity was found in the first ${
                      activity.pagesScanned * ALERT_PAGE_LIMIT
                    } recent inbox records.`
                  : "No alert activity has been persisted for this watched object yet."
              }
            </div>
          `
      }

      <div class="sb-pi-reconcile-meta">
        Reconcile result · ${activity.newAlerts} new alert${
          activity.newAlerts === 1 ? "" : "s"
        } across ${activity.watchesChecked} watch${
          activity.watchesChecked === 1 ? "" : "es"
        } checked.
      </div>
    </section>
  `;
}

function createPanel({
  host,
  apiBase,
  sourceUrl,
  mode,
}) {
  let destroyed = false;
  let loading = false;
  let current = null;
  let watchedKeys = new Set();
  let privateStateError = "";

  function targetKey(target) {
    return `${target.kind}:${target.id}`;
  }

  function isWatching(target) {
    return watchedKeys.has(
      targetKey(target)
    );
  }

  function renderLoading(label) {
    if (destroyed) return;

    host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-loading">
          <span class="sb-pi-spinner"></span>
          <div>
            <strong>${escapeHtml(label)}</strong>
            <small>
              Reading only persisted Sportabase intelligence.
            </small>
          </div>
        </div>
      </section>
    `;
  }

  function renderMissing(message) {
    if (destroyed) return;

    host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-eyebrow">
          PERSISTENT INTELLIGENCE
        </div>

        <h3>Canonical history is not ready yet</h3>

        <p class="sb-pi-copy">
          ${escapeHtml(message)}
        </p>

        <button
          class="sb-pi-button sb-pi-button-secondary"
          type="button"
          data-sb-pi-retry
        >
          Check persisted record again
        </button>
      </section>
    `;

    host
      .querySelector("[data-sb-pi-retry]")
      ?.addEventListener("click", () => {
        void openInitialMedia();
      });
  }

  function renderError(message) {
    if (destroyed) return;

    host.innerHTML = `
      <section class="sb-pi-card is-error">
        <div class="sb-pi-eyebrow">
          PERSISTENT INTELLIGENCE
        </div>

        <h3>History temporarily unavailable</h3>

        <p class="sb-pi-copy">
          ${escapeHtml(message)}
        </p>

        <button
          class="sb-pi-button sb-pi-button-secondary"
          type="button"
          data-sb-pi-retry
        >
          Retry
        </button>
      </section>
    `;

    host
      .querySelector("[data-sb-pi-retry]")
      ?.addEventListener("click", () => {
        void openInitialMedia();
      });
  }

  function bindActions() {
    if (!current || destroyed) return;

    host
      .querySelectorAll("[data-sb-pi-open-kind]")
      .forEach((button) => {
        button.addEventListener("click", () => {
          const kind = button.getAttribute(
            "data-sb-pi-open-kind"
          );
          const id = button.getAttribute(
            "data-sb-pi-open-id"
          );

          if (kind && id) {
            void openTarget(kind, id);
          }
        });
      });

    host
      .querySelector("[data-sb-pi-watch]")
      ?.addEventListener("click", trustedUserAction(() => {
        void addWatch();
      }));

    host
      .querySelector("[data-sb-pi-activity]")
      ?.addEventListener("click", trustedUserAction(() => {
        void checkActivity();
      }));

    host
      .querySelector("[data-sb-pi-more]")
      ?.addEventListener("click", () => {
        void loadMoreHistory();
      });

    host
      .querySelector("[data-sb-pi-back-media]")
      ?.addEventListener("click", () => {
        void openInitialMedia();
      });

    host
      .querySelector("[data-sb-pi-original]")
      ?.addEventListener("click", () => {
        const url = current?.identity?.canonicalUrl;
        if (url) {
          window.open(
            url,
            "_blank",
            "noopener,noreferrer"
          );
        }
      });
  }

  function renderCurrent() {
    if (!current || destroyed) return;

    const {
      target,
      history,
      identity,
      relations,
      activity,
    } = current;

    const watching = isWatching(target);
    const policyNotes =
      historyPolicyNotes(history.policy);

    host.innerHTML = `
      <section class="sb-pi-card">
        <div class="sb-pi-head">
          <div>
            <div class="sb-pi-eyebrow">
              PERSISTENT INTELLIGENCE
            </div>

            <h3>${escapeHtml(identity.title)}</h3>

            <p class="sb-pi-subtitle">
              ${escapeHtml(
                identity.subtitle ||
                humanize(target.kind)
              )}
            </p>
          </div>

          <span class="sb-pi-kind">
            ${escapeHtml(target.kind.toUpperCase())}
          </span>
        </div>

        <div class="sb-pi-time-grid">
          <div>
            <span>FIRST SEEN</span>
            <strong>${escapeHtml(
              formatTime(identity.firstSeenAt)
            )}</strong>
          </div>

          <div>
            <span>LAST SEEN</span>
            <strong>${escapeHtml(
              formatTime(identity.lastSeenAt)
            )}</strong>
          </div>
        </div>

        <div class="sb-pi-actions">
          <button
            class="sb-pi-button ${
              watching
                ? "sb-pi-button-active"
                : "sb-pi-button-primary"
            }"
            type="button"
            data-sb-pi-watch
            ${watching ? "disabled" : ""}
          >
            ${
              watching
                ? "Watching future changes"
                : "Watch future changes"
            }
          </button>

          <button
            class="sb-pi-button sb-pi-button-secondary"
            type="button"
            data-sb-pi-activity
            ${watching ? "" : "disabled"}
          >
            Check watch activity
          </button>

          ${
            identity.canonicalUrl
              ? `
                <button
                  class="sb-pi-button sb-pi-button-secondary"
                  type="button"
                  data-sb-pi-original
                >
                  Open original ↗
                </button>
              `
              : ""
          }

          ${
            target.kind !== "media"
              ? `
                <button
                  class="sb-pi-button sb-pi-button-quiet"
                  type="button"
                  data-sb-pi-back-media
                >
                  Back to analyzed media
                </button>
              `
              : ""
          }
        </div>

        ${
          privateStateError
            ? `
              <p class="sb-pi-private-warning">
                History remains public, but watch controls are unavailable: ${escapeHtml(
                  privateStateError
                )}
              </p>
            `
            : ""
        }

        <section class="sb-pi-policy">
          <span>INTERPRETATION BOUNDARIES</span>
          ${
            policyNotes.length
              ? policyNotes
                  .map(
                    (note) => `
                      <p>
                        <i></i>
                        ${escapeHtml(note)}
                      </p>
                    `
                  )
                  .join("")
              : `
                <p>
                  <i></i>
                  Persisted chronology is descriptive context, not a truth score.
                </p>
              `
          }
        </section>

        <section class="sb-pi-section">
          <div class="sb-pi-section-head">
            <div>
              <span>PERSISTED GRAPH</span>
              <h4>Related intelligence</h4>
            </div>
            <strong>${relations.length}</strong>
          </div>

          ${
            relations.length
              ? `
                <div class="sb-pi-relations">
                  ${relations
                    .map(relationMarkup)
                    .join("")}
                </div>
              `
              : `
                <div class="sb-pi-empty-inline">
                  No related canonical objects are exposed by this history response yet.
                </div>
              `
          }
        </section>

        <section class="sb-pi-section">
          <div class="sb-pi-section-head">
            <div>
              <span>DOMAIN CHRONOLOGY</span>
              <h4>Persisted history</h4>
            </div>
            <strong>${history.events?.length || 0}</strong>
          </div>

          <p class="sb-pi-note">
            Ordering reflects domain occurrence time. It does not imply truth, credibility, novelty, or independent corroboration.
          </p>

          ${
            history.events?.length
              ? `
                <div class="sb-pi-events">
                  ${history.events
                    .map(eventMarkup)
                    .join("")}
                </div>
              `
              : `
                <div class="sb-pi-empty-inline">
                  No persisted history events are exposed for this object yet.
                </div>
              `
          }

          ${
            history.pagination?.next_cursor
              ? `
                <button
                  class="sb-pi-button sb-pi-button-secondary sb-pi-more"
                  type="button"
                  data-sb-pi-more
                >
                  Load more history
                </button>
              `
              : ""
          }
        </section>

        ${activityMarkup(activity)}
      </section>
    `;

    bindActions();
  }

  async function loadWatchState() {
    privateStateError = "";

    try {
      const response = await requestJson(
        apiBase,
        "/watchlists",
        { privateRequest: true }
      );

      watchedKeys = new Set(
        (response?.items || []).map(
          (item) =>
            `${item.target_kind}:${item.target_id}`
        )
      );
    } catch (error) {
      privateStateError = errorMessage(error);
      watchedKeys = new Set();
    }
  }

  async function openTarget(kind, id) {
    if (loading || destroyed) return;

    loading = true;
    renderLoading(
      `Loading ${humanize(kind)} history…`
    );

    try {
      const history = await requestJson(
        apiBase,
        historyPathFor(kind, id, {
          limit: 30,
        })
      );

      if (destroyed) return;

      const target = { kind, id };
      current = {
        target,
        history,
        identity: historyIdentity(
          kind,
          history
        ),
        relations: historyRelations(
          kind,
          history
        ),
        activity: null,
      };

      renderCurrent();
    } catch (error) {
      if (destroyed) return;

      if (error?.status === 404) {
        const modeCopy =
          mode === "video"
            ? "The video readout is available, but its canonical media history has not been persisted yet. Browser-capture persistence may still be processing."
            : "The article readout is available, but Sportabase does not currently expose a canonical media-history record for this URL.";

        renderMissing(modeCopy);
      } else {
        renderError(errorMessage(error));
      }
    } finally {
      loading = false;
    }
  }

  async function openInitialMedia() {
    if (loading || destroyed) return;

    try {
      const mediaId =
        await mediaItemIdForUrl(sourceUrl);
      await openTarget("media", mediaId);
    } catch (error) {
      renderError(errorMessage(error));
    }
  }

  async function addWatch() {
    if (
      !current ||
      loading ||
      isWatching(current.target)
    ) {
      return;
    }

    loading = true;

    try {
      const response = await requestJson(
        apiBase,
        "/watchlists",
        {
          method: "POST",
          privateRequest: true,
          body: {
            target_kind:
              current.target.kind,
            target_id:
              current.target.id,
          },
        }
      );

      watchedKeys.add(
        targetKey(current.target)
      );

      if (
        response?.created === false
      ) {
        watchedKeys.add(
          targetKey(current.target)
        );
      }

      privateStateError = "";
      renderCurrent();
    } catch (error) {
      privateStateError =
        errorMessage(error);
      renderCurrent();
    } finally {
      loading = false;
    }
  }

  async function loadMoreHistory() {
    if (
      !current ||
      loading ||
      !current.history?.pagination
        ?.next_cursor
    ) {
      return;
    }

    loading = true;

    try {
      const next = await requestJson(
        apiBase,
        historyPathFor(
          current.target.kind,
          current.target.id,
          {
            limit: 30,
            cursor:
              current.history.pagination
                .next_cursor,
          }
        )
      );

      current.history = {
        ...current.history,
        events: [
          ...(current.history.events || []),
          ...(next?.events || []),
        ],
        pagination:
          next?.pagination ||
          current.history.pagination,
      };

      current.relations =
        historyRelations(
          current.target.kind,
          current.history
        );

      renderCurrent();
    } catch (error) {
      privateStateError =
        errorMessage(error);
      renderCurrent();
    } finally {
      loading = false;
    }
  }

  async function checkActivity() {
    if (
      !current ||
      loading ||
      !isWatching(current.target)
    ) {
      return;
    }

    loading = true;

    try {
      const reconcile = await requestJson(
        apiBase,
        "/watchlists/alerts/reconcile",
        {
          method: "POST",
          privateRequest: true,
        }
      );

      let cursor = "";
      let pagesScanned = 0;
      let truncated = false;
      const alerts = [];

      while (
        pagesScanned < MAX_ALERT_PAGES
      ) {
        const params =
          new URLSearchParams();
        params.set(
          "unread_only",
          "false"
        );
        params.set(
          "limit",
          String(ALERT_PAGE_LIMIT)
        );
        if (cursor) {
          params.set("cursor", cursor);
        }

        const page = await requestJson(
          apiBase,
          `/watchlists/alerts?${params.toString()}`,
          { privateRequest: true }
        );

        alerts.push(
          ...(page?.items || [])
        );
        pagesScanned += 1;

        cursor = String(
          page?.pagination?.next_cursor ||
          ""
        );

        if (!cursor) {
          break;
        }
      }

      truncated = Boolean(cursor);

      current.activity = {
        alerts: filterAlertsForTarget(
          alerts,
          current.target
        ),
        pagesScanned,
        truncated,
        newAlerts: Number(
          reconcile?.new_alerts || 0
        ),
        watchesChecked: Number(
          reconcile?.watches_checked || 0
        ),
      };

      privateStateError = "";
      renderCurrent();
    } catch (error) {
      privateStateError =
        errorMessage(error);
      renderCurrent();
    } finally {
      loading = false;
    }
  }

  void loadWatchState()
    .finally(() => {
      if (!destroyed) {
        void openInitialMedia();
      }
    });

  return {
    destroy() {
      destroyed = true;
      host.innerHTML = "";
    },
  };
}

export function createPersistentIntelligenceIntegration({
  root,
  apiBase,
  sourceUrl,
  mode,
} = {}) {
  if (!root) {
    return {
      destroy() {},
    };
  }

  const normalizedApiBase = String(
    apiBase ||
    "https://sportabase-api.onrender.com"
  ).replace(/\/+$/, "");

  let activePanel = null;
  let activeResults = null;

  function sync() {
    const results =
      root.querySelector(
        ".sb-article-results, .sb-video-results"
      );

    if (!results) {
      if (activePanel) {
        activePanel.destroy();
        activePanel = null;
        activeResults = null;
      }
      return;
    }

    if (
      results === activeResults &&
      results.querySelector(
        "[data-sb-persistent-intelligence-host]"
      )
    ) {
      return;
    }

    activePanel?.destroy();

    const host =
      document.createElement("div");

    host.setAttribute(
      "data-sb-persistent-intelligence-host",
      ""
    );

    const actions =
      results.querySelector(
        ".sb-article-result-actions, .sb-result-actions"
      );

    if (actions?.parentNode === results) {
      results.insertBefore(
        host,
        actions
      );
    } else {
      results.append(host);
    }

    activeResults = results;
    activePanel = createPanel({
      host,
      apiBase: normalizedApiBase,
      sourceUrl:
        sourceUrl || window.location.href,
      mode,
    });
  }

  const observer = new MutationObserver(sync);
  observer.observe(root, {
    childList: true,
    subtree: true,
  });

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
