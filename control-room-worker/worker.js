const RENDER_ORIGIN = "https://sportabase-control-room-origin.onrender.com";
const CONTROL_ROOM_PREFIX = "/admin/control-room";
const SESSION_PATH = `${CONTROL_ROOM_PREFIX}/session`;
const AI_USAGE_PATH = `${CONTROL_ROOM_PREFIX}/ai-usage?days=7`;
const PROVENANCE_HEADER = "X-Sportabase-Origin-Provenance";

function noStoreHeaders(extra = {}) {
  return {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    ...extra,
  };
}

function textResponse(body, status) {
  return new Response(body, {
    status,
    headers: noStoreHeaders({
      "Content-Type": "text/plain; charset=utf-8",
    }),
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function validateGatewayContext(request, env) {
  const originSecret = env.ORIGIN_PROVENANCE_SECRET;
  if (typeof originSecret !== "string" || originSecret.length < 32) {
    return { error: textResponse("Control Room gateway unavailable", 503) };
  }

  const accessJwt = request.headers.get("Cf-Access-Jwt-Assertion");
  if (!accessJwt) {
    return { error: textResponse("Forbidden", 403) };
  }

  return { originSecret, accessJwt };
}

function buildOriginRequest(request, pathname, search, context) {
  const originUrl = new URL(RENDER_ORIGIN);
  originUrl.pathname = pathname;
  originUrl.search = search;

  const headers = new Headers(request.headers);
  headers.delete(PROVENANCE_HEADER);
  headers.set(PROVENANCE_HEADER, context.originSecret);
  headers.set("Cf-Access-Jwt-Assertion", context.accessJwt);
  headers.delete("Cookie");

  return {
    url: originUrl.toString(),
    init: {
      method: request.method,
      headers,
      body:
        request.method === "GET" || request.method === "HEAD"
          ? undefined
          : request.body,
      redirect: "manual",
    },
  };
}

async function fetchOrigin(request, pathname, search, context) {
  const originRequest = buildOriginRequest(
    request,
    pathname,
    search,
    context,
  );

  try {
    return await fetch(originRequest.url, originRequest.init);
  } catch {
    return null;
  }
}

function isoFromEpoch(value) {
  return Number.isFinite(value)
    ? new Date(value * 1000).toISOString()
    : "Unavailable";
}

function numericValue(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function formatInt(value) {
  return Math.max(0, Math.trunc(numericValue(value))).toLocaleString("en-US");
}

function formatPercent(value) {
  return `${numericValue(value).toFixed(2)}%`;
}

function formatUsd(value) {
  return `$${numericValue(value).toFixed(6)}`;
}

function metricStateClass(value, dangerWhenPositive = false) {
  const numeric = numericValue(value);
  if (dangerWhenPositive && numeric > 0) {
    return "warn";
  }
  return "ok";
}

function renderFailureRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return '<tr><td colspan="4" class="empty">No provider failures recorded in the current usage day.</td></tr>';
  }

  return rows
    .map((row) => `
      <tr>
        <td>${escapeHtml(row?.mode || "unknown")}</td>
        <td>${escapeHtml(row?.failure_type || "unknown")}</td>
        <td>${escapeHtml(row?.status_code || "0")}</td>
        <td>${formatInt(row?.count)}</td>
      </tr>`)
    .join("");
}

function renderBreakdownRows(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return '<tr><td colspan="7" class="empty">No provider activity recorded in the current usage day.</td></tr>';
  }

  return rows
    .map((row) => `
      <tr>
        <td>${escapeHtml(row?.mode || "unknown")}</td>
        <td>${escapeHtml(row?.model || "unknown")}</td>
        <td>${escapeHtml(row?.status || "unknown")}</td>
        <td>${formatInt(row?.request_count)}</td>
        <td>${formatInt(row?.prompt_tokens)}</td>
        <td>${formatInt(row?.output_tokens)}</td>
        <td>${formatInt(row?.thought_tokens)}</td>
      </tr>`)
    .join("");
}

function renderDashboard(session, usage, usageError = "") {
  const principal = session?.principal ?? {};
  const methods = Array.isArray(principal.auth_methods)
    ? principal.auth_methods.join(", ")
    : "Unavailable";

  const authenticatedAt = isoFromEpoch(principal.authenticated_at_epoch);
  const expiresAt = isoFromEpoch(principal.expires_at_epoch);

  const capacity = usage?.capacity ?? {};
  const summary = usage?.summary ?? {};
  const metrics = usage?.metrics ?? {};
  const windowInfo = usage?.window ?? {};

  const usageHealthy = Boolean(usage && !usageError);
  const usageStatusText = usageHealthy ? "Live upstream" : "Unavailable";
  const providerAttempts = formatInt(summary.provider_attempts);
  const remainingCalls = capacity.remaining_calls === null || capacity.remaining_calls === undefined
    ? "Unbounded"
    : formatInt(capacity.remaining_calls);
  const capacityUsed = capacity.capacity_used_percent === null || capacity.capacity_used_percent === undefined
    ? "N/A"
    : formatPercent(capacity.capacity_used_percent);
  const failureCount = formatInt(summary.failed_calls);
  const totalTokens = formatInt(summary.total_tokens);
  const averageLatency = `${formatInt(summary.average_latency_ms)} ms`;
  const successRate = formatPercent(metrics.success_rate_percent);
  const cacheHitRate = formatPercent(metrics.cache_hit_rate_percent);
  const estimatedCost = formatUsd(metrics.estimated_paid_cost_usd);
  const usageDay = usage?.usage_day_utc || "Unavailable";
  const generatedAt = usage?.upstream_generated_at || "Unavailable";
  const upstreamSource = usage?.source || "Unavailable";
  const requestWindow = Number.isFinite(Number(windowInfo.requested_days))
    ? `${formatInt(windowInfo.requested_days)} days`
    : "Unavailable";

  const usageBanner = usageHealthy
    ? `<div class="status-line"><span class="dot"></span> Access verified · AI telemetry live</div>`
    : `<div class="status-line warn"><span class="dot warn-dot"></span> Access verified · AI telemetry unavailable</div>`;

  const aiUsageBody = usageHealthy
    ? `
        <section id="ai-quota">
          <div class="section-heading">
            <div><h2>AI &amp; Quota</h2><p>Live provider telemetry bridged from the operational Sportabase API.</p></div>
            <span class="live-badge">Live upstream</span>
          </div>

          <div class="metrics ai-metrics">
            <div class="metric">
              <div class="metric-label">Provider attempts</div>
              <div class="metric-value">${providerAttempts}</div>
              <div class="metric-meta">Usage day ${escapeHtml(usageDay)}</div>
            </div>
            <div class="metric">
              <div class="metric-label">Calls remaining</div>
              <div class="metric-value ${capacity.exhausted ? "warn" : "ok"}">${escapeHtml(remainingCalls)}</div>
              <div class="metric-meta">${escapeHtml(capacityUsed)} of configured daily capacity used.</div>
            </div>
            <div class="metric">
              <div class="metric-label">Total tokens</div>
              <div class="metric-value">${totalTokens}</div>
              <div class="metric-meta">Prompt + output + thought tokens recorded upstream.</div>
            </div>
            <div class="metric">
              <div class="metric-label">Provider failures</div>
              <div class="metric-value ${metricStateClass(summary.failed_calls, true)}">${failureCount}</div>
              <div class="metric-meta">${escapeHtml(successRate)} successful completed calls.</div>
            </div>
          </div>

          <div class="two-col">
            <section class="panel">
              <div class="panel-head"><strong>Provider health</strong><span>${escapeHtml(usageStatusText)}</span></div>
              <table class="table">
                <tr><td>Global daily cap</td><td>${formatInt(capacity.global_daily_call_cap)}</td></tr>
                <tr><td>Average latency</td><td>${escapeHtml(averageLatency)}</td></tr>
                <tr><td>Cache hit rate</td><td>${escapeHtml(cacheHitRate)}</td></tr>
                <tr><td>Estimated paid cost</td><td>${escapeHtml(estimatedCost)}</td></tr>
                <tr><td>Unique clients</td><td>${formatInt(summary.unique_clients)}</td></tr>
                <tr><td>In-flight joins</td><td>${formatInt(summary.inflight_joins)}</td></tr>
              </table>
            </section>

            <section class="panel">
              <div class="panel-head"><strong>Telemetry source</strong><span>Server-to-server</span></div>
              <table class="table">
                <tr><td>Source</td><td>${escapeHtml(upstreamSource)}</td></tr>
                <tr><td>Generated at</td><td>${escapeHtml(generatedAt)}</td></tr>
                <tr><td>Usage day UTC</td><td>${escapeHtml(usageDay)}</td></tr>
                <tr><td>Window</td><td>${escapeHtml(requestWindow)}</td></tr>
                <tr><td>Window start</td><td>${escapeHtml(windowInfo.start_day_utc || "Unavailable")}</td></tr>
                <tr><td>Window end</td><td>${escapeHtml(windowInfo.end_day_utc || "Unavailable")}</td></tr>
              </table>
            </section>
          </div>

          <section class="panel">
            <div class="panel-head"><strong>Today by model / mode</strong><span>${formatInt(summary.records)} ledger records</span></div>
            <div class="table-scroll">
              <table class="table data-table">
                <thead>
                  <tr><th>Mode</th><th>Model</th><th>Status</th><th>Requests</th><th>Prompt</th><th>Output</th><th>Thought</th></tr>
                </thead>
                <tbody>${renderBreakdownRows(usage?.today_breakdown)}</tbody>
              </table>
            </div>
          </section>

          <section class="panel">
            <div class="panel-head"><strong>Failure breakdown</strong><span>${failureCount} failed calls</span></div>
            <div class="table-scroll">
              <table class="table data-table">
                <thead><tr><th>Mode</th><th>Failure type</th><th>Status</th><th>Count</th></tr></thead>
                <tbody>${renderFailureRows(usage?.failure_breakdown)}</tbody>
              </table>
            </div>
          </section>
        </section>`
    : `
        <section id="ai-quota">
          <div class="section-heading">
            <div><h2>AI &amp; Quota</h2><p>Provider telemetry could not be loaded. Security/session status remains independently verified.</p></div>
            <span class="degraded-badge">Unavailable</span>
          </div>
          <section class="panel degraded-panel">
            <div class="panel-head"><strong>Telemetry bridge</strong><span>Degraded</span></div>
            <div class="degraded-copy">${escapeHtml(usageError || "Upstream telemetry unavailable")}</div>
          </section>
        </section>`;

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sportabase Control Room</title>
  <style>
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #090b0f;
      color: #e7ebf2;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; min-height: 100vh; background: #090b0f; }
    a { color: inherit; text-decoration: none; }
    .app { min-height: 100vh; display: grid; grid-template-columns: 220px 1fr; }
    .sidebar {
      border-right: 1px solid #222733;
      background: #0c0f14;
      padding: 18px 14px;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    .brand { display: flex; align-items: center; gap: 10px; padding: 4px 8px 18px; border-bottom: 1px solid #202530; }
    .mark { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid #343b49; font-size: 12px; font-weight: 800; }
    .brand strong { font-size: 13px; letter-spacing: .01em; }
    .brand small { display: block; margin-top: 2px; color: #747e8e; font-size: 10px; text-transform: uppercase; letter-spacing: .12em; }
    nav { margin-top: 18px; }
    .nav-item { display: flex; justify-content: space-between; align-items: center; padding: 9px 10px; margin: 2px 0; color: #8f98a7; font-size: 12px; border-left: 2px solid transparent; }
    .nav-item:hover { color: #dce3ed; background: #121720; }
    .nav-item.active { color: #eef2f7; background: #151a22; border-left-color: #69d9ad; }
    .nav-item .pending { color: #555f6f; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
    .nav-item .live { color: #78e3b7; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
    .side-footer { position: absolute; left: 14px; right: 14px; bottom: 18px; border-top: 1px solid #202530; padding: 14px 8px 0; color: #626d7d; font-size: 10px; line-height: 1.5; }
    .main { min-width: 0; }
    .topbar { min-height: 62px; border-bottom: 1px solid #222733; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 24px; background: #0b0e13; position: sticky; top: 0; z-index: 5; }
    .title { font-size: 14px; font-weight: 700; }
    .subtle { color: #747e8e; font-size: 11px; }
    .status-line { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #9aa4b2; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #54d9a5; }
    .warn-dot { background: #e2b96f; }
    .content { padding: 22px 24px 36px; max-width: 1280px; }
    .section-heading { display: flex; align-items: end; justify-content: space-between; gap: 18px; margin-bottom: 12px; }
    .section-heading h1, .section-heading h2 { margin: 0; font-size: 15px; letter-spacing: .01em; }
    .section-heading p { margin: 4px 0 0; color: #707a89; font-size: 11px; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); border: 1px solid #242a35; background: #0d1117; margin-bottom: 22px; }
    .metric { min-height: 104px; padding: 15px; border-right: 1px solid #242a35; }
    .metric:last-child { border-right: 0; }
    .metric-label { color: #6f7988; font-size: 9px; text-transform: uppercase; letter-spacing: .11em; }
    .metric-value { margin-top: 14px; font-size: 17px; font-weight: 700; overflow-wrap: anywhere; }
    .metric-meta { margin-top: 6px; color: #687281; font-size: 10px; line-height: 1.5; }
    .ok { color: #78e3b7; }
    .warn { color: #e2b96f; }
    .panel { border: 1px solid #242a35; background: #0d1117; margin-bottom: 22px; }
    .panel-head { padding: 12px 14px; border-bottom: 1px solid #242a35; display: flex; justify-content: space-between; gap: 14px; align-items: center; }
    .panel-head strong { font-size: 11px; text-transform: uppercase; letter-spacing: .09em; }
    .panel-head span { color: #687281; font-size: 10px; }
    .table { width: 100%; border-collapse: collapse; }
    .table td, .table th { padding: 11px 14px; border-bottom: 1px solid #1e232c; font-size: 11px; vertical-align: top; text-align: left; }
    .table tr:last-child td { border-bottom: 0; }
    .table td:first-child { width: 190px; color: #747e8e; }
    .data-table th { color: #687281; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; font-weight: 600; }
    .data-table td:first-child { width: auto; color: #cbd2dc; }
    .empty { color: #626d7d !important; text-align: center !important; padding: 20px 14px !important; }
    .table-scroll { overflow-x: auto; }
    .two-col { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }
    .live-badge, .degraded-badge { border: 1px solid #2a303b; padding: 4px 7px; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
    .live-badge { color: #78e3b7; border-color: #315143; }
    .degraded-badge { color: #e2b96f; border-color: #584a31; }
    .degraded-panel { border-color: #584a31; }
    .degraded-copy { padding: 18px 14px; color: #a99470; font-size: 11px; }
    #ai-quota { scroll-margin-top: 84px; margin-top: 2px; }
    .placeholder-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); border-top: 1px solid #242a35; border-left: 1px solid #242a35; }
    .placeholder { min-height: 120px; padding: 14px; border-right: 1px solid #242a35; border-bottom: 1px solid #242a35; background: #0d1117; }
    .placeholder strong { font-size: 11px; }
    .placeholder p { margin: 8px 0 0; color: #687281; font-size: 10px; line-height: 1.5; }
    .tag { display: inline-block; margin-top: 14px; color: #788292; border: 1px solid #2a303b; padding: 3px 6px; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
    code { color: #b7c0ce; }
    @media (max-width: 900px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; border-right: 0; border-bottom: 1px solid #222733; }
      nav { display: none; }
      .side-footer { display: none; }
      .topbar { position: static; }
      .metrics { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .metric:nth-child(2) { border-right: 0; }
      .metric:nth-child(-n+2) { border-bottom: 1px solid #242a35; }
      .placeholder-grid, .two-col { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .topbar { align-items: flex-start; flex-direction: column; padding: 14px 16px; }
      .content { padding: 18px 16px 28px; }
      .metrics { grid-template-columns: 1fr; }
      .metric { border-right: 0; border-bottom: 1px solid #242a35; }
      .metric:last-child { border-bottom: 0; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand">
        <div class="mark">SB</div>
        <div><strong>Sportabase</strong><small>Control Room</small></div>
      </div>
      <nav aria-label="Control Room sections">
        <a class="nav-item active" href="#overview"><span>Overview</span></a>
        <div class="nav-item"><span>Pipeline</span><span class="pending">Later</span></div>
        <a class="nav-item" href="#ai-quota"><span>AI &amp; Quota</span><span class="${usageHealthy ? "live" : "pending"}">${usageHealthy ? "Live" : "Degraded"}</span></a>
        <div class="nav-item"><span>Sources</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>Jobs</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>Intelligence</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>Errors</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>Security</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>Releases</span><span class="pending">Later</span></div>
      </nav>
      <div class="side-footer">Owner-only surface<br><code>${SESSION_PATH}</code></div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <div class="title">Overview</div>
          <div class="subtle">Operational status, secured session and live AI telemetry</div>
        </div>
        ${usageBanner}
      </header>

      <div class="content">
        <section id="overview">
          <div class="section-heading">
            <div><h1>System status</h1><p>Only live, verified signals are shown as healthy.</p></div>
          </div>
          <div class="metrics">
            <div class="metric">
              <div class="metric-label">Control Room</div>
              <div class="metric-value ok">Healthy</div>
              <div class="metric-meta">Session endpoint returned an authenticated principal.</div>
            </div>
            <div class="metric">
              <div class="metric-label">Origin gateway</div>
              <div class="metric-value ok">Verified</div>
              <div class="metric-meta">Worker -> Render provenance accepted.</div>
            </div>
            <div class="metric">
              <div class="metric-label">Access posture</div>
              <div class="metric-value ok">${escapeHtml(principal.auth_strength || "Verified")}</div>
              <div class="metric-meta">${escapeHtml(methods)}</div>
            </div>
            <div class="metric">
              <div class="metric-label">AI telemetry</div>
              <div class="metric-value ${usageHealthy ? "ok" : "warn"}">${escapeHtml(usageStatusText)}</div>
              <div class="metric-meta">${usageHealthy ? `Source: ${escapeHtml(upstreamSource)}` : "Control Room remains available without telemetry."}</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head"><strong>Security session</strong><span>Backend attested</span></div>
          <table class="table">
            <tr><td>Owner</td><td>${escapeHtml(principal.email || "Verified principal")}</td></tr>
            <tr><td>Authenticated at</td><td>${escapeHtml(authenticatedAt)}</td></tr>
            <tr><td>Expires at</td><td>${escapeHtml(expiresAt)}</td></tr>
            <tr><td>Authentication methods</td><td>${escapeHtml(methods)}</td></tr>
            <tr><td>Gateway provenance</td><td class="ok">Worker -> Render verified</td></tr>
            <tr><td>Direct-origin bypass</td><td class="ok">Blocked</td></tr>
          </table>
        </section>

        ${aiUsageBody}

        <section>
          <div class="section-heading">
            <div><h2>Remaining instrumentation</h2><p>Modules stay empty until their backend data contracts are ready.</p></div>
          </div>
          <div class="placeholder-grid">
            <div class="placeholder"><strong>Content Pipeline</strong><p>Ingestion, extraction, browser capture and media processing health.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Sources</strong><p>Source freshness, failures, blocks and evidence availability.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Jobs</strong><p>Pending, running, retried and failed background operations.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Intelligence</strong><p>Claims, stories, entity resolution and verification pipeline state.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Errors</strong><p>Recent application, provider and pipeline failures.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Releases</strong><p>Deployed commit, rollout state and feature flags.</p><span class="tag">Not instrumented</span></div>
          </div>
        </section>
      </div>
    </main>
  </div>
</body>
</html>`;

  return new Response(html, {
    status: 200,
    headers: noStoreHeaders({
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
    }),
  });
}

async function handleDashboard(request, context) {
  const sessionResponse = await fetchOrigin(
    request,
    SESSION_PATH,
    "",
    context,
  );

  if (!sessionResponse) {
    return textResponse("Control Room origin unavailable", 502);
  }

  if (!sessionResponse.ok) {
    return textResponse(
      "Control Room session verification failed",
      sessionResponse.status,
    );
  }

  let session;
  try {
    session = await sessionResponse.json();
  } catch {
    return textResponse("Control Room session response invalid", 502);
  }

  if (session?.authenticated !== true || !session?.principal) {
    return textResponse("Control Room session verification failed", 403);
  }

  const usageResponse = await fetchOrigin(
    request,
    `${CONTROL_ROOM_PREFIX}/ai-usage`,
    "?days=7",
    context,
  );

  if (!usageResponse) {
    return renderDashboard(session, null, "Control Room AI telemetry origin request failed.");
  }

  if (!usageResponse.ok) {
    return renderDashboard(
      session,
      null,
      `Control Room AI telemetry returned HTTP ${usageResponse.status}.`,
    );
  }

  let usage;
  try {
    usage = await usageResponse.json();
  } catch {
    return renderDashboard(session, null, "Control Room AI telemetry response was invalid.");
  }

  return renderDashboard(session, usage);
}

async function proxyControlRoomRequest(request, incomingUrl, context) {
  const originResponse = await fetchOrigin(
    request,
    incomingUrl.pathname,
    incomingUrl.search,
    context,
  );

  if (!originResponse) {
    return textResponse("Control Room origin unavailable", 502);
  }

  const responseHeaders = new Headers(originResponse.headers);
  responseHeaders.set("Cache-Control", "no-store");
  responseHeaders.set("X-Content-Type-Options", "nosniff");
  responseHeaders.set("Referrer-Policy", "no-referrer");

  return new Response(originResponse.body, {
    status: originResponse.status,
    statusText: originResponse.statusText,
    headers: responseHeaders,
  });
}

export default {
  async fetch(request, env) {
    const incomingUrl = new URL(request.url);

    if (incomingUrl.pathname === "/") {
      return Response.redirect(
        `${incomingUrl.origin}${CONTROL_ROOM_PREFIX}`,
        302,
      );
    }

    if (
      incomingUrl.pathname !== CONTROL_ROOM_PREFIX &&
      !incomingUrl.pathname.startsWith(`${CONTROL_ROOM_PREFIX}/`)
    ) {
      return textResponse("Not Found", 404);
    }

    const context = validateGatewayContext(request, env);
    if (context.error) {
      return context.error;
    }

    if (
      incomingUrl.pathname === CONTROL_ROOM_PREFIX &&
      request.method === "GET"
    ) {
      return handleDashboard(request, context);
    }

    return proxyControlRoomRequest(request, incomingUrl, context);
  },
};