# Sportabase #35E — three-way claim semantic extraction router

#35E adds a deterministic routing contract above the already locked #35B full structured extraction boundary and #35D partial-semantics boundary.

It performs zero provider calls. It does not change the production multimodal bridge, claim persistence, story membership, adjudication, authority, reliability, independence, corroboration, database schema, or Live Merit.

## Why this exists

#35C produced two successful live positive extractions and one hard-negative output that returned `insufficient` because the model recognized a `match_event` / `scored` semantic interpretation but could not supply the `event_key` required for durable match-event identity.

#35D established that this incomplete interpretation is still useful as partial semantics: it may support safe exclusion from a full transfer claim when an explicit structural conflict exists, while never minting claim identity or establishing same-claim membership.

#35E therefore separates three model-output outcomes:

1. `extracted` — enough information exists for the locked #35A/#35B full identity path;
2. `partial` — useful structured semantics exist, but durable full identity is incomplete, so the candidate must route to the locked #35D partial path;
3. `insufficient` — no valid full or partial structured candidate can be established for the expected subject.

## Routing contract

```text
model-shaped structured envelope
        |
        +-- extracted ----> locked #35B parser ----> locked #35A identity
        |
        +-- partial ------> locked #35D partial semantics
        |
        +-- insufficient -> no semantic candidate
```

The #35E router itself does not mint identity.

## Extracted

An `extracted` candidate must satisfy the existing locked #35B full extraction path.

That means the candidate must satisfy the full #35A canonical claim contract, including all identity fields required for its event type.

The router does not auto-downgrade an invalid or incomplete `extracted` candidate to `partial`. A status mismatch fails closed.

## Partial

A `partial` candidate must be valid under the locked #35D partial-semantics contract and must genuinely be incomplete for full #35A identity.

A complete candidate submitted with `status=partial` fails closed and must be emitted as `extracted` instead.

Partial semantics:

- do not receive a core key;
- do not receive a core fingerprint;
- do not receive a specific fingerprint;
- cannot establish same-claim membership;
- cannot establish truth;
- cannot establish authority or reliability;
- cannot establish independence or corroboration;
- cannot affect Live Merit.

A later deterministic #35D comparison may use a partial candidate for safe exclusion only when an explicit structural conflict exists.

## Insufficient

`insufficient` means neither the full nor partial structured contracts can be satisfied for the expected subject.

It must set `candidate=null` and include a reason.

Insufficient output produces no identity and no partial semantic candidate.

## Bellingham target behavior

The mocked regression target is:

```text
"Jude Bellingham completed his move to Real Madrid in 2023."
    -> extracted
    -> full transfer identity

"Jude Bellingham signed for Real Madrid after his transfer from Borussia Dortmund."
    -> extracted
    -> full transfer identity

"Real Madrid presented Jude Bellingham as a new midfielder."
    -> extracted
    -> full transfer identity under the currently locked #35A taxonomy

"Jude Bellingham later scored in a league match."
    -> partial
    -> match_event / scored
    -> event_key missing
    -> no fingerprint
    -> structurally incompatible with the full transfer anchor

text with no supported structured event for the expected subject
    -> insufficient
```

#35E does not change the frozen #35C measured result. It uses that observation as design evidence only.

## Status mismatches fail closed

The router deliberately does not silently correct status mistakes.

- complete candidate + `partial` -> reject;
- incomplete candidate + `extracted` -> reject;
- non-null candidate + `insufficient` -> reject.

This prevents the router from becoming a fuzzy or heuristic identity authority.

## Prompt boundary

`build_claim_semantic_extraction_router_prompt()` describes all three statuses and embeds the locked full and partial schemas.

The source text is wrapped in `<UNTRUSTED_CLAIM_TEXT>` and explicitly treated as source data rather than instructions.

The prompt forbids invented entity keys and forbids truth, authority, reliability, independence, corroboration, training, confidence, source identity, provider identity, and Merit fields.

## Zero-provider checkpoint

#35E contains no Gemini client, API-key loading, network request, provider runtime, or `gemini_usage` write.

All #35E tests use deterministic model-shaped envelopes.

## Production boundary

#35E intentionally does **not**:

- modify the locked #35A canonical identity contract;
- modify the locked #35B parser or prompt;
- modify the locked #35D partial-semantics contract;
- modify the #35C measured live baseline;
- switch the production multimodal bridge;
- migrate existing claims;
- modify database schema;
- create story membership;
- change adjudication;
- establish source authority or reliability;
- establish independence or corroboration;
- affect Live Merit.

A future checkpoint may evaluate whether the three-way prompt causes real Gemini output to choose `partial` for the previously observed Bellingham hard negative. That future live check must remain capacity-bounded and must not change the historical #35C baseline.
