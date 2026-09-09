import { authHeaders, isPrivatePath } from "./account-client.mjs";
import productConfig from "./product-config.mjs";
import { shouldEmitLandingEvent } from "./analytics-boundary.mjs";
import {
  normalizeArticleIntelligence,
} from "./article-intelligence.mjs";
import {
  canonicalTargetUrl,
  notificationCapability,
  persistentClientId,
  serializePushSubscription,
  urlBase64ToUint8Array,
} from "./web-push-helpers.mjs";


const DEFAULT_API =
  "https://sportabase-api.onrender.com";

const RESOLVE_TIMEOUT_MS = 30000;
const ANALYZE_TIMEOUT_MS = 120000;
const INSIGHT_TIMEOUT_MS = 20000;

let activeAnalysisController = null;
let cricketChart = null;


function getApiBase() {
  const params =
    new URLSearchParams(
      window.location.search
    );

  const override =
    String(
      params.get("api") || ""
    ).trim();

  if (override) {
    try {
      const parsed =
        new URL(override);

      if (
        parsed.protocol === "http:" ||
        parsed.protocol === "https:"
      ) {
        return override.replace(
          /\/+$/,
          ""
        );
      }
    } catch (_) {
      // Ignore invalid development override.
    }
  }

  return DEFAULT_API;
}


const API = getApiBase();

if (shouldEmitLandingEvent(productConfig, location)) {
  void fetch(`${productConfig.apiBase}/product-events/landing`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ platform: "web" }),
    keepalive: true,
  }).catch(() => {});
}


function byId(id) {
  return document.getElementById(id);
}


function clampScore(value) {
  const numeric = Number(value);

  if (!Number.isFinite(numeric)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(
      100,
      Math.round(numeric)
    )
  );
}


function clean(value) {
  return String(
    value ?? ""
  ).trim();
}


function hostnameForUrl(value) {
  try {
    return new URL(value).hostname;
  } catch (_) {
    return clean(value);
  }
}


function stringList(value) {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) =>
      clean(item)
    )
    .filter(Boolean);
}


function getClientId() {
  return persistentClientId(localStorage, crypto);
}


async function fetchJson(
  path,
  {
    method = "GET",
    body = undefined,
    timeoutMs = 30000,
    signal = null,
    privateRequest = false,
  } = {}
) {
  const requiresAuth = privateRequest || isPrivatePath(path);
  const verifiedHeaders = requiresAuth ? await authHeaders() : {};
  const privateClientId = privateRequest ? getClientId() : null;
  if (privateRequest && !privateClientId) {
    throw new Error("Persistent browser storage is required for this private feature.");
  }
  const controller =
    new AbortController();

  let timedOut = false;

  const forwardAbort = () => {
    controller.abort(
      signal?.reason
    );
  };

  if (
    signal &&
    typeof signal.addEventListener ===
      "function"
  ) {
    if (signal.aborted) {
      forwardAbort();
    } else {
      signal.addEventListener(
        "abort",
        forwardAbort,
        {
          once: true,
        }
      );
    }
  }

  const timeout =
    window.setTimeout(
      () => {
        timedOut = true;
        controller.abort();
      },
      timeoutMs
    );

  try {
    const response =
      await fetch(
        `${requiresAuth ? productConfig.apiBase : API}${path}`,
        {
          method,
          headers: {
            ...verifiedHeaders,
            Accept:
              "application/json",
            ...(body !== undefined
              ? {
                  "Content-Type":
                    "application/json",
                }
              : {}),
            ...(privateRequest
              ? { "X-Sportabase-Client-ID": privateClientId }
              : {}),
          },
          body:
            body === undefined
              ? undefined
              : JSON.stringify(
                  body
                ),
          signal:
            controller.signal,
        }
      );

    const text =
      await response.text();

    let data = null;

    try {
      data =
        text
          ? JSON.parse(text)
          : null;
    } catch (_) {
      data = null;
    }

    if (!response.ok) {
      const detail =
        clean(
          data?.detail ||
          data?.message ||
          text
        );

      if (response.status === 429) {
        throw new Error(
          "The analysis quota is temporarily exhausted. Try again after it resets."
        );
      }

      if (response.status === 503) {
        throw new Error(
          "The analysis service is temporarily unavailable."
        );
      }

      throw new Error(
        detail ||
        `Sportabase returned HTTP ${response.status}.`
      );
    }

    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      if (timedOut) {
        throw new Error(
          "The request took too long and was stopped."
        );
      }

      throw error;
    }

    throw error;
  } finally {
    window.clearTimeout(
      timeout
    );

    signal?.removeEventListener?.(
      "abort",
      forwardAbort
    );
  }
}


