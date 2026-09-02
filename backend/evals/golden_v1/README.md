# Sportabase Golden-Set Evaluation V1

This package evaluates human-approved product expectations against frozen
candidate output. It is a separate, offline evaluation path: it does not create
provider clients, fetch URLs, run Whisper, initialize a database, or call an
application analysis handler.

## Golden, candidate, and baseline

- A **golden** is a deliberately authored, human-approved expectation.
- A **candidate** is the output being evaluated.
- A **baseline** is historical machine output useful for diagnostics only.

Candidate and baseline output never becomes correct merely because the current
system produced it. This tool has no accept, update, or baseline-overwrite mode.

## Layout and formats

`corpus/manifest.json` freezes the corpus and case-schema versions and lists
case files in deterministic order. Each case has its own directory containing
`case.json` and only its required UTF-8 artifacts. V1 supports saved final JSON
and raw provider text replay through explicitly allowlisted deterministic
normalizers.

The evaluator types are fixed in code. Fixtures cannot provide regexes, code,
imports, callbacks, templates, database paths, or network locations. Paths must
remain inside the case directory. JSON depth, collection count, file size, and
whole-case size are bounded before evaluation.

## Run

From `backend/`:

```powershell
python -m evals.golden_v1 --corpus evals/golden_v1/corpus
python -m evals.golden_v1 --format json
python -m evals.golden_v1 --validate-only
python -m evals.golden_v1 --list-cases
python -m evals.golden_v1 --case article.transfer.official.synthetic-001
python -m evals.golden_v1 --tag transcript --mode video
python -m evals.golden_v1 --json-out golden-v1-report.json
python -m evals.golden_v1 --candidate-root path/to/candidates
```

`--case` and `--tag` may be repeated. An unknown requested `--case` is an error
with exit code 2. Tag and mode filters may legitimately select zero cases; the
terminal report explicitly says `0 cases selected by filters` and does not
describe that result as a golden pass.
An external candidate root uses `<case-id>/candidate.json` for selected
`final_output` cases; provider-raw artifacts remain case-owned and immutable.
Approved cases gate; draft and `needs_review` cases are skipped. Human-review
markers produce a warning and never turn a deterministic failure into a pass.

Exit codes are:

- `0`: no failed or invalid cases;
- `1`: golden regression, or a warning with `--warnings-as-errors`;
- `2`: invalid corpus, candidate, replay artifact, or configuration.

The deterministic payload excludes timestamps, durations, random IDs, and
absolute paths. It uses UTF-8, sorted keys, stable case/check ordering, finite
numbers, and a digest of the payload before the digest field is added.

## Adding or changing a case

1. Author or edit repository-safe synthetic/original-paraphrase input.
2. Author expected semantics intentionally; never copy current output as truth.
3. Run `--validate-only`.
4. Evaluate the candidate fixture.
5. Inspect every per-check diff.
6. Obtain human repository review and mark the case approved.
7. Commit the reviewable fixture change with its annotation/corpus version.

An expectation semantics change increments `annotation_version` and the corpus
version under the repository's review policy. Reviewer names are unnecessary;
Git history and code review provide provenance.

There is no overall AI-quality or credibility score because classification,
summary fact coverage, Merit, Evidence, Logic, localization, and canonical
identity are different dimensions. Reports retain per-case failures and expose
only coherent per-dimension counts. Merit remains informational/reporting
quality, not truth probability.

Live provider evaluation remains in the existing bounded live tooling. It is
intentionally absent here so the default command cannot consume quota and
model drift cannot be confused with deterministic product regression.

Fact alternatives use Unicode-normalized, case-folded literal substring
matching. Authors must use sufficiently specific phrases and avoid short,
ambiguous tokens: a short token can occur inside an unrelated longer word.
V1 deliberately provides neither fixture regexes nor semantic matching.
