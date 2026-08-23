# Sportabase Workflow Guide

This file is the durable working agreement for Sportabase development. Keep it current as the project evolves. Add or revise rules when a workflow preference, repository constraint, testing convention, or architectural safety boundary becomes stable enough to rely on across future context windows.

## 1. Command Style

For Sportabase coding work, provide large, directly runnable Windows PowerShell blocks.

- Never use placeholders such as `<file>`, `<branch>`, `<path>`, or pseudo-shell examples in blocks intended to be executed.
- Use exact known paths, filenames, branch names, and commit messages.
- Prefer one substantial checkpoint block over many tiny command fragments.
- Stop only when terminal output is genuinely needed before the next risky step.
- Keep commands fast, precise, and easy to paste into PowerShell.

Known local paths:

```text
C:\Users\Yuvraj\Documents\Sportabase
C:\Users\Yuvraj\Documents\Sportabase\backend
```

## 2. Standard Backend Validation Order

For backend work, use this order unless the change clearly requires a different gate:

1. Make the related implementation edits together.
2. Run `py_compile` and import checks when relevant.
3. Run focused `pytest` tests for the changed subsystem.
4. Run the full backend regression before commit:

```powershell
cd C:\Users\Yuvraj\Documents\Sportabase\backend
python -m pytest -q
```

5. Return to repo root and run:

```powershell
cd C:\Users\Yuvraj\Documents\Sportabase
git status --short
git diff --check
git diff --stat
```

6. Stage exact intended files only.
7. Commit with a specific message.
8. Push the exact current branch.
9. Fetch and verify local/remote refs match.

Typical final verification:

```powershell
git fetch origin
git status -sb
git rev-parse HEAD
git rev-parse origin/<exact-current-branch>
git log -1 --oneline
```

In executable blocks, replace the branch token above with the real branch name before presenting it to the user.

## 3. Environment Guards

Preserve known regression-test environment guards where required.

For tests that need the historical default-OFF Control Room state:

```powershell
$env:SPORTABASE_CONTROL_ROOM_ENABLED = "0"
```

Remove the temporary override after validation:

```powershell
Remove-Item Env:SPORTABASE_CONTROL_ROOM_ENABLED -ErrorAction SilentlyContinue
```

Do not modify `backend\.env` merely to force a regression-test state.

## 4. Test Safety

- Focused tests first, full backend regression before commit.
- Prefer `pytest` for the backend regression gate.
- Do not trigger real Gemini/provider calls during ordinary regression tests.
- If a test unexpectedly attempts a live provider call, stop and inspect instead of consuming quota blindly.
- Treat warnings separately from failures unless they indicate a real regression.
- Do not commit if focused tests, full regression, or `git diff --check` fail.

## 5. Git Discipline

- Work on the intended feature branch, not `main`, unless explicitly requested.
- Verify branch/state before risky edits when branch identity matters.
- Stage exact files only; do not sweep unrelated changes into commits.
- Do not alter unrelated pending work.
- Push the exact branch name.
- After push, verify `HEAD` and `origin/<branch>` resolve to the same SHA.
- A clean `git status -sb` after push is the preferred final checkpoint.

## 6. Sportabase Merit / Evidence Safety Rules

These product rules must remain intact across implementation work:

- **No corroboration is not the same as false.** A genuine first scoop must not be penalized merely for being early or unverified.
- Article classification such as `transfer_official` describes how the article presents itself; it does not establish truth.
- Merit Score is broader informational merit, not a probability-of-truth score.
- Evidence status should remain conceptually separate from article type and Merit.
- Dependency/copying may reduce originality or independence but does not automatically establish falsity.
- Weak provenance or unknown source identity should limit positive evidence rather than automatically create a harsh falsehood penalty.
- Strong negative Merit eligibility requires machine-verifiable negative evidence, not persuasive model prose alone.
- Raw/model-derived contradiction edges do not by themselves establish falsehood.
- Existing certified positive live Merit behavior must remain isolated from experimental negative Merit work.
- Negative Merit remains shadow/calibration-only until separately certified for live release.
- Do not invent negative score weights before calibration against defensible cases.

## 7. Provider / Quota Discipline

