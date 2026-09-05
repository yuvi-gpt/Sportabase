# Web Push V1

Web Push is an optional browser delivery provider layered on the existing persisted Watchlist alert pipeline:

```text
persisted intelligence -> Watchlist reconciliation -> product_alert_events
  -> product_notification_alert_ledger -> Expo and Web Push deliveries
```

It does not create intelligence, invoke Gemini or search, or call a provider during Watchlist reconciliation. The watchable kinds remain exactly `entity`, `story`, `claim`, and `media`; Sources and Reporters remain inspectable only.

## Configuration

Set all three values on the backend:

- `SPORTABASE_WEB_PUSH_VAPID_PUBLIC_KEY`: URL-safe base64 VAPID public key. This is intentionally returned to browsers.
- `SPORTABASE_WEB_PUSH_VAPID_PRIVATE_KEY`: corresponding private key. It remains server-side and must never be committed or exposed.
- `SPORTABASE_WEB_PUSH_VAPID_SUBJECT`: a `mailto:` contact or HTTPS contact URL.

The shared notification worker still requires `SPORTABASE_NOTIFICATIONS_ENABLED=1`. Existing poll, lease, and request-timeout environment settings apply to both providers. Missing VAPID configuration disables only Web Push dispatch; Expo continues normally.

The static website must be served over HTTPS (or localhost for development), and `service-worker.js` must be served from the frontend root with JavaScript content type so its scope includes the application. The site fetches the public VAPID key from `GET /notifications/web/config`; no VAPID value is hardcoded into frontend source.

## Product and privacy behavior

Permission is requested only after the user clicks **Enable notifications**. A persistent, browser-local Sportabase client ID is required for private subscription and mark-read routes. If local storage cannot persist an ID, public analysis remains available and browser notification controls are unavailable; there is no shared anonymous, IP, or fingerprint fallback.

Browser endpoints, P-256 keys, and auth secrets are stored only for provider delivery. Product APIs return an opaque subscription ID and metadata, never those credentials or the internal client-key hash. A new or reassigned subscription starts at the current notification-ledger sequence, preventing historical alerts from being pushed.

Endpoints are attacker-controlled. Registration retains public-address validation as defense-in-depth. Each dispatch attempt resolves the endpoint once, validates **all** returned IPv4/IPv6 addresses, and rejects the entire destination if any answer is loopback, private, link-local, reserved, unspecified, multicast, otherwise non-global, or malformed. Localhost names (including trailing-dot forms) and scoped IPv6 endpoints are rejected. After validating every answer, dispatch selects the first address in the OS resolver's preference order. Public IP literals are checked directly without DNS.

Delivery uses an isolated `SafeWebPushSession`, requests adapter, and urllib3 HTTPS pool for that attempt. The pool's connection class overrides TCP socket creation: it passes the selected canonical numeric address and explicit IPv4/IPv6 family directly to `socket.connect`, without calling `getaddrinfo` or urllib3's resolving `create_connection` helper again. This binds the checked address to the socket destination and closes the DNS-rebinding validation/connect gap. It also retains the original request target when issuing the HTTP request, preserving opaque path/query escapes through urllib3 normalization. There is no unpinned fallback or automatic connection retry; a later ledger retry resolves and validates afresh.

The original hostname remains the TLS SNI and certificate hostname assertion target, using requests' normal CA bundle and required certificate-chain verification. TLS remains entirely in urllib3/Python's standard TLS stack; verification cannot be disabled through this session. Internationalized hostnames use requests' IDNA representation, and a DNS trailing dot is removed for TLS identity. The HTTP `Host` retains the original authority, including explicit ports and IPv6 brackets, and the endpoint path/query is retained through requests preparation. For literal-IP endpoints, normal IP certificate identity verification applies (TLS libraries do not send DNS SNI for IP literals). This is destination-address pinning, not certificate/public-key pinning. urllib3 documents its separate [SNI and certificate hostname settings](https://urllib3.readthedocs.io/en/stable/advanced-usage.html#custom-sni-hostname).

Redirects are disabled at both transport layers: the session calls the adapter directly without requests' redirect machinery, and the adapter sends with urllib3 redirects disabled. Provider 3xx responses are permanent delivery failures; `Location` is never followed. Pools and connections are closed after each attempt. Unsafe destinations invalidate the subscription and preserve current-delivery failure versus sibling cancellation behavior. Resolution outages, connection failures, and TLS failures use the existing bounded transport retry policy with generic error details.

Web Push is a **direct-only** transport. `trust_env=False` prevents inheritance of `HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY`, and `NO_PROXY` settings (including lowercase equivalents), system proxy discovery, and `.netrc` credentials. Explicit proxy settings are rejected. Environment CA-bundle overrides are also not inherited; requests' default CA trust remains in use. Other Sportabase HTTP clients, including Expo, are unchanged.

Network-level egress controls remain recommended defense-in-depth: deny private/link-local metadata and internal service destinations at the platform firewall. Address pinning does not protect against compromised routing, transparent network interception, or infrastructure that routes globally numbered addresses to internal services. Recheck the transport-boundary tests when upgrading requests/urllib3; this implementation was verified with Python 3.14.7, pywebpush 2.5.0, requests 2.34.2, and urllib3 2.7.0, without dependency changes.

Microsoft Edge on Windows may issue Web Push endpoints under `notify.windows.com`. `pywebpush` documents that WNS requires `X-WNS-Type` while warning that this non-standard header can be rejected by other services. Sportabase therefore sends `X-WNS-Type: wns/raw` and the matching binary content type only to `notify.windows.com` and its subdomains. FCM, Mozilla, Apple, and other standards-based endpoints receive no WNS headers. This remains part of the manual Edge deployment gate because acceptance by a real WNS subscription is not exercised by automated tests.

Push clicks use the real static index query landing (`?target_kind=...&target_id=...`) and load the existing public history API. The service worker constructs that URL itself and will not navigate to a payload-supplied external origin. An alert ID is passed in a fragment, removed immediately by the page, and used for best-effort private mark-read; mark-read failure never blocks history navigation.

## Manual deployment/E2E gate

Automated tests use fake sockets/TLS handshakes and provider responses; they make no external delivery requests. Production Web Push remains disabled and unverified pending the deployment E2E gate below. Enable it only in the controlled deployment test until that gate succeeds:

1. Generate a VAPID key pair using an approved operational secret-generation process; do not commit either key.
2. Configure the three Web Push environment variables on the backend and set `SPORTABASE_NOTIFICATIONS_ENABLED=1` with deliberate poll/lease/timeout values.
3. Deploy the backend and confirm `/notifications/web/config` reports `available: true` and exposes only the public key.
4. Deploy the unchanged static-file structure over HTTPS, including the manifest, helper module, and root service worker.
5. In deployed Chrome or Edge on Windows, open the site and click **Enable notifications**. Accept the browser permission prompt.
6. Confirm the browser subscription appears through the private subscription API for that same persistent browser identity, without credential fields in the response.
7. Create or use a Watchlist watch in the same client identity.
8. Cause a future persisted alert through the normal Sportabase intelligence and Watchlist flow. Do not insert a synthetic provider delivery.
9. Let the enabled notification worker reconcile, materialize, and deliver the alert.
10. Confirm a Windows/browser notification appears, click it, and confirm the static canonical intelligence landing opens for the correct kind and ID.
11. Confirm the corresponding alert is marked read when identity is available; a simulated mark-read failure must not prevent navigation.
12. Disable notifications from the site and confirm both browser unsubscribe and backend subscription removal.

Native Expo remains a separate provider with its existing `/notifications/devices` contract and still requires its own physical-device deployment test.
