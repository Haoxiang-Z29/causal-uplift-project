import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from inspect_criteo_d1 import EXPECTED_COLUMNS, FEATURES, inspect  # noqa: E402


class InspectCriteoD1Test(unittest.TestCase):
    def write_fixture(self, rows):
        temporary = tempfile.NamedTemporaryFile(suffix=".csv.gz", delete=False)
        temporary.close()
        path = Path(temporary.name)
        with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(EXPECTED_COLUMNS)
            writer.writerows(rows)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    @staticmethod
    def row(treatment, conversion, visit, exposure):
        return ["0.5"] * 12 + [treatment, conversion, visit, exposure]

    def test_contract_and_aggregates(self):
        path = self.write_fixture(
            [
                self.row("1", "1", "1", "1"),
                self.row("1", "0", "1", "0"),
                self.row("0", "0", "0", "0"),
                self.row("0", "1", "1", "0"),
            ]
        )
        result = inspect(path, verify_hash=False, expected_rows=4)
        self.assertEqual(result["shape"], [4, 16])
        self.assertEqual(result["by_treatment"]["1"]["n"], 2)
        self.assertEqual(result["observed_assignment_effect"]["conversion"], 0.0)
        self.assertEqual(result["observed_assignment_effect"]["visit"], 0.5)
        self.assertEqual(result["locked_contract"]["pre_treatment_covariates"], FEATURES)
        self.assertEqual(result["overall"],
            {
                "treatment_ratio": 0.5,
                "conversion_rate": 0.5,
                "visit_rate": 0.75,
            },
        )
        self.assertNotIn(
            "exposure", result["locked_contract"]["pre_treatment_covariates"]
        )

    def test_rejects_nonbinary_label(self):
        path = self.write_fixture(
            [self.row("1", "2", "1", "1"), self.row("0", "0", "0", "0")]
        )
        with self.assertRaisesRegex(ValueError, "conversion must be binary"):
            inspect(path, verify_hash=False, expected_rows=2)


if __name__ == "__main__":
    unittest.main()