- Minimize paid/provider calls during development.
- Prefer deterministic tests, mocks, persisted fixtures, and zero-provider validation whenever possible.
- Do not repeat an already-completed live provider test without a specific reason.
- When a provider call is necessary, make the call budget explicit and bounded first.

## 8. Working Style

- Prefer larger implementation blocks rather than over-granular instructions.
- Be explicit about what is verified repository state versus assumption.
- Never invent repository facts.
- Use synthetic fixtures that are obviously fictional when testing examples could otherwise be mistaken for real sports news.
- Keep architectural changes conservative around truth, authority, evidence, and live Merit boundaries.

## 9. Maintenance Rule

This is a living project file.

Update it when a new development convention, safety rule, repository workflow, test requirement, environment guard, or architectural invariant becomes stable enough that future Sportabase work should rely on it. Do not clutter it with temporary debugging notes, one-off guesses, or unverified assumptions.

## PowerShell Git Pager Safety

- In runnable PowerShell validation blocks, prefer git --no-pager diff, git --no-pager diff --check, git --no-pager diff --stat, and git --no-pager log so Git cannot interrupt a checkpoint with an interactive pager.
- If Git has already opened the pager, press q to return to PowerShell.

## Negative Merit Two-Gate Calibration Boundary

- A persisted direct-stakeholder contradiction lineage alone is not sufficient for negative-Merit penalty calibration.
- A negative-evidence candidate becomes calibration-eligible only when both the direct-authority contradiction lineage gate and the persisted machine-verified contradiction-semantics gate pass for the claim.
- Machine-verified contradiction semantics describe verified source/claim semantics; they do not by themselves establish objective falsity.
- Passing both gates still does not authorize a live negative Merit adjustment. Numeric negative weights require separate calibration, real-world controls, and a dedicated negative release certificate/runtime.
- Absence of corroboration, an early exclusive, or a model-only contradiction must never create a negative Merit penalty.

## Negative Merit Evaluation Boundary

- Deterministic negative-Merit policy fixtures validate safety behavior only; they are not real-world calibration evidence.
- The policy evaluation harness must include a two-gate candidate plus authority-only, semantics-only, no-negative-evidence, and early-exclusive controls.
- Until real-world calibration is separately certified, any nonzero negative adjustment, changed shadow total, changed live total, or enabled live negative score effect is a safety violation.
- Passing policy evaluation never authorizes a numeric negative weight or live negative Merit.
- Real-world machine-verifiable calibration cases and a separate negative release certificate/runtime are required before any live negative score effect.

## Negative Merit Calibration Observation Boundary

- Measure real-world legacy Merit score distributions for two-gate observations and negative controls before selecting any numeric penalty weight.
- A two-gate observation is not a falsehood label. It records verified direct-authority contradiction lineage plus machine-verified contradiction semantics only.
- Negative-Merit calibration dataset v1 accepts unresolved outcomes only. Do not create or trust resolved-against-claim labels until a dedicated machine-verifiable canonical-outcome verifier exists.
- Real-world calibration observations require immutable HTTPS source captures with content hashes and machine-verified lineage.
- Early exclusives and absence-of-corroboration cases belong in the control population and must not become negative evidence.
- Calibration observation collection must not change shadow or live Merit, choose a penalty weight, or authorize release.

## Canonical Outcome Resolution Boundary

- Canonical outcome comparison is deterministic structured-state analysis, not source verification and not a truth oracle.
- Canonical outcome v1 supports only positive completed-transfer claims and requires the same canonical subject, transfer destination, and explicit effective period.
- Overlapping explicit origin and transfer-kind fields must not conflict.
- A later failed/cancelled transfer state, or an explicit negation of the same completed transfer, may become a resolution-against-claim candidate only.
- Sequential states such as agreed then failed must not automatically be treated as falsehood because both may have been accurate at different times.
- A resolution candidate cannot become a resolved calibration label until its later outcome is separately bound to machine-verified authoritative source evidence.
- Canonical outcome comparison cannot change shadow or live Merit, select a numeric penalty, or establish permanent objective truth.

## Verified Canonical Outcome Resolution Boundary

