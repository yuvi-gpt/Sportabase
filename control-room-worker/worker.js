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

  // Never trust provenance supplied by the browser.
  headers.delete(PROVENANCE_HEADER);
  headers.set(PROVENANCE_HEADER, context.originSecret);

  // Preserve the Access assertion for authoritative backend validation.
  headers.set("Cf-Access-Jwt-Assertion", context.accessJwt);

  // The backend does not use browser session cookies.
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

function renderDashboard(session) {
  const principal = session?.principal ?? {};
  const methods = Array.isArray(principal.auth_methods)
    ? principal.auth_methods.join(" · ")
    : "Unavailable";

  const authenticatedAt = Number.isFinite(principal.authenticated_at)
    ? new Date(principal.authenticated_at * 1000).toISOString()
    : "Unavailable";
  const expiresAt = Number.isFinite(principal.expires_at)
    ? new Date(principal.expires_at * 1000).toISOString()
    : "Unavailable";

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
      background: #07090d;
      color: #f4f7fb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 10% 0%, rgba(75, 102, 255, .16), transparent 32rem),
        radial-gradient(circle at 100% 20%, rgba(43, 205, 173, .08), transparent 28rem),
        #07090d;
    }
    .shell { max-width: 1180px; margin: 0 auto; padding: 34px 24px 54px; }
    .topbar { display: flex; justify-content: space-between; gap: 24px; align-items: center; margin-bottom: 36px; }
    .brand { display: flex; align-items: center; gap: 14px; }
    .mark {
      width: 42px; height: 42px; display: grid; place-items: center;
      border: 1px solid rgba(255,255,255,.12); border-radius: 13px;
      background: rgba(255,255,255,.05); font-weight: 800; letter-spacing: -.04em;
    }
    h1 { margin: 0; font-size: 20px; letter-spacing: -.025em; }
    .eyebrow { margin: 0 0 3px; color: #828a99; font-size: 12px; text-transform: uppercase; letter-spacing: .14em; }
    .status {
      display: inline-flex; align-items: center; gap: 8px; border: 1px solid rgba(84, 223, 166, .22);
      background: rgba(84, 223, 166, .07); color: #9df1ce; padding: 8px 11px; border-radius: 999px; font-size: 12px;
    }
    .dot { width: 7px; height: 7px; border-radius: 50%; background: #57dda8; box-shadow: 0 0 18px rgba(87,221,168,.75); }
    .hero { margin: 58px 0 34px; }
    .hero h2 { margin: 0; max-width: 780px; font-size: clamp(38px, 6vw, 72px); line-height: .98; letter-spacing: -.055em; }
    .hero p { margin: 20px 0 0; max-width: 650px; color: #9aa3b2; font-size: 16px; line-height: 1.65; }
    .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 14px; }
    .card {
      grid-column: span 4; min-height: 176px; padding: 20px;
      border: 1px solid rgba(255,255,255,.09); border-radius: 18px;
      background: rgba(18,21,28,.72); backdrop-filter: blur(16px);
    }
    .card.wide { grid-column: span 8; }
    .label { color: #7f8897; font-size: 11px; text-transform: uppercase; letter-spacing: .13em; }
    .value { margin-top: 15px; font-size: 20px; font-weight: 650; letter-spacing: -.025em; overflow-wrap: anywhere; }
    .meta { margin-top: 9px; color: #8f98a7; font-size: 13px; line-height: 1.55; overflow-wrap: anywhere; }
    .secure { color: #9df1ce; }
    .footer { margin-top: 24px; color: #646d7b; font-size: 12px; }
    code { color: #cdd5e2; }
    @media (max-width: 760px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      .hero { margin-top: 40px; }
      .card, .card.wide { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="mark">SB</div>
        <div>
          <p class="eyebrow">Owner console</p>
          <h1>Sportabase Control Room</h1>
        </div>
      </div>
      <div class="status"><span class="dot"></span> Secure session active</div>
    </header>

    <section class="hero">
      <h2>System intelligence, without the noise.</h2>
      <p>The private operating surface for Sportabase. Authentication, origin provenance, and backend authorization are all active before this page is rendered.</p>
    </section>

    <section class="grid">
      <article class="card wide">
        <div class="label">Authenticated owner</div>
        <div class="value">${escapeHtml(principal.email || "Verified principal")}</div>
        <div class="meta">Identity verified by Cloudflare Access and revalidated by the Render backend.</div>
      </article>

      <article class="card">
        <div class="label">Security posture</div>
        <div class="value secure">${escapeHtml(principal.auth_strength || "Verified")}</div>
        <div class="meta">${escapeHtml(methods)}</div>
      </article>

      <article class="card">
        <div class="label">Session issued</div>
        <div class="value">${escapeHtml(authenticatedAt)}</div>
        <div class="meta">Backend-attested authentication time.</div>
      </article>

      <article class="card">
        <div class="label">Session expires</div>
        <div class="value">${escapeHtml(expiresAt)}</div>
        <div class="meta">Short-lived owner session; re-authentication is required after expiry.</div>
      </article>

      <article class="card">
        <div class="label">Gateway</div>
        <div class="value secure">Worker → Render verified</div>
        <div class="meta">Private provenance header accepted. Direct-origin bypass remains blocked.</div>
      </article>
    </section>

    <div class="footer">Sportabase Control Room · session diagnostics remain available at <code>${SESSION_PATH}</code></div>
  </main>
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

async function handleDashboard(request, incomingUrl, context) {
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
    return textResponse("Control Room session verification failed", sessionResponse.status);
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
      return handleDashboard(request, incomingUrl, context);
    }

    return proxyControlRoomRequest(request, incomingUrl, context);
  },
};
