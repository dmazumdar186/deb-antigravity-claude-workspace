"""
stats.py
description: Wilson score interval helper for the metro-sample qualify-rate confidence interval.
inputs: Imported by sample_audit.py; no CLI args (importable module).
outputs: Pure function — no filesystem or network side effects.
"""

from __future__ import annotations

import math


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Wilson score interval for k successes out of n trials.

    Returns (p_hat_pct, ci_low_pct, ci_high_pct) as percentages 0..100. n=0 returns (0.0, 0.0, 0.0).
    """
    if n <= 0:
        return 0.0, 0.0, 0.0

    p_hat = k / n
    denominator = 1 + z**2 / n
    center = p_hat + z**2 / (2 * n)
    margin = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n)

    low = (center - margin) / denominator
    high = (center + margin) / denominator
    low = max(0.0, low)
    high = min(1.0, high)

    return p_hat * 100, low * 100, high * 100