- A deterministic canonical-outcome comparison is not enough to create a resolved-against-claim label by itself.
- Verified canonical resolution requires a persisted structured canonical claim, a verified canonical-outcome proof with immutable content hash, a canonical URL belonging to the verified source, and verified direct-stakeholder claim-participation lineage.
- The outcome proof must itself be part of the verified direct-authority participant lineage for the claim.
- A verified resolution-against-claim emits a machine-verified stance judgment with basis class `canonical_resolution`; callers do not choose the machine derivation mode or evaluator identity.
- Canonical resolution may satisfy the machine semantic contradiction gate, but it still does not establish permanent objective truth or authorize a numeric negative Merit penalty.
- Supporting or temporally indeterminate outcomes must fail closed and must not create negative resolution evidence.
- Live negative Merit remains disabled until real-world calibration and a separate negative release certificate/runtime are completed.

## Resolved Negative Merit Calibration Boundary

- Negative-Merit calibration dataset v2 distinguishes unresolved two-gate observations from `resolved_against_claim_observation` cases.
- A resolved-against-claim calibration label is accepted only when accompanied by the persisted verified canonical-outcome-resolution verifier result for the same claim.
- The verifier result must preserve the machine-verified `stance=contradicts` judgment with basis class `canonical_resolution`, verified evidence identity, direct-authority lineage, and immutable canonical source capture hash.
- The verifier's canonical URL, source identity, and content SHA256 must match an immutable source capture in the calibration observation.
- A resolved label remains a temporally verified canonical resolution, not a declaration of permanent objective truth.
- Unresolved observations may not carry resolved-outcome verification, and resolved observation classes may not be used without resolved status.
- Resolved calibration examples remain measurement-only: numeric negative penalty selection and live negative Merit remain disabled until separate calibration and release certification.

## Resolved Negative Merit Real-World Corpus Boundary

- Real-world negative-Merit calibration uses a frozen offline corpus under `backend/evals`; synthetic policy fixtures do not count as real-world evidence.
- The corpus keeps separate populations for resolved-against-claim cases, unresolved two-gate cases, authority-only controls, semantic-only controls, no-negative-evidence controls, and legitimate early-exclusive controls.
- A corpus is not measurement-complete while any required population is absent.
- Resolved cases still require the exact verified canonical-outcome-resolution lineage accepted by the calibration dataset.
- The corpus digest freezes case content so deliberate case changes become explicit evaluation-data changes.
- Corpus evaluation cannot select a numeric penalty, enable live negative Merit, call providers, or establish permanent objective truth.
- Only after sufficient real-world resolved cases and controls are collected and their score distributions inspected may penalty weights be evaluated.

## Negative Merit Real-Case Inventory Boundary

- Inspect persisted real-world calibration candidates through a read-only SQLite inventory before exporting anything into the frozen negative-Merit corpus.
- Recover the pre-live-positive-overlay legacy Merit total from persisted analysis debug lineage rather than treating the stored live score as the calibration baseline.
- Persisted direct-authority and machine-semantic evidence may be reconstructed into gate inputs only when their exact verifier contracts still validate through the Negative Merit shadow.
- A resolved candidate requires persisted machine-verified `stance=contradicts` lineage with basis class `canonical_resolution` plus its verified canonical-outcome proof record.
- Inventory classification is discovery metadata, not corpus admission, a falsehood label, or release authorization.
- No-negative-evidence cases must never be automatically relabeled as early-exclusive controls; legitimate exclusivity requires separate curation.
- The inventory must perform no provider calls, no database writes, no verification persistence, and no live Merit changes.

## Historical Article Intelligence Backfill Boundary

- Legacy `stories` rows may be inspected as potential historical claim seeds, but current rule-classifier confidence alone is not sufficient for automatic backfill admission.
- Historical claim backfill requires an explicit high-precision headline claim signal compatible with the current claim-bearing article type; classifier/signal mismatches require review.
- Newsletter, subscription, signup, and similar service-content rows must never be admitted as sports-claim seeds merely because the generic classifier emits a claim-bearing type.
- A historical backfill admission means only that the headline may be recorded as a reported claim. It does not establish truth, authority, contradiction, corroboration, or live Merit impact.
- Stored legacy `stories.merit_score` values are archival outputs from the old pipeline and are not valid current negative-Merit calibration baselines.
- Historical backfill planning must be read-only and provider-free. Any later persistence step must use an explicit frozen admission set and exact database safety checks.

