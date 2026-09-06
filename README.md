# Sportabase

## Evidence-first sports intelligence

Sportabase is a sports intelligence platform that turns articles, videos, sources, reporters, claims, evidence, and analysis history into a persistent, explainable intelligence graph.

It is not merely a summarizer and it is not a truth machine. Its job is to answer:

- What is being claimed?
- Which media items and stories carry the claim?
- Who originated or repeated it?
- What evidence supports, contradicts, corrects, or supersedes it?
- Which corroboration is genuinely independent?
- How has persisted intelligence changed over time?
- What should a user be able to search, inspect, revisit, watch, and eventually act on?

The product currently spans a FastAPI backend, Chrome extension, React Native / Expo mobile app, and internal control-room surfaces. SQLite remains the current persistence layer.

---

## Current project checkpoint — 4 September 2026

### Current `main`

Latest verified remote `main` after the Notifications Push V1 merge:

```text
f5ebc411ab1e14823a56d61946b4b25ff1dc1034
```

Latest merged product unit:

```text
Add push notification delivery
```

The following roadmap units are now integrated into `main`:

- Search + Historical Intelligence V1;
- Watchlists + Alerts V1 backend;
- mobile Watchlists + Alerts productization;
- mobile canonical intelligence detail/history;
- Chrome extension ↔ persistent intelligence integration;
- Sources + Reporters as first-class inspectable intelligence objects across backend, mobile, and extension;
- Notifications Push V1 with explicit native opt-in and separate provider delivery.

### Latest verification checkpoint

Final backend verification on the Notifications Push V1 feature tree:

```text
3660 passed, 2 skipped, 11 warnings, 694 subtests passed in 61.43s
```

Focused notification contract tests:

```text
5 passed, 2 warnings in 0.72s
```

Mobile verification:

```text
npm ci                              PASS
npx expo install expo-notifications PASS (~57.0.17, SDK 57)
npx tsc --noEmit                    PASS
npx expo export --platform web      PASS
git diff --check                    PASS
```

The static web export now includes `/notifications`. Real push delivery was tested with mocked Expo tickets; a physical-device end-to-end delivery test remains a deployment gate before production enablement.

There are currently no GitHub Actions/status checks configured for this repo, so the local backend, TypeScript, Expo export, extension tests/build, and repository-integrity checks remain the execution gates for these product branches.

---

## Backend foundation now integrated

The backend includes:

- article and YouTube analysis with distinct article/video semantics;
- canonical media, story, claim, entity, source, reporter, evidence, and snapshot records;
- canonical entity resolution and aliases;
- claim extraction, normalization, support, evidence, and evolution history;
- story clustering and story evolution;
- source profiles, reporting coverage, provenance, dependency, and independence analysis;
- persistent analysis and operational event history;
- readiness, capacity, quota, provider-reliability, caching, retry, and multi-model routing controls;
- long-video transcript compression and analysis;
- golden-set evaluation and structured validation paths;
- homepage storyline aggregation;
- public Search + Historical Intelligence APIs;
- Watchlists + Alerts V1 with client-scoped ownership and deterministic persisted-event reconciliation;
- dedicated product-history contracts for canonical Sources and Reporters.

### Search + Historical Intelligence V1

Public product-safe endpoints:

- `GET /intelligence/search`
- `GET /intelligence/entities/{entity_id}/history`
- `GET /intelligence/stories/{story_id}/history`
- `GET /intelligence/claims/{claim_id}/history`
- `GET /intelligence/media/{media_item_id}/history`
- `GET /intelligence/sources/{source_id}/history`
- `GET /intelligence/reporters/{reporter_id}/history`

Search supports six inspectable object kinds:

- `entity`
- `story`
- `claim`
- `media`
- `source`
- `reporter`

Search is lexical discovery only. A matching string does not create a canonical relationship or verified intelligence link.

History endpoints expose canonical identity, persisted relationships, chronology, pagination, and explicit interpretation policies. Domain chronology is not treated as truth, credibility, novelty, or independent corroboration.

---

## Sources + Reporters product intelligence

Sources and Reporters are now first-class **inspectable** intelligence objects.

