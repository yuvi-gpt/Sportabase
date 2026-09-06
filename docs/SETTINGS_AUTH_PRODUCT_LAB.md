# Settings and authentication product lab

This document describes the account, installation, preferences, personal activity, notifications, and product analytics foundations shared by the Sportabase web app, Expo app, and Chrome extension. It is an implementation guide, not a record of live Clerk or push-provider verification.

## Identity and ownership

Four identities remain deliberately separate:

- Clerk authenticates a durable external user subject. The backend stores only a domain-separated SHA-256 hash of that subject and assigns an opaque `acct_…` Sportabase account ID.
- Each installation creates a random UUID without fingerprinting. Web uses `localStorage`, mobile uses AsyncStorage for this non-secret ID, and the extension uses `chrome.storage.local`.
- The pre-account client capability remains available only for a one-time authenticated claim. The claim runs in the installation write transaction and is idempotent for the first account. Bootstrap returns `claimed`, `already_claimed_by_account`, `already_claimed_elsewhere`, or `not_requested`; the elsewhere result is nonfatal and never reassigns data. Clients persist a terminal local migration marker so later account switches normally omit the capability. If that marker is lost, the backend still registers the new account/device without exposing or moving the first account's watches, alerts, activity, history, preferences, registrations, or legacy link.
- My Activity is account-owned usage metadata. It does not replace canonical Intelligence History and never establishes canonical graph relationships.

JWT claims, session tokens, and raw Clerk subjects never become client-selectable ownership keys. `X-Sportabase-Client-ID` cannot override the verified account in the composed application.

## Clerk boundaries and configuration

The FastAPI middleware accepts Bearer session JWTs only on account and product-action routes. It permits RS256, selects configured JWKS keys by `kid`, rejects weak or ambiguous RSA keys, verifies signature, issuer, expiry, not-before, issued-at, subject, and session ID, and optionally enforces audience and authorized party. JWKS is fetched only from the configured HTTPS issuer, without redirects, with response-size and cache limits. Errors become an opaque 401 response. Cloudflare/admin guards remain separate.

Backend environment:

- `CLERK_ISSUER`: required Clerk issuer origin, with no path or query.
- `CLERK_AUDIENCE`: optional expected JWT audience.
- `CLERK_AUTHORIZED_PARTIES`: comma-separated browser/extension origins permitted when an `azp` claim is present. Production startup fails if this is empty. Current Clerk documentation defines `azp` as the Origin used when minting the token and permits verification to skip the check when that claim is absent; this matters for native Expo tokens. A present value is always required to be a non-empty string and must match this allowlist.
- `SPORTABASE_ENV=production`: enables fail-closed deployment configuration checks.
- `SPORTABASE_ALLOWED_ORIGINS`: exact comma-separated CORS origins. Production startup fails rather than falling back to wildcard CORS when it is absent.
- `CLERK_SECRET_KEY`: required only for final Clerk-user deletion. Product access is revoked before that provider call; a provider failure leaves the account in a fail-closed `deleting` state that may retry deletion.

The static web app uses Clerk's vanilla browser client and a public publishable key supplied in deployment-generated `frontend/product-config.mjs`. The file must also specify the API origin. A production config is rejected until `cspDeploymentConfigured` is explicitly true; set that flag only after the deployed static host has an exact CSP covering the selected Clerk tenant and Sportabase API. No secret belongs in the browser bundle. The checked-in empty key produces an explicit unavailable state and never activates a test adapter.

Mobile uses pinned `@clerk/expo`, hosted auth, and Clerk's secure token cache backed by `expo-secure-store`. Configure `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY`, `EXPO_PUBLIC_SPORTABASE_API_URL`, and the exact HTTPS canonical web origin in `EXPO_PUBLIC_SPORTABASE_WEB_URL`. The privacy link is omitted with a clear unavailable state when that canonical origin is absent or invalid. AsyncStorage contains non-secret device IDs, the one-time migration marker, the current notification registration ID, and cached appearance values only.

