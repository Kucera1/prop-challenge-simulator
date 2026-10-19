"""Conversion of trading costs into R (multiples of the initial risk).

A cost quoted as a fraction of price is NOT the same number in R: if the stop is
2 % away from the entry, a 0.1 % round-trip cost eats 0.1 / 2 = 0.05 R.
Subtracting the price-percentage directly from R understates the cost by the
factor 1 / stop_pct, which is a classic backtest error.
"""
import numpy as np


def cost_in_r(cost_pct, stop_pct):
    """Round-trip cost expressed in R. Both arguments are fractions of the entry price."""
    stop_pct = np.asarray(stop_pct, dtype=float)
    if np.any(stop_pct <= 0):
        raise ValueError("stop distance must be positive")
    return np.asarray(cost_pct, dtype=float) / stop_pct


def net_r(gross_r, cost_pct, stop_pct):
    """Result of a trade in R after subtracting the round-trip cost."""
    return np.asarray(gross_r, dtype=float) - cost_in_r(cost_pct, stop_pct)
