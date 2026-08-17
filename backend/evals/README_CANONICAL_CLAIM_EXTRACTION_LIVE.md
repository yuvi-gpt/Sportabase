# Sportabase #35C — bounded live structured claim extraction

#35C is the first live-provider validation of the locked #35B structured extraction boundary and the locked #35A deterministic canonical-claim identity contract.

It is evaluation tooling only. It does not switch the production multimodal bridge, migrate existing claims, change story membership, change adjudication, change authority or independence logic, or affect Live Merit.

## What #35C measures

#34B showed that independently generated free-text claim candidates were too unstable to serve directly as cross-source deterministic identity.

#35A introduced deterministic structured claim identity. #35B introduced a strict model-output boundary, entity allowlist and fail-closed parser.

#35C asks one narrow empirical question:

> Can real Gemini extraction produce structured candidates from four independent Bellingham scenario texts such that the locked deterministic identity layer converges the two positives and separates the same-subject hard negative?

## Exact provider plan

The frozen live case is `football_bellingham_real_madrid_2023`.

Exactly four unique source texts are evaluated:

1. X anchor;
2. web positive;
3. YouTube positive;
4. same-subject X hard negative.

Each unique source is extracted exactly once.

Therefore:

- exact provider calls: 4;
- repeated anchor calls: 0;
- one internal eval client bucket per source;
- maximum calls per eval client: 1;
- call 5 is forbidden;
- model: `gemini-3.5-flash`;
- mode: `canonical_claim_extraction`.

All four real requests pass through the existing #34A model-aware capacity runtime and production `gemini_usage` ledger.

## Frozen inputs

#35C reads the four source paraphrases from the already frozen multimodal golden corpus. It does not fetch publisher text or modify the frozen corpus.

The explicit evaluation entity allowlist contains only:

- `football|player|jude-bellingham`;
- `football|club|real-madrid`;
- `football|club|borussia-dortmund`.

This allowlist is evaluation context. It does not establish truth, source authority, corroboration, or independence.

## Expected quality behavior

The model is asked only to propose candidate semantics through the #35B output contract.

The quality target is:

```text
anchor transfer -> web positive       same canonical core
anchor transfer -> YouTube positive   same canonical core
anchor transfer -> later match goal   different canonical core
```

The anchor should extract as a completed transfer to Real Madrid.

If the model returns `insufficient`, malformed output, an unsupported taxonomy value, an invented entity, or otherwise invalid output, the parser fails closed and the quality result records the miss.

A model-quality failure is a measured result. It does not authorize changing the result after seeing it, weakening #35A identity, weakening #35B validation, or changing Live Merit.

## Hard-safety behavior

The hard negative must never be accepted as the same core as the anchor when both are extracted.

The evaluation never treats model output as proof of:

- truth;
- authority;
- reliability;
- independence;
- corroboration;
- training eligibility;
- Merit.

The structured model output remains candidate semantics only. Deterministic #35A code remains the identity authority.

## Data and telemetry boundaries

The production database is used only for the real #34A Gemini usage ledger and its existing compatible schema.

#35C does not create or mutate production claim, evidence, observation, story, graph, adjudication, or Merit state.

The sanitized evaluation report may retain normalized structured candidates, deterministic fingerprints, quality results, hard-safety results and token/ledger telemetry.

It must not retain:

- raw Gemini response text;
- raw provider prompts;
- API keys;
- user identity;
- arbitrary client identity.

## Zero-cost preflight

Before loading the API key, the CLI verifies that all four calls fit the current #34A provider-day global, model and per-client capacity.

`--describe` performs zero provider calls and does not read the API key.

## Live execution

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m evals.run_canonical_claim_extraction_live --describe --max-calls 4
```

The real bounded evaluation requires explicit opt-in:

```powershell
.\.venv\Scripts\python.exe -m evals.run_canonical_claim_extraction_live --live --max-calls 4 --json-out .\canonical-claim-extraction-live-report.json
```

If any `[Gemini N/4 START]` line appears, provider quota has been crossed. Do not blindly rerun the live evaluation after that point. Reconcile the production usage ledger first.

A completed four-call run with hard safety passing may be baselined even when quality fails. Quality failure is evidence for subsequent design work, not permission to tune away the observed result.
