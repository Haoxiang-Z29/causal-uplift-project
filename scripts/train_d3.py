#!/usr/bin/env python3
"""D3 response/S/T learner comparison on the fixed D2 validation split.

The CLI is deliberately gated.  Importing this module and running its synthetic
tests are safe, but the real Criteo fit requires the learner to confirm the D3
score contract first.  D3 never reads the test split; D4 owns that final gate.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache" / "matplotlib"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402


DATA_PATH = ROOT / "data" / "processed" / "criteo_modeling_data.csv.gz"
D2_AUDIT_PATH = ROOT / "artifacts" / "d2_audit_split.json"
ARTIFACT_DIR = ROOT / "artifacts" / "d3"
RESULTS_PATH = ARTIFACT_DIR / "validation_results.csv"
PREDICTIONS_PATH = ARTIFACT_DIR / "validation_predictions.csv.gz"
CURVES_PATH = ARTIFACT_DIR / "validation_gain_curves.csv.gz"
CURVE_PLOT_PATH = ARTIFACT_DIR / "validation_gain_curves.png"
RUN_RECORD_PATH = ARTIFACT_DIR / "run_record.json"

FEATURES = tuple(f"f{i}" for i in range(12))
TREATMENT = "treatment"
OUTCOME = "conversion"
SPLIT = "split"
TRAIN = "train"
VALIDATION = "validation"
FORBIDDEN_D3_SPLIT = "test"
CONFIRMATION = "treated-response_s-learner_t-learner_logit_v1"
MODEL_SEED = 20260805
TOP_FRACTION = 0.10
CHUNK_SIZE = 250_000
DEBUG_OVERSAMPLE_FACTOR = 1.5


@dataclass(frozen=True)
class SplitData:
    x: np.ndarray
    treatment: np.ndarray
    outcome: np.ndarray

    @property
    def n_rows(self) -> int:
        return int(self.x.shape[0])


@dataclass
class LearnerBundle:
    scaler: StandardScaler
    treated_outcome_model: LogisticRegression
    control_outcome_model: LogisticRegression
    s_model: LogisticRegression


@dataclass(frozen=True)
class Predictions:
    response_score: np.ndarray
    s_mu1: np.ndarray
    s_mu0: np.ndarray
    s_uplift: np.ndarray
    t_mu1: np.ndarray
    t_mu0: np.ndarray
    t_uplift: np.ndarray


def _positive_probability(model: LogisticRegression, x: np.ndarray) -> np.ndarray:
    """Return P(Y=1), locating the positive column from model.classes_."""
    positive_columns = np.flatnonzero(model.classes_ == 1)
    if positive_columns.size != 1:
        raise ValueError(f"model classes must contain exactly one positive class: {model.classes_}")
    return model.predict_proba(x)[:, int(positive_columns[0])]


def _validate_split(data: SplitData, name: str) -> None:
    if data.x.ndim != 2 or data.x.shape[1] != len(FEATURES):
        raise ValueError(f"{name}: expected X shape (n, {len(FEATURES)}), got {data.x.shape}")
    if data.n_rows != len(data.treatment) or data.n_rows != len(data.outcome):
        raise ValueError(f"{name}: X/T/Y lengths differ")
    if data.n_rows == 0:
        raise ValueError(f"{name}: split is empty")
    if not np.isfinite(data.x).all():
        raise ValueError(f"{name}: X contains missing or non-finite values")
    if not np.isin(data.treatment, (0, 1)).all():
        raise ValueError(f"{name}: treatment must be binary")
    if not np.isin(data.outcome, (0, 1)).all():
        raise ValueError(f"{name}: outcome must be binary")


def _splitmix64(values: np.ndarray, *, salt: int) -> np.ndarray:
    """Return deterministic outcome-blind priorities for debug sampling."""
    x = np.asarray(values, dtype=np.uint64) + np.uint64(MODEL_SEED + salt)
    x = (x ^ (x >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    x = (x ^ (x >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return x ^ (x >> np.uint64(31))


def _d2_split_row_counts() -> dict[str, int]:
    """Read the verified D2 modeling-row counts used to size debug samples."""
    if not D2_AUDIT_PATH.exists():
        raise FileNotFoundError(f"missing D2 audit artifact: {D2_AUDIT_PATH}")
    audit = json.loads(D2_AUDIT_PATH.read_text(encoding="utf-8"))
    cell_counts = audit["sample_split_arm_outcome_counts"]
    return {
        split_name: sum(
            count
            for key, count in cell_counts.items()
            if key.startswith(f"{split_name}_")
        )
        for split_name in (TRAIN, VALIDATION)
    }


def load_train_validation(
    source: Path = DATA_PATH,
    *,
    chunk_size: int = CHUNK_SIZE,
    max_train_rows: int | None = None,
    max_validation_rows: int | None = None,
    expected_split_rows: dict[str, int] | None = None,
) -> tuple[SplitData, SplitData]:
    """Load only D2 train/validation rows with bounded CSV read memory.

    Row caps exist only for smoke/debug runs.  A final D3 evidence run must use
    both caps as None and records that fact in run_record.json.
    """
    if not source.exists():
        raise FileNotFoundError(f"missing D2 modeling data: {source}")

    usecols = [*FEATURES, TREATMENT, OUTCOME, SPLIT]
    dtypes = {feature: "float32" for feature in FEATURES}
    dtypes.update({TREATMENT: "int8", OUTCOME: "int8", SPLIT: "string"})
    pieces: dict[str, list[pd.DataFrame]] = {TRAIN: [], VALIDATION: []}
    limits = {TRAIN: max_train_rows, VALIDATION: max_validation_rows}
    if any(limit is not None for limit in limits.values()):
        expected_split_rows = expected_split_rows or _d2_split_row_counts()
        for split_name, limit in limits.items():
            if limit is not None and not 0 < limit <= expected_split_rows[split_name]:
                raise ValueError(
                    f"{split_name}: debug row cap must be within verified split size"
                )

    for chunk in pd.read_csv(
        source,
        usecols=usecols,
        dtype=dtypes,
        chunksize=chunk_size,
        compression="gzip",
    ):
        if (chunk[SPLIT] == FORBIDDEN_D3_SPLIT).any():
            # Seeing the label while streaming is harmless; appending or using
            # any test row in D3 is forbidden.
            pass
        row_numbers = chunk.index.to_numpy(dtype=np.uint64, copy=False)
        for salt, split_name in enumerate((TRAIN, VALIDATION), start=1):
            limit = limits[split_name]
            split_mask = (chunk[SPLIT] == split_name).to_numpy()
            if limit is None:
                selected = chunk.loc[split_mask, usecols]
            else:
                priorities = _splitmix64(row_numbers, salt=salt)
                expected_candidates = min(
                    expected_split_rows[split_name],
                    int(np.ceil(limit * DEBUG_OVERSAMPLE_FACTOR)),
                )
                keep_fraction = expected_candidates / expected_split_rows[split_name]
                threshold = np.uint64(
                    keep_fraction * np.iinfo(np.uint64).max
                )
                keep = split_mask & (priorities <= threshold)
                selected = chunk.loc[keep, usecols].copy()
                selected["_debug_hash"] = priorities[keep]
            if not selected.empty:
                pieces[split_name].append(selected)

    def combine(split_name: str) -> SplitData:
        if not pieces[split_name]:
            raise ValueError(f"no rows loaded for {split_name}")
        frame = pd.concat(pieces[split_name], ignore_index=True)
        limit = limits[split_name]
        if limit is not None:
            if len(frame) < limit:
                raise ValueError(
                    f"{split_name}: deterministic debug candidates {len(frame)} "
                    f"below requested {limit}"
                )
            frame = frame.nsmallest(limit, "_debug_hash").drop(columns="_debug_hash")
        data = SplitData(
            x=frame.loc[:, list(FEATURES)].to_numpy(dtype=np.float32, copy=True),
            treatment=frame[TREATMENT].to_numpy(dtype=np.int8, copy=True),
            outcome=frame[OUTCOME].to_numpy(dtype=np.int8, copy=True),
        )
        _validate_split(data, split_name)
        return data

    return combine(TRAIN), combine(VALIDATION)


def s_learner_design(x_scaled: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    """Create [X, T, T*X] so one model can express heterogeneous uplift."""
    treatment_column = np.asarray(treatment, dtype=x_scaled.dtype).reshape(-1, 1)   # treatment转化为列向量 数据类型和x_scaled一致
    if x_scaled.ndim != 2 or len(x_scaled) != len(treatment_column):
        raise ValueError("S-learner X/T shapes differ")
    return np.concatenate(
        [x_scaled, treatment_column, x_scaled * treatment_column], axis=1
    )


def _new_logistic_model() -> LogisticRegression:
    return LogisticRegression(
        C=1.0,
        solver="lbfgs",
        max_iter=300,
        tol=1e-4,
        random_state=MODEL_SEED,
    )


def fit_learners(train: SplitData) -> LearnerBundle:
    """Fit the treated response model, control model, and one S-learner.

    The treated response model is intentionally reused as T-Learner mu1.  This
    makes the conceptual comparison exact: response ranks by mu1, while the
    T-Learner ranks by mu1-mu0.
    """
    _validate_split(train, TRAIN)
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(train.x)
    treated = train.treatment == 1
    control = ~treated
    if not treated.any() or not control.any():
        raise ValueError("training data must contain both treatment arms")

    treated_model = _new_logistic_model().fit(
        x_scaled[treated], train.outcome[treated] # 输入实验组的 X, Y
    )
    control_model = _new_logistic_model().fit(
        x_scaled[control], train.outcome[control] # 输入对照组的 X, Y
    )
    s_model = _new_logistic_model().fit(
        s_learner_design(x_scaled, train.treatment), train.outcome  # 输入全部训练集的 [X, T, T*X], Y
    )
    return LearnerBundle(
        scaler=scaler,
        treated_outcome_model=treated_model,
        control_outcome_model=control_model,
        s_model=s_model,
    )


def predict_counterfactuals(
    models: LearnerBundle, x: np.ndarray
) -> Predictions:
    """Predict both potential-outcome means and subtract mu1-mu0."""
    x_scaled = models.scaler.transform(x)
    n_rows = len(x_scaled)

    # Response baseline: predicted conversion probability if treated.
    response_score = _positive_probability(models.treated_outcome_model, x_scaled)

    # T-Learner: two separately fitted arm models, evaluated for every user.
    t_mu1 = response_score.copy()
    t_mu0 = _positive_probability(models.control_outcome_model, x_scaled)
    t_uplift = t_mu1 - t_mu0

    # S-Learner: the same fitted model receives two counterfactual copies.
    s_mu1 = _positive_probability(
        models.s_model, s_learner_design(x_scaled, np.ones(n_rows, dtype=np.int8))
    )   # 算 μ1：把 T 全设为 1，构造 [X,1,X×1]=[X,1,X]，送入 s_model。
    s_mu0 = _positive_probability(
        models.s_model, s_learner_design(x_scaled, np.zeros(n_rows, dtype=np.int8))
    )   # 算 μ0：把 T 全设为 0，构造 [X,0,X×0]=[X,0,X]，送入 s_model。
    s_uplift = s_mu1 - s_mu0

    predictions = Predictions(
        response_score=response_score,
        s_mu1=s_mu1,
        s_mu0=s_mu0,
        s_uplift=s_uplift,
        t_mu1=t_mu1,
        t_mu0=t_mu0,
        t_uplift=t_uplift,
    )
    validate_predictions(predictions, n_rows)
    return predictions


def validate_predictions(predictions: Predictions, n_rows: int) -> None:
    for name, values in predictions.__dict__.items():
        if values.shape != (n_rows,):
            raise ValueError(f"{name}: expected shape {(n_rows,)}, got {values.shape}")
        if not np.isfinite(values).all():
            raise ValueError(f"{name}: contains non-finite values")
    for name in ("response_score", "s_mu1", "s_mu0", "t_mu1", "t_mu0"):
        values = getattr(predictions, name)
        if ((values < 0.0) | (values > 1.0)).any():
            raise ValueError(f"{name}: probability outside [0,1]")
    if not np.allclose(predictions.s_uplift, predictions.s_mu1 - predictions.s_mu0):
        raise ValueError("S-learner uplift is not mu1-mu0")
    if not np.allclose(predictions.t_uplift, predictions.t_mu1 - predictions.t_mu0):
        raise ValueError("T-learner uplift is not mu1-mu0")


def gain_and_qini(
    treatment: np.ndarray,
    outcome: np.ndarray,
    score: np.ndarray,
    *,
    propensity: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized D2 metric contract: sorted IPW gain, baseline, Qini curve."""
    if not (len(treatment) == len(outcome) == len(score)):
        raise ValueError("metric input lengths differ")
    if not 0.0 < propensity < 1.0:
        raise ValueError("propensity must be strictly between 0 and 1")
    order = np.argsort(-score, kind="stable")   # 降序排列分数
    ranked_t = treatment[order].astype(np.float64)  # 按照分数排序后的treatment
    ranked_y = outcome[order].astype(np.float64)  # 按照分数排序后的outcome

    # 计算IPW贡献
    contributions = ranked_t * ranked_y / propensity
    contributions -= (1.0 - ranked_t) * ranked_y / (1.0 - propensity)    

    # 生成曲线
    gain = np.concatenate(([0.0], np.cumsum(contributions, dtype=np.float64)))  # 累加 得到gain曲线
    baseline = np.linspace(0.0, gain[-1], num=len(gain), dtype=np.float64)  # 生成baseline 对角线
    return gain, baseline, order