function setApiState(
  state,
  label
) {
  const element =
    byId("api-state");

  element.classList.remove(
    "is-online",
    "is-offline"
  );

  if (state === "online") {
    element.classList.add(
      "is-online"
    );
  }

  if (state === "offline") {
    element.classList.add(
      "is-offline"
    );
  }

  element.lastChild.textContent =
    ` ${label}`;
}


function setStatus(
  message,
  {
    error = false,
  } = {}
) {
  const element =
    byId("analysis-status");

  element.textContent =
    message;

  element.classList.toggle(
    "is-error",
    Boolean(error)
  );
}


function setList(
  element,
  values,
  fallback
) {
  element.replaceChildren();

  const items =
    values.length
      ? values
      : [fallback];

  for (const item of items) {
    const li =
      document.createElement(
        "li"
      );

    li.textContent =
      item;

    element.appendChild(
      li
    );
  }
}


function renderIntelligence(
  raw
) {
  const card =
    byId(
      "intelligence-card"
    );

  const intelligence =
    normalizeArticleIntelligence(
      raw
    );

  if (!intelligence) {
    card.hidden = true;
    return;
  }

  card.hidden = false;

  card.classList.toggle(
    "is-unavailable",
    intelligence.status ===
      "unavailable"
  );

  byId(
    "intelligence-label"
  ).textContent =
    intelligence.label;

  byId(
    "intelligence-detail"
  ).textContent =
    intelligence.detail;

  byId(
    "intelligence-state"
  ).textContent =
    intelligence.status ===
      "available"
      ? "ASSESSED"
      : "LIMITED";

  byId(
    "corroboration-value"
  ).textContent =
    intelligence
      .corroborationLabel;

  byId(
    "independence-value"
  ).textContent =
    intelligence
      .independenceLabel;

  byId(
    "candidate-count"
  ).textContent =
    String(
      intelligence
        .candidateCount
    );

  byId(
    "verification-pairs"
  ).textContent =
    String(
      intelligence
        .verificationPairs
    );

  byId(
    "intelligence-metrics"
  ).hidden =
    intelligence.status !==
    "available";

  byId(
    "intelligence-note"
  ).textContent =
    intelligence
      .affectsMeritScore
      ? (
          "This evidence signal is included in the displayed Merit Score."
        )
      : (
          "This evidence signal is informational while validation remains active and does not alter the displayed Merit Score."
        );
}


