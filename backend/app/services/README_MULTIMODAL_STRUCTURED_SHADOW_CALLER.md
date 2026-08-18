# Sportabase #35J — runtime structured-shadow caller plumbing

#35J wires the #35I structured-claim shadow bridge into the real multimodal intelligence runtime while preserving the existing production path.

## Boundary

The real caller is `run_multimodal_intelligence_runtime(...)` in `multimodal_intelligence_runtime.py`.

Before #35J it calls the existing dry-run bridge directly for the left and right semantic manifests.

#35J adds an opt-in caller adapter:

```text
multimodal intelligence runtime
        |
        +-- shadow OFF (default)
        |      -> existing bridge_builder directly
        |      -> exact existing production plan
        |
        +-- shadow ON
               -> #35J caller adapter
               -> #35I structured shadow bridge
                      |
                      +-- untouched production_plan
                      +-- diagnostic structured_shadow
```

Only `production_plan` continues into common-claim selection, persistence, observation semantics, adjudication, corroboration, and Merit shadowing.

The structured shadow report has no feedback path.

## Default-off guarantee

`structured_claim_shadow_enabled=False` remains the default.

When disabled:

- the runtime calls the existing injected `bridge_builder` directly;
- structured output maps are ignored;
- the #35I wrapper is not called;
- no diagnostic sink is called;
- the runtime response schema is unchanged;
- the rest of the runtime call order is unchanged.

## Enabled path

When enabled, the caller receives already-computed model-shaped structured outputs for left and right candidates plus an explicit entity allowlist.

#35J itself never calls Gemini.

The enabled path calls #35I, which in turn uses:

```text
#35G protocol ownership
  -> #35E extracted / partial / insufficient router
     -> full: #35B -> #35A
     -> partial: #35D
     -> insufficient: none
```

The #35I result is split into:

- `production_plan`: the normal dry-run bridge plan used by the existing runtime;
- `structured_shadow`: diagnostic-only structured semantics.

## Diagnostic sink

The runtime may receive an optional `structured_shadow_sink` callback.

The sink receives bounded sanitized reports for left and right shadow evaluations.

The sink is not part of the runtime response and cannot influence claim selection or persistence.

If the sink raises, the error is swallowed and normal runtime execution continues.

## Shadow failure isolation

If the #35I wrapper unexpectedly raises or returns an invalid envelope, #35J falls back to the existing `bridge_builder` for that side.

The runtime therefore still receives a normal production plan.

The diagnostic report records an error, but the production request is not failed by the shadow layer.

This fallback is allowed because both the existing bridge and #35I bridge are dry-run planning boundaries; no persistence has occurred yet.

## No response-schema change

#35J intentionally does not add structured shadow data to the multimodal runtime response.

This preserves behavior for existing consumers and prevents downstream code from accidentally treating shadow semantics as production identity.

Inspection is available only through the optional diagnostic sink.

## No authority

Structured shadow output cannot:

- select the production claim;
- filter production candidates;
- replace production claim identity;
- persist claims;
- persist evidence;
- persist observations;
- create story membership;
- establish corroboration;
- establish authority or reliability;
- establish independence;
- establish truth;
- affect Live Merit;
- create training labels.

## Zero-provider checkpoint

#35J performs:

- zero Gemini calls;
- zero Gemini tokens;
- zero API-key reads;
- zero network calls from the new adapter;
- zero database writes from the new adapter.

All tests use injected deterministic runtime collaborators.

## Production changes in scope

#35J intentionally changes only the actual caller plumbing in `multimodal_intelligence_runtime.py` plus additive adapter/docs/tests.

It does **not**:

- modify `multimodal_intelligence_bridge.py`;
- modify #35I shadow semantics;
- modify #35G protocol ownership;
- modify #35E routing;
- modify #35D partial semantics;
- modify #35B full extraction;
- modify #35A identity;
- rewrite the #35C, #35F, or #35H live baselines;
- switch production identity;
- migrate claims;
- change database schema;
- change Live Merit behavior.

A later checkpoint may decide how normal semantic/model execution supplies precomputed structured envelopes to these new runtime parameters. #35J only creates the safe caller plumbing.