def evaluate_ranking(
    name: str,
    score_semantics: str,
    score: np.ndarray,
    validation: SplitData,
    *,
    propensity: float,
    top_fraction: float = TOP_FRACTION,
) -> tuple[dict, np.ndarray, np.ndarray]:   

    gain, baseline, order = gain_and_qini(
        validation.treatment,
        validation.outcome,
        score,
        propensity=propensity,
    )
    qini_curve = gain - baseline
    qini = float(np.trapezoid(qini_curve, dx=1.0 / validation.n_rows))  # 积分 计算Qini曲线下的面积 即Qini系数

    k = max(1, int(validation.n_rows * top_fraction))   # 验证集总样本数2,096,612   乘 0.10 
    top_t = validation.treatment[order[:k]] # 前k个样本的treatment
    top_y = validation.outcome[order[:k]]   # 前k个样本的outcome

    treated_y = top_y[top_t == 1]   # 前k个样本 里面 实验组 的outcome
    control_y = top_y[top_t == 0]   # 前k个样本 里面 对照组 的outcome

    if len(treated_y) == 0 or len(control_y) == 0:
        raise ValueError(f"{name}: top-k prefix lacks one treatment arm")

    row = {
        "model": name,
        "score_semantics": score_semantics,
        "validation_rows": validation.n_rows,
        "propensity": propensity,
        "top_fraction": top_fraction,
        "selected_count": k,
        "top_treated_count": int(len(treated_y)),
        "top_control_count": int(len(control_y)),
        "top_treated_conversions": int(treated_y.sum()),
        "top_control_conversions": int(control_y.sum()),
        "qini_coefficient": qini,
        "top_raw_incremental_gain": float(gain[k]),
        "top_incremental_gain_per_selected": float(gain[k] / k),
        "top_observed_uplift": float(treated_y.mean() - control_y.mean()),
        "outcome_auc": float(roc_auc_score(validation.outcome, score)),
        "score_min": float(score.min()),
        "score_mean": float(score.mean()),
        "score_max": float(score.max()),
        "negative_score_fraction": float(np.mean(score < 0)), # 计算负分数占比 理论值恒等于0
    }
    return row, gain, baseline