The MV3 extension creates `@clerk/chrome-extension/client` in its service worker with `{background:true}`. Content scripts submit a small allowlist of typed product operations over runtime messages; they never receive the session token and cannot select an arbitrary URL. Account preferences, account navigation and sign-out live on `settings.html`, an extension-owned page. The worker accepts those messages only from that exact extension URL. Side-effecting overlay controls also require a trusted browser user event, so a hostile host page cannot dispatch synthetic clicks to start analysis, mutate watches, reconcile Activity, or open extension settings. Build-time public values are `SPORTABASE_CLERK_PUBLISHABLE_KEY`, `SPORTABASE_CLERK_SYNC_HOST`, and `SPORTABASE_API_BASE`; `SPORTABASE_DEPLOYMENT=production` makes a build fail when any is absent. The sync host must be the exact HTTPS origin of a Sportabase web app using the same Clerk application. Release packaging must add the configured sync host and Clerk Frontend API origins to `host_permissions`; those tenant-specific origins are intentionally absent from source control.

Local tests use injected verifier keys/JWKS and module- or constructor-level test adapters. There is no request header, query parameter, environment default, or production code path that enables test authentication.

## Preferences and devices

`sportabase-preferences-v1` rejects extra fields, wrong types, unsupported enum values, invalid clock strings, and invalid IANA timezones. Account defaults cover presentation, language/region, analysis presentation, notification policy, analytics consent, and activity retention. Each registered installation stores a platform, display name, sync revision, `follows_defaults`, and validated override patch.

Effective preferences are deterministic:

```text
account defaults + device overrides, when follows_defaults is false
account defaults, when follows_defaults is true
```

Optimistic revisions reject stale writes. Privacy controls apply only at account scope. Platform-only geometry, push credentials, and local session material do not enter the shared contract. The extension's position, dimensions, remembered placement, and reset behavior stay in Chrome storage.

Presentation preferences may change density and how much supporting explanation is initially expanded. They cannot change Merit Score meaning; combine video Evidence and Logic scores; infer credibility or truth from chronology, counts, repetition, or dependency; change canonical relations; or add source/reporter watches.

## Notifications and quiet hours

Native Expo and Web Push remain separate providers over the existing persisted alert ledger. Watchlist reconciliation remains ledger-only and performs no provider, Gemini, or network work. Entity, story, claim, and media remain the exact watchable kinds.

Delivery policy is evaluated before materialization and again before a lease is claimed. A disabled master or kind cancels provider delivery without deleting the in-app alert. Quiet hours compute against the effective device preference and explicit IANA timezone. During a quiet window, delivery returns to `pending` with its next eligible UTC minute; no attempt is consumed and the worker cannot busy-loop. Walking UTC minutes through the local window handles midnight crossings, nonexistent spring-forward times, and repeated fall-back times.

Provider registration and unregistration retain their established credential, retry, lease, and Web Push DNS-pinning/SSRF protections. Account deletion blanks/disables credentials before calling Clerk, then removes private delivery data after provider deletion succeeds.

Account notification registration is not treated as analytics. Provider registration is followed by an ownership binding; binding failure returns an error and compensates by deleting the new provider registration. If compensation itself is interrupted, the unbound account registration remains ineligible for delivery and a same-account retry can repair the binding idempotently. Analytics events after registration/unregistration are separate best-effort writes.

`POST /account/device/sign-out` deletes only Expo/Web Push registrations bound to the authenticated account plus current installation, including pending delivery rows through foreign-key cascades, and then removes those bindings. Watches, in-app Alerts and personal history remain. Web revokes the backend relationship before unsubscribing its browser `PushSubscription`; mobile revokes it before clearing its local Expo registration ID; the extension also calls the boundary before Clerk sign-out. A backend failure aborts sign-out so delivery ownership is not silently stranded. Other account devices are untouched, and the removed token/subscription may subsequently be registered by another account on the same physical device.

## My Activity, export, and deletion

Completed article and video analyses can record a safe title, sanitized reopen URL, optional canonical media reference, timestamp, originating platform, and installation ID. Query strings and fragments are removed except the YouTube video ID needed to reopen. Article bodies, transcripts, analysis payloads, tokens, and push credentials are excluded. Activity supports cursor pagination, literal-safe title search, type filtering, revisit, account-wide clear, and JSON export.

