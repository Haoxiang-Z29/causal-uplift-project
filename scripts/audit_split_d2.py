#!/usr/bin/env python3
"""D2 audit and deterministic outcome-blind sample/split scaffold.

The full-data run is intentionally gated by --confirm-plan.  The learner must
first explain and accept the sampling/split contract recorded in the D2 packet.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from inspect_criteo_d1 import DATA_PATH, EXPECTED_COLUMNS, EXPECTED_ROWS, FEATURES


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "artifacts" / "d2_audit_split.json"
SAMPLE_PATH = ROOT / "data" / "processed" / "criteo_modeling_data.csv.gz"

# Raw CSV labels and column positions from the locked D1 dataset contract.
CONTROL_ARM = "0"
TREATED_ARM = "1"
NEGATIVE_OUTCOME = "0"
POSITIVE_OUTCOME = "1"
BINARY_VALUES = {NEGATIVE_OUTCOME, POSITIVE_OUTCOME}
TREATMENT_COLUMN = "treatment"
PRIMARY_OUTCOME_COLUMN = "conversion"
TREATMENT_COLUMN_INDEX = EXPECTED_COLUMNS.index(TREATMENT_COLUMN)
PRIMARY_OUTCOME_COLUMN_INDEX = EXPECTED_COLUMNS.index(PRIMARY_OUTCOME_COLUMN)
FEATURE_COLUMN_INDICES = tuple(EXPECTED_COLUMNS.index(name) for name in FEATURES)

# Reproducible sampling and split contract.
SEED = 20260804
HASH_BUCKET_COUNT = 1_000_000
TRAIN_SPLIT = "train"
VALIDATION_SPLIT = "validation"
TEST_SPLIT = "test"
EVALUATION_SPLITS = (VALIDATION_SPLIT, TEST_SPLIT)
TRAIN_FRACTION = 0.70
VALIDATION_FRACTION = 0.15
TEST_FRACTION = 0.15
TRAIN_KEEP_FRACTION = 0.20
TRAIN_BUCKET_CUTOFF = int(TRAIN_FRACTION * HASH_BUCKET_COUNT)
VALIDATION_BUCKET_CUTOFF = int(
    (TRAIN_FRACTION + VALIDATION_FRACTION) * HASH_BUCKET_COUNT
)
TRAIN_KEEP_BUCKET_CUTOFF = int(TRAIN_KEEP_FRACTION * HASH_BUCKET_COUNT)
MIN_EVAL_CONTROL_CONVERSIONS = 100


def stable_bucket(row_index: int, *, seed: int, salt: str) -> int:
    payload = f"{seed}:{salt}:{row_index}".encode("ascii")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") % HASH_BUCKET_COUNT


def split_for_row(row_index: int, *, seed: int = SEED) -> str:
    bucket = stable_bucket(row_index, seed=seed, salt="split")
    if bucket < TRAIN_BUCKET_CUTOFF:
        return TRAIN_SPLIT
    if bucket < VALIDATION_BUCKET_CUTOFF:
        return VALIDATION_SPLIT
    return TEST_SPLIT


def selected_for_modeling(
    row_index: int, split: str, *, seed: int = SEED
) -> bool:
    """Keep full validation/test and an outcome-blind 20% of train."""
    if split != TRAIN_SPLIT:
        return True
    return (
        stable_bucket(row_index, seed=seed, salt="train_sample")
        < TRAIN_KEEP_BUCKET_CUTOFF
    )


def control_conversion_count_name(split: str) -> str:
    """Return the public field name for one split's control conversions."""
    return f"{split}_control_conversions"


def rare_cell_check(
    control_conversion_counts,
    minimum=MIN_EVAL_CONTROL_CONVERSIONS,
):
    """Warn when an evaluation split has too few observed control conversions."""
    counts = {}
    warnings = []

    for split in EVALUATION_SPLITS:
        count_name = control_conversion_count_name(split)
        control_conversions = control_conversion_counts.get(count_name, 0)
        counts[count_name] = control_conversions

        if control_conversions < minimum:
            warnings.append(
                f"{count_name} below {minimum}; "
                "top-k uplift estimates may be unstable"
            )

    return {
        "threshold": minimum,
        "counts": counts,
        "status": "warning" if warnings else "pass",
        "warnings": warnings,
    }

@dataclass
class RunningStats:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0
    minimum: float = math.inf
    maximum: float = -math.inf

    def add(self, value: float) -> None:
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)

    @property
    def variance(self) -> float:
        return self.m2 / (self.n - 1) if self.n > 1 else 0.0


def standardized_mean_difference(a: RunningStats, b: RunningStats) -> float:
    pooled_sd = math.sqrt((a.variance + b.variance) / 2.0)
    if pooled_sd == 0.0:
        return 0.0 if a.mean == b.mean else math.copysign(math.inf, a.mean - b.mean)
    return (a.mean - b.mean) / pooled_sd