The product model is intentionally historical and provenance-oriented rather than reputation-score-oriented:

```text
Source / Reporter
├─ canonical identity
├─ reporting history
├─ stories & claims covered
├─ media attribution
├─ dependency relationships
├─ independence assertions
├─ direct evidence links
└─ persisted chronology
```

The backend profile contracts expose empirical counts and persisted facts only. They do **not** manufacture a `reliability_score`, credibility percentage, trust score, or truth probability.

Interpretation boundaries are explicit:

- chronology is not truth;
- reporting volume is not reliability;
- source count is not independence;
- dependency is not falsehood;
- absence of verified independence is not evidence of dependence;
- evidence quantity is not probability.

A dependency record means Sportabase has persisted an upstream/downstream relationship. It does not mean the downstream reporting is false.

A verified independence assertion is positive provenance-backed evidence of independence. Missing verified independence evidence is not automatically evidence of dependence.

---

## Watchlists + Alerts V1

Product API:

- `POST /watchlists`
- `GET /watchlists`
- `DELETE /watchlists/{watch_id}`
- `POST /watchlists/alerts/reconcile`
- `GET /watchlists/alerts`
- `POST /watchlists/alerts/{alert_id}/read`

Supported watch targets remain exactly:

- `entity`
- `story`
- `claim`
- `media`

Sources and reporters are inspectable but **not watchable in Alerts V1**. This separation is deliberate and must not be silently widened through shared TypeScript types or backend validation changes.

### Ownership and privacy

- Every private route requires an explicit, non-empty `x-sportabase-client-id` header.
- There is no IP, `x-forwarded-for`, account, or hardware-fingerprint fallback.
- The raw installation ID is never persisted or returned.
- A SHA-256 digest with namespace `sportabase:watchlists:v1:` is persisted internally.
- Every private read and write is client-scoped.
- Cross-client watch and alert probes return `404`.
- Watch IDs and alert IDs are opaque.
- `user_history` is separate and is not reused as subscription identity.

### Baselines, discovery ordering, and late arrivals

Creating a watch establishes a baseline at the current maximum global discovery sequence, so historical intelligence does not flood the alert inbox.

Eligible persisted events are appended by SQLite triggers to an AUTOINCREMENT discovery ledger. Watches advance through that integer total order rather than through event timestamps.

This preserves correct behavior for:

- identical timestamps;
- late-arriving evidence with old domain time;
- repeated reconciliation;
- bounded partial batches;
- concurrent reconciliation;
- process restarts.

Alert insertion and watermark advancement occur together inside one transaction. Stable source-event keys plus database uniqueness constraints prevent duplicate alerts.

### Reconciliation behavior

Reconciliation is explicit, deterministic, bounded, and local:

- zero Gemini calls;
- zero external HTTP calls;
- zero web search;
- zero notification-provider calls;
- maximum 100 watches per client;
- maximum 200 ledger records scanned per watch/request;
- maximum 50 new alerts per watch/reconciliation;
- maximum 100 alerts per inbox page.

Canonical intelligence is read-only during reconciliation. Only watch watermarks and alert rows are written.

---

## Notifications Push V1

Push delivery is a separate product layer on top of persisted Watchlist alerts. It does not put provider calls inside Watchlist reconciliation.

Private device API:

- `POST /notifications/devices`
- `GET /notifications/devices`
- `DELETE /notifications/devices/{device_id}`

The delivery model includes:

- explicit native iOS/Android opt-in;
- Expo push-token registration scoped by the existing private client identity;
- a post-registration alert baseline so old inbox alerts are not pushed retroactively;
- an append-only notification alert ledger;
- unique per-device/per-alert delivery jobs;
- leased delivery claiming and bounded retries;
- permanent invalid-device handling for `DeviceNotRegistered`;
- canonical intelligence deep links from push taps;
- best-effort mark-read synchronization with the in-app Alerts inbox.

Privacy and semantic boundaries:

- raw Expo push tokens are required server-side for delivery but are never returned by product APIs;
- push payloads contain no client key or raw installation identity;
- watchable kinds remain exactly `entity`, `story`, `claim`, and `media`;
- Sources and Reporters remain inspectable but not watchable;
- notification materialization makes no Gemini calls;
- Watchlist reconciliation itself still makes zero notification-provider calls.

