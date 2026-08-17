# Sportabase #34B model-dependent golden evaluation

This is the bounded observed full-pipeline evaluation layer built on top of the
frozen #33 multimodal golden corpus and the #34A Gemini capacity runtime. It is
evaluation tooling only; it is not a production API or worker path.

The live subset contains exactly one historical scenario-derived case:

- `football_bellingham_real_madrid_2023`

The case preserves all three routed same-subject candidates:

- X anchor -> positive web candidate;
- X anchor -> positive YouTube candidate;
- X anchor -> same-subject X hard negative.

The hard negative is intentionally allowed through deterministic routing and is
expected to be rejected by the downstream exact-common-claim gate.

The X anchor has no article-style legacy Merit baseline, so the expected Merit
baseline mode is `not_applicable`. No synthetic Merit baseline may be created.

## Provider-call plan

The live run has a hard evaluator cap of 12 provider calls.

For the frozen Bellingham case:

- candidate pairs: 3;
- guaranteed semantic-fusion calls: 6 (2 per pair);
- conditional claim-observation calls: up to 6 (2 per pair that survives the
  model-dependent exact-common-claim gate);
- possible actual totals: 6, 8, 10, or 12;
- call 13 is forbidden before provider dispatch.

The exact final count is deliberately not predicted before the model runs.

## #34A capacity integration

Unlike the earlier experimental live-eval design, #34B does not bypass the
Sportabase Gemini ledger. Every real provider request is routed through the
existing #34A `gemini_runtime.generate_gemini_content` path and therefore uses:

- model-aware provider-day accounting;
- the 4 RPM Sportabase dispatch target;
- minimum same-model pacing of about 15 seconds;
- usable input TPM protection;
- model RPD reserve protection;
- the global all-model Sportabase provider-day cap;
- per-client fair-share caps;
- pre-call estimated input-token checks;
- post-call exact token reconciliation;
- existing provider error classification.

The evaluation uses one clearly labelled internal client bucket per candidate
pair. Each pair can consume at most four calls, so the locked production
per-client fair-share cap of eight is not weakened or overridden. All three
buckets still share the same production global/model provider-day capacity.

Before any API key is read or provider call is sent, the live CLI checks that the
complete 12-call envelope still fits the current global, model, and per-pair
provider-day capacity. If it does not fit, the run fails closed at zero cost.

## Database boundaries

The full sports-intelligence evaluation state still uses a fresh temporary
SQLite database. Frozen captures, identities, claims, observations, evidence,
adjudication state, corroboration state, and story/claim graph materialization
never write into the real Sportabase intelligence database.

The one intentional real-database write is the production `gemini_usage` ledger,
because #34B makes real provider calls and those calls must be counted by #34A.
The outer checkpoint verifies that every real call reconciles to exactly one
ledger row and that all non-`gemini_usage` database state remains unchanged.

## Safe telemetry

For each actual provider dispatch the CLI prints:

- `Gemini N/12 START` with mode/model;
- exact prompt/output/thought/cached/total token counts when complete;
- cumulative calls and total tokens.

The sanitized report contains aggregate and per-call operational telemetry,
including the production usage-row ID used for reconciliation. It never stores
prompt contents, raw response text, API keys, or user identity.

## Safety boundaries

The evaluation:

- uses the frozen scenario-derived corpus; no publisher text is fetched;
- performs no web/network access except the explicitly opted-in Gemini calls;
- executes the real exact-common-claim gate;
- executes real adjudication/corroboration machinery;
- materializes the existing #32 story/claim graph in the temporary DB;
- never treats golden labels as truth, authority, or independence;
- never invokes Live Merit release;
- never consumes a release certificate;
- never applies a score effect.

## Run

From `backend/`, inspect the plan and current provider-day capacity with zero
provider calls and without reading the API key:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --describe
```

A true zero-call dry run is:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live --max-calls 0
```

The bounded live run is:

```powershell
.\.venv\Scripts\python.exe -m evals.run_multimodal_golden_live `
  --live `
  --max-calls 12 `
  --json-out .\golden-live-report.json
```

A quality miss is reported for investigation and does not authorize a product or
Merit change. Capacity, provider, infrastructure, or hard-safety failures fail
closed. If a provider call has already been recorded in `gemini_usage`, do not
blindly rerun the live evaluation; inspect the ledger first because real provider
quota has already been consumed.


## Evaluation-only text semantic adapter

The frozen #33 scenario captures intentionally contain short original text
paraphrases only. Platform labels such as X or YouTube do not fabricate a
media component, transcript, image, or video artifact.

Production semantic execution schedules `multimodal_semantic_fusion` only when
a normalized item contains real media components. #34B does not change that
production behavior.

For this model-dependent evaluation only, the temporary per-case runtime copy
adds one semantic-fusion work unit over each item's already-materialized text
artifacts. The work unit executes the existing production
`GeminiSemanticInterpreter.fuse()` implementation. No frozen capture text,
dataset labels, dataset digest, production semantic scheduler, production API
path, Live Merit path, or production source file is changed.

This makes the frozen three-pair Bellingham experiment's call plan explicit:

- two evaluation semantic-fusion calls per anchor/candidate pair;
- three candidate pairs;
- six guaranteed fusion calls;
- two additional claim-observation calls only for each pair that survives the
  exact-common-claim gate;
- possible actual totals of 6, 8, 10, or 12;
- call 13 remains impossible.

A failure of two independently generated fusion outputs to produce the same
deterministic claim ID is a model-dependent quality result. It must be reported,
not repaired by weakening the exact-common-claim gate.
