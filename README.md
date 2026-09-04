# Sportabase

## Evidence-first sports intelligence

Sportabase is a sports intelligence platform that turns articles, videos, sources, claims, and evidence into a persistent, explainable intelligence graph.

It is not merely a summarizer and it is not a truth machine. Its job is to answer:

- What is being claimed?
- Which media items and stories carry the claim?
- Who originated or repeated it?
- What evidence supports, contradicts, corrects, or supersedes it?
- Which corroboration is genuinely independent?
- How has the persisted intelligence changed over time?
- What should a user be able to search, revisit, watch, and eventually act on?

The product currently spans a FastAPI backend, Chrome extension, React Native mobile app, and internal control-room surfaces. SQLite remains the current persistence layer.

---

## Current project checkpoint — 4 September 2026

The backend has moved well beyond the original URL-in, summary-out MVP. The durable foundation now includes:

- article and YouTube analysis with distinct article/video semantics;
- canonical media, story, claim, entity, source, reporter, evidence, and snapshot records;
- canonical entity resolution and aliases;
- claim extraction, normalization, support, evidence, and evolution history;
- story clustering and story evolution;
- source profiles, reporting coverage, and source-independence analysis;
- persistent analysis and operational event history;
- readiness, capacity, quota, provider-reliability, and multi-model routing controls;
- long-video transcript compression and analysis;
- golden-set evaluation and structured validation paths;
- homepage storyline aggregation;
- public search and historical-intelligence APIs;
- a locally completed Watchlists + Alerts V1 implementation awaiting its final Git commit and push.

### Latest remote checkpoint

Roadmap item **#12 — Search + Historical Intelligence V1** is committed on:

- Branch: `backend-search-historical-intelligence-v1`
- Commit: `8f691a53f6d445587169fdd8ce36b88e2776d4c9`
- Commit message: `add search and historical intelligence API`

It exposes:

- `GET /intelligence/search`
- `GET /intelligence/entities/{entity_id}/history`
- `GET /intelligence/stories/{story_id}/history`
- `GET /intelligence/claims/{claim_id}/history`
- `GET /intelligence/media/{media_item_id}/history`

The API uses product-safe projections and deterministic cursor pagination. Search is lexical discovery only; it does not invent canonical relationships or treat a matching string as verified intelligence.

### Current local checkpoint

Roadmap item **#13 — Watchlists + Alerts V1** has been implemented in the local worktree:

- Worktree: `C:\Users\Yuvraj\Documents\Sportabase-watchlists-alerts`
- Branch: `backend-watchlists-alerts-v1`
- Exact base: `8f691a53f6d445587169fdd8ce36b88e2776d4c9`
- Current state: six intended files staged; not yet committed or pushed at the time of this update

Final exact-tree backend checkpoint:

```text
3651 passed, 3 skipped, 12 warnings, 694 subtests passed in 96.29s
```

Staged feature diff:

```text
6 files changed, 699 insertions(+)
```

The staged files are:

- `backend/app/application/composition.py`
- `backend/app/db/schema.py`
- `backend/app/routes/watchlists_product.py`
- `backend/app/watchlists/__init__.py`
- `backend/app/watchlists/runtime.py`
- `backend/tests/test_watchlists_alerts_api.py`

The immediate next action is to inspect the staged diff/status one last time, commit it, push `backend-watchlists-alerts-v1`, and verify the remote branch and commit SHA. Do not redo the implementation or rerun the full backend suite unless production code changes.

---

## Watchlists + Alerts V1

### Product API

- `POST /watchlists`
- `GET /watchlists`
- `DELETE /watchlists/{watch_id}`
- `POST /watchlists/alerts/reconcile`
- `GET /watchlists/alerts`
- `POST /watchlists/alerts/{alert_id}/read`

### Supported targets

V1 watches exactly four stable public intelligence objects:

- `entity`
- `story`
- `claim`
- `media`

Sources and reporters are deliberately excluded until they have equivalent dedicated product-history contracts.

### Ownership and privacy invariants

- Every private route requires an explicit, non-empty `x-sportabase-client-id` header.
- There is no IP, `x-forwarded-for`, or `request.client.host` fallback.
- The raw installation ID is never persisted or returned.
- A SHA-256 digest with the namespace `sportabase:watchlists:v1:` is persisted as the internal owner key.
- Every private read and write is client-scoped.
- Cross-client watch and alert probes return `404`.
- Watch IDs and alert IDs are opaque.
- `user_history` is untouched and is not reused as subscription state.

### Baselines, watermarks, and late arrivals

