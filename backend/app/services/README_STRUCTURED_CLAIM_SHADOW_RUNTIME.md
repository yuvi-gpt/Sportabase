# Sportabase #35J — structured claim shadow runtime caller adapter

#35J moves the structured claim stack one step closer to the real multimodal runtime without switching production claim identity.

It is a **zero-provider checkpoint** and is additive only.

## Why this shape

Repository inspection showed that the existing multimodal runtime already exposes an explicit `bridge_builder=` dependency seam, and the existing multimodal shadow API already exposes an explicit `runtime_runner=` dependency seam.

That means #35J does not need to edit either large production file.

Instead it adds a caller adapter:

```text
make_structured_claim_shadow_runtime_runner(...)
                  |
                  v
existing multimodal_shadow_api runtime_runner seam
                  |
                  v
run_multimodal_intelligence_runtime_with_structured_shadow(...)
                  |
                  +---- shadow OFF ----> existing runtime unchanged
                  |
                  +---- shadow ON
                           |
                           v
                  existing runtime
                           |
                           | bridge_builder injection only
                           v
                  #35I structured shadow bridge
                           |
                           +--> production plan -> existing runtime
                           |
                           +--> structured report -> diagnostics only
```

The existing runtime remains authoritative.

## Default is OFF

`structured_claim_shadow_enabled=False` is the default.

When disabled, #35J delegates directly to the caller-supplied runtime runner and deliberately does not inspect:

- structured outputs;
- entity allowlists;
- shadow bridge configuration.

It does not inject a bridge builder and returns the exact existing runtime result.

This keeps the disabled path behaviorally identical to the current runtime.

## Enabled path

When explicitly enabled, #35J installs one bridge-builder dependency into the existing runtime.

For each existing left/right bridge call, the injected builder calls the locked #35I wrapper with already-computed structured model output for that side.

#35I returns:

```text
production_plan
structured_shadow
```

Only `production_plan` is returned into the existing runtime.

The structured shadow report is retained separately and attached to a copy of the final runtime result after the ordinary runtime has completed.

The runtime therefore continues to use its existing production claim selection, persistence, observation semantics, adjudication, corroboration, and Merit-shadow stages.

## No production feedback path

Structured diagnostics cannot be used by #35J to:

- replace a production claim ID;
- filter a production candidate;
- change the persistence scope;
- persist a structured full claim;
- persist partial semantics;
- create evidence or observations;
- create story membership;
- establish corroboration;
- establish authority or reliability;
- establish independence;
- establish truth;
- affect Live Merit;
- create training labels.

#35J does not run full-vs-partial comparison logic.

## Shadow failure isolation

If #35I or the structured shadow report fails while the injected bridge builder is running, #35J recomputes the ordinary locked production bridge directly and returns that production plan to the existing runtime.

The structured side records a bounded error diagnostic.

This means a structured-shadow evaluation failure cannot break the normal runtime path.

A genuine production runtime or production bridge failure is still allowed to fail normally; #35J does not hide production failures.

## No raw model-output retention

The precomputed model-shaped structured output is passed into #35I only for validation.

#35J does not copy the raw model output into its runtime result.

The returned diagnostics contain only the normalized/bounded #35I shadow report.

## Provider accounting

#35J adds **zero additional provider calls** and **zero additional provider tokens**.

This wording is intentional: the existing multimodal runtime can already make its ordinary Gemini calls when it runs in production. #35J does not duplicate those calls and does not add a structured-extraction provider call.

The #35J checkpoint itself uses mocked runtime dependencies and therefore performs:

- zero Gemini calls;
- zero Gemini tokens;
- zero provider API-key reads;
- zero network calls;
- zero database writes.

## Existing API/runtime seams

The adapter factory returns a callable compatible with the existing `multimodal_shadow_api.execute_multimodal_shadow_api(..., runtime_runner=...)` seam.

The adapter itself uses the existing `run_multimodal_intelligence_runtime(..., bridge_builder=...)` seam.

No existing API request model is changed and no HTTP caller can enable structured shadow through #35J alone.

That is deliberate. A later checkpoint can decide whether and how server-side configuration supplies a configured runtime runner.

## Production boundary

#35J intentionally does **not**:

- modify `multimodal_intelligence_runtime.py`;
- modify `multimodal_shadow_api.py`;
- modify `multimodal_intelligence_bridge.py`;
- modify #35I shadow semantics;
- modify #35G protocol ownership;
- modify #35E routing;
- modify #35D partial semantics;
- modify #35B extraction validation;
- modify #35A canonical identity;
- rewrite #35C, #35F, or #35H measured baselines;
- switch production claim identity;
- persist structured identity;
- migrate existing claims;
- modify database schema;
- create story membership;
- establish truth, authority, reliability, independence, or corroboration;
- affect Live Merit.

## What #35J proves

With shadow disabled:

```text
caller -> existing runtime -> existing bridge -> existing behavior
```

With shadow enabled:

```text
caller
  -> #35J adapter
       -> existing runtime
            -> injected bridge-builder seam
                 -> #35I
                      -> production plan back to runtime
                      -> diagnostics only to #35J
```

The production plan remains the only plan consumed by the existing runtime.
