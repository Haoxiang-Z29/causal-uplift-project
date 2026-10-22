#!/usr/bin/env python3
"""Download the public Hillstrom challenge CSV and verify its fixed hash."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from pathlib import Path

from inspect_d1 import DATA_PATH, EXPECTED_SHA256, sha256


SOURCE_URL = (
    "http://www.minethatdata.com/"
    "Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv"
)


def main() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DATA_PATH.exists() and sha256(DATA_PATH) == EXPECTED_SHA256:
        print(f"Dataset already present and verified: {DATA_PATH}")
        return

    with tempfile.NamedTemporaryFile(
        dir=DATA_PATH.parent, prefix="hillstrom-", suffix=".csv", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
                shutil.copyfileobj(response, temporary)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    actual_hash = sha256(temporary_path)
    if actual_hash != EXPECTED_SHA256:
        temporary_path.unlink(missing_ok=True)
        raise ValueError(
            f"SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual_hash}"
        )

    temporary_path.replace(DATA_PATH)
    print(f"Downloaded and verified: {DATA_PATH}")


if __name__ == "__main__":
    main()
