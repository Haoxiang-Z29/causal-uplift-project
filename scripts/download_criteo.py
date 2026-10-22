#!/usr/bin/env python3
"""Download the official Criteo Uplift unbiased v2.1 archive safely."""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "criteo-uplift-v2.1.csv.gz"
SOURCE_URL = (
    "https://criteostorage.blob.core.windows.net/"
    "criteo-research-datasets/criteo-uplift-v2.1.csv.gz"
)
EXPECTED_SHA256 = "2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DATA_PATH.exists() and sha256(DATA_PATH) == EXPECTED_SHA256:
        print(f"Dataset already present and verified: {DATA_PATH}")
        return

    with tempfile.NamedTemporaryFile(
        dir=DATA_PATH.parent, prefix="criteo-v2.1-", suffix=".csv.gz", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        try:
            with urllib.request.urlopen(SOURCE_URL, timeout=120) as response:
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
