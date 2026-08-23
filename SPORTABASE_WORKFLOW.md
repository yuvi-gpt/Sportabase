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
