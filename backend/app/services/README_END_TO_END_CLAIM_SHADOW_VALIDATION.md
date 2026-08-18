# Sportabase — End-to-End Claim Shadow Validation

This is the final validation checkpoint for the Claim Intelligence Engine.

It closes the gap between the existing multimodal semantic fusion call and the structured claim sidecar path without introducing a second Gemini request or switching production claim identity.

## Final validated flow

```text
content artifacts
      |
      v
existing multimodal_fusion Gemini call
      |
      +-- normal claim candidate fields
      |      text / confidence / provenance
      |
      +-- structured_claim_output
                 |
                 v
      semantic sidecar metadata
                 |
                 v
      Structured Claim Input
                 |
                 v
      Runtime Shadow Integration
                 |
                 v
      Structured Claim Shadow Bridge
                 |
                 v
      Model Protocol Boundary
                 |
                 v
      Claim Router
          /       |       \
       full    partial   insufficient
        |          |          |
 Claim Identity  no ID      no ID
```

The structured path remains observational. The existing production bridge plan continues unchanged.

## Existing call, not a second call

The normal semantic fusion request already uses Gemini mode:

`multimodal_fusion`

When structured claim shadowing is enabled and the caller has not supplied an explicit precomputed structured mapping, the runtime provides a bounded canonical subject/entity context to semantic execution.

Semantic execution appends a structured-claim Task 3 to the existing fusion prompt.

There is still exactly one `multimodal_fusion` provider call for that fusion operation.

No `structured_claim_generator`, second client, second provider mode, or follow-up model call is introduced.

## Default production behavior stays unchanged

Structured claim shadowing remains disabled by default.

When disabled:

- no structured context is built;
- the existing fusion prompt remains byte-for-byte equivalent to the pre-validation prompt;
- no structured output is requested;
- the existing production bridge is called normally;
- the existing runtime response schema remains unchanged.

An explicit precomputed structured-output mapping also continues to work and does not require changing the fusion prompt.

## Canonical subject and entity context

The structured prompt cannot safely guess canonical entity keys.

The runtime therefore builds an optional structured fusion context from the already-existing verified bridge bindings plus an explicit entity allowlist.

The context includes:

- expected canonical `subject_key`;
- allowed canonical entity keys;
- optional canonical names and entity types;
- the locked deterministic three-way Claim Router schema.

If the subject is unresolved or is not present in the allowlist, structured prompting does not activate. Shadow plumbing must not turn an unresolved identity input into a production request failure.

## Structured output ownership

For every normal claim candidate, the model may emit:

`structured_claim_output`

with the existing three-way router envelope:

- `extracted`
- `partial`
- `insufficient`

The model owns only the semantic proposal.

The model does not own durable identity.

The nested candidate must not control its validator contract version. The Model Protocol Boundary removes model-supplied nested candidate version metadata before deterministic validation when necessary.

The deterministic Claim Intelligence Engine still owns:

- taxonomy validation;
- full identity completeness;
- canonical keys;
- fingerprints;
- partial semantics safety;
- fail-closed handling.

Neither model output nor deterministic claim identity establishes truth.

## Sidecar remains isolated from production identity

The structured proposal is removed from the normal candidate payload and stored in claim-candidate artifact metadata under:

`structured_claim_outputs_by_candidate_id`

Therefore:

- normal candidate payload stays unchanged;
- candidate ID formula stays unchanged;
- candidate artifact content hash stays unchanged by the sidecar;
- the existing production bridge continues to ignore structured metadata;
- the sidecar can be collected automatically only by the structured shadow path.

## Runtime activation rule

Automatic structured prompting occurs only when all of the following are true:

1. `structured_claim_shadow_enabled=True`;
2. that side did not receive an explicit `*_structured_claim_outputs` mapping;
3. the side has a canonical bound subject;
4. the subject is in the supplied entity allowlist.

If an explicit structured mapping is provided, it remains authoritative for the shadow input and no model-produced sidecar is required for that side.

## Live validation budget

The final live validation uses exactly one Gemini provider call.

It reuses:

- model `gemini-3.5-flash`;
- mode `multimodal_fusion`;
- the existing Gemini usage ledger and capacity guard;
- a fresh evaluation client bucket.

Call two is forbidden.

The validation fixture is intentionally small:

`Jude Bellingham scored in a league match.`

Expected structured behavior is partial match-event semantics because the sentence supports `match_event / scored` but does not identify the exact match/event key.

A quality miss is recorded as measured evidence and does not authorize weakening deterministic gates.

## What the live baseline stores

The committed baseline may store:

- provider usage IDs and token counts;
- base and structured prompt digests;
- prompt character lengths and delta;
- normalized claim candidate / routed semantic fields;
- sidecar collection summary;
- quality result;
- hard-safety result.

It does not store:

- the raw Gemini response;
- the full Gemini prompt;
- API keys;
- provider credentials.

## Token-cost observation

The final evaluator records the actual prompt/output/thought/total tokens for the one structured fusion call.

It also records the deterministic character-size increase between the old base fusion prompt and the structured fusion prompt.

This is the first cost datapoint for later Sportabase Control Room tracking. It is not treated as a universal cost estimate from one sample.

## Hard safety requirements

The end-to-end structured shadow may not:

- change the production bridge plan;
- select the production claim;
- filter production candidates;
- replace production claim identity;
- persist a structured claim;
- persist structured evidence;
- persist a structured observation;
- create story membership;
- establish corroboration;
- establish authority;
- establish reliability;
- establish independence;
- establish truth;
- affect Live Merit;
- create training labels.

Shadow or model failure remains non-authoritative.

## Scope of the final checkpoint

The intended implementation changes are limited to:

1. additive Structured Claim Fusion context/prompt helper;
2. semantic execution optional structured context support;
3. runtime optional canonical entity metadata and context plumbing;
4. deterministic tests and contracts;
5. one-call live evaluator and sanitized committed baseline.

It does not switch production claim identity and it does not migrate existing claims.

## Completion boundary

Once the deterministic suites pass, the exact one-call live validation completes, the sanitized baseline is committed, and the hard-safety result passes, the **Claim Intelligence Engine is complete as a shadow-validated backend subsystem**.

The old numbered/lettered development sequence is then historical Git traceability only.

The next project activity is the agreed **Architecture and Nomenclature Reset**: map the whole Sportabase workflow using functional system names, identify overlaps/dead code, and define the canonical system boundaries before beginning another major subsystem.
