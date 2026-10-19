"""Synthetic trade generator - the only data source of this project.

Each trade follows a random walk measured in R: every day the close moves by
Normal(drift, volatility) and the day's low lies below both the previous and the
new close. The trade exits when
  * the low touches -1 R (stop; filled exactly at the stop, gaps are not modelled),
  * the close reaches target_r (take profit at the close), or
  * max_hold_days have passed (exit at the close).
`drift` is the edge knob: 0 means no edge before costs; costs then make it negative.
"""
import numpy as np

from .costs import cost_in_r
from .trades import Trade


def generate_trades(n_days, signals_per_day=0.4, drift=0.03, volatility=0.45, target_r=2.0,
                    max_hold_days=20, stop_pct_range=(0.02, 0.06), cost_pct=0.001, seed=0):
    """Returns a list of Trade objects that all exit before n_days. Same seed = same trades."""
    rng = np.random.default_rng(seed)
    trades = []
    for entry_day in range(n_days):
        for _ in range(rng.poisson(signals_per_day)):
            trade = _one_trade(rng, entry_day, drift, volatility, target_r, max_hold_days, stop_pct_range, cost_pct)
            if trade.exit_day < n_days:
                trades.append(trade)
    return trades


def _one_trade(rng, entry_day, drift, volatility, target_r, max_hold_days, stop_pct_range, cost_pct):
    cost_r = float(cost_in_r(cost_pct, rng.uniform(*stop_pct_range)))
    closes, lows = [], []
    previous = 0.0                       # entry at the open = 0 R
    for day in range(max_hold_days):
        close = previous + rng.normal(drift, volatility)
        low = min(previous, close) - abs(rng.normal(0.0, volatility / 2.0))
        closes.append(close)
        lows.append(low)
        if low <= -1.0:
            r = -1.0 - cost_r
            lows[-1] = r                 # the position is gone at the stop; a deeper low comes after the exit
            break
        if close >= target_r or day == max_hold_days - 1:
            r = close - cost_r
            lows[-1] = min(low, r)
            break
        previous = close
    return Trade(entry_day, entry_day + len(closes) - 1, r, np.array(closes), np.array(lows))