def audit_and_split(
    source: Path = DATA_PATH,
    *,
    output_sample: Path = SAMPLE_PATH,
    expected_rows: int | None = EXPECTED_ROWS,
) -> dict:
    stats = {
        arm: {feature: RunningStats() for feature in FEATURES}
        for arm in (CONTROL_ARM, TREATED_ARM)
    }
    missing = {
        arm: {feature: 0 for feature in FEATURES}
        for arm in (CONTROL_ARM, TREATED_ARM)
    }
    arm_outcome = {}
    split_counts = {}
    row_count = 0
    output_count = 0
    full_split_counts = {}

    output_sample.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(source, "rt", encoding="utf-8", newline="") as source_handle, gzip.open(
        output_sample, "wt", encoding="utf-8", newline=""
    ) as sample_handle:
        reader = csv.reader(source_handle)
        columns = next(reader)
        if columns != EXPECTED_COLUMNS:
            raise ValueError(f"unexpected columns: {columns}")
        writer = csv.writer(sample_handle)
        writer.writerow(columns + ["split"])

        for row_index, row in enumerate(reader):
            row_count += 1
            arm = row[TREATMENT_COLUMN_INDEX]
            outcome = row[PRIMARY_OUTCOME_COLUMN_INDEX]
            if arm not in BINARY_VALUES or outcome not in BINARY_VALUES:
                raise ValueError(
                    f"row {row_index}: treatment and conversion must be binary"
                )
            arm_outcome[(arm, outcome)] = arm_outcome.get((arm, outcome), 0) + 1
            for feature, column_index in zip(FEATURES, FEATURE_COLUMN_INDICES):
                raw = row[column_index]
                if raw == "":
                    missing[arm][feature] += 1
                    continue
                value = float(raw)
                if not math.isfinite(value):
                    raise ValueError(f"row {row_index}: non-finite {feature}={raw}")
                stats[arm][feature].add(value)

            split = split_for_row(row_index)
            full_key = (split, arm, outcome)
            full_split_counts[full_key] = full_split_counts.get(full_key, 0) + 1
            if selected_for_modeling(row_index, split):
                writer.writerow(row + [split])
                output_count += 1
                key = (split, arm, outcome)
                split_counts[key] = split_counts.get(key, 0) + 1

    if expected_rows is not None and row_count != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, got {row_count}")

    balance = {}
    for feature in FEATURES:
        treated = stats[TREATED_ARM][feature]
        control = stats[CONTROL_ARM][feature]
        balance[feature] = {
            "treated_mean": treated.mean,
            "control_mean": control.mean,
            "smd": standardized_mean_difference(treated, control),
            "treated_min": treated.minimum,
            "treated_max": treated.maximum,
            "control_min": control.minimum,
            "control_max": control.maximum,
        }

    control_conversion_counts = {
        control_conversion_count_name(split): full_split_counts.get(
            (split, CONTROL_ARM, POSITIVE_OUTCOME),
            0,
        )
        for split in EVALUATION_SPLITS
    }
    rare_cell_result = rare_cell_check(control_conversion_counts)

    return {
        "full_rows": row_count,
        "modeling_data_rows": output_count,
        "sampling_contract": {
            "method": "split full data first; keep validation/test; BLAKE2b outcome-blind subsample of train",
            "seed": SEED,
            "train_keep_rate": TRAIN_KEEP_FRACTION,
            "source_order_dependency": "source SHA-256 is fixed by D1",
        },
        "split_contract": {
            "method": "BLAKE2b hash of every source row index before train subsampling",
            "train_validation_test": [
                TRAIN_FRACTION,
                VALIDATION_FRACTION,
                TEST_FRACTION,
            ],
            "stratification": "not forced; T/Y cells are audited after hashing",
            "selection_rule": "model/tuning use train+validation only; test once after freeze",
        },
        "full_arm_outcome_counts": {
            f"T{arm}_Y{outcome}": count
            for (arm, outcome), count in sorted(arm_outcome.items())
        },
        "full_split_arm_outcome_counts": {
            f"{split}_T{arm}_Y{outcome}": count
            for (split, arm, outcome), count in sorted(full_split_counts.items())
        },
        "sample_split_arm_outcome_counts": {
            f"{split}_T{arm}_Y{outcome}": count
            for (split, arm, outcome), count in sorted(split_counts.items())
        },
        "missing_by_arm": missing,
        "feature_balance": balance,
        "duplicate_unit_check": {
            "status": "not_identifiable",
            "reason": "the public schema has no stable user identifier; identical feature rows need not be duplicate users",
        },
        "leakage_boundary": {
            "allowed_X": FEATURES,
            "forbidden_X": ["conversion", "visit", "exposure"],
            "special_role": {"treatment": "learner treatment input, never ordinary X"},
        },
        "rare_cell_check": rare_cell_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-plan",
        action="store_true",
        help="confirm the D2 sampling/split contract before the full run",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.confirm_plan:
        raise SystemExit(
            "Plan not yet confirmed. Read docs/day2_packet.md and rerun with --confirm-plan."
        )
    result = audit_and_split()
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"Wrote {AUDIT_PATH}")
    print(f"Wrote {SAMPLE_PATH}")


if __name__ == "__main__":
    main()
