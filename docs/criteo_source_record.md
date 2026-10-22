# Criteo Uplift unbiased v2.1 source record

Status: selected, downloaded, and fully streamed on 2026-08-04. Archive
integrity, hash, schema, row count, binary fields, empty-feature checks, and arm
aggregates have been verified locally.

## Authoritative source

- Publisher page: https://ailab.criteo.com/criteo-uplift-prediction-dataset/
- Official v2.1 object: https://criteostorage.blob.core.windows.net/criteo-research-datasets/criteo-uplift-v2.1.csv.gz
- Local raw path: `data/raw/criteo-uplift-v2.1.csv.gz`
- License stated by publisher: CC BY-NC-SA 4.0.
- Repository policy: raw and processed data stay ignored by Git; the public
  repository records source, attribution, scripts, hashes, and derived aggregate
  evidence rather than redistributing the raw file.

## Why this version

The publisher's erratum says the first release contained advertiser-related
leakage that could artificially improve uplift prediction. This project excludes
that release and uses only the unbiased version linked by the publisher.

Publisher-reported figures for the unbiased release:

- compressed size: 297 MB;
- rows: 13,979,592;
- average visit rate: 0.046992;
- average conversion rate: 0.00292;
- treatment ratio: 0.85.

Publisher-listed columns:

- anonymized dense features: `f0` through `f11`;
- randomized-group indicator: `treatment`;
- labels: `conversion`, `visit`;
- effective-ad-delivery indicator: `exposure`.

## Evidence boundary

The publisher figures above are source metadata. Verified local archive evidence:

- compressed bytes: `311422618`;
- SHA-256: `2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`;
- gzip integrity: passed;
- actual header: `f0` through `f11`, followed by `treatment`, `conversion`,
  `visit`, `exposure`.

The user has confirmed the unit, treatment, primary/secondary outcomes,
pre-treatment feature boundary, and exclusion of `exposure`. The full local scan
recorded:

- shape: `13,979,592 × 16`;
- control: `2,096,937` rows, conversion rate `0.0019375880`, visit rate
  `0.0382009569`, and zero effective exposures;
- treatment: `11,882,655` rows, conversion rate `0.0030894611`, visit rate
  `0.0485433600`, and exposure rate `0.0360367275`;
- observed assignment differences: conversion `0.0011518731`, visit
  `0.0103424031`;
- overall treatment ratio `0.8500001288`, conversion rate `0.0029166803`, and
  visit rate `0.0469920009`; these fields were added and rerun by the user;
- no empty strings in `f0` through `f11` and no non-binary values in the four
  binary columns.

These checks do not yet cover duplicate units, numeric ranges, distribution
balance, sampling, train/validation/test splitting, or Uplift evaluation; those
belong to D2.
