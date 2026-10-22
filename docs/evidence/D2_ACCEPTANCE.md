# D2 Acceptance Evidence — Audit, Split, and Uplift Evaluation

Date closed: 2026-08-05. User-reported focused time: 6h. This file distinguishes
verified project artifacts, user-owned explanations, synthetic metric checks,
and work that has not yet been performed.

## D2-T1 — Data audit and split

Status: `completed / independent_pass`.

Verified full-data and split evidence:

- Audited all 13,979,592 rows of the D1-locked Criteo unbiased v2.1 source.
- Applied a deterministic, outcome-blind BLAKE2b 70/15/15 split with seed
  `20260804` before training subsampling.
- Retained all validation/test rows and an outcome-blind 20% of train, producing
  6,149,755 modeling rows in a 135 MB compressed derived file.
- Validation conversions: control 581, treatment 5,629.
- Test conversions: control 624, treatment 5,655.
- No missing values were observed in `f0`–`f11` in either randomized arm.
- Maximum absolute full-data SMD was 0.048836 for `f3`.  This supports rough
  observed univariate mean balance; it does not prove complete randomization,
  nonlinear/joint balance, absence of unobserved imbalance, or future validity.
- Duplicate units are not identifiable because the public schema has no stable
  user ID; identical anonymous rows were not silently deleted.
- User-selected rare-cell gate: validation and test must each have at least 100
  control conversions.  The full rerun passed at 581/624.  The user correctly
  explained that this does not guarantee significance, unbiasedness, or stable
  top-k prefixes.

Reproducibility evidence after the user-reviewed refactor:

- Derived gzip SHA-256:
  `917f3387de981af74349924ecf7e94331f9b603d21eb1a81a4bc9f6843098f51`.
- Audit JSON SHA-256:
  `5254043c948fed3e199bfa7409c00f62c1415847f60fa389f6d58dbfb6b147e8`.
- Artifact: `artifacts/d2_audit_split.json`.
- Derived data: `data/processed/criteo_modeling_data.csv.gz` (ignored by Git).
- Implementation: `scripts/audit_split_d2.py`.

User ownership evidence:

- Explained finite-sample balance, post-treatment exposure, differential
  missingness, duplicate-unit limits, and treatment-prediction diagnostics.
- Chose the split/sample design based on rare control conversions.
- Chose and initially implemented the rare-cell threshold, wrote boundary
  tests, debugged an input/output-key mismatch, challenged magic constants,
  and reviewed the semantic refactor before the full rerun.

## D2-T2 — Uplift evaluation

Status: `completed / independent_pass`.

Metric convention:

- Ranked IPW gain:
  `G(k)=sum[T_i*Y_i/p - (1-T_i)*Y_i/(1-p)]`.
- Random baseline: `B(k)=k/n * G(n)`.
- Qini coefficient: trapezoidal area under `G-B`, with x normalized to `[0,1]`
  and y left as raw cumulative IPW gain.
- Fixed-budget summaries report raw `G(k)`, `G(k)/k` per selected user, and
  `G(k)/n` per eligible user.
- These conventions must be recorded because library normalizations differ.

Verified synthetic checks and user ownership:

- Correctly calculated response AUC=0.75 from positive/negative pairs.
- At p=0.8, correctly calculated contributions `[1.25,0,-5,1.25]`, Gain
  `[0,1.25,1.25,-3.75,-2.5]`, random baseline, Qini deviations, and Qini=0.625.
- Correctly distinguished raw gain, per-selected uplift, per-eligible policy
  value, and unknown individual persuadable labels.
- Implemented `incremental_policy_value_at_k` and normal/k=0 tests.
- Predicted and added exact perfect-ish/neutral/reversed Gain and Qini regression
  tests (+2/0/-2).
- Correctly explained why using p=0.5 instead of Criteo's p≈0.85 overweights
  treated conversions, underweights control conversions, biases raw Gain, and
  also corrupts the Qini curve and baseline.

Implementation: `scripts/uplift_metrics.py`; tests:
`tests/test_uplift_metrics.py`.

## Evidence boundary

- No response model, S-Learner, T-Learner, Criteo prediction, Criteo Gain/Qini
  curve, real model comparison, or resume-ready model metric exists yet.
- Qini values in D2 are synthetic sanity checks, not Criteo performance.
- The local Python 3.12 virtual environment exists, but third-party numerical
  packages were not successfully imported as of D2.  D2 uses the standard
  library and is not blocked; D3 must resolve or replace the model stack.

## Reproduce D2 evidence

Final verified project test result at D2 close: 18/18 passed.

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 -m unittest discover -s tests -v
python3 scripts/audit_split_d2.py --confirm-plan
gzip -t data/processed/criteo_modeling_data.csv.gz
```