function renderAnalysis(
  data,
  source
) {
  const results =
    byId("results");

  const score =
    clampScore(
      data?.merit_score
    );

  const title =
    clean(
      data?.title
    ) ||
    clean(
      source?.title
    ) ||
    "Analyzed article";

  const articleType =
    clean(
      data?.localized_article_type
    ) ||
    clean(
      data?.article_type_label
    ) ||
    clean(
      data?.article_type
    ) ||
    "Article analysis";

  byId(
    "merit-score"
  ).textContent =
    String(score);

  byId(
    "merit-badge"
  ).textContent =
    clean(data?.badge) ||
    "ANALYZED";

  byId(
    "score-fill"
  ).style.width =
    `${score}%`;

  byId(
    "result-title"
  ).textContent =
    title;

  byId(
    "article-type"
  ).textContent =
    articleType;

  setList(
    byId("summary-list"),
    stringList(
      data?.tldr
    ),
    "No summary was returned."
  );

  const localizedReasons =
    stringList(
      data?.localized_reasons
    );

  setList(
    byId("reason-list"),
    localizedReasons.length
      ? localizedReasons
      : stringList(
          data?.reasons
        ),
    "No score explanation was returned."
  );

  renderIntelligence(
    data?.intelligence
  );

  const finalUrl =
    clean(
      data?.url
    ) ||
    clean(
      source?.normalized_url
    ) ||
    clean(
      source?.url
    );

  byId(
    "source-title"
  ).textContent =
    title;

  byId(
    "source-domain"
  ).textContent =
    hostnameForUrl(
      finalUrl
    );

  const sourceLink =
    byId("source-link");

  sourceLink.href =
    finalUrl || "#";

  results.hidden = false;

  results.scrollIntoView({
    behavior:
      window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches
        ? "auto"
        : "smooth",
    block: "start",
  });
}


async function analyzeArticle() {
  try { await authHeaders(); } catch (error) { setStatus(error.message, { error: true }); return; }
  const input =
    byId("article-url");

  const button =
    byId(
      "analyze-button"
    );

  const url =
    clean(input.value);

  if (!url) {
    setStatus(
      "Paste an article URL first.",
      {
        error: true,
      }
    );

    return;
  }

  try {
    const parsed =
      new URL(url);

    if (
      parsed.protocol !==
        "http:" &&
      parsed.protocol !==
        "https:"
    ) {
      throw new Error();
    }
  } catch (_) {
    setStatus(
      "Enter a complete http:// or https:// article URL.",
      {
        error: true,
      }
    );

    return;
  }

  activeAnalysisController?.abort();

  const controller =
    new AbortController();

  activeAnalysisController =
    controller;

  button.disabled = true;
  button.textContent =
    "Analyzing?";

  byId("results").hidden =
    true;

  try {
    setStatus(
      "Resolving the article and extracting readable text?"
    );

    const resolved =
      await fetchJson(
        "/resolve-content",
        {
          method: "POST",
          body: {
            url,
          },
          timeoutMs:
            RESOLVE_TIMEOUT_MS,
          signal:
            controller.signal,
        }
      );

    if (
      resolved?.source !==
        "article" ||
      resolved?.mode !==
        "article"
    ) {
      throw new Error(
        "That link was not resolved as a readable sports article."
      );
    }

    const content =
      clean(
        resolved?.content
      );

    if (
      content.length < 50
    ) {
      throw new Error(
        "Sportabase could not extract enough readable article text."
      );
    }

    setStatus(
      `Article ready ? ${Number(
        resolved.content_characters ||
        content.length
      ).toLocaleString()} characters ? running intelligence analysis?`
    );

    const analysis =
      await fetchJson(
        "/analyze",
        {
          method: "POST",
          body: {
            title:
              clean(
                resolved.title
              ) ||
              "Untitled article",

            url:
              clean(
                resolved.normalized_url
              ) ||
              url,

            text: content,
            max_bullets: 4,
          },
          timeoutMs:
            ANALYZE_TIMEOUT_MS,
          signal:
            controller.signal,
        }
      );

    if (
      controller.signal.aborted
    ) {
      return;
    }

    renderAnalysis(
      analysis,
      resolved
    );

    setStatus(
      "Analysis complete."
    );
  } catch (error) {
    if (
      error?.name ===
        "AbortError" ||
      controller.signal.aborted
    ) {
      return;
    }

    console.error(
      "[sportabase-web] analysis failed:",
      error
    );

    setStatus(
      clean(
        error?.message
      ) ||
      "Sportabase could not analyze that article.",
      {
        error: true,
      }
    );
  } finally {
    if (
      activeAnalysisController ===
      controller
    ) {
      activeAnalysisController =
        null;

      button.disabled =
        false;

      button.textContent =
        "Analyze";
    }
  }
}


