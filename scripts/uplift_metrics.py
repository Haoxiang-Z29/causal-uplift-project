#!/usr/bin/env python3
"""Transparent randomized-trial uplift metrics used by the D2 sanity case.

The main curve is an inverse-propensity-weighted (IPW) cumulative gain curve:

    G(k) = sum_{i<=k} [T_i Y_i / p - (1-T_i) Y_i / (1-p)]

Rows must already be sorted from highest to lowest model score.  With constant
random assignment probability p, G(k) estimates cumulative incremental outcomes
among the first k ranked rows.  This module deliberately avoids an uplift
library so its normalization and sign can be checked against a hand calculation.
"""

from __future__ import annotations

from typing import Sequence


def _validate_binary(name: str, values: Sequence[int]) -> None:
    invalid = sorted(set(values) - {0, 1})
    if invalid:
        raise ValueError(f"{name} must be binary 0/1; got {invalid}")


def cumulative_ipw_gain(
    treatment: Sequence[int],
    outcome: Sequence[int],
    *,
    propensity: float,
) -> list[float]:
    """Return G(0)..G(n) for rows in descending-score order."""
    if len(treatment) != len(outcome):
        raise ValueError("treatment and outcome lengths differ")
    if not 0.0 < propensity < 1.0:
        raise ValueError("propensity must be strictly between 0 and 1")
    _validate_binary("treatment", treatment)
    _validate_binary("outcome", outcome)

    gain = [0.0]
    running = 0.0
    for t_i, y_i in zip(treatment, outcome):
        if t_i == 1:
            running += y_i / propensity
        else:
            running -= y_i / (1.0 - propensity)
        gain.append(running)
    return gain


def random_baseline(gain: Sequence[float]) -> list[float]:
    """Straight line from (0, 0) to the observed end-point G(n)."""
    if not gain:
        raise ValueError("gain cannot be empty")
    n = len(gain) - 1
    if n == 0:
        return [gain[0]]
    return [gain[-1] * index / n for index in range(n + 1)]


def trapezoid_area(values: Sequence[float], *, normalize_x: bool = True) -> float:
    """Area under equally spaced points; x is [0,1] when normalized."""
    if len(values) < 2:
        raise ValueError("at least two curve points are required")
    width = 1.0 / (len(values) - 1) if normalize_x else 1.0
    return width * sum(
        (left + right) / 2.0 for left, right in zip(values, values[1:])
    )


def qini_coefficient(gain: Sequence[float]) -> float:
    """Area between the IPW gain curve and its random-order baseline."""
    baseline = random_baseline(gain)
    return trapezoid_area([g - b for g, b in zip(gain, baseline)])


def uplift_at_k(
    treatment: Sequence[int], outcome: Sequence[int], *, k: int
) -> float:
    """Observed treated-minus-control outcome rate in the first k rows.

    This descriptive top-k estimator requires both arms inside the prefix.
    It is intentionally not silently smoothed when one arm is absent.
    """
    if not 1 <= k <= len(treatment) or len(treatment) != len(outcome):
        raise ValueError("k must be within equally-sized inputs")
    _validate_binary("treatment", treatment)
    _validate_binary("outcome", outcome)
    treated = [y for t, y in zip(treatment[:k], outcome[:k]) if t == 1]
    control = [y for t, y in zip(treatment[:k], outcome[:k]) if t == 0]
    if not treated or not control:
        raise ValueError("top-k prefix must contain both treatment arms")
    return sum(treated) / len(treated) - sum(control) / len(control)

def incremental_policy_value_at_k(
    gain: Sequence[float],
    *,
    k: int,
) -> dict:
    """Summarize top-k incremental value relative to treating nobody."""
    eligible_count = len(gain) - 1
    if not 1 <= k <= eligible_count:
        raise ValueError("k must be within the range of eligible rows")

    return {
        "selected_count": k,
        "eligible_count": eligible_count,
        "raw_incremental_gain": gain[k],
        "incremental_gain_per_selected": gain[k] / k,
        "incremental_gain_per_eligible": gain[k] / eligible_count,
    }
    
