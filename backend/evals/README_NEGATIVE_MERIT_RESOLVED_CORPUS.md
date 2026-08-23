# Negative Merit resolved real-world corpus

This directory contains the offline evaluation machinery for the resolved
negative-Merit calibration corpus.

The corpus runner is deliberately separate from production scoring. It does not
choose a negative Merit weight, enable live negative Merit, call Gemini, or
establish permanent objective truth.

Required populations:

- resolved_against_claim_observation
- two_gate_observation
- authority_only_control
- semantic_only_control
- no_negative_evidence_control
- exclusive_no_corroboration_control

A resolved case is accepted by the underlying calibration dataset only when it
contains the persisted canonical-outcome-resolution verifier result for the same
claim and matching immutable source capture.

Unit-test fixtures test the harness only. They do not count as real-world corpus
evidence.

From backend, create an empty collection template with:

    python -m evals.run_negative_merit_resolved_corpus --write-template .\negative-merit-resolved-corpus.json

Evaluate a frozen corpus with:

    python -m evals.run_negative_merit_resolved_corpus --corpus .\negative-merit-resolved-corpus.json --json-out .\negative-merit-resolved-report.json

Exit code 0 means every required population is present.
Exit code 1 means the corpus is valid but incomplete.
Exit code 2 means the corpus is malformed or unverifiable.

A passing corpus still does not authorize a numeric penalty. Real score
distributions and false-positive controls must be inspected before any negative
release certificate can be considered.

## Real-case inventory

Before adding cases to the frozen corpus, inspect the persisted Sportabase database
with the read-only inventory runner:

    python -m evals.run_negative_merit_real_case_inventory

The inventory opens SQLite in read-only/query-only mode. It does not persist new
verification, call providers, modify Merit, or admit cases into the corpus.

For each persisted primary article claim it reports the latest analysis snapshot,
the pre-live-overlay legacy Merit total when recoverable, persisted direct-authority
and machine-semantic gates, canonical-resolution lineage, source-capture readiness,
and a suggested calibration class.

The suggested class is discovery metadata only. In particular, a row with no
negative evidence is never automatically called a legitimate exclusive scoop.
Exclusive controls require separate curation because absence of corroboration does
not prove exclusivity.
