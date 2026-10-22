import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from inspect_d1 import EXPECTED_COLUMNS, inspect  # noqa: E402


class InspectD1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = inspect()

    def test_shape_and_schema(self):
        self.assertEqual(self.result["shape"], [64_000, len(EXPECTED_COLUMNS)])

    def test_all_randomized_arms_exist(self):
        self.assertEqual(
            set(self.result["arms"]),
            {"No E-Mail", "Mens E-Mail", "Womens E-Mail"},
        )

    def test_locked_binary_problem(self):
        contract = self.result["locked_binary_contract"]
        self.assertGreater(contract["n"], 40_000)
        self.assertEqual(contract["primary_outcome"], "conversion")


if __name__ == "__main__":
    unittest.main()

