# Sportabase

## Evidence-first sports intelligence

Sportabase is a sports intelligence platform that turns articles, videos, sources, claims, evidence, and analysis history into a persistent, explainable intelligence graph.

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

Latest verified remote `main`:

```text
9691575c0232450a16170973bb54d9a293bb7494
```

Latest merge:

```text
Add mobile intelligence detail and history flow
```

The backend intelligence line, Watchlists + Alerts V1, mobile watchlists/alerts productization, and mobile canonical intelligence detail/history flow are all integrated into `main`.

### Backend foundation now integrated

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
- Watchlists + Alerts V1 with client-scoped ownership and deterministic persisted-event reconciliation.

### Search + Historical Intelligence V1

Public product-safe endpoints:

- `GET /intelligence/search`
- `GET /intelligence/entities/{entity_id}/history`
- `GET /intelligence/stories/{story_id}/history`
- `GET /intelligence/claims/{claim_id}/history`
- `GET /intelligence/media/{media_item_id}/history`

Search is lexical discovery only. A matching string does not create a canonical relationship or verified intelligence link.

History endpoints expose canonical identity, persisted relationships, chronology, pagination, and explicit interpretation policies. Domain chronology is not treated as truth, credibility, novelty, or independent corroboration.

### Watchlists + Alerts V1

Watchlists + Alerts V1 is committed, pushed, integrated, and available on `main`.

Product API:

- `POST /watchlists`
- `GET /watchlists`
- `DELETE /watchlists/{watch_id}`
- `POST /watchlists/alerts/reconcile`
- `GET /watchlists/alerts`
- `POST /watchlists/alerts/{alert_id}/read`

Supported targets remain exactly:

- `entity`
- `story`
- `claim`
- `media`

Sources and reporters remain deliberately excluded until they receive equivalent dedicated product-history contracts.

Final exact backend checkpoint from the completed Watchlists + Alerts implementation tree:

```text
3651 passed, 3 skipped, 12 warnings, 694 subtests passed in 96.29s
```

The feature diff at that checkpoint was:

```text
6 files changed, 699 insertions(+)
```

No full backend suite was rerun during later Git-only integration because backend production code was not changed by those merge operations.

---

## Mobile productization now completed

### Mobile Watchlists + Alerts product flow

Merged through PR #3.

Merge commit on `main`:

```text
576b6b8108e34cbb012338f5fd011bef2edd76cf
```

The mobile app now includes:

- persistent installation-scoped client identity for `x-sportabase-client-id`;
- public persisted-intelligence discovery;
- watch creation from Discover;
- Watchlist management;
- explicit alert reconciliation;
- Alerts inbox;
- unread filtering;
- pagination;
- mark-read behavior;
- persistent Analyze / Discover / Watches / Alerts navigation.

Client identity is randomly generated and persisted on-device. It is not derived from IP address, account details, or hardware fingerprinting. The backend hashes the raw client ID before persistence.

Verification completed before merge:

```text
npx tsc --noEmit                     PASS
npx expo export --platform web      PASS
git diff --check                    PASS
```

The Expo export included:

- `/`
- `/explore`
- `/watchlists`
- `/alerts`
- `/handle-share`

### Mobile canonical intelligence detail + history flow

Merged through PR #4.

Current `main` merge commit:

```text
9691575c0232450a16170973bb54d9a293bb7494
```

The mobile app now lets users move from Discover, Watchlists, or Alerts into the underlying canonical Sportabase object and persisted graph.

Supported detail objects:

- entity
- story
- claim
- media

The detail experience includes:

- canonical identity;
- first-seen / last-seen metadata;
- related persisted graph objects;
- navigation across entity/story/claim/media relationships;
- paginated persisted history timelines;
- explicit interpretation-policy notes;
- watch creation directly from detail pages;
- kind-level Alerts access;
- original-media navigation where a canonical URL exists;
- article Merit displayed as reporting/informational quality, not truth probability;
- video Evidence Score, Logic Score, and Verdict kept separate;
- chronology explicitly described as chronology, not credibility.

The route is intentionally static for Expo Router / static web export:

```text
/intelligence?kind=<entity|story|claim|media>&id=<canonical_id>
```

Verification completed on the final feature branch tree:

```text
npm ci                              PASS
npx tsc --noEmit                    PASS
npx expo export --platform web      PASS
git diff --check                    PASS
```

The Expo export included the new route:

```text
/intelligence
```

At verification time, local and remote feature SHAs matched exactly at:

```text
fbee13607fe0ecec9f59a1a304c292654d143e25
```

Post-merge comparison confirmed zero file differences between the reviewed feature tree and `main`.

### CI note

There are currently no GitHub Actions/status checks configured for these mobile branches. Local TypeScript and Expo static-export checks are therefore the current execution gates for mobile feature branches.

---

## Watchlists + Alerts invariants

### Ownership and privacy

- Every private route requires an explicit, non-empty `x-sportabase-client-id` header.
- There is no IP, `x-forwarded-for`, or `request.client.host` fallback.
- The raw installation ID is never persisted or returned.
- A SHA-256 digest with namespace `sportabase:watchlists:v1:` is persisted internally.
- Every private read and write is client-scoped.
- Cross-client watch and alert probes return `404`.
- Watch IDs and alert IDs are opaque.
- `user_history` is untouched and is not reused as subscription state.

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

