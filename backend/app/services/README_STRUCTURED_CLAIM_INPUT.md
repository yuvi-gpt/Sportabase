# Sportabase — Structured Claim Input Wiring

This checkpoint connects semantic claim candidates to the Claim Intelligence Engine without adding a provider call or changing the existing production candidate payload, candidate artifact identity, or production claim identity.

## Why this exists

The multimodal semantic fusion stage already creates deterministic claim candidates with:

- `candidate_id`
- candidate text
- source artifact IDs
- modality sources
- interpretation confidence
- uncertainty

The structured-claim shadow path already accepts structured claim proposals keyed by that same `candidate_id`.

Before this checkpoint, those mappings had to be supplied manually by the runtime caller.

Structured Claim Input Wiring removes that manual gap.

## Flow

```text
existing multimodal semantic fusion
        |
        +-- normal claim candidate payload
        |       (unchanged)
        |
        +-- optional bounded structured sidecar
                stored in artifact metadata
                keyed by existing candidate_id
                         |
                         v
              Structured Claim Input
                         |
                         v
              Runtime Shadow Caller
                         |
                         v
              Structured Claim Shadow Bridge
                         |
                         v
              Claim Intelligence Engine
```

## Sidecar instead of candidate-payload mutation

The structured proposal is intentionally **not** inserted into the existing `claim_candidates` payload.

Semantic execution places optional structured proposals in the claim-candidate artifact metadata under:

`structured_claim_outputs_by_candidate_id`

The existing artifact hashing logic hashes the candidate payload, not artifact metadata. Therefore a structured sidecar can be attached without changing the existing candidate artifact ID or content hash.

The existing production bridge reads the `claim_candidates` payload and ignores this sidecar metadata.

This prevents the shadow plumbing from altering the old claim candidate, its deterministic candidate ID, or the production bridge's candidate-container content hash.

## Current checkpoint boundary

This checkpoint does **not** change the real Gemini fusion prompt.

The production interpreter therefore does not begin requesting structured claim proposals yet.

It only teaches semantic execution how to preserve an optional proposal as sidecar metadata when an interpreter supplies one, and teaches the runtime shadow caller to discover that sidecar automatically.

The final Claim Intelligence checkpoint will make the existing fusion call request the structured proposal and will validate the end-to-end live path.

## Candidate identity is preserved

`candidate_id` remains generated exactly as before from candidate text and source artifact IDs.

The structured proposal is not part of that candidate-ID hash.

Structured Claim Input never generates a candidate ID.

## Correlation only

The input collector deliberately does not validate claim semantics.

It does not decide whether a candidate is:

- full identity;
- partial semantics;
- insufficient;
- equivalent to another claim;
- true;
- authoritative;
- reliable;
- independent;
- corroborated.

It only correlates an optional bounded proposal with an already-existing candidate ID.

Downstream Claim Intelligence owns semantic validation and fail-closed behavior.

## Automatic runtime wiring

When structured shadow mode is enabled:

- an explicit structured-output mapping still wins when supplied;
- when that mapping is absent, the runtime shadow caller derives it from claim-candidate sidecar metadata;
- shadow mode disabled does not inspect structured inputs at all;
- malformed input collection falls back to the existing production bridge;
- the production runtime response remains unchanged.

## Duplicate and unbound handling

If the same candidate ID appears more than once in the semantic manifest, the collector suppresses that candidate's structured output.

If sidecar metadata names a candidate ID that is not present in the same claim-candidate container, the output is ignored and reported as unbound.

The collector never guesses which candidate should own ambiguous output.

## No extra model spend

This checkpoint performs:

- zero Gemini calls;
- zero Gemini tokens;
- zero API-key reads;
- zero network calls from the new collector;
- zero database writes from the new collector.

The final Claim Intelligence checkpoint is designed to reuse the existing multimodal fusion call rather than add a second structured-claim call.

## No authority

Structured Claim Input cannot:

- select a production claim;
- filter production candidates;
- replace production identity;
- persist a claim;
- persist evidence;
- persist an observation;
- create story membership;
- establish corroboration;
- establish authority or reliability;
- establish independence;
- establish truth;
- change Live Merit;
- create training labels.

## Files intentionally changed

This checkpoint adds the Structured Claim Input collector and its tests/docs, then makes two small existing-file changes:

1. `semantic_execution.py` can preserve an optional structured proposal as claim-candidate **metadata sidecar** while keeping the normal claim-candidate payload and artifact hash unchanged. The current real prompt remains unchanged.
2. `multimodal_structured_shadow_caller.py` automatically collects those sidecars when the caller did not explicitly supply a structured-output mapping.

It does not modify:

- `multimodal_intelligence_runtime.py`;
- `multimodal_intelligence_bridge.py`;
- structured claim shadow semantics;
- Claim Intelligence parsing or identity contracts;
- claim persistence;
- database schema;
- Live Merit behavior;
- historical live baselines.