Personal export uses explicit tables and fields. It includes preferences, installations, activity, watches, alerts, internal notification-binding identifiers, and sanitized account-owned `user_history` fields (`media_item_id`, first/last analyzed timestamps, and analysis count). Canonical Intelligence History remains separate. The export excludes Clerk subjects/hashes, Bearer tokens, push tokens, Web Push endpoints and encryption keys, arbitrary URL query material, snapshot contents, article bodies, and transcripts.

Account deletion requires an exact confirmation and a recent Clerk verification-age claim. A transaction first changes the account to `deleting` and disables provider credentials. If Clerk deletion fails, normal product access stays blocked and the user can only retry deletion. On success, Sportabase removes account-private installations, links, watches, alerts, activity, analytics, notification data, settings and lifecycle values. The fail-closed tombstone retains exactly the opaque Sportabase row ID, deterministic domain-separated Clerk-subject hash and `deleted` status so an unexpired old JWT cannot recreate the account; timestamps and revision are zeroed. This retained deterministic hash is a deliberate anti-recreation identifier, not anonymous or erasable private state. Global canonical intelligence remains untouched.

## First-party analytics and privacy

Optional product analytics accepts only enumerated event names and platform values. Authenticated product events such as `settings_opened`, active-use counts and optional funnel events respect the account opt-in, are retained for 90 days, and are best-effort: their database failure cannot replace a successful analysis, watch or notification result. My Activity is also best-effort after provider success, so a database lock cannot cause a client retry to consume provider quota again. Turning analytics off deletes the account's retained optional events.

Necessary operational/account data is not optional analytics: registered-account totals and lifecycle state, installation ownership, persisted watch ownership, notification registration/binding state, deletion recovery state and provider quota/operational telemetry exist to run and secure the requested features. Disabling analytics does not claim to erase these records. No analytics path accepts or stores raw auth/JWTs, push tokens, article bodies, transcripts, arbitrary URL/referrer/user-agent/IP fields, or free-form event payloads.

Anonymous landing acquisition remains aggregate-only, but the checked-in web configuration is explicitly `development` with landing emission disabled. The client emits only when a generated deployment config sets both `deployment: "production"` and `landingAnalyticsEnabled: true`, and the page is a non-local HTTPS origin. Localhost, test and Playwright sessions therefore cannot write production acquisition events.

The existing admin guard protects aggregate account, DAU/WAU/MAU, new-account, analysis, first-analysis, watch-creator, notification-registration, and returning-active figures. Anonymous landing counts are acquisition signals and can include bots; they are not registered-user or unique-eyeball counts. No user-level analytics route is public.

## Deployment and real-world gates

Before release, create a Clerk application and configure authorized parties, redirect URLs, hosted-auth callbacks, mobile deep links, and the extension sync host. Generate the web public config with an explicit production deployment/analytics decision, Clerk live publishable key, API origin, and `cspDeploymentConfigured: true` only after the exact deployed CSP is present. Set `SPORTABASE_ENV=production`, exact `CLERK_AUTHORIZED_PARTIES`, and exact `SPORTABASE_ALLOWED_ORIGINS`; startup is expected to fail if the two allowlists are absent. Generate the extension manifest host permissions from the tenant sync/Frontend API origins and use `SPORTABASE_DEPLOYMENT=production` for the build. Configure an exact CSP for the deployed static web and extension assets rather than a wildcard. Provision `CLERK_SECRET_KEY` only in the backend secret store and test provider-deletion retry behavior in staging.

The deterministic suites prove local JWT and ownership behavior without Clerk network access. They do not prove tenant configuration, real sign-in redirects, session revocation, Clerk key rotation over the network, native iOS/Android secure-store behavior, extension cookie/sync behavior, real Expo push, Web Push delivery, browser permission prompts, or native assistive-technology UX. Those require staging browsers, unpacked/packaged extension checks, and physical iOS/Android devices before release.