function metricElement(
  label,
  value
) {
  const root =
    document.createElement(
      "div"
    );

  root.className =
    "insight-metric";

  const labelNode =
    document.createElement(
      "span"
    );

  labelNode.textContent =
    label;

  const valueNode =
    document.createElement(
      "strong"
    );

  valueNode.textContent =
    String(value);

  root.append(
    labelNode,
    valueNode
  );

  return root;
}


function renderCricketChart(
  series
) {
  const ChartConstructor =
    window.Chart;

  const canvas =
    byId(
      "cricket-insight-chart"
    );

  if (
    !ChartConstructor ||
    !canvas ||
    !series
  ) {
    return;
  }

  cricketChart?.destroy();

  cricketChart =
    new ChartConstructor(
      canvas.getContext("2d"),
      {
        type: "line",

        data: {
          labels:
            series.labels || [],

          datasets: [
            {
              label:
                "Bowl-first choice rate",
              data:
                series
                  .bowl_first_choice_rate ||
                [],
              borderColor:
                "#78f54a",
              backgroundColor:
                "transparent",
              tension: 0.3,
            },
            {
              label:
                "Chase win rate",
              data:
                series
                  .chase_win_rate ||
                [],
              borderColor:
                "#65cfee",
              backgroundColor:
                "transparent",
              tension: 0.3,
            },
            {
              label:
                "Bat-first win rate",
              data:
                series
                  .bat_first_win_rate ||
                [],
              borderColor:
                "#f4c766",
              backgroundColor:
                "transparent",
              tension: 0.3,
            },
          ],
        },

        options: {
          responsive: true,

          plugins: {
            legend: {
              labels: {
                color:
                  "#c7d0ca",
              },
            },
          },

          scales: {
            x: {
              ticks: {
                color:
                  "#89958d",
              },

              grid: {
                color:
                  "rgba(255,255,255,.05)",
              },
            },

            y: {
              min: 0,
              max: 1,

              ticks: {
                color:
                  "#89958d",
              },

              grid: {
                color:
                  "rgba(255,255,255,.05)",
              },
            },
          },
        },
      }
    );
}


async function loadCricketInsight() {
  const target =
    byId("insight-status");

  try {
    const data =
      await fetchJson(
        "/insights/cricket/ipl/chasing-bias?history_limit=5",
        {
          timeoutMs:
            INSIGHT_TIMEOUT_MS,
        }
      );

    target.replaceChildren();

    const trend =
      data?.trend;

    const latest =
      data?.latest_metrics || {};

    const summary =
      data?.summary || {};

    if (!trend) {
      const copy =
        document.createElement(
          "p"
        );

      copy.className =
        "insight-copy";

      copy.textContent =
        "No active IPL chasing-bias signal right now.";

      target.appendChild(
        copy
      );

      target.appendChild(
        metricElement(
          "MATCHES ANALYZED",
          summary.matches_analyzed ??
            "N/A"
        )
      );

      return;
    }

    const heading =
      document.createElement(
        "div"
      );

    heading.className =
      "insight-heading";

    const title =
      document.createElement(
        "h3"
      );

    title.textContent =
      clean(trend.title) ||
      "Current IPL trend";

    const confidence =
      document.createElement(
        "span"
      );

    confidence.className =
      "secondary-badge";

    confidence.textContent =
      clean(
        trend.confidence
      ) ||
      "OBSERVED";

    heading.append(
      title,
      confidence
    );

    const copy =
      document.createElement(
        "p"
      );

    copy.className =
      "insight-copy";

    copy.textContent =
      clean(
        trend.insight
      );

    const grid =
      document.createElement(
        "div"
      );

    grid.className =
      "insight-grid";

    grid.append(
      metricElement(
        "MATCHES ANALYZED",
        summary.matches_analyzed ??
          "N/A"
      ),

      metricElement(
        "SIGNAL ACTIVE",
        summary
          .current_signal_active
          ? "Yes"
          : "No"
      ),

      metricElement(
        "BOWL-FIRST RATE",
        latest
          .rolling_bowl_first_choice_rate ??
          "N/A"
      ),

      metricElement(
        "CHASE WIN RATE",
        latest
          .rolling_chase_win_rate ??
          "N/A"
      )
    );

    target.append(
      heading,
      copy,
      grid
    );

    renderCricketChart(
      data?.chart_series
    );
  } catch (error) {
    target.replaceChildren();

    const message =
      document.createElement(
        "p"
      );

    message.className =
      "insight-copy";

    message.textContent =
      "Live IPL trend intelligence is unavailable right now.";

    target.appendChild(
      message
    );

    console.warn(
      "[sportabase-web] insight unavailable:",
      error
    );
  }
}


