# D3 Acceptance Evidence — Response, S-Learner, and T-Learner

Date closed: 2026-08-06. User-reported time: not itemized by task (D3 total not
separately reported). This file distinguishes verified project artifacts,
user-owned explanations, and work that has not yet been performed. It follows
the same evidence-boundary format as `docs/evidence/D2_ACCEPTANCE.md`.

## D3-T1 — Response-model baseline

Status: `completed / independent_pass`.

- The response baseline is a treated-only `LogisticRegression` fit on
  `Y ~ X` with treated rows only; its score is `mu1_hat = P(Y=1|X,T=1)`, an
  ordinary predicted conversion probability, not a treatment effect.
- The user predicted, before running the code, that `negative_score_fraction`
  for this model must be exactly 0 because a sigmoid output is bounded in
  `[0,1]`. The full-validation rerun confirmed `negative_score_fraction=0.0`,
  matching the prediction.

## D3-T2 — S-Learner and T-Learner

Status: `completed / independent_pass`.

- S-Learner: one shared `LogisticRegression` fit on `[scaled X, T, T*scaled X]`;
  `s_uplift = s_mu1 - s_mu0` from two counterfactual copies of the same fitted
  model (`T` forced to 1, then to 0) for every validation row.
- T-Learner: two independently fitted arm models (`treated_outcome_model`,
  `control_outcome_model`); `t_uplift = t_mu1 - t_mu0` where `t_mu1` is reused
  from the response baseline model.
- The user predicted, before running the code, that T's
  `negative_score_fraction` would be higher than S's, reasoning that the
  smaller control arm (~15%) and T's fully independent arm models would carry
  more variance. The full-validation result was the opposite direction:
  `s_learner=0.417267`, `t_learner=0.112712`.
- The user did not discard the failed prediction. Instead they proposed a
  structural explanation: S shares parameters and a global `T*X` interaction,
  producing a broad-but-shallow negative region; T's fully decoupled arm
  models produce a narrower but occasionally deep negative tail. This was
  recorded at D3 close as a plausible but unverified shape hypothesis.

## Verified full-validation results (Criteo unbiased v2.1, D2 fixed split)

| model | qini_coefficient | top_raw_incremental_gain | outcome_auc | negative_score_fraction |
|---|---:|---:|---:|---:|
| response | 1228.9707 | 2375.3289 | 0.9494 | 0.0000 |
| s_learner | 1156.6673 | 2330.1627 | 0.8979 | 0.4173 |
| t_learner | 1163.0317 | 2363.1006 | 0.8935 | 0.1127 |

Ranking diagnostics: `s_t_score_pearson=0.980862`,
`s_t_top10_overlap_fraction=0.945660`.

These are observed validation results on one fixed split and one fixed model
configuration (`C=1.0`, seed `20260805`). They are not confirmed to be
statistically significant or stable across seeds; no repeated-seed or
bootstrap variance estimate has been produced. That check is deferred to D6.

## D4 rerun verification (2026-08-06)

A clean, no-debug-cap rerun was executed from the confirmed contract entry
point:

```bash
cd /Users/hx/dev/work2/causal-uplift-project
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/train_d3.py --confirm-contract treated-response_s-learner_t-learner_logit_v1
```

Result: 24/24 tests passed; the rerun completed in 42.4 seconds; the
regenerated `artifacts/d3/run_record.json` and
`artifacts/d3/validation_results.csv` were byte-for-byte identical to the
pre-rerun files (verified with `diff`, zero output). Row-count cross-check:
`train_rows=1,957,575` and `validation_rows=2,096,612` exactly equal the sum
of the corresponding four treatment/outcome cells recorded in
`artifacts/d2_audit_split.json`, which is inconsistent with any test-row
contamination. A repository-wide search confirmed the only references to the
literal `"test"` split value are a passive no-op branch in
`scripts/train_d3.py` (`FORBIDDEN_D3_SPLIT`) and D2's own audit aggregation in
`scripts/audit_split_d2.py`; no code path assigns test rows into the D3
train/validation loading buckets.

## D4 result interpretation notes

- `outcome_auc` cannot be used to rank response against S/T because their
  prediction targets differ: response directly fits `P(Y=1|X,T=1)`
  (aligned with the AUC's own label), while S/T fit a *difference* of two
  probabilities that has no direct supervised label. A fair cross-model
  ranking metric must instead be one that evaluates the induced ranking under
  the same IPW/Qini construction, i.e. `qini_coefficient`.
- Even on the fair metric (Qini), response is numerically highest in this
  validation run, but the margin between the three models
  (`1228.97` vs `1163.03` vs `1156.67`) is small relative to the ~2.1M-row
  IPW-weighted computation, and no significance or repeated-run variance
  check exists yet. The correct claim is "response has the highest observed
  Qini on this split under this model configuration," not "response is
  significantly better."
- At least two plausible, non-code-bug explanations exist for a linear S/T
  comparison losing to a simple response baseline on this dataset: (1) `tau_hat`
  is a difference of two independently noisy probability estimates, and
  subtraction adds rather than cancels variance, while response never needs
  `mu0_hat`; (2) Criteo's small and sparse control arm (~15% of rows, ~0.19%
  control conversion rate) gives `mu0_hat` especially high estimator variance,
  which propagates into both S's counterfactual branch and T's independent
  control model.

## D4 negative-uplift distribution diagnostic (descriptive only, no retraining)

Computed directly from `artifacts/d3/validation_predictions.csv.gz`
(2,096,612 rows), not from a new model run:

