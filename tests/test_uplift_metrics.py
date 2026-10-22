import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from uplift_metrics import (  # noqa: E402
    cumulative_ipw_gain,
    qini_coefficient,
    random_baseline,
    uplift_at_k,
    incremental_policy_value_at_k,
)


class UpliftMetricsTest(unittest.TestCase):
    # Ranked hand case from docs/day2_packet.md.
    treatment = [1, 0, 1, 0, 1, 0, 1, 0]
    outcome = [1, 0, 1, 0, 0, 1, 0, 1]

    def test_incremental_policy_value_at_k_normal(self):
        gain = [0.0, 2.0, 2.0, 4.0, 4.0, 4.0, 2.0, 2.0, 0.0]
        result = incremental_policy_value_at_k(gain, k=2)
        expected = {
            "selected_count": 2,
            "eligible_count": 8,
            "raw_incremental_gain": 2.0,
            "incremental_gain_per_selected": 1.0,
            "incremental_gain_per_eligible": 0.25,
        }
        self.assertEqual(result, expected)

    def test_incremental_policy_value_at_k_boundary_zero(self):
        gain = [0.0, 2.0, 2.0, 4.0, 4.0, 4.0, 2.0, 2.0, 0.0]
        with self.assertRaises(ValueError):
            incremental_policy_value_at_k(gain, k=0)

    def test_hand_calculated_ipw_gain(self):
        gain = cumulative_ipw_gain(self.treatment, self.outcome, propensity=0.5)
        self.assertEqual(gain, [0.0, 2.0, 2.0, 4.0, 4.0, 4.0, 2.0, 2.0, 0.0])
        self.assertEqual(random_baseline(gain), [0.0] * 9)
        self.assertEqual(qini_coefficient(gain), 2.5)

    def test_top_quarter_uplift(self):
        self.assertEqual(uplift_at_k(self.treatment, self.outcome, k=2), 1.0)

    def test_reversed_ranking_has_negative_early_gain(self):
        gain = cumulative_ipw_gain(
            list(reversed(self.treatment)),
            list(reversed(self.outcome)),
            propensity=0.5,
        )
        self.assertLess(min(gain[1:4]), 0.0)

    def test_invalid_inputs_fail_loudly(self):
        with self.assertRaisesRegex(ValueError, "strictly between"):
            cumulative_ipw_gain([1], [1], propensity=1.0)
        with self.assertRaisesRegex(ValueError, "both treatment arms"):
            uplift_at_k([1, 1], [1, 0], k=2)

    def test_qini_ranking_sanity(self):
        treated = 1
        control = 0
        converted = 1
        balanced_propensity = 0.5

        treatment_rankings = {
            "perfect_ish": [treated, treated, control, control],
            "neutral": [treated, control, control, treated],
            "reversed": [control, control, treated, treated],
        }

        expected_gains = {
            "perfect_ish": [0.0, 2.0, 4.0, 2.0, 0.0],
            "neutral": [0.0, 2.0, 0.0, -2.0, 0.0],
            "reversed": [0.0, -2.0, -4.0, -2.0, 0.0],
        }

        expected_qini = {
            "perfect_ish": 2.0,
            "neutral": 0.0,
            "reversed": -2.0,
        }

        outcomes = [converted] * 4

        for ranking_name, treatment in treatment_rankings.items():
            gain = cumulative_ipw_gain(
                treatment,
                outcomes,
                propensity=balanced_propensity,
            )

            self.assertEqual(gain, expected_gains[ranking_name])
            self.assertEqual(
                qini_coefficient(gain),
                expected_qini[ranking_name],
            )


if __name__ == "__main__":
    unittest.main()

