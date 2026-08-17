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

The accepted provider-call range is **0-12**.

- `0` is a true dry run. It reads no API key, makes exactly zero Gemini calls,
  and consumes zero Gemini tokens.
- `12` is the live full-case headroom required to preserve the entire
  two-positive-plus-hard-negative inspection scope.
- `1-11` are not spent by the live CLI because they cannot guarantee completion
  of the frozen full-case path without truncating the evaluation.

A nonzero live run requires explicit `--live` opt-in and a configured
`GEMINI_API_KEY`. The budget is checked before every provider call, so call 13
cannot be sent.

Before the API key is used or any provider call is made, the CLI prints a
zero-cost execution plan. For the frozen Bellingham case the plan is:

- 3 anchor/candidate pairs;
- 6 guaranteed semantic calls (2 per pair);
- up to 6 conditional claim-observation calls (2 per pair that survives the
  model-dependent exact-claim gate);
- minimum 6 provider calls;
- maximum 12 provider calls;
- possible actual totals: 6, 8, 10, or 12.

The exact final provider-call count cannot be known honestly before the model
runs, because the observation calls are conditional on model-dependent
exact-claim acceptance. The CLI therefore reports the exact pre-run set of
possible totals instead of inventing a number, then logs the exact actual count
as calls occur.

Each provider call logs only safe operational telemetry:

- call index and hard cap;
- mode and model;
- status;
- prompt tokens;
- output tokens;
- thought tokens;
- cached tokens;
- total tokens;
- cumulative call count;
- cumulative token count.

The post-call and post-run token values come from Gemini `usage_metadata`. If the
provider omits `total_token_count`, the evaluator reconstructs total tokens from
prompt + output + thought token counts.

The sanitized report contains the per-call telemetry and aggregate totals, but
never prompt contents, raw model response text, API keys, or client identity.

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

The frozen captures are short original evaluation paraphrases of a historical
sports scenario. They are not publisher verbatim text and the evaluator does not
fetch the original sources.

## Run

From `backend/`, inspect the full plan for zero provider cost:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --describe
```

A true zero-call dry run is:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --max-calls 0
```

The full bounded live run is:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live `
  --live `
  --max-calls 12 `
  --json-out .\golden-live-report.json
```

The live run does **not** necessarily make 12 calls. Twelve is only the
fail-closed headroom. The exact actual total will be one of 6, 8, 10, or 12 and
will be printed together with exact observed token usage.

A quality miss does not authorize any product or Merit change. It is recorded as
a failure to investigate. The CLI exits nonzero for a hard safety failure or an
incomplete provider run, but not merely because a model-dependent quality metric
misses the golden expectation.
