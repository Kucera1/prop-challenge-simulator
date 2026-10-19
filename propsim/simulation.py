"""Day-by-day portfolio simulation and evaluation of challenge rules.

Position sizing: every trade risks a fixed fraction of the INITIAL capital, so the
equity in R units maps linearly to account equity: equity = 1 + risk * R.
Every phase starts from a flat account (no positions carried over).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .rules import DAILY_BASE_INITIAL
from .trades import group_by_entry_day

EPS = 1e-12     # tolerance for comparisons on exact rule boundaries (e.g. exactly -5 %)

PASS, DAILY, DRAWDOWN, TIMEOUT = "pass", "daily_loss", "max_drawdown", "timeout"


@dataclass
class DailyPath:
    """Account path of one simulated phase, in R units relative to the phase start."""
    close_r: np.ndarray     # equity at each day's close (closed results + open profit)
    low_r: np.ndarray       # equity at each day's worst point
    balance_r: np.ndarray   # closed results only, after the day's exits (= the midnight balance)
    entries: np.ndarray     # number of new positions opened each day
    accepted: list          # trades actually taken


def simulate(candidates_by_day, risk, start, n_days, rng, max_open=3):
    """Simulates days start..start+n_days-1 starting with a flat account.

    When more candidates arrive than free slots (max_open), the order is random:
    this models that, in real time, it is not known which signal will be the better one.
    A position occupies its slot including its exit day.
    """
    steps = np.zeros(n_days)          # realized R booked on the exit day
    open_close = np.zeros(n_days)     # open profit at close of positions not exiting that day
    alive_low = np.zeros(n_days)      # sum of worst open profit of positions alive that day
    entries = np.zeros(n_days, dtype=int)
    open_exits, accepted = [], []
    for day in range(start, start + n_days):
        open_exits = [x for x in open_exits if x >= day]
        candidates = candidates_by_day.get(day, [])
        for i in rng.permutation(len(candidates)):
            if len(open_exits) >= max_open:
                break
            trade = candidates[i]
            open_exits.append(trade.exit_day)
            accepted.append(trade)
            e, x = day - start, trade.exit_day - start
            last = min(x, n_days - 1)
            entries[e] += 1
            alive_low[e:last + 1] += trade.low_r[:last - e + 1]
            if x < n_days:
                steps[x] += trade.r
                open_close[e:x] += trade.close_r[:-1]
            else:
                open_close[e:] += trade.close_r[:n_days - e]
    balance = np.cumsum(steps)
    balance_midnight = np.concatenate([[0.0], balance[:-1]])
    return DailyPath(close_r=balance + open_close, low_r=balance_midnight + alive_low,
                     balance_r=balance, entries=entries, accepted=accepted)


def run_phase(path, risk, rules, target):
    """Returns (outcome, day_index) for one phase; day_index is 0-based within the phase.

    The daily limit compares each day's worst equity with the balance at the previous
    midnight (closed trades only), so open profit that evaporates is not a daily loss.
    If a breach and the target fall on the same day, the breach wins: with daily data
    it is unknown which came first, so the conservative assumption is taken.
    """
    eq_close = 1.0 + risk * path.close_r
    eq_low = 1.0 + risk * path.low_r
    balance_midnight = np.concatenate([[1.0], 1.0 + risk * path.balance_r[:-1]])
    if rules.daily_loss_base == DAILY_BASE_INITIAL:
        daily = eq_low <= balance_midnight - rules.daily_loss_limit + EPS
    else:
        daily = eq_low <= balance_midnight * (1.0 - rules.daily_loss_limit) + EPS
    drawdown = eq_low <= 1.0 - rules.max_drawdown + EPS
    trading_days = np.cumsum(path.entries > 0)
    passed = (eq_close >= 1.0 + target - EPS) & (trading_days >= rules.min_trading_days)
    breach = daily | drawdown
    i_breach = int(np.argmax(breach)) if breach.any() else None
    i_pass = int(np.argmax(passed)) if passed.any() else None
    if i_breach is not None and (i_pass is None or i_breach <= i_pass):
        return (DAILY if daily[i_breach] else DRAWDOWN), i_breach
    if i_pass is not None:
        return PASS, i_pass
    return TIMEOUT, len(eq_close) - 1


def run_challenge(candidates_by_day, risk, rules, start, rng, max_open=3):
    """Runs all phases from `start`. Returns (outcome, failed_phase or None, calendar days used)."""
    day = start
    for phase, target in enumerate(rules.phase_targets, start=1):
        path = simulate(candidates_by_day, risk, day, rules.max_days_per_phase, rng, max_open)
        outcome, i = run_phase(path, risk, rules, target)
        day += i + 1
        if outcome != PASS:
            return outcome, phase, day - start
    return PASS, None, day - start


def monthly_start_days(n_days, rules, origin="2000-01-01"):
    """Day indices of the first day of each month that leave room for every phase to finish."""
    calendar = pd.date_range(origin, periods=n_days, freq="D")
    firsts = pd.date_range(calendar[0], calendar[-1], freq="MS")
    need = rules.max_days_per_phase * len(rules.phase_targets)
    return [int(calendar.get_loc(d)) for d in firsts if calendar.get_loc(d) + need <= n_days]


def evaluate(trades, risk, rules, start_days, n_repeats=20, seed=0, max_open=3):
    """Rolling-start evaluation: every start is replayed n_repeats times with a different
    random choice among simultaneous signals. Returns a DataFrame with one row per run."""
    candidates = group_by_entry_day(trades)
    rng = np.random.default_rng(seed)
    rows = []
    for start in start_days:
        for repeat in range(n_repeats):
            outcome, phase, days = run_challenge(candidates, risk, rules, start, rng, max_open)
            rows.append(dict(start=start, repeat=repeat, outcome=outcome, failed_phase=phase, days=days))
    return pd.DataFrame(rows)


def summarize(results):
    """Pass probability, median days to pass and the breakdown of failures."""
    passed = results["outcome"] == PASS
    counts = results["outcome"].value_counts()
    return dict(runs=len(results), pass_rate=float(passed.mean()),
                median_days_to_pass=float(results.loc[passed, "days"].median()) if passed.any() else float("nan"),
                **{f"n_{k}": int(counts.get(k, 0)) for k in (PASS, DAILY, DRAWDOWN, TIMEOUT)})
