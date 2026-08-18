# Sportabase #35H — one-call live validation through protocol ownership

#35H performs one tightly bounded real Gemini call to answer the remaining empirical question after #35G:

> With the exact same #35E model prompt and frozen Bellingham hard-negative source used in #35F, does the provider result survive the new deterministic #35G protocol-ownership boundary and reach the locked #35D partial-semantics comparison correctly?

#35H changes the deterministic parse path only. It does not rewrite the #35E prompt after observing #35F.

## Exact provider budget

- model: `gemini-3.5-flash`
- provider calls: exactly 1
- hard-negative calls: 1
- anchor calls: 0
- positive-source calls: 0
- repeated calls: 0
- call 2 is forbidden
- fresh client bucket: `eval35h:bellingham:hard-negative`
- mode: `claim_semantic_protocol_owned_router`

The frozen source is:

```text
Jude Bellingham later scored in a league match, a different claim from his transfer.
```

The deterministic transfer anchor is not re-extracted by Gemini.

## Controlled difference from #35F

#35F used:

```text
Gemini response
    -> locked #35E parser directly
    -> locked #35D partial semantics
```

That measured one quality failure caused by model-supplied nested contract-version metadata.

#35H uses:

```text
Gemini response
    -> locked #35G protocol ownership
    -> locked #35E three-way router
    -> locked #35D partial semantics
```

The #35E prompt itself remains unchanged.

## Desired live outcome

The desired semantic result is:

```text
status: partial
route: partial_semantics
event_type: match_event
state: scored
missing_identity_fields: [facets.event_key]
core fingerprint: none
specific fingerprint: none
```

Then the locked #35D comparison against the deterministic transfer anchor should produce:

```text
status: structurally_incompatible
structural_conflicts: [event_type]
safe_exclusion: true
safe_acceptance: false
```

The provider may either include or omit nested `candidate.version` metadata. If it supplies that metadata, #35G must remove it before validation. If it omits it, #35G must not fabricate a model-supplied value. In either case, the locked deterministic validator owns and assigns the internal candidate contract version after validation.

## Quality failure is still a measured result

If Gemini returns `insufficient`, malformed output, a different supported semantic interpretation, or otherwise fails the desired quality target while hard safety remains intact, #35H records that result honestly.

A quality failure does not authorize:

- rerunning the single call blindly;
- changing the frozen #35F measurement;
- prompt-tuning and replacing the observed #35H result;
- weakening #35A identity;
- weakening #35D partial semantics;
- weakening #35E status validation;
- weakening #35G protocol ownership;
- fuzzy same-claim matching;
- changing truth, authority, reliability, independence, corroboration, or Live Merit logic.

Once `[Gemini 1/1 START]` appears, do not rerun the checkpoint after a later failure. Recover from the production `gemini_usage` ledger instead.

## Hard safety

#35H must fail hard safety if protocol ownership rewrites semantics or status, if a partial candidate gains fingerprints or safe-acceptance authority, or if the hard negative merges onto the transfer anchor as a full same-core claim.

The model still does not establish:

- truth;
- authority;
- reliability;
- independence;
- corroboration;
- training eligibility;
- Live Merit.

Raw Gemini response text and the raw prompt are not stored in the committed sanitized baseline.

## Production boundary

#35H intentionally does **not**:

- modify #35A canonical identity;
- modify #35B full extraction;
- modify #35D partial semantics;
- modify #35E three-way routing;
- modify #35G protocol ownership;
- rewrite the #35C baseline;
- rewrite the #35F baseline;
- switch the production multimodal bridge;
- migrate existing claims;
- modify database schema;
- create story membership;
- change adjudication;
- establish truth or source authority;
- establish reliability;
- establish independence or corroboration;
- affect Live Merit.

Only the production `gemini_usage` ledger is expected to change, by exactly one provider row if the live call completes.