async function checkHealth() {
  try {
    const health =
      await fetchJson(
        "/health",
        {
          timeoutMs: 12000,
        }
      );

    if (health?.ok) {
      setApiState(
        "online",
        "API ONLINE"
      );

      return;
    }

    throw new Error();
  } catch (_) {
    setApiState(
      "offline",
      "API OFFLINE"
    );
  }
}


function initialize() {
  byId(
    "analyze-button"
  ).addEventListener(
    "click",
    analyzeArticle
  );

  byId(
    "article-url"
  ).addEventListener(
    "keydown",
    (event) => {
      if (
        event.key === "Enter"
      ) {
        analyzeArticle();
      }
    }
  );

  checkHealth();
  loadCricketInsight();
  initializeWebPush();
  loadIntelligenceLanding();
}


function setNotificationState(message, { enable = false, disable = false, busy = false } = {}) {
  byId("notification-status").textContent = message;
  const enableButton = byId("enable-notifications");
  const disableButton = byId("disable-notifications");
  enableButton.hidden = !enable;
  enableButton.disabled = busy;
  disableButton.hidden = !disable;
  disableButton.disabled = busy;
}


async function backendSubscriptions() {
  return fetchJson("/notifications/web/subscriptions", { privateRequest: true });
}


async function removeBackendSubscriptions(items) {
  await Promise.all((items || []).map((item) =>
    fetchJson(`/notifications/web/subscriptions/${encodeURIComponent(item.id)}`, {
      method: "DELETE", privateRequest: true,
    })
  ));
}


async function registerBrowserSubscription(subscription, knownBackendItems = null) {
  const response = await fetchJson("/notifications/web/subscriptions", {
    method: "POST", privateRequest: true,
    body: serializePushSubscription(subscription),
  });
  const backend = knownBackendItems === null ? await backendSubscriptions() : { items: knownBackendItems };
  const stale = (backend?.items || []).filter((item) => item.id !== response?.subscription?.id);
  if (stale.length) await removeBackendSubscriptions(stale);
  return response;
}


async function reconcileWebPushState() {
  await authHeaders();
  const capability = notificationCapability(window);
  if (capability === "insecure") {
    setNotificationState("Browser notifications require HTTPS (localhost is allowed for development).");
    return;
  }
  if (capability === "unsupported") {
    setNotificationState("This browser does not support Web Push.");
    return;
  }
  if (!getClientId()) {
    setNotificationState("Persistent browser storage is unavailable, so private notifications cannot be enabled.");
    return;
  }
  if (capability === "denied") {
    setNotificationState("Notification permission is blocked. Change it in browser site settings to continue.");
    return;
  }
  const config = await fetchJson("/notifications/web/config");
  if (!config?.available || !config?.vapid_public_key) {
    setNotificationState("Web Push is not configured on the Sportabase server.");
    return;
  }
  const registration = await navigator.serviceWorker.register("./service-worker.js", { scope: "./" });
  const browserSubscription = await registration.pushManager.getSubscription();
  const backend = await backendSubscriptions();
  if (browserSubscription) {
    await registerBrowserSubscription(browserSubscription, backend?.items || []);
    setNotificationState("Enabled for Watchlist alerts on this browser.", { disable: true });
  } else {
    if (backend?.items?.length) await removeBackendSubscriptions(backend.items);
    setNotificationState("Not enabled. Permission is requested only when you choose Enable.", { enable: true });
  }
}


