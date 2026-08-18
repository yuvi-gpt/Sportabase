# Sportabase #35G — model protocol ownership boundary

#35G is a zero-provider deterministic protocol boundary built above locked #35E.

It addresses the exact #35F measured failure without changing the measured #35F baseline and without weakening #35A, #35B, #35D, or #35E.

## Why this exists

#35F made one real Gemini call with the locked #35E three-way prompt. Hard safety passed, but quality failed because the model-shaped partial candidate reached the #35D path with the wrong nested contract-version metadata.

The sanitized #35F error was:

```text
partial candidate failed the locked #35D partial-semantics path:
Unsupported partial semantic contract version.
```

The failure was therefore a protocol-ownership mismatch, not permission to weaken semantic validation.

## Ownership rule

The model may propose semantic content:

```text
status
subject_key
event_type
state
negated
roles
facets
reason
```

Sportabase deterministic code owns internal candidate contract versions.

The model does **not** own:

```text
canonical claim contract version
partial semantic contract version
fingerprint versions
comparison versions
```

The outer #35E envelope version remains strict because it identifies the model-facing output protocol itself.

## Exact #35G behavior

Before the locked #35E parser sees a candidate, #35G removes only a nested candidate key whose normalized name is `version`.

Nothing else is repaired or rewritten.

```text
model-shaped #35E envelope
        |
        | outer version must still be exact
        v
#35G protocol ownership boundary
        |
        | remove candidate.version only
        v
locked #35E router
        |
        +-- extracted -> locked #35B -> locked #35A
        |
        +-- partial   -> locked #35D
        |
        +-- insufficient -> none
```

After validation, the locked deterministic validator assigns the appropriate internal candidate version.

## Exact #35F regression target

The previously failing model-shaped partial candidate can contain:

```text
status: partial
candidate.version: canonical-claim-contract-v1
subject: Jude Bellingham
event_type: match_event
state: goal
facets: {}
```

#35G strips only the nested model-owned version metadata.

The locked #35D path must then yield:

```text
status: partial
route: partial_semantics
event_type: match_event
state: scored
missing_identity_fields: [facets.event_key]
candidate.version: partial-claim-semantics-contract-v1
core fingerprint: none
specific fingerprint: none
```

A later deterministic #35D comparison against the full Bellingham transfer anchor can then report `structurally_incompatible` and `safe_exclusion=true` while `safe_acceptance=false`.

## What #35G does not repair

All of these still fail closed:

- wrong or missing outer #35E envelope version;
- duplicate normalized candidate version keys;
- unsupported semantic fields;
- forbidden truth/authority/reliability fields;
- invented entity keys;
- wrong subject;
- unknown event type or state;
- complete candidate labeled `partial`;
- incomplete candidate labeled `extracted`;
- non-null candidate labeled `insufficient`;
- malformed JSON.

#35G never changes `status`, `reason`, subject, event type, state, negation, roles, or facets to make an answer pass.

## Safety boundary

Protocol normalization is not semantic correction.

A model candidate does not gain truth, authority, reliability, independence, corroboration, training eligibility, same-claim authority, or Live Merit influence merely because non-authoritative version metadata was removed.

Partial semantics still receive no fingerprints and still cannot establish same-claim membership.

## Zero-provider checkpoint

#35G performs:

- zero Gemini calls;
- zero Gemini tokens;
- zero API-key reads;
- zero network calls;
- zero database writes.

## Production boundary

#35G intentionally does **not**:

- modify the locked #35A canonical claim contract;
- modify the locked #35B full extraction boundary;
- modify the locked #35D partial-semantics contract;
- modify the locked #35E three-way router;
- modify or overwrite the measured #35F baseline;
- switch the production multimodal bridge;
- migrate existing claims;
- modify database schema;
- create story membership;
- change adjudication;
- establish truth or authority;
- establish reliability;
- establish independence or corroboration;
- affect Live Merit.

A future one-call live checkpoint may reuse the same #35E prompt but parse the response through #35G before #35E/#35D validation. That future measurement must use a new client bucket and preserve #35F as historical evidence.
