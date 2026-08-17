# Sportabase #35B — structured canonical claim extraction boundary

#35B defines the zero-provider-call interface between model-generated semantic text and the locked #35A canonical claim identity contract.

It does **not** call Gemini, does not change the existing multimodal bridge, does not change claim persistence, and does not affect Live Merit.

## Why this exists

#34B proved that independently generated free-text claim candidates are not stable enough to be used directly as durable cross-source claim identity. #35A solved the deterministic identity side by defining structured canonical claims, core fingerprints, specific fingerprints, and material-conflict checks.

#35B solves the interface problem: what may a future model extraction step propose, how is that output validated, and where does deterministic authority begin?

The boundary is:

```text
untrusted claim text
    -> strict extraction prompt contract
    -> model JSON candidate (future provider step; not executed in #35B)
    -> strict extraction envelope parser
    -> entity allowlist validation
    -> locked #35A normalize_canonical_claim()
    -> deterministic core/specific fingerprints
```

The model may propose semantics. The model may not establish identity by saying two claims are equivalent.

## Zero-cost checkpoint

#35B performs no provider dispatches.

The module contains no Gemini client, generator, API key loading, provider runtime invocation, network access, or usage-ledger writes. Tests supply model-shaped JSON directly to the parser.

Real provider validation belongs to #35C.

## Extraction envelope

The only accepted output envelope is:

```json
{
  "version": "canonical-claim-extraction-output-v1",
  "status": "extracted",
  "candidate": {
    "version": "canonical-claim-contract-v1",
    "subject_key": "football|player|jude-bellingham",
    "event_type": "transfer",
    "state": "completed",
    "negated": false,
    "roles": {
      "destination": "football|club|real-madrid"
    },
    "facets": {
      "effective_period": "2023"
    }
  },
  "reason": ""
}
```

If required identity information is absent, the allowed fail-closed form is:

```json
{
  "version": "canonical-claim-extraction-output-v1",
  "status": "insufficient",
  "candidate": null,
  "reason": "destination not stated"
}
```

Unknown envelope fields fail closed.

## Entity allowlist

A model is not permitted to create entity identity.

The extraction request supplies an explicit set of already-resolved canonical entity keys. The candidate subject must equal the expected subject, and every entity-valued role emitted by the candidate must be in the allowlist.

For example, if the only club entities supplied are:

```text
football|club|real-madrid
football|club|borussia-dortmund
```

then a model output containing:

```text
football|club|invented-club
```

is rejected before a canonical fingerprint is exposed.

Entity resolution remains a separate system concern.

## Taxonomy authority

#35B derives its event types, states, roles, facets and required fields directly from the locked #35A contract.

It does not maintain a second competing taxonomy.

Unknown event types, states, roles, facets, malformed JSON, missing required fields, invalid negation types, wrong subjects, invented entities, and forbidden identity fields fail closed.

## Forbidden semantic leakage

The extraction candidate may not contain fields related to:

- truth or verification;
- source authority;
- reliability, trust or credibility;
- independence;
- corroboration;
- Merit or score effects;
- training eligibility;
- model or source confidence;
- publisher, reporter, provider or model identity;
- source URL.

Those concepts are not claim identity.

The extraction policy explicitly records that the model output is candidate semantics only and that the deterministic #35A normalizer is authoritative for identity shape.

## Prompt-injection boundary

`build_canonical_claim_extraction_prompt()` places claim text inside an explicit `UNTRUSTED_CLAIM_TEXT` boundary and states that source text is data, not instructions.

This does not make model execution inherently safe by itself; it is one layer. More importantly, the returned JSON must still pass the strict parser, entity allowlist and #35A normalization before any identity fingerprint is accepted.

## Bellingham target

With model-shaped JSON supplied by tests rather than Gemini, #35B proves that:

```text
transfer/completed/Bellingham -> Real Madrid
transfer/signed/Bellingham -> Real Madrid from Dortmund
transfer/presented/Bellingham -> Real Madrid
```

normalize to compatible #35A transfer cores, while:

```text
match_event/scored/Bellingham/later-match
```

remains a different core.

This is still not evidence that Gemini will extract those structures reliably. That measurement belongs to #35C.

## #35B boundaries

#35B intentionally does **not**:

- call Gemini;
- read a Gemini API key;
- change the #34A capacity runtime;
- change `gemini_usage`;
- modify the existing multimodal semantic-fusion prompt;
- switch the existing bridge canonical-key path;
- migrate existing claim rows;
- alter database schema;
- change story membership;
- change adjudication;
- change authority, reliability or independence logic;
- change corroboration;
- change Live Merit;
- modify the frozen #33 corpus;
- modify the #34B live baseline.

## Next checkpoint

#35C is the bounded live extraction evaluation. It will use the already-tested #35B prompt/output boundary and the locked #35A deterministic identity layer, then measure whether real Gemini outputs produce the expected structured Bellingham identities.

A #35C model-quality failure will be an observed result. It will not authorize weakening the deterministic identity or safety gates.