Creating a watch establishes a baseline at the current maximum global discovery sequence, so historical intelligence does not flood the alert inbox.

Eligible persisted events are appended by SQLite triggers to an AUTOINCREMENT discovery ledger. Watches advance through that total order using an integer sequence rather than an event timestamp. This preserves correct behavior for:

- identical timestamps;
- late-arriving evidence whose `occurred_at` predates watch creation;
- repeated reconciliation;
- bounded partial batches;
- concurrent reconciliation;
- process restarts.

Alert insertion and watermark advancement occur together inside a transaction. A failed alert write cannot silently advance beyond the event. Stable source-event keys plus a database uniqueness constraint prevent duplicate alerts.

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

- Entity watches react only through verified claim/entity participation and graph relationships derived from that verified path. Lexical mentions do not alert.
- Story watches can react to new claim links, media links, source observations, reporter observations, evidence links, and analysis snapshots.
- Claim watches can react to observation/evidence links, verified entity participants, story links, adjudication revisions, and adjudication transitions.
- Media watches react to new analysis snapshots.

Alert summaries are deterministic and neutral. They do not use AI and do not claim that an event is breaking, confirmed, true, reliable, or credible unless that precise persisted semantic is explicitly represented.

Deleting a watch cascades its subscription alerts without altering the underlying intelligence or another client's watch. Alerts begin unread; marking one read is client-scoped and idempotent. Inbox cursors are versioned, validated, deterministic, and bound to the current client and filters.

---

## Product semantics that must not regress

### Articles

The **Merit Score** measures reporting/informational quality and evidential support. It is not a truth probability or a credibility percentage.

### Videos

Video analysis keeps these concepts separate:

- Evidence Score
- Logic Score
- Verdict

Do not create a composite video credibility score.

### Corroboration

Repetition is not independence. Ten rewrites of one report remain one reporting origin unless the persisted provenance graph establishes otherwise.

### History

Persisted history distinguishes domain time (`occurred_at` or `observed_at`) from discovery/materialization time. Chronology alone is never proof of truth, credibility, or novelty.

---

## Architecture

### Backend

- Python 3.14-compatible FastAPI application
- SQLite persistence with idempotent startup schema initialization
- dedicated domain/service/runtime modules rather than route-heavy business logic
- product-safe public projections separated from internal/admin records
- provider routing, capacity accounting, caching, retry, and readiness controls

### Browser extension

- JavaScript/Chrome Extension APIs
- article extraction and analysis overlay
- YouTube transcript extraction and analysis
- localized UI, loading states, settings, caching, and trust-oriented result presentation

### Mobile

- React Native, Expo Router, and TypeScript
- shared-link and pasted-link ingestion
- article and video result surfaces
- evolving Home, Explore, History, story, media, watchlist, and notification experiences

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

Completed backend foundations include entity resolution, claim/story intelligence, evidence and support graphs, history, source profiles, reporting coverage, independence, story evolution, storyline aggregation, golden evaluation, long-video compression, provider reliability, task-specific model routing, and Search + Historical Intelligence V1.

Current boundary:

1. Commit and push Watchlists + Alerts V1.
2. Verify the exact remote branch head and diff.
3. Decide the next roadmap unit before opening another implementation worktree.
4. Keep delivery channels—push, email, SMS, Slack, webhooks, and browser notifications—out of the V1 in-app alert subsystem.
5. Preserve the completed backend intelligence graph while productizing watchlists, history, story/media pages, and alert experiences across mobile and extension surfaces.

Future predictive work may use information momentum, evidence growth, source quality, team/player context, structured sports data, and market movement. It must be evaluated empirically and must not be smuggled into the Merit Score as an unsupported truth predictor.

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

For a new Sportabase chat, use this README together with live Git/GitHub inspection. The README is a checkpoint, not a substitute for verification. If the local worktree and GitHub disagree, stop and establish which state is authoritative before changing code.

The next chat should begin by verifying:

```powershell
cd C:\Users\Yuvraj\Documents\Sportabase-watchlists-alerts
git status -sb
git status --short
git rev-parse HEAD
git log -1 --oneline
git diff --cached --stat
```

At the recorded checkpoint, the expected next operation is final commit/push verification for Watchlists + Alerts V1—not another implementation pass.

---

## Long-term vision

Sportabase aims to become the intelligence layer for global sports information: a system that remembers what was claimed, traces where it came from, measures how evidence changed, learns from outcomes, and helps users understand the story rather than merely consume the headline.

**Sportabase — understand the story, not just the headline.**
