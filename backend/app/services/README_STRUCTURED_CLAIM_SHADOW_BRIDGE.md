# Sportabase #35I — structured claim production shadow bridge

#35I introduces an additive, opt-in production-service shadow boundary for the structured claim stack built in #35A-#35H.

It does **not** switch production claim identity.

## Why this exists

#35H live-validated the structured hard-negative path:

```text
Gemini
  -> #35G protocol ownership
  -> #35E three-way router
  -> #35D partial semantics
```

The next architectural step is to let the production multimodal bridge inspect precomputed structured model outputs without allowing those outputs to change production behavior.

The existing `build_item_intelligence_bridge(...)` remains the authoritative bridge plan and is already dry-run-only. #35I wraps it rather than modifying it.

## Exact runtime shape

```text
build_item_intelligence_bridge_with_structured_shadow(...)
        |
        | always first
        v
locked production multimodal bridge
        |
        +--> authoritative production bridge plan
        |
        +--> optional #35I shadow observation
                 |
                 +--> candidate_id correlation only
                 |
                 +--> #35G protocol ownership
                         |
                         +--> #35E router
                                |
                                +--> full -> #35B -> #35A
                                +--> partial -> #35D
                                +--> insufficient -> none
```

The production bridge plan object is returned untouched.

## Shadow is opt-in and off by default

`shadow_enabled=False` is the default.

When disabled:

- the production bridge still runs normally;
- structured outputs are ignored;
- #35G is not called;
- no shadow parsing occurs;
- the shadow report is marked `disabled`;
- there are no provider calls or database writes.

This makes the wrapper safe to introduce before any production caller adopts shadow mode.

## Inputs

Shadow mode receives already-computed model-shaped structured outputs keyed by an existing multimodal `candidate_id`:

```text
structured_outputs_by_candidate_id = {
  "claim-candidate:a": <model-shaped #35E envelope>
}
```

#35I does not call Gemini or any provider.

It also receives an explicit entity allowlist for the locked #35G/#35E validators.

## Candidate correlation is not identity

The existing multimodal `candidate_id` is used only to correlate a shadow result with the production bridge candidate that produced the current dry-run proposal.

Correlation by candidate ID does **not** mean:

- same canonical claim;
- story membership;
- corroboration;
- truth;
- authority;
- reliability;
- independence.

Unbound shadow output IDs are reported for inspection and ignored.

## Full structured shadow result

A full structured result may expose the deterministic #35A fingerprints in the shadow report.

That does not authorize replacing the production claim proposal.

```text
shadow route: full_identity
core fingerprint: visible for inspection
specific fingerprint: visible for inspection
persistence_allowed: false
replaces_production_identity: false
```

The current production bridge claim proposal remains unchanged.

## Partial structured shadow result

A partial result remains non-identity:

```text
shadow route: partial_semantics
identity_complete: false
core fingerprint: none
specific fingerprint: none
persistence_allowed: false
```

#35I does not run a full-vs-partial comparison and does not filter production candidates based on partial semantics.

That is intentional. Shadow mode is observation only.

## Insufficient result

A valid `insufficient` model envelope is recorded as a successful shadow evaluation with route `none` and no candidate.

It does not modify the production candidate.

## Failure isolation

The production bridge is built before any shadow parsing occurs.

If the shadow layer receives malformed JSON, wrong subject, unsupported taxonomy, forbidden truth/authority fields, status mismatch, invalid entity allowlist, or any other parser failure:

```text
production bridge plan -> still returned
shadow row -> error
production request -> not failed by shadow
```

#35I catches shadow-evaluation failures only after the production plan has been constructed. It never repairs semantic content to make an answer pass.

## No feedback path

The shadow result cannot feed back into the production bridge plan.

#35I has no operation that can:

- mutate a `PersistenceProposal`;
- create or update a claim;
- record evidence;
- record a source observation;
- create a claim link;
- create story membership;
- establish corroboration;
- establish authority or reliability;
- establish independence;
- change adjudication;
- affect Live Merit;
- create training labels.

The wrapper imports no database runtime and no Gemini runtime.

## Protocol and semantic ownership

The structured side reuses the locked contracts:

```text
#35G -> model/internal protocol ownership
#35E -> extracted / partial / insufficient routing
#35D -> incomplete partial semantics
#35B -> complete extraction validation
#35A -> complete deterministic claim identity
```

#35I adds no new claim identity semantics.

## Privacy / storage boundary

Raw model output is an input to the shadow parser only.

The shadow report stores:

- normalized structured candidate semantics when validation succeeds;
- normalized routing metadata;
- deterministic fingerprints only for complete full identity;
- bounded generic parser errors when validation fails.

The shadow report explicitly marks `raw_model_output_stored=false`.

## Zero-provider checkpoint

#35I performs:

- zero Gemini calls;
- zero Gemini tokens;
- zero provider API-key reads;
- zero network calls;
- zero database writes.

## Production boundary

#35I intentionally does **not**:

- modify `multimodal_intelligence_bridge.py`;
- modify #35A canonical identity;
- modify #35B full extraction;
- modify #35D partial semantics;
- modify #35E three-way routing;
- modify #35G protocol ownership;
- rewrite the #35C, #35F, or #35H measured baselines;
- switch production claim identity;
- persist structured full claims;
- persist partial semantics;
- migrate existing claims;
- modify database schema;
- create story membership;
- establish truth, authority, reliability, independence, or corroboration;
- affect Live Merit.

A later checkpoint may decide how an actual production caller supplies model output into this shadow wrapper. That future work must preserve the same no-feedback boundary until structured identity is explicitly approved for production use.
