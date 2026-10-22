#!/usr/bin/env python3
"""Validate the immutable Hillstrom CSV and emit a small D1 inspection artifact."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "hillstrom.csv"
OUTPUT_PATH = ROOT / "artifacts" / "d1_data_inspection.json"
EXPECTED_SHA256 = "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
EXPECTED_COLUMNS = [
    "recency", "history_segment", "history", "mens", "womens", "zip_code",
    "newbie", "channel", "segment", "visit", "conversion", "spend",
]
EXPECTED_ARMS = {"No E-Mail", "Mens E-Mail", "Womens E-Mail"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(path: Path = DATA_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing dataset: {path}")
    actual_hash = sha256(path)
    if actual_hash != EXPECTED_SHA256:
        raise ValueError(f"SHA-256 mismatch: {actual_hash}")

    arm_counts = Counter()
    outcomes = defaultdict(lambda: {"visit": 0, "conversion": 0, "spend": 0.0})
    row_count = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(f"unexpected columns: {reader.fieldnames}")
        for line_no, row in enumerate(reader, start=2):
            row_count += 1
            arm = row["segment"]
            if arm not in EXPECTED_ARMS:
                raise ValueError(f"line {line_no}: unexpected arm {arm!r}")
            if row["visit"] not in {"0", "1"} or row["conversion"] not in {"0", "1"}:
                raise ValueError(f"line {line_no}: outcomes must be binary")
            arm_counts[arm] += 1
            outcomes[arm]["visit"] += int(row["visit"])
            outcomes[arm]["conversion"] += int(row["conversion"])
            outcomes[arm]["spend"] += float(row["spend"])

    if row_count != 64_000:
        raise ValueError(f"expected 64000 rows, got {row_count}")
    if set(arm_counts) != EXPECTED_ARMS:
        raise ValueError(f"missing experimental arm: {set(arm_counts)}")

    by_arm = {}
    for arm in sorted(EXPECTED_ARMS):
        n = arm_counts[arm]
        by_arm[arm] = {
            "n": n,
            "visit_rate": outcomes[arm]["visit"] / n,
            "conversion_rate": outcomes[arm]["conversion"] / n,
            "mean_spend": outcomes[arm]["spend"] / n,
        }

    binary_n = arm_counts["Mens E-Mail"] + arm_counts["No E-Mail"]
    return {
        "source_sha256": actual_hash,
        "shape": [row_count, len(EXPECTED_COLUMNS)],
        "columns": EXPECTED_COLUMNS,
        "arms": by_arm,
        "locked_binary_contract": {
            "included_arms": ["Mens E-Mail", "No E-Mail"],
            "n": binary_n,
            "treatment": "1 iff segment == 'Mens E-Mail'",
            "primary_outcome": "conversion",
            "unit": "customer",
        },
        "warning": "Arm means are data inspection, not an individual treatment-effect label.",
    }


def main() -> None:
    result = inspect()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

