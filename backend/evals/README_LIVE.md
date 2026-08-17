# Sportabase model-dependent golden evaluation

This is the **observed full-pipeline evaluation** layer built on top of the frozen
#33 deterministic golden corpus. It is evaluation tooling only; it is not a
production API or worker path.

The default live subset contains exactly one full scenario-derived case:

- `football_bellingham_real_madrid_2023`

The case keeps all three routed same-subject candidates from the frozen corpus:

- a positive web corroborator;
- a positive YouTube corroborator;
- a same-subject X hard negative that must fail the exact-claim gate.

The anchor is a non-article X capture, so there is no article-style legacy Merit
baseline to fabricate. The expected Merit baseline mode is `not_applicable`.

## Safety, call planning, and token telemetry

A live run requires explicit `--live` opt-in and a configured `GEMINI_API_KEY`.
The default and hard maximum provider-call budget is **12 calls**. The budget is
checked before every provider call, so call 13 cannot be sent.

Before the API key is used or any provider call is made, the CLI prints a zero-cost
execution plan. For the frozen Bellingham case the plan is:

- 3 anchor/candidate pairs;
- 6 guaranteed semantic calls (2 per pair);
- up to 6 conditional claim-observation calls (2 per pair that survives the
  model-dependent exact-claim gate);
- minimum 6 provider calls;
- maximum 12 provider calls;
- possible actual totals: 6, 8, 10, or 12.

The exact final provider-call count cannot be known honestly before the model runs,
because the observation calls are conditional on model-dependent exact-claim
acceptance. The CLI therefore reports the exact pre-run range instead of inventing a
number, then logs the exact actual count as calls occur.

Each provider call logs only safe operational telemetry: call index, cap, mode,
model, status, prompt tokens, output tokens, thought tokens, cached tokens, total
tokens, and cumulative call/token totals. Prompt contents, model response text, and
the API key are never written to the call log or committed baseline.

The live evaluation:

- creates a fresh temporary SQLite database for the case;
- stores the frozen captures through the real browser-capture inbox path;
- runs the real multi-source cluster execution and exact-common-claim gate;
- runs real Gemini semantic fusion and claim-observation semantics;
- runs adjudication and corroboration machinery;
- runs #32 validated story/claim graph materialization;
- records provider call and token metadata locally in the report;
- does not write the production Gemini usage ledger;
- does not open `backend/data/sportabase.db`;
- does not invoke the Live Merit release path;
- never treats a golden label as truth, authority, or independence.

The frozen captures are short original evaluation paraphrases of a historical sports
scenario. They are not publisher verbatim text and the evaluator does not fetch the
original sources.

## Run

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --describe
```

The command above spends **zero** provider calls and prints the full call plan.
To make the bounded live run:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live `
  --live `
  --max-calls 12 `
  --json-out .\golden-live-report.json
```

A quality miss does not authorize any product or Merit change. It is recorded as a
failure to investigate. The CLI exits nonzero for a hard safety failure or an
incomplete provider run, but not merely because a model-dependent quality metric
misses the golden expectation.
