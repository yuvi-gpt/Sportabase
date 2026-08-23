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