def _downsample_curve(
    model_name: str, gain: np.ndarray, baseline: np.ndarray, max_points: int = 1001
) -> pd.DataFrame:
    indices = np.unique(np.linspace(0, len(gain) - 1, num=min(max_points, len(gain))).astype(int))
    return pd.DataFrame(
        {
            "model": model_name,
            "rank_count": indices,
            "rank_fraction": indices / (len(gain) - 1),
            "gain": gain[indices],
            "random_baseline": baseline[indices],
            "qini_curve": gain[indices] - baseline[indices],
        }
    )


def run_validation_comparison(
    train: SplitData,
    validation: SplitData,
    *,
    debug_caps: dict[str, int | None],
) -> dict:
    evidence_level = (
        "debug_only"
        if any(value is not None for value in debug_caps.values())
        else "full_validation"
    )
    models = fit_learners(train)
    predictions = predict_counterfactuals(models, validation.x)
    propensity = float(validation.treatment.mean())
    score_specs = (
        ("response", "mu1=P(Y=1|X,T=1); not an effect", predictions.response_score),
        ("s_learner", "mu1-mu0 from one outcome model", predictions.s_uplift),
        ("t_learner", "mu1-mu0 from separate arm models", predictions.t_uplift),
    )

    rows = []
    curve_frames = []
    for name, semantics, score in score_specs:
        row, gain, baseline = evaluate_ranking(
            name, semantics, score, validation, propensity=propensity
        )
        row["evidence_level"] = evidence_level
        rows.append(row)
        curve_frame = _downsample_curve(name, gain, baseline)
        curve_frame["evidence_level"] = evidence_level
        curve_frames.append(curve_frame)

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    results = pd.DataFrame(rows)
    results.to_csv(RESULTS_PATH, index=False)
    pd.DataFrame(
        {
            TREATMENT: validation.treatment,
            OUTCOME: validation.outcome,
            **predictions.__dict__,
        }
    ).to_csv(PREDICTIONS_PATH, index=False, compression="gzip")
    curves = pd.concat(curve_frames, ignore_index=True)
    curves.to_csv(CURVES_PATH, index=False, compression="gzip")

    fig, axis = plt.subplots(figsize=(8, 5))
    for model_name, frame in curves.groupby("model", sort=False):
        axis.plot(frame["rank_fraction"], frame["qini_curve"], label=model_name)
    axis.axhline(0.0, color="black", linewidth=0.8)
    axis.set(xlabel="ranked population fraction", ylabel="IPW gain minus random baseline")
    axis.legend()
    fig.tight_layout()
    fig.savefig(CURVE_PLOT_PATH, dpi=160)
    plt.close(fig)

    top_k = max(1, int(validation.n_rows * TOP_FRACTION))
    s_top = set(np.argsort(-predictions.s_uplift, kind="stable")[:top_k])
    t_top = set(np.argsort(-predictions.t_uplift, kind="stable")[:top_k])
    run_record = {
        "evidence_level": evidence_level,
        "contract": CONFIRMATION,
        "dataset": str(DATA_PATH.relative_to(ROOT)),
        "test_split_used": False,
        "train_rows": train.n_rows,
        "validation_rows": validation.n_rows,
        "debug_caps": debug_caps,
        "features": list(FEATURES),
        "treatment": TREATMENT,
        "outcome": OUTCOME,
        "propensity_source": "observed validation assignment ratio",
        "propensity": propensity,
        "model": {
            "class": "sklearn.linear_model.LogisticRegression",
            "base_learner_shared": True,
            "s_design": "[scaled X, T, T*scaled X]",
            "regularization_C": 1.0,
            "max_iter": 300,
            "seed": MODEL_SEED,
        },
        "versions": {
            "python": os.sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "ranking_diagnostics": {
            "s_t_score_pearson": float(np.corrcoef(predictions.s_uplift, predictions.t_uplift)[0, 1]),
            "s_t_top10_overlap_fraction": len(s_top & t_top) / top_k,
        },
        "artifacts": {
            "results": str(RESULTS_PATH.relative_to(ROOT)),
            "predictions": str(PREDICTIONS_PATH.relative_to(ROOT)),
            "curves": str(CURVES_PATH.relative_to(ROOT)),
            "curve_plot": str(CURVE_PLOT_PATH.relative_to(ROOT)),
        },
    }
    RUN_RECORD_PATH.write_text(json.dumps(run_record, indent=2) + "\n", encoding="utf-8")
    print(results.to_string(index=False))
    print(json.dumps(run_record, indent=2))
    return run_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-contract",
        help=f"required exact value: {CONFIRMATION}",
    )
    parser.add_argument("--max-train-rows", type=int)
    parser.add_argument("--max-validation-rows", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.confirm_contract != CONFIRMATION:
        raise SystemExit(
            "D3 causal score contract is not confirmed. Read docs/day3_packet.md, "
            f"answer checkpoint 1, then use --confirm-contract {CONFIRMATION}"
        )
    train, validation = load_train_validation(
        max_train_rows=args.max_train_rows,
        max_validation_rows=args.max_validation_rows,
    )
    run_validation_comparison(
        train,
        validation,
        debug_caps={
            "max_train_rows": args.max_train_rows,
            "max_validation_rows": args.max_validation_rows,
        },
    )


if __name__ == "__main__":
    main()
