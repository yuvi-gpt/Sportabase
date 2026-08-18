# Sportabase #35F — one-call live three-way router validation

#35F performs one tightly bounded real Gemini call to answer one new empirical question left by #35E:

> When the frozen Bellingham hard-negative sentence is evaluated with the new three-way extraction prompt, does Gemini return `partial` rather than the older #35C `insufficient` result?

The checkpoint is intentionally narrow. It does not repeat the anchor, web-positive, or YouTube-positive provider calls that were already measured in #35C.

## Exact provider budget

- model: `gemini-3.5-flash`
- provider calls: exactly 1
- hard-negative calls: 1
- anchor calls: 0
- positive-source calls: 0
- call 2 is forbidden
- client bucket: `eval35f:bellingham:hard-negative`

The one call uses the locked #35E three-way prompt and parser.

## Frozen source

The live source remains the frozen #35C/#33 Bellingham hard negative:

```text
Jude Bellingham later scored in a league match, a different claim from his transfer.
```

The deterministic comparison anchor is not re-extracted by the model. It is the locked canonical transfer structure:

```text
subject: Jude Bellingham
event_type: transfer
state: completed
destination: Real Madrid
effective_period: 2023
```

## Desired live outcome

The desired model-shaped result is:

```text
status: partial
candidate:
  subject_key: football|player|jude-bellingham
  event_type: match_event
  state: scored
  event_key: missing
```

The locked #35E router must then route the candidate to #35D partial semantics.

#35D must report:

```text
structurally_incompatible
safe_exclusion = true
safe_acceptance = false
```

The partial candidate must receive no core key, no core fingerprint, and no specific fingerprint.

## Measured failure is allowed

If Gemini still returns `insufficient`, malformed output, or another safe but incorrect route, #35F records a model-quality failure.

A quality failure is a measured result. It does not authorize:

- rerunning the call blindly;
- tuning the prompt after observing the answer and replacing the measurement;
- weakening #35A identity;
- weakening #35D partial-semantics safety;
- enabling fuzzy same-claim matching;
- changing truth, authority, reliability, independence, corroboration, or Live Merit logic.

If the single provider call has started, do not rerun the checkpoint after a later failure. Recover from the `gemini_usage` ledger instead.

## Hard safety

#35F does not permit the hard negative to become a transfer match merely to satisfy quality.

Hard safety fails if, among other things:

- a partial result receives a fingerprint;
- partial semantics gain safe-acceptance authority;
- a full hard-negative candidate merges onto the transfer anchor;
- forbidden truth/authority/reliability fields enter candidate identity;
- raw provider response text is stored.

## Sanitized measurement

The live report may retain:

- validated structured candidate semantics;
- route/status;
- missing identity fields;
- deterministic #35D comparison;
- token counts;
- provider ledger usage IDs;
- capacity telemetry;
- report digest.

It does not store the raw Gemini response, raw prompt, API key, or user identity.

The frozen source sentence itself is not sensitive and is already part of the repository evaluation corpus.

## Production boundary

#35F intentionally does **not**:

- modify #35A canonical identity;
- modify #35B full extraction;
- modify #35D partial semantics;
- modify #35E three-way routing;
- rewrite the historical #35C baseline;
- switch the production multimodal bridge;
- migrate existing claims;
- modify database schema;
- create story membership;
- change adjudication;
- establish truth or authority;
- establish reliability;
- establish independence or corroboration;
- affect Live Merit.

Only the production `gemini_usage` ledger is expected to change, and only by the one bounded provider call.
