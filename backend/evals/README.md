# Sportabase multimodal golden evaluation

This directory is an **offline evaluation harness**, not a production runtime path.
It was introduced after the autonomous multimodal pipeline, multi-source clustering,
and validated story/claim graph materialization were already in place.

## What the frozen corpus is

`multimodal_golden_cases.py` contains historical sports **scenario-derived** cases.
The short capture text is original evaluation prose. It does not copy publisher
articles or social posts, and the default runner performs no network fetches.

The corpus covers football and Formula One, all browser-capture platforms currently
supported by Sportabase (`web`, `x`, `instagram`, `tiktok`, `reddit`, `facebook`,
`youtube`), multilingual routing, same-subject hard negatives, ambiguous subject
partitions, multi-entity rejection, same-URL exclusion, and no-signal fail-closed
behavior.

Golden labels are **evaluation labels only**. They do not establish truth, source
authority, independence, evidence verification, training eligibility, or Merit.

## Default deterministic run

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden
```

Optional JSON report:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden `
  --json-out .\golden-report.json
```

The deterministic mode creates a fresh temporary SQLite database for every case,
loads the real Sportabase schema, stores the frozen browser captures through the
real inbox persistence path, then executes the real candidate-discovery and
multi-source selection services with `semantic_assessments=0`.

It does **not**:

- use `backend/data/sportabase.db`;
- call Gemini;
- fetch the network;
- alter Live Merit;
- treat ranking as truth confidence.

## Full-pipeline observed scoring

The deterministic layer deliberately stops before model-dependent exact-claim
interpretation. To score a later real full-pipeline run, first create the expected
artifact shape:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden `
  --write-observed-template .\observed-template.json `
  --describe
```

Populate an observed artifact from the actual pipeline, then score it:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden `
  --observed .\observed-run.json `
  --json-out .\observed-score.json
```

Observed scoring checks accepted/rejected members, story count, Merit-baseline mode,
and safety boundaries. It explicitly fails if a run reports a synthetic Merit
baseline, a Live Merit effect, or truth/authority/independence establishment from
the evaluation flow.

## Interpreting results

The shortlist and candidate score are routing signals. A same-subject hard negative
is expected to survive deterministic routing in several cases and must be rejected
later by the exact-claim layer. That is intentional: the golden harness grades each
stage against the responsibility that stage actually owns.

Do not tune product logic merely to maximize this frozen set. Add new cases for real
failure modes, keep old cases immutable when possible, and record any deliberate
label change as an evaluation-version change.
