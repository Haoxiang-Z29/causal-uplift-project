import csv
import gzip
import math
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_split_d2 as module  # noqa: E402
from audit_split_d2 import (  # noqa: E402
    CONTROL_ARM,
    EVALUATION_SPLITS,
    MIN_EVAL_CONTROL_CONVERSIONS,
    NEGATIVE_OUTCOME,
    POSITIVE_OUTCOME,
    RunningStats,
    TEST_SPLIT,
    TRAIN_SPLIT,
    TREATED_ARM,
    VALIDATION_SPLIT,
    control_conversion_count_name,
    rare_cell_check,
    split_for_row,
    standardized_mean_difference,
)
from inspect_criteo_d1 import EXPECTED_COLUMNS, FEATURES  # noqa: E402

class AuditSplitD2Test(unittest.TestCase):
    def test_split_is_deterministic_and_uses_valid_names(self):
        probe_row_count = 100
        first = [split_for_row(index) for index in range(probe_row_count)]
        second = [split_for_row(index) for index in range(probe_row_count)]
        self.assertEqual(first, second)
        self.assertEqual(set(first), {TRAIN_SPLIT, VALIDATION_SPLIT, TEST_SPLIT})

    def test_smd_matches_hand_case(self):
        treated, control = RunningStats(), RunningStats()
        for value in (2.0, 4.0):
            treated.add(value)
        for value in (1.0, 3.0):
            control.add(value)
        # Means differ by 1; both sample variances are 2, so pooled SD=sqrt(2).
        self.assertAlmostEqual(
            standardized_mean_difference(treated, control), 1.0 / math.sqrt(2.0)
        )

    def test_tiny_audit_records_nonidentifiable_duplicates(self):
        temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(temp_dir))
        source = temp_dir / "tiny.csv.gz"
        target = temp_dir / "sample.csv.gz"
        rows = [
            [str(index + offset) for index in range(len(FEATURES))]
            + [arm, outcome, NEGATIVE_OUTCOME, NEGATIVE_OUTCOME]
            for offset, (arm, outcome) in enumerate(
                [
                    (CONTROL_ARM, NEGATIVE_OUTCOME),
                    (CONTROL_ARM, POSITIVE_OUTCOME),
                    (TREATED_ARM, NEGATIVE_OUTCOME),
                    (TREATED_ARM, POSITIVE_OUTCOME),
                ]
            )
        ]
        with gzip.open(source, "wt", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(EXPECTED_COLUMNS)
            writer.writerows(rows)

        old_cutoff = module.TRAIN_KEEP_BUCKET_CUTOFF
        module.TRAIN_KEEP_BUCKET_CUTOFF = module.HASH_BUCKET_COUNT
        try:
            result = module.audit_and_split(
                source, output_sample=target, expected_rows=len(rows)
            )
        finally:
            module.TRAIN_KEEP_BUCKET_CUTOFF = old_cutoff
        self.assertEqual(result["full_rows"], 4)
        self.assertEqual(result["modeling_data_rows"], 4)
        self.assertEqual(result["duplicate_unit_check"]["status"], "not_identifiable")
        self.assertTrue(target.exists())

    def test_validation_and_test_are_never_subsampled(self):
        probe_row_count = 100
        for index in range(probe_row_count):
            for split in EVALUATION_SPLITS:
                self.assertTrue(module.selected_for_modeling(index, split))

    def test_rare_cell_check_warns_below_threshold(self):
        minimum = MIN_EVAL_CONTROL_CONVERSIONS
        counts = {
            control_conversion_count_name(VALIDATION_SPLIT): minimum - 1,
            control_conversion_count_name(TEST_SPLIT): minimum + 1,
        }

        result = rare_cell_check(counts, minimum=minimum)

        self.assertEqual(result["threshold"], minimum)
        self.assertEqual(result["counts"], counts)
        self.assertEqual(result["status"], "warning")
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn(VALIDATION_SPLIT, result["warnings"][0])


    def test_rare_cell_check_passes_at_threshold(self):
        minimum = MIN_EVAL_CONTROL_CONVERSIONS
        counts = {
            control_conversion_count_name(VALIDATION_SPLIT): minimum,
            control_conversion_count_name(TEST_SPLIT): minimum + 1,
        }

        result = rare_cell_check(counts, minimum=minimum)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