async function enableWebPush() {
  setNotificationState("Requesting notification permission…", { enable: true, busy: true });
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      setNotificationState(permission === "denied"
        ? "Notification permission was denied or blocked in browser settings."
        : "Notification permission was not granted.", { enable: permission !== "denied" });
      return;
    }
    const config = await fetchJson("/notifications/web/config");
    if (!config?.available) throw new Error("Web Push is not configured on the server.");
    const registration = await navigator.serviceWorker.register("./service-worker.js", { scope: "./" });
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key),
      });
    }
    await registerBrowserSubscription(subscription);
    setNotificationState("Enabled for Watchlist alerts on this browser.", { disable: true });
  } catch (error) {
    setNotificationState(`Could not enable notifications: ${clean(error?.message) || "unknown error"}`, { enable: true });
  }
}


async function disableWebPush() {
  setNotificationState("Disabling browser notifications…", { disable: true, busy: true });
  try {
    const registration = await navigator.serviceWorker.getRegistration("./");
    const browserSubscription = await registration?.pushManager.getSubscription();
    const backend = await backendSubscriptions();
    await removeBackendSubscriptions(backend?.items);
    if (browserSubscription) await browserSubscription.unsubscribe();
    setNotificationState("Disabled. You can enable notifications again at any time.", { enable: true });
  } catch (error) {
    setNotificationState(`Could not fully disable notifications: ${clean(error?.message) || "unknown error"}`, { enable: true });
  }
}


async function initializeWebPush() {
  byId("enable-notifications").addEventListener("click", enableWebPush);
  byId("disable-notifications").addEventListener("click", disableWebPush);
  setNotificationState("Sign in to manage browser notifications.", { enable: true });
}


async function loadIntelligenceLanding() {
  const params = new URLSearchParams(window.location.search);
  const kind = clean(params.get("target_kind"));
  const targetId = clean(params.get("target_id"));
  if (!canonicalTargetUrl(document.baseURI, kind, targetId)) return;
  const landing = byId("intelligence-landing");
  landing.hidden = false;
  byId("landing-title").textContent = `${kind[0].toUpperCase()}${kind.slice(1)} intelligence`;
  byId("landing-status").textContent = `Loading persisted history for ${targetId}…`;
  const alertMatch = /^#alert=([^&]+)$/.exec(window.location.hash);
  const alertId = alertMatch ? decodeURIComponent(alertMatch[1]) : "";
  if (alertId) {
    history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    if (getClientId()) {
      fetchJson(`/watchlists/alerts/${encodeURIComponent(alertId)}/read`, {
        method: "POST", privateRequest: true,
      }).catch(() => {});
    }
  }
  const pathKind = kind === "media" ? "media" : `${kind}s`;
  try {
    const data = await fetchJson(`/intelligence/${pathKind}/${encodeURIComponent(targetId)}/history`);
    byId("landing-status").textContent = "Persisted chronology and evidence context. Chronology is not truth.";
    byId("landing-content").textContent = JSON.stringify(data, null, 2).slice(0, 12000);
    landing.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    byId("landing-status").textContent = `Intelligence history is unavailable: ${clean(error?.message)}`;
  }
}


initialize();

document.addEventListener("sportabase:account-ready", () => { void reconcileWebPushState().catch(error => setNotificationState(error.message)); });