The worker is disabled by default. Production delivery requires explicit `SPORTABASE_NOTIFICATIONS_ENABLED=1`; `SPORTABASE_NOTIFICATIONS_POLL_SECONDS` should be set deliberately based on deployment load rather than relying on the code default.

Real-device delivery remains unverified until a deployed backend and physical iOS/Android device complete an end-to-end Expo push test.

Web Push V1 is being implemented on its feature branch as an additive delivery provider over the same alert ledger. Configuration, privacy boundaries, static-service-worker requirements, and the unperformed manual deployment gate are documented in [`docs/WEB_PUSH_V1.md`](docs/WEB_PUSH_V1.md). This note does not change the verified `main` checkpoint above.

---

## Mobile product

The mobile app now supports six inspectable intelligence kinds while preserving four watchable kinds.

### Discover

Discover searches:

- entities;
- stories;
- claims;
- media;
- sources;
- reporters.

A search result is discovery only and does not create a graph relationship or reliability judgement.

Source and Reporter results open read-only reporting profiles and explicitly show that they are not watchable in Alerts V1.

### Intelligence detail

Static Expo Router route:

```text
/intelligence?kind=<entity|story|claim|media|source|reporter>&id=<canonical_id>
```

Entity/story/claim/media detail preserves existing watch and alert behavior.

Source/reporter detail includes:

- canonical identity;
- first-seen / last-seen metadata;
- recorded empirical counts;
- interpretation boundaries;
- related persisted media/story/claim/source/reporter objects;
- paginated persisted chronology;
- no Watch button;
- no Alerts button;
- no reliability, trust, or credibility score.

---

## Chrome extension

The Chrome extension is now integrated with persistent Sportabase intelligence rather than operating only as an isolated analysis surface.

### Persistent intelligence flow

From article/video analysis results, the extension can:

- resolve persisted canonical media identity;
- open entity/story/claim/media intelligence history;
- navigate related persisted graph objects;
- watch supported canonical objects using explicit persistent client identity;
- check exact-target future alert activity;
- preserve existing article/video scoring semantics.

### Reporting Profiles

A separate additive read-only Reporting Profiles surface appears when the current persisted media item has canonical `source_id` and/or `reporter_id` attribution.

It can expose:

- source/reporter identity;
- first/last seen;
- empirical activity counts;
- related persisted intelligence;
- dependencies;
- independence assertions;
- evidence links;
- persisted chronology;
- source ↔ reporter navigation.

The Reporting Profiles surface:

- performs no watchlist writes;
- sends no private client-identity header;
- makes no Gemini/provider call;
- does not infer or fabricate missing source/reporter attribution;
- does not expose a reliability score.

---

## Product semantics that must not regress

### Articles

The **Merit Score** measures reporting/informational quality and evidential support. It is not a truth probability or credibility percentage.

### Videos

Video analysis keeps these concepts separate:

- Evidence Score
- Logic Score
- Verdict

Do not create a composite video credibility score.

### Corroboration

Repetition is not independence. Ten rewrites of one report remain one reporting origin unless the persisted provenance graph establishes otherwise.

### History

Persisted history distinguishes domain time (`occurred_at` / `observed_at`) from discovery/materialization time. Chronology alone is never proof of truth, credibility, novelty, or independence.

### Sources and reporters

History, provenance, dependencies, corrections/reversals, first-vs-repeated reporting, and verified evidence behavior are legitimate product facts. A single reductive source/reporter reliability score is not part of the current product contract.

---

## Architecture

### Backend

- Python 3.14-compatible FastAPI application
- SQLite persistence with idempotent startup schema initialization
- dedicated domain/service/runtime modules rather than route-heavy business logic
- product-safe public projections separated from internal/admin records
- provider routing, capacity accounting, caching, retry, and readiness controls
- persistent canonical intelligence graph and product-history APIs

### Browser extension

- JavaScript / Chrome Extension APIs
- modular source structure under `extension/src`
- esbuild browser bundle pipeline
- article extraction and analysis overlay
- YouTube transcript extraction and analysis
- persistent intelligence navigation and watch integration
- read-only Source/Reporter Reporting Profiles

