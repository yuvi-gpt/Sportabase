# Sportabase #35D — partial claim semantics and safe exclusion

#35D defines a deterministic representation for semantic information that is useful but not complete enough to mint durable claim identity.

It performs zero provider calls. It does not change the existing #35B model extraction boundary, the production multimodal bridge, claim persistence, story membership, adjudication, authority, independence, corroboration, or Live Merit.

## Why this exists

#35C produced the desired live convergence for the two Bellingham transfer positives, but the same-subject hard negative returned `insufficient` because a `match_event` requires an `event_key` and the frozen text did not identify the exact match.

That fail-closed behavior was correct: the model did not invent a match identity.

However, the result exposed a second distinction Sportabase needs:

1. enough semantics to establish a durable claim identity;
2. enough semantics to prove structural incompatibility with an existing full claim.

Those are not the same threshold.

## The asymmetry

#35D intentionally allows only one useful inference from incomplete semantics:

```text
full canonical claim
        +
incomplete partial semantics
        +
explicit structural conflict
        ->
safe exclusion from that full claim
```

Partial semantics can never establish that two claims are the same.

If a partial candidate does not conflict with the full claim, the result is `undetermined`, not equivalent.

## Bellingham target

A full canonical anchor may be:

```text
subject: Jude Bellingham
event_type: transfer
state: completed
destination: Real Madrid
```

The observed #35C hard-negative interpretation can be represented without inventing a match key:

```text
subject: Jude Bellingham
event_type: match_event
state: scored
missing identity field: event_key
```

This candidate has no durable identity and receives no fingerprint.

But `match_event` conflicts with the anchor's `transfer` event type, so the pair is `structurally_incompatible` and may be safely excluded from that transfer claim.

By contrast:

```text
subject: Jude Bellingham
event_type: transfer
state: completed
destination: missing
```

contains no field that conflicts with the completed Real Madrid transfer anchor. It is therefore `undetermined`.

It may not be accepted as the same claim and may not be excluded merely because information is missing.

## Partial candidate contract

A partial semantic candidate may contain only:

- `subject_key`;
- `event_type`;
- optional `state`;
- optional `negated`;
- known roles for the selected event type;
- known facets for the selected event type.

The event taxonomy, state aliases, role aliases, facet aliases, forbidden identity fields, and full-identity requirements are derived from the locked #35A canonical claim contract.

Unknown taxonomy, unknown fields, invented role entities, malformed values, forbidden truth/authority fields, and entities outside the supplied allowlist fail closed.

## Complete candidates do not belong here

If a candidate satisfies the full #35A canonical identity contract, #35D rejects it from the partial-only path with `PartialClaimSemanticsCompleteError`.

A complete candidate must go through the full #35A/#35B identity path.

This prevents #35D from becoming a second claim identity system.

## No fingerprints

Partial candidates never receive:

- a core key;
- a core fingerprint;
- a specific fingerprint.

The corresponding output fields are deliberately empty.

Partial semantics are not persisted as canonical claim identity by #35D.

## Structural incompatibility

`compare_full_claim_to_partial_semantics()` first requires a valid full #35A claim and a genuinely incomplete #35D candidate.

It may return only:

- `structurally_incompatible` — at least one supplied semantic field conflicts with the full claim;
- `undetermined` — no supplied field conflicts, but the partial candidate remains incomplete.

Potential conflict fields include:

- subject;
- event type;
- state when supplied;
- negation when supplied;
- overlapping role values;
- overlapping facet values.

The comparison never returns `same`, `same_core`, `equivalent`, or any acceptance result.

## Safety boundary

Partial semantics do not establish:

- truth;
- verification;
- source authority;
- reliability or credibility;
- independence;
- corroboration;
- training eligibility;
- Live Merit.

Fuzzy similarity is not used. A model is not allowed to declare equivalence.

## Zero-cost checkpoint

#35D contains no Gemini client, Gemini API key loading, provider runtime call, HTTP request, network client, or `gemini_usage` write.

All #35D tests use deterministic in-memory candidates.

## Production boundary

#35D intentionally does **not**:

- change the locked #35A canonical identity contract;
- change the locked #35B extraction parser or prompt;
- change the #35C measured baseline;
- change the production multimodal bridge;
- migrate existing claim rows;
- change database schema;
- create story membership;
- change adjudication;
- change authority or independence logic;
- change corroboration;
- change Live Merit.

A future checkpoint may decide how a model extraction step can emit structured partial semantics. That future integration must preserve this asymmetry: partial semantics may support exclusion only when explicit structural conflict exists, and may never establish same-claim membership.
