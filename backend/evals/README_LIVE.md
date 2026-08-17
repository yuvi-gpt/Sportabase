# Sportabase model-dependent golden evaluation

This is the **observed full-pipeline evaluation** layer built on top of the frozen
#33 deterministic golden corpus. It is evaluation tooling only; it is not a
production API or worker path.

The default live subset contains exactly two scenario-derived cases:

- `football_bellingham_real_madrid_2023`
- `f1_alonso_aston_extension_2024`

Both anchors are non-article captures, so there is no article-style legacy Merit
baseline to fabricate. The expected Merit baseline mode is `not_applicable`.

## Safety and cost boundary

A live run requires explicit `--live` opt-in and a configured `GEMINI_API_KEY`.
The default and hard maximum provider-call budget is **24 calls**. The budget is
checked before every provider call, so call 25 cannot be sent.

The live evaluation:

- creates a fresh temporary SQLite database for every case;
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

The frozen captures are short original evaluation paraphrases of historical sports
scenarios. They are not publisher verbatim text and the evaluator does not fetch the
original sources.

## Run

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --describe
```

The command above spends **zero** provider calls. To make the bounded live run:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live `
  --live `
  --max-calls 24 `
  --json-out .\golden-live-report.json
```

A quality miss does not authorize any product or Merit change. It is recorded as a
failure to investigate. The CLI exits nonzero for a hard safety failure or an
incomplete provider run, but not merely because a model-dependent quality metric
misses the golden expectation.
