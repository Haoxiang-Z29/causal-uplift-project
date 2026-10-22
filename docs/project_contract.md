# D1 Project Contract — Criteo Uplift unbiased v2.1

## User-confirmed causal contract

- Dataset: the official Criteo Uplift unbiased v2.1 release. The original
  release is excluded because the publisher reported advertiser-related
  leakage.
- Unit: one anonymized user row.
- Treatment `T`: randomized `treatment` assignment (`1` = treatment group,
  `0` = control), not actual `exposure`.
- Primary outcome `Y`: binary `conversion` after assignment.
- Secondary diagnostic outcome: binary `visit`; it is not a feature for the
  conversion model.
- Pre-treatment covariates `X`: dense anonymized features `f0` through `f11`.
- Excluded from ordinary `X`: `treatment` defines T; `conversion` defines the
  primary Y; `visit` is a post-treatment secondary outcome; `exposure` is a
  post-assignment effective-exposure indicator.
- Estimand: `CATE(x) = E[Y(1)-Y(0) | X=x]` for the intention-to-treat effect of
  randomized assignment on conversion.
- Decision: before ad delivery, rank eligible users by estimated incremental
  conversion under a fixed targeting/contact budget.

An S-Learner may technically receive `[X, T]` as model input. This does not turn
`T` into a pre-treatment user covariate; it is still the treatment variable used
to construct the two potential-outcome predictions.

## Non-overclaiming project statement

> This project uses Criteo's public randomized advertising incrementality data
> to compare conversion-response ranking with estimated incremental-conversion
> ranking under a fixed targeting budget. The primary target is the
> intention-to-treat CATE of randomized assignment, estimated from anonymized
> pre-treatment features and evaluated on held-out randomized data. Offline
> results do not identify every user's true ITE, the causal effect of actual ad
> exposure, or performance on a future employer's traffic.

## Known design limitations

- The treatment ratio is approximately 85/15 rather than balanced; randomization
  supports causal comparison, but the smaller control arm raises variance.
- Conversion is rare, so subgroup and top-k estimates may be unstable.
- Features are anonymized. We can discuss statistical heterogeneity and ranking
  behavior, but cannot assign invented business meanings to `f0`–`f11`.
- Actual exposure is post-assignment and non-random. Estimating an exposure
  effect would require a different estimand and additional assumptions.
- The publisher used non-uniform subsampling for privacy, so the benchmark's
  aggregate incrementality should not be presented as the source advertisers'
  original production effect.

## Sampling and evaluation boundary

The full archive is retained locally and ignored by Git. D1 verifies the entire
file. A deterministic modeling sample may be created only after D2 fixes its
method, seed, and invariants; it must not be selected by conversion outcome.
Train/validation/test splitting and Uplift metrics remain D2 work and are not
completed by this contract.

## Hillstrom fallback

The earlier verified Hillstrom setup is preserved in
`docs/hillstrom_fallback_contract.md`. It is not a parallel modeling branch and
will be reactivated only if the Criteo route exceeds the agreed technical risk
limit.

## Prospective research seed (proposal, not completed evidence)

Proposed question: under a fixed advertising budget and possible user-experience
cost, when does incremental-effect ranking improve net value over response
ranking, and how stable is that decision under treatment imbalance, rare
conversion, cost assumptions, and population shift?

Employer-specific treatment definitions, auction mechanics, attribution
windows, value/cost units, frequency caps, interference, privacy constraints,
and online validation requirements remain unknown and require alignment.
