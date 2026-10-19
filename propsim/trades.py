"""Trade representation used by the simulator.

A trade is described in R units (1 R = distance from entry to the initial stop),
day by day from the entry day to the exit day inclusive. Daily granularity means
the simulator sees each day's close and low, not the intraday order of events.
"""
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, eq=False)
class Trade:
    entry_day: int          # index of the entry day (the entry happens at that day's open)
    exit_day: int           # index of the exit day, >= entry_day
    r: float                # realized result in R, after costs
    close_r: np.ndarray     # open profit in R at each day's close, entry_day..exit_day
    low_r: np.ndarray       # worst open profit in R during each day; on the exit day the worst point
                            # before the position was closed (see from_prices)

    def __post_init__(self):
        n = self.exit_day - self.entry_day + 1
        if n < 1:
            raise ValueError("exit_day must not precede entry_day")
        if len(self.close_r) != n or len(self.low_r) != n:
            raise ValueError(f"close_r and low_r must have {n} values (one per day held)")

    @classmethod
    def from_prices(cls, entry_day, entry, stop_distance, lows, closes, r, stopped):
        """Builds a long trade from daily prices.

        lows/closes cover entry_day..exit_day. On the exit day the worst point is the
        realized result if the trade was stopped (anything below the stop happened after
        the exit), otherwise the lower of the day's low and the realized result.
        """
        lows = np.asarray(lows, dtype=float)
        closes = np.asarray(closes, dtype=float)
        low_r = (lows - entry) / stop_distance
        low_r[-1] = r if stopped else min(low_r[-1], r)
        return cls(entry_day, entry_day + len(closes) - 1, float(r), (closes - entry) / stop_distance, low_r)


def group_by_entry_day(trades):
    """Dictionary entry_day -> list of trades that are candidates on that day."""
    out = {}
    for t in trades:
        out.setdefault(t.entry_day, []).append(t)
    return out