| | s_uplift (negative subset) | t_uplift (negative subset) |
|---|---:|---:|
| negative fraction | 0.417267 | 0.112712 |
| negative count | 874,847 | 236,313 |
| conditional mean | -0.0000962 | -0.0001574 |
| conditional median | -0.0000691 | -0.0000218 |
| 5th percentile | -0.000119 | -0.000261 |
| 95th percentile | -0.000010 | -0.000002 |

The mean/median divergence for `t_uplift` (mean more negative than median)
indicates a right-skewed, heavy-tailed negative distribution: most of T's
negative predictions are mild, but a minority are much more extreme than any
S negative value. This partially supports and partially refines the D3 shape
hypothesis: it is not simply "S shallow, T deep" but "S broad-and-uniform,
T narrow-with-a-heavy-tail." A candidate mechanism — the independently
fitted `control_model` is a global linear estimator whose coefficients carry
higher variance because they are fit on a smaller, sparser positive-outcome
sample, and that coefficient variance can be amplified along some feature
directions — is proposed but not yet verified against the actual `t_mu0`
values of the most extreme rows. That verification is deferred (candidate
work for D6/D8), and no new model was trained to produce this diagnostic.

## Reproducibility

Environment (installed and tested):

```text
python 3.12.13
numpy==2.5.1
pandas==3.0.5
scikit-learn==1.9.0
matplotlib==3.11.1
```

Exact run order from a clean checkout (assumes the raw Criteo archive has
already been downloaded per `docs/criteo_source_record.md`):

```bash
cd /Users/hx/dev/work2/causal-uplift-project
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# D1: verify raw archive integrity and locked contract
.venv/bin/python scripts/download_criteo.py
.venv/bin/python scripts/inspect_criteo_d1.py

# D2: full audit, deterministic split, and derived modeling data
.venv/bin/python scripts/audit_split_d2.py --confirm-plan

# D3/D4: full-validation response/S/T comparison (test split is never read)
.venv/bin/python scripts/train_d3.py \
  --confirm-contract treated-response_s-learner_t-learner_logit_v1

# all unit tests
.venv/bin/python -m unittest discover -s tests -v
```

Seed and split contract:

- Split seed `20260804` (BLAKE2b hash of source row index, fixed 70/15/15
  train/validation/test, outcome-blind); recorded in
  `artifacts/d2_audit_split.json`.
- Model seed `20260805`, hardcoded as `MODEL_SEED` in `scripts/train_d3.py`;
  not a runtime-overridable argument, so any rerun uses the same seed.
- `--max-train-rows` / `--max-validation-rows` exist only for
  `debug_only`-labeled smoke runs; a resume-safe evidence run must omit both
  and confirm `evidence_level=full_validation` in `run_record.json`.

Artifact index:

| Path | Produced by | Contents |
|---|---|---|
| `artifacts/d1_criteo_inspection.json` | `scripts/inspect_criteo_d1.py` | D1 archive integrity, schema, arm aggregates |
| `artifacts/d2_audit_split.json` | `scripts/audit_split_d2.py` | Full-data audit, split contract, balance, rare-cell gate |
| `artifacts/d3/run_record.json` | `scripts/train_d3.py` | Run configuration, row counts, versions, ranking diagnostics |
| `artifacts/d3/validation_results.csv` | `scripts/train_d3.py` | Per-model Qini/top-k/AUC summary row |
| `artifacts/d3/validation_predictions.csv.gz` | `scripts/train_d3.py` | Per-row `treatment`, `conversion`, and all six potential-outcome/uplift scores |
| `artifacts/d3/validation_gain_curves.csv.gz` | `scripts/train_d3.py` | Downsampled Gain/baseline/Qini curve points per model |
| `artifacts/d3/validation_gain_curves.png` | `scripts/train_d3.py` | Qini-curve plot for all three models |

## Experiment log

- **D3 debug-run arm-blocked sampling bug (2026-08-05).** The derived
  modeling file preserves the source file's row order, and treatment/control
  rows are not interleaved — they appear in large contiguous blocks. The
  first 100k-row debug run used a naive "read the first N rows of the split"
  cap, which happened to land entirely inside a treated block. The defensive
  check in `fit_learners` (`if not treated.any() or not control.any(): raise
  ValueError(...)`) correctly stopped the run instead of silently fitting a
  broken T-Learner. This is best read not as "a bug was found" but as "a
  deliberately written guard against violating the two-arm requirement caught
  a real sampling-design mistake." The fix replaced the head-cap with a fixed,
  outcome-and-treatment-blind row-hash priority (`_splitmix64`, seeded from
  the row index) applied across the whole split, so a debug sample is
  guaranteed to be reproducible and to cover both arms without selecting on
  `T` or `Y`. A regression test (`test_debug_caps_are_hash_sampled_not_source_heads`)
  now locks this behavior in.
- **D4 clean rerun (2026-08-06).** Full-validation rerun reproduced
  `run_record.json` and `validation_results.csv` byte-for-byte; see the "D4
  rerun verification" section above.

## Evidence boundary

- No repeated-seed, bootstrap, or top-k sensitivity check exists yet (D6).
- No X-Learner or other additional learner exists yet (D5).
- No cost/budget-aware policy exists yet (D7).
- The negative-uplift shape hypothesis for T's heavy tail is proposed but not
  verified against per-row feature values (candidate D6/D8 diagnostic).
- These D3/D4 results must not be presented as a general claim that response
  ranking outperforms Uplift modeling; they are specific to this validation
  split, this linear model configuration, and this dataset.
