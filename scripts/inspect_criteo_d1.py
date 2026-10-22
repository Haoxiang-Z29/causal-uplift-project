#!/usr/bin/env python3
"""Stream and validate the Criteo Uplift unbiased v2.1 dataset."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import Optional

from download_criteo import DATA_PATH, EXPECTED_SHA256, sha256


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "artifacts" / "d1_criteo_inspection.json"
FEATURES = [f"f{i}" for i in range(12)]
EXPECTED_COLUMNS = FEATURES + ["treatment", "conversion", "visit", "exposure"]
EXPECTED_ROWS = 13_979_592
BINARY_VALUES = {"0", "1"}


def inspect(
    path: Path = DATA_PATH,
    *,
    verify_hash: bool = True,
    expected_rows: Optional[int] = EXPECTED_ROWS,
) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing dataset: {path}")

    actual_hash = sha256(path) if verify_hash else None
    if verify_hash and actual_hash != EXPECTED_SHA256:
        raise ValueError(f"SHA-256 mismatch: {actual_hash}")

    arm_counts = Counter()
    conversion_counts = Counter()
    visit_counts = Counter()
    exposure_counts = Counter()
    missing_features = Counter()
    control_exposure_count = 0
    row_count = 0

    with gzip.open(path, mode="rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            columns = next(reader)
        except StopIteration as exc:
            raise ValueError("empty gzip CSV") from exc
        if columns != EXPECTED_COLUMNS:
            raise ValueError(f"unexpected columns: {columns}")

        for line_no, row in enumerate(reader, start=2):
            if len(row) != len(EXPECTED_COLUMNS):
                raise ValueError(
                    f"line {line_no}: expected {len(EXPECTED_COLUMNS)} fields, got {len(row)}"
                )
            treatment, conversion, visit, exposure = row[12:16]
            for name, value in (
                ("treatment", treatment),
                ("conversion", conversion),
                ("visit", visit),
                ("exposure", exposure),
            ):
                if value not in BINARY_VALUES:
                    raise ValueError(f"line {line_no}: {name} must be binary, got {value!r}")

            row_count += 1
            arm_counts[treatment] += 1
            conversion_counts[treatment] += int(conversion)
            visit_counts[treatment] += int(visit)
            exposure_counts[treatment] += int(exposure)
            if treatment == "0" and exposure == "1":
                control_exposure_count += 1
            for index, value in enumerate(row[:12]):
                if value == "":
                    missing_features[FEATURES[index]] += 1

    if expected_rows is not None and row_count != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, got {row_count}")
    if set(arm_counts) != BINARY_VALUES:
        raise ValueError(f"both randomized arms must exist, got {set(arm_counts)}")

    by_treatment = {}
    for arm in ("0", "1"):
        n = arm_counts[arm]
        by_treatment[arm] = {
            "n": n,
            "conversion_count": conversion_counts[arm],
            "conversion_rate": conversion_counts[arm] / n,
            "visit_count": visit_counts[arm],
            "visit_rate": visit_counts[arm] / n,
            "exposure_count": exposure_counts[arm],
            "exposure_rate": exposure_counts[arm] / n,
        }

    assignment_effect = {
        outcome: by_treatment["1"][f"{outcome}_rate"]
        - by_treatment["0"][f"{outcome}_rate"]
        for outcome in ("conversion", "visit")
    }

    overall = {
        "treatment_ratio": arm_counts["1"] / row_count,
        "conversion_rate": sum(conversion_counts.values()) / row_count,
        "visit_rate": sum(visit_counts.values()) / row_count,
    }

    return {
        "source_sha256": actual_hash,
        "compressed_bytes": path.stat().st_size,
        "shape": [row_count, len(EXPECTED_COLUMNS)],
        "columns": EXPECTED_COLUMNS,
        "missing_feature_counts": dict(missing_features),
        "by_treatment": by_treatment,
        "overall": overall,
        "observed_assignment_effect": assignment_effect,
        "control_rows_with_exposure_1": control_exposure_count,
        "locked_contract": {
            "unit": "anonymized user row",
            "treatment": "randomized treatment assignment",
            "estimand": "CATE/ITT of assignment on conversion",
            "primary_outcome": "conversion",
            "secondary_outcome": "visit",
            "pre_treatment_covariates": FEATURES,
            "excluded_from_covariates": {
                "treatment": "treatment indicator, not a user covariate",
                "conversion": "primary outcome",
                "visit": "post-treatment secondary outcome",
                "exposure": "post-assignment effective-exposure indicator",
            },
        },
        "warning": (
            "Observed arm differences estimate assignment effects at the population level; "
            "they are not individual treatment-effect labels or trained-model results."
        ),
    }


def main() -> None:
    result = inspect()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
