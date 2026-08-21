const RENDER_ORIGIN = "https://sportabase-control-room-origin.onrender.com";
const CONTROL_ROOM_PREFIX = "/admin/control-room";
const SESSION_PATH = `${CONTROL_ROOM_PREFIX}/session`;
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

function renderDashboard(session) {
  const principal = session?.principal ?? {};
  const methods = Array.isArray(principal.auth_methods)
    ? principal.auth_methods.join(", ")
    : "Unavailable";

  const authenticatedAt = isoFromEpoch(principal.authenticated_at_epoch);
  const expiresAt = isoFromEpoch(principal.expires_at_epoch);

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
    body { margin: 0; min-height: 100vh; background: #090b0f; }
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
    .nav-item.active { color: #eef2f7; background: #151a22; border-left-color: #69d9ad; }
    .nav-item .pending { color: #555f6f; font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
    .side-footer { position: absolute; left: 14px; right: 14px; bottom: 18px; border-top: 1px solid #202530; padding: 14px 8px 0; color: #626d7d; font-size: 10px; line-height: 1.5; }
    .main { min-width: 0; }
    .topbar { min-height: 62px; border-bottom: 1px solid #222733; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 24px; background: #0b0e13; }
    .title { font-size: 14px; font-weight: 700; }
    .subtle { color: #747e8e; font-size: 11px; }
    .status-line { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #9aa4b2; }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #54d9a5; }
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
    .panel { border: 1px solid #242a35; background: #0d1117; margin-bottom: 22px; }
    .panel-head { padding: 12px 14px; border-bottom: 1px solid #242a35; display: flex; justify-content: space-between; gap: 14px; align-items: center; }
    .panel-head strong { font-size: 11px; text-transform: uppercase; letter-spacing: .09em; }
    .panel-head span { color: #687281; font-size: 10px; }
    .table { width: 100%; border-collapse: collapse; }
    .table td { padding: 11px 14px; border-bottom: 1px solid #1e232c; font-size: 11px; vertical-align: top; }
    .table tr:last-child td { border-bottom: 0; }
    .table td:first-child { width: 190px; color: #747e8e; }
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
      .metrics { grid-template-columns: repeat(2, minmax(0,1fr)); }
      .metric:nth-child(2) { border-right: 0; }
      .metric:nth-child(-n+2) { border-bottom: 1px solid #242a35; }
      .placeholder-grid { grid-template-columns: 1fr; }
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
        <div class="nav-item active"><span>Overview</span></div>
        <div class="nav-item"><span>Pipeline</span><span class="pending">Later</span></div>
        <div class="nav-item"><span>AI &amp; Quota</span><span class="pending">Next</span></div>
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
          <div class="subtle">Operational status and secured session</div>
        </div>
        <div class="status-line"><span class="dot"></span> Access verified</div>
      </header>

      <div class="content">
        <section>
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
              <div class="metric-label">Owner</div>
              <div class="metric-value">${escapeHtml(principal.email || "Verified principal")}</div>
              <div class="metric-meta">Exact allowlisted identity.</div>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head"><strong>Security session</strong><span>Backend attested</span></div>
          <table class="table">
            <tr><td>Authenticated at</td><td>${escapeHtml(authenticatedAt)}</td></tr>
            <tr><td>Expires at</td><td>${escapeHtml(expiresAt)}</td></tr>
            <tr><td>Authentication methods</td><td>${escapeHtml(methods)}</td></tr>
            <tr><td>Gateway provenance</td><td class="ok">Worker -> Render verified</td></tr>
            <tr><td>Direct-origin bypass</td><td class="ok">Blocked</td></tr>
          </table>
        </section>

        <section>
          <div class="section-heading">
            <div><h2>Instrumentation</h2><p>These modules stay empty until their backend data contracts are ready.</p></div>
          </div>
          <div class="placeholder-grid">
            <div class="placeholder"><strong>AI &amp; Quota</strong><p>Provider calls, quota remaining, token usage, failures and latency.</p><span class="tag">Next instrumentation target</span></div>
            <div class="placeholder"><strong>Content Pipeline</strong><p>Ingestion, extraction, browser capture and media processing health.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Sources</strong><p>Source freshness, failures, blocks and evidence availability.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Jobs</strong><p>Pending, running, retried and failed background operations.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Intelligence</strong><p>Claims, stories, entity resolution and verification pipeline state.</p><span class="tag">Not instrumented</span></div>
            <div class="placeholder"><strong>Errors &amp; Releases</strong><p>Recent exceptions, provider errors, deployed commit and feature flags.</p><span class="tag">Not instrumented</span></div>
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

  return renderDashboard(session);
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
