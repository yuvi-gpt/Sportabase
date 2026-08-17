# Sportabase #35A — canonical claim identity contract

#35A defines a structured, deterministic claim-identity contract. It does not replace the existing multimodal bridge yet and it does not change any live product behavior.

## Why this exists

The #34B Bellingham live evaluation proved that independently generated semantic-fusion claim text is not stable enough to be used directly as cross-source identity. The existing multimodal bridge derives its canonical claim key from the normalized generated claim text. Two paraphrases can therefore describe the same underlying event while receiving different deterministic claim IDs.

#35A separates semantic interpretation from durable identity.

AI may later propose a structured claim candidate. Deterministic code normalizes that candidate and computes identity fingerprints. Neither the model nor the fingerprint establishes truth, authority, source reliability, independence, corroboration, training eligibility, or Merit.

## Contract

A canonical claim candidate contains only:

- `subject_key`
- `event_type`
- `state`
- `negated`
- `roles`
- `facets`

The initial event taxonomy is deliberately small and grounded in the frozen Sportabase golden corpus:

- transfer
- contract
- tenure / appointment / departure
- retirement
- injury
- availability
- lineup
- match or race result
- match or race event
- championship
- disciplinary action

Unknown event types, unknown states, unknown role keys and unknown facet keys fail closed. The identity layer is not an open-ended metadata bucket.

## Core identity versus specificity

#35A exposes two deterministic fingerprints.

The **core fingerprint** contains only the minimum fields selected for the event type. It is intended to avoid fragmentation when one source contains extra but non-conflicting detail that another source omits.

The **specific fingerprint** contains all normalized roles and material facets provided by that candidate.

Example transfer claims:

```text
A: Bellingham completed a move to Real Madrid in 2023.
B: Bellingham signed for Real Madrid from Borussia Dortmund.
```

Their structured candidates may normalize to the same core:

```text
subject_key = football|player|jude-bellingham
event_type = transfer
state = completed
destination = football|club|real-madrid
negated = false
```

while retaining different specific facets such as `effective_period=2023` or `origin=football|club|borussia-dortmund`.

A same-subject hard negative such as "Bellingham scored in a later league match" becomes a `match_event` claim and therefore cannot share the transfer core fingerprint.

## Material conflicts

Matching cores are not sufficient by themselves.

`compare_canonical_claims()` checks overlapping material roles and facets. If both candidates provide the same optional field and disagree, the result is `material_conflict`.

For example, two completed-transfer candidates with the same subject and destination but conflicting explicit origins are not treated as cleanly compatible merely because their core fingerprint matches.

This is deterministic conflict detection. It does not use embeddings, cosine similarity, fuzzy text thresholds, or an AI yes/no equivalence decision.

## Safety boundaries

Fields related to any of the following are forbidden from claim identity input:

- truth / verification
- authority
- reliability / trust / credibility
- independence
- corroboration
- Merit or score effects
- training eligibility
- model or source confidence
- publisher / reporter / provider identity
- source URL

Those concepts remain separate evidence, provenance, observation, adjudication and scoring concerns.

The compatibility output explicitly states:

- deterministic only
- no fuzzy similarity
- no model equivalence decision
- does not establish truth
- does not establish authority
- does not establish independence
- does not establish corroboration
- does not affect Live Merit

## #35A boundaries

#35A intentionally does **not**:

- call Gemini;
- modify the Gemini capacity runtime;
- change the existing multimodal bridge canonical-key path;
- migrate existing claim rows;
- alter database schema;
- change story membership;
- change adjudication;
- change source authority or independence logic;
- change Live Merit;
- modify the frozen #33/#34B golden corpus or baseline.

Those integrations belong to later checkpoints after this contract is locked by deterministic tests.

## Bellingham regression target

The contract-level target is:

```text
X transfer anchor <-> web transfer positive       same core, no material conflict
X transfer anchor <-> YouTube transfer positive   same core, no material conflict
X transfer anchor <-> later-goal hard negative    different core
```

This is not yet a claim that the live pipeline can extract these structures reliably. #35A proves only that, **if** the candidate semantics are represented this way, identity behavior is deterministic and safety-preserving.