### Event behavior

- Entity watches react only through verified claim/entity participation and graph relationships derived from that verified path.
- Story watches can react to claim links, media links, source observations, reporter observations, evidence links, and analysis snapshots.
- Claim watches can react to observation/evidence links, verified entity participants, story links, adjudication revisions, and adjudication transitions.
- Media watches react to new analysis snapshots.

Alert summaries are deterministic and neutral. They do not use AI and do not claim that an event is breaking, confirmed, true, reliable, or credible unless that precise persisted semantic is explicitly represented.

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

---

## Architecture

### Backend

- Python 3.14-compatible FastAPI application
- SQLite persistence with idempotent startup schema initialization
- dedicated domain/service/runtime modules rather than route-heavy business logic
- product-safe public projections separated from internal/admin records
- provider routing, capacity accounting, caching, retry, and readiness controls

### Browser extension

- JavaScript / Chrome Extension APIs
- article extraction and analysis overlay
- YouTube transcript extraction and analysis
- localized UI, loading states, settings, caching, and trust-oriented result presentation
- modular source structure under `extension/src`
- esbuild browser bundle pipeline

The extension still needs first-class integration with the persistent intelligence graph now available to mobile.

### Mobile

- React Native
- Expo Router
- TypeScript
- shared-link and pasted-link ingestion
- article and video result surfaces
- persisted intelligence discovery
- watchlists and in-app alerts
- canonical entity/story/claim/media detail pages
- persisted graph traversal and chronological history

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
- mobile canonical intelligence detail/history productization.

### Current next roadmap unit

**Chrome extension ↔ persistent intelligence integration.**

Target product flow:

```text
Analyze article / video
        ↓
Persisted Sportabase intelligence object
        ↓
Open canonical history / intelligence
        ↓
Watch future changes
        ↓
See persisted changes through in-product alert/history surfaces
```

The extension integration should consume existing backend product contracts rather than create a separate intelligence model.

Initial intended scope:

- expose persisted canonical intelligence from extension analysis results;
- allow opening entity/story/claim/media history from the extension;
- allow watching supported canonical objects using explicit stable client identity;
- surface whether a watched object has future persisted alert activity where product-safe data permits;
- preserve article/video scoring semantics;
- preserve lexical-search vs canonical-relationship distinctions;
- do not add push/email/SMS/Slack/webhook/browser-notification delivery yet.

After extension integration, a strong next product unit is **Sources + Reporters as first-class intelligence objects**, including dedicated product-history contracts before making them watchable.

Future predictive work may use information momentum, evidence growth, source quality, team/player context, structured sports data, and market movement. It must be evaluated empirically and must not be smuggled into the Merit Score as an unsupported truth predictor.

---

## Local worktree safety

The primary local repo may contain unrelated UI/design work on other branches. Do not reset, switch, pull, or clean that worktree without first inspecting it.

Use isolated Git worktrees for new roadmap units.

Verified recent feature worktrees include:

```text
C:\Users\Yuvraj\Documents\Sportabase-mobile-watchlists-alerts
C:\Users\Yuvraj\Documents\Sportabase-mobile-intelligence-detail
```

Those feature branches are already merged. Do not extend them for the next roadmap unit.

---

## Conversation continuity protocol

> **Context warning for every future Sportabase chat:** Treat a long conversation as an operational risk. Before the chat becomes large enough that earlier technical context may be truncated, proactively warn Yuvraj and propose a checkpoint update. Do not wait for the final message or pretend an exact context meter is available. The warning should occur early enough to capture the current branch, base/head SHAs, worktree, dirty/staged state, files changed, tests and exact results, architectural decisions, invariants, blockers, and next command.

When a context checkpoint is needed:

1. Stop before starting another large implementation or review chunk.
2. Summarize only verified state; clearly distinguish remote, committed, local, staged, and planned work.
3. Update this README/checkpoint on GitHub when authorized.
4. Produce a self-contained handoff prompt for the next chat.
5. Never claim a branch, commit, push, test result, or clean worktree without evidence.
6. Preserve exact SHAs, exact test commands/results, and non-negotiable semantic constraints.

Recommended warning language:

```text
Context warning: this Sportabase thread is getting long enough that we should checkpoint before the next major step. I should save the verified Git/GitHub state, tests, decisions, remaining risks, and the exact next action now, then give you a clean handoff prompt for a new chat.
```

---

## Handoff source of truth

For a new Sportabase chat, use this README together with live Git/GitHub inspection. The README is a checkpoint, not a substitute for verification.

At this checkpoint the authoritative remote base is:

```text
main = 9691575c0232450a16170973bb54d9a293bb7494
```

Before beginning the next feature:

1. verify live `origin/main`;
2. create a clean feature branch/worktree from that verified base;
3. inspect the current extension architecture before editing;
4. implement the extension persistent-intelligence integration as a bounded product slice;
5. avoid backend changes unless a concrete missing product contract is demonstrated.

Do not return to Watchlists + Alerts backend implementation or mobile scaffolding unless a verified regression requires it.

---

## Long-term vision

Sportabase aims to become the intelligence layer for global sports information: a system that remembers what was claimed, traces where it came from, measures how evidence changed, learns from outcomes, and helps users understand the story rather than merely consume the headline.

**Sportabase — understand the story, not just the headline.**