### Mobile

- React Native
- Expo Router
- TypeScript
- shared-link and pasted-link ingestion
- article and video result surfaces
- persisted intelligence discovery
- watchlists and in-app alerts
- six-kind canonical intelligence inspection
- four-kind watch contract
- persisted graph traversal and chronological history
- explicit push-notification opt-in and notification settings
- push-tap routing into canonical intelligence

---

## Development principles

1. Evidence over confidence.
2. Persisted relationships over lexical resemblance.
3. Independent corroboration over repetition.
4. History over static reputation.
5. Explainability over black-box scoring.
6. Stories and claims over isolated URLs.
7. Trajectory over isolated snapshots.
8. Probability and uncertainty over fake certainty.
9. Product-safe projections over raw database exposure.
10. Database constraints and transactions as the final correctness boundary.

---

## Roadmap status

Completed foundations now include:

- entity resolution;
- claim/story intelligence;
- evidence and support graphs;
- history;
- source profiles;
- reporting coverage and independence;
- story evolution;
- storyline aggregation;
- golden evaluation;
- long-video compression;
- provider reliability and task-specific model routing;
- Search + Historical Intelligence V1;
- Watchlists + Alerts V1;
- mobile Watchlists + Alerts productization;
- mobile canonical intelligence detail/history productization;
- Chrome extension persistent-intelligence integration;
- first-class Source/Reporter inspectable product intelligence;
- Notifications Push V1.

### Current next roadmap unit

**Prediction**, after completing the Notifications production-enablement gate.

Before predictive product work is treated as production-facing, Notifications still needs one deployment validation step: enable the worker in a controlled environment, register a physical iOS/Android device, persist a new watched intelligence event, and confirm one real Expo push arrives and deep-links to the expected canonical object.

After that validation, the next major research/product unit is **prediction**.

Future predictive work may use:

- information momentum;
- evidence growth;
- source/reporting context;
- team/player context;
- structured sports data;
- market movement.

Predictive outputs must be empirically evaluated and must not be smuggled into the Merit Score as unsupported truth prediction.

---

## Gemini/provider capacity policy

Current Gemini 3.6 Flash provider envelope used by Sportabase planning:

```text
Provider envelope: 5 RPM / 250,000 input TPM / 20 RPD per model
Sportabase usable: 4 RPM / 200,000 input TPM / 16 RPD
Reserve: 4 calls
```

Provider day is interpreted in `America/Los_Angeles`; analytics remain UTC.

`429` and `503` remain distinct operational states. Cache hits and inflight joins do not consume new provider slots.

Provider-backed tests should remain intentionally limited when a deterministic local contract test can verify the change instead.

---

## Local worktree safety

The primary local repo may contain unrelated UI/design work on other branches. Do not reset, switch, pull, or clean that worktree without first inspecting it.

Use isolated Git worktrees for roadmap units.

Recent isolated feature worktrees include:

```text
C:\Users\Yuvraj\Documents\Sportabase-mobile-watchlists-alerts
C:\Users\Yuvraj\Documents\Sportabase-mobile-intelligence-detail
C:\Users\Yuvraj\Documents\Sportabase-extension-persistent-intelligence
C:\Users\Yuvraj\Documents\Sportabase-sources-reporters
```

Those feature branches are merged. Do not extend them for the next roadmap unit.

---

## Collaboration and execution preferences

These rules describe how ChatGPT and Codex should work with Yuvraj on Sportabase:

