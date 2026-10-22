import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from train_d3 import (  # noqa: E402
    SplitData,
    fit_learners,
    gain_and_qini,
    load_train_validation,
    predict_counterfactuals,
    s_learner_design,
    evaluate_ranking,
)
from uplift_metrics import cumulative_ipw_gain, qini_coefficient, random_baseline  # noqa: E402


class TrainD3Test(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(20260805)
        n = 800
        x = rng.normal(size=(n, 12)).astype(np.float32)
        treatment = rng.binomial(1, 0.6, size=n).astype(np.int8)
        logits = -1.5 + 0.3 * x[:, 0] + treatment * (0.6 + 0.5 * x[:, 1])
        probability = 1.0 / (1.0 + np.exp(-logits))
        outcome = rng.binomial(1, probability).astype(np.int8)
        self.data = SplitData(x=x, treatment=treatment, outcome=outcome)

    def test_s_design_encodes_counterfactual_copies(self):
        x = np.array([[1.0, 2.0], [3.0, 4.0]])
        treated = s_learner_design(x, np.array([1, 1]))
        control = s_learner_design(x, np.array([0, 0]))
        np.testing.assert_array_equal(treated[:, :2], x)
        np.testing.assert_array_equal(treated[:, 2], [1.0, 1.0])
        np.testing.assert_array_equal(treated[:, 3:], x)
        np.testing.assert_array_equal(control[:, 2:], 0.0)

    def test_counterfactual_predictions_have_expected_contract(self):
        models = fit_learners(self.data)
        predictions = predict_counterfactuals(models, self.data.x[:25])
        for values in predictions.__dict__.values():
            self.assertEqual(values.shape, (25,))
            self.assertTrue(np.isfinite(values).all())
        np.testing.assert_allclose(
            predictions.s_uplift, predictions.s_mu1 - predictions.s_mu0
        )
        np.testing.assert_allclose(
            predictions.t_uplift, predictions.t_mu1 - predictions.t_mu0
        )
        np.testing.assert_allclose(predictions.response_score, predictions.t_mu1)

    def test_vectorized_metric_matches_d2_transparent_case(self):
        treatment = np.array([1, 0, 1, 0, 1, 0, 1, 0], dtype=np.int8)
        outcome = np.array([1, 0, 1, 0, 0, 1, 0, 1], dtype=np.int8)
        score = np.arange(8, 0, -1, dtype=float)
        gain, baseline, order = gain_and_qini(
            treatment, outcome, score, propensity=0.5
        )
        expected_gain = cumulative_ipw_gain(treatment, outcome, propensity=0.5)
        np.testing.assert_array_equal(order, np.arange(8))
        np.testing.assert_allclose(gain, expected_gain)
        np.testing.assert_allclose(baseline, random_baseline(expected_gain))
        qini = np.trapezoid(gain - baseline, dx=1.0 / len(treatment))
        self.assertAlmostEqual(qini, qini_coefficient(expected_gain))

    def test_loader_returns_only_train_and_validation(self):
        columns = [*(f"f{i}" for i in range(12)), "treatment", "conversion", "split"]
        rows = [
            [*range(12), 1, 1, "train"],
            [*range(12), 0, 0, "validation"],
            [*range(12), 1, 1, "test"],
        ]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tiny.csv.gz"
            with gzip.open(source, "wt", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerows(rows)
            train, validation = load_train_validation(source, chunk_size=2)
        self.assertEqual(train.n_rows, 1)
        self.assertEqual(validation.n_rows, 1)
        self.assertEqual(train.treatment.tolist(), [1])
        self.assertEqual(validation.treatment.tolist(), [0])

    def test_debug_caps_are_hash_sampled_not_source_heads(self):
        columns = [*(f"f{i}" for i in range(12)), "treatment", "conversion", "split"]
        rows = []
        for split_name in ("train", "validation"):
            rows.extend(
                [[*range(12), 1, index % 2, split_name] for index in range(200)]
            )
        for split_name in ("train", "validation"):
            rows.extend(
                [[*range(12), 0, index % 2, split_name] for index in range(200)]
            )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "arm_blocked.csv.gz"
            with gzip.open(source, "wt", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                writer.writerows(rows)
            train, validation = load_train_validation(
                source,
                chunk_size=100,
                max_train_rows=80,
                max_validation_rows=80,
                expected_split_rows={"train": 400, "validation": 400},
            )
        self.assertEqual(train.n_rows, 80)
        self.assertEqual(validation.n_rows, 80)
        self.assertEqual(set(train.treatment), {0, 1})
        self.assertEqual(set(validation.treatment), {0, 1})

    def test_evaluate_ranking_metrics_and_negative_fraction(self):
        """测试 evaluate_ranking 的各项输出契约、Top-K 截取及负分比例的精确数学期望。"""
        # 1. 构造一个精确可控的小样本验证集 (n = 10)
        n = 10
        x_dummy = np.zeros((n, 2), dtype=np.float32)
        
        # 构造 score，其中包含正好 3 个负数 (-0.5, -1.0, -0.2)，负分比例期望为 3/10 = 0.3
        score = np.array([1.5, 0.8, -0.5, -1.0, 0.5, 0.2, -0.2, 0.1, 0.3, 0.4], dtype=np.float32)
        
        # 构造 treatment 和 outcome，并确保按照 -score 排序后的前 k 名（例如 top_fraction=0.4 时 k=4）
        # 同时包含 treated (1) 和 control (0)，避免触发 ValueError
        treatment = np.array([1, 1, 0, 0, 1, 0, 1, 0, 1, 0], dtype=np.int8)
        outcome = np.array([1, 0, 1, 0, 1, 1, 0, 0, 1, 0], dtype=np.int8)
        
        val_split = SplitData(x=x_dummy, treatment=treatment, outcome=outcome)
        propensity = 0.6
        top_fraction = 0.4  # k = max(1, int(10 * 0.4)) = 4
        
        # 2. 执行被测函数 evaluate_ranking
        row, gain, baseline = evaluate_ranking(
            name="mock_uplift_model",
            score_semantics="uplift",
            score=score,
            validation=val_split,
            propensity=propensity,
            top_fraction=top_fraction
        )
        
        # 3. 对负分比例进行精确断言
        self.assertIn("negative_score_fraction", row)
        self.assertAlmostEqual(row["negative_score_fraction"], 0.3, places=7)
        
        # 4. 对 evaluate_ranking 返回的字典契约进行严格断言
        self.assertEqual(row["model"], "mock_uplift_model")
        self.assertEqual(row["validation_rows"], n)
        self.assertEqual(row["selected_count"], 4)
        self.assertEqual(row["top_treated_count"] + row["top_control_count"], 4)
        self.assertEqual(len(gain), n + 1)     # gain 包含原点 0.0，长度应为 n_rows + 1
        self.assertEqual(len(baseline), n + 1)


if __name__ == "__main__":
    unittest.main()