## Historical Claim Seed Persistence Boundary

- Historical article claim persistence must use a frozen allowlist produced from the high-precision planner; current planner digest and exact admitted story identities must still match before any write.
- The frozen historical backfill persists only the reported-claim seed layer: source, media item, primary claim, source observation, and claim link.
- Historical RSS/feed title-summary material is explicitly not a full article capture. Its media metadata must set `full_article_capture=false`, and the real-case inventory must therefore keep it ineligible for calibration export until a genuine current article capture and analysis snapshot exist.
- Historical `stories.merit_score` values remain archival only and must never become the current negative-Merit calibration baseline.
- Historical claim-seed persistence performs no Gemini/provider calls, creates no verification evidence, establishes no truth, changes no live Merit, and creates no analysis snapshot.
- The backfill must be idempotent and must be rehearsed against a database clone before applying the frozen allowlist to the local Sportabase database.

## Current Full-Article Capture Boundary

- A historical claim seed becomes a current full-capture candidate only after Sportabase can fetch the live source through its safe article resolver and the fetched page still matches the frozen claim identity.
- Capture selection must consider semantic and article-type stability as well as retrieval quality. Fetch success, same-domain identity, and title overlap alone are insufficient when the current page represents a different claim or article state.
- Persist the exact source URL, extracted title, body SHA-256, analysis-content hash, capture time, article type, scoring versions, and snapshot identity in a manifest. Do not store copyrighted article body text in the repository.
- Provider-free capture may use the normal Sportabase article scoring and snapshot path only with Gemini generation, intelligence-shadow discovery, analysis-cache writes, and user-history writes explicitly suppressed.
- A current scoring snapshot is not a truth judgment and creates no verification evidence by itself.
- `corpus_export_ready` means structural readiness only. It does not admit a case into the frozen calibration corpus and does not establish truth or falsity.
- A structurally ready no-negative-evidence case still requires curator evidence before it may be treated as an early-exclusive control. Absence of corroboration or contradiction never proves exclusivity.

## Real-World Negative Candidate Batch Boundary

- Real-world negative-Merit candidate collection freezes both the claimant-side page and the later direct-authority statement using HTTPS URLs, capture timestamps, and SHA-256 content hashes.
- Candidate collection may measure the current deterministic Merit score of the retrievable claimant page, but that score is not a truth probability and the measurement does not authorize any numeric penalty.
- A publisher claim paired with a direct club denial remains an unverified contradiction candidate until the existing direct-authority and machine-semantic verifier contracts independently pass.
- Candidate capture itself establishes no objective claim truth, creates no live Merit effect, performs no Gemini/provider call, and writes nothing to the production database.
- Direct-authority denial candidates must be evaluated semantically before calibration; headline opposition or apparent contradiction alone is insufficient.
- The sacred first-scoop rule remains unchanged: absence of corroboration is never negative evidence.
- When a direct authority provides an original-language statement and an AI-translated mirror, freeze the original-language authority page for evidence capture; translation may assist presentation but must not replace the canonical source capture.

## Real-World Two-Gate Calibration Boundary

- Real-world direct-denial calibration must re-fetch the frozen claimant and authority URLs and require exact equality with the previously frozen content SHA-256 values before verifier execution.
- Deterministic claimant-assertion and direct-authority-denial phrases may feed the existing `direct_authority_record` trusted stance basis only after exact frozen-source identity and subject checks pass.
- Real-world two-gate calibration executes the production direct-authority, direct-stakeholder contradiction, machine-verified revision, machine semantic contradiction, Negative Merit shadow, and calibration-dataset contracts in an isolated evaluation database. Evaluation-only entity bindings must never be confused with production persisted bindings.
- A two-gate calibration observation is evidence that the captured source semantics contradict the captured claim under the verified lineage; it is not permanent objective truth.
- The first provisional negative adjustment is selected from the measured real-world two-gate/control score separation using half of the median separation, rounded upward, with a 15-point cap and a 5-point floor. The calibration report itself never authorizes live release.
- Live negative Merit still requires a separate release certificate/runtime with fail-closed certificate identity, strict two-gate eligibility, explicit score clamping, positive-release composition tests, and first-scoop protection.