1. Be direct, evidence-led, and willing to challenge an assumption when the code or data disagrees. Do not agree reflexively, invent certainty, or report an action as complete without verifying it.
2. Prefer large, meaningful, coherent checkpoints over endless microsteps. For user-run work, explain the objective and risk first, then normally provide one copy-pasteable PowerShell block. State clearly whether more steps remain.
3. Use live GitHub state as the remote source of truth. Inspect the branch/ref, exact SHAs, PR state, CI results, relevant files, and diffs before making claims. Treat this README as a checkpoint, not proof that GitHub or a local worktree still matches it.
4. Prefer the GitHub connector for remote inspection, CI diagnosis, PR administration, and narrowly scoped branch changes when it can complete the work honestly. Use local Codex/CLI when local reproduction, filesystem-only state, or substantial implementation work genuinely requires it. Do not consume Codex usage or a manual reset merely for work the connector can safely perform.
5. Keep manual Codex usage resets in reserve and use them only when necessary. A usage reset and a context-window handoff solve different problems.
6. For substantial work, use a dedicated verified branch/worktree. Before editing, inspect the worktree path, branch, HEAD, status, and relevant diff. Do not touch another checkout or worktree.
7. Preserve user changes. On any failed checkpoint, stop and report the exact command and output. Do not reset, clean, discard, force-push, rebase, or otherwise rewrite work to escape a failure unless Yuvraj explicitly authorizes that exact action.
8. Keep authorization boundaries explicit. A request to inspect, diagnose, review, or report does not authorize code changes. A request to implement does not automatically authorize committing, pushing, opening or updating a PR, marking it ready, merging, or deploying. State what was and was not changed.
9. Reproduce a defect before fixing it when practical. Fix root causes rather than weakening tests, hiding overflow, swallowing errors, or papering over product behavior. Run targeted gates first, then the appropriate complete gate; report exact commands and pass/fail counts.
10. Avoid unnecessary Gemini/provider calls. Prefer deterministic local contract tests when they can verify the behavior, and preserve distinct quota, capacity, transport, authentication, and service-error semantics.
11. During long work, provide concise progress updates at useful boundaries. If a local action is required, give only the next safe action unless a complete chronological block is materially clearer.
12. Preserve Sportabase's locked product, evidence, privacy, security, and deployment invariants. Do not broaden a focused task into unrelated refactoring.

---

## Conversation continuity protocol

> **Context warning for every future Sportabase chat:** Treat a long conversation as an operational risk. Before the chat becomes large enough that earlier technical context may be truncated, proactively warn Yuvraj and propose a checkpoint update. Do not wait for the final message or pretend an exact context meter is available. The warning should occur early enough to capture the current branch, base/head SHAs, worktree, dirty/staged state, files changed, tests and exact results, architectural decisions, invariants, blockers, and next command.

A Codex usage-limit reset replenishes usage quota; it does **not** enlarge, restore, or protect a conversation's context window. Never spend a reset merely because a chat is long. When context risk appears, finish only the current bounded step, write the verified checkpoint, and continue in a new chat before beginning another large implementation or review pass.

When a context checkpoint is needed:

1. Stop before starting another large implementation or review chunk.
2. Summarize only verified state; clearly distinguish remote, committed, local, staged, and planned work.
3. Update this README/checkpoint on GitHub when authorized.
4. Produce a self-contained handoff prompt for the next chat.
5. Never claim a branch, commit, push, test result, or clean worktree without evidence.
6. Preserve exact SHAs, exact test commands/results, and non-negotiable semantic constraints.

---

## Handoff source of truth

For a new Sportabase chat, use this README together with live Git/GitHub inspection. The README is a checkpoint, not a substitute for verification.

At this checkpoint the authoritative product merge is:

```text
main = f5ebc411ab1e14823a56d61946b4b25ff1dc1034
```

Before beginning the next feature:

1. verify live `origin/main`;
2. create a clean feature branch/worktree from that verified base;
3. preserve the six inspectable / four watchable intelligence-kind split;
4. preserve reconciliation as persisted-ledger-only with zero Gemini/provider/notification calls;
5. keep notification delivery separate from reconciliation and disabled until production configuration is intentional;
6. complete a physical-device push delivery test before calling Notifications production-enabled;
7. keep source/reporter history empirical and score-free;
8. begin prediction as an empirically evaluated layer that does not alter Merit Score semantics.

Do not return to Watchlists backend, mobile scaffolding, extension persistence, Source/Reporter first-class integration, or Notifications implementation unless a verified regression or deployment finding requires it.

---

## Long-term vision

Sportabase aims to become the intelligence layer for global sports information: a system that remembers what was claimed, traces where it came from, measures how evidence changed, learns from outcomes, and helps users understand the story rather than merely consume the headline.

**Sportabase — understand the story, not just the headline.**
