"""Hand-computed cases for the portfolio simulation and the challenge rules.

Prices in the helper are chosen so that every expected R value can be checked on paper:
entry 100 and stop distance 10 means a low of 95 is -0.5 R, a close of 89.5 is -1.05 R, etc.
"""
import numpy as np
import pytest

from propsim import ChallengeRules, Trade, evaluate, group_by_entry_day, run_challenge, run_phase, simulate, summarize
from propsim.rules import DAILY_BASE_MIDNIGHT
from propsim.simulation import DAILY, DRAWDOWN, PASS, TIMEOUT, DailyPath

N_DAYS = 40
NO_MIN_DAYS = ChallengeRules(min_trading_days=0, max_days_per_phase=N_DAYS)


def trade(day, entry, stop_distance, rows, r, stopped):
    """rows = [(low, close), ...] for consecutive days starting at `day`."""
    lows, closes = zip(*rows)
    return Trade.from_prices(day, entry, stop_distance, lows, closes, r, stopped)


def run(trades, max_open=3, n_days=N_DAYS):
    return simulate(group_by_entry_day(trades), 0.01, 0, n_days, np.random.default_rng(0), max_open)


def test_single_stopped_trade():
    path = run([trade(3, 100.0, 10.0, [(95.0, 96.0), (89.0, 89.5)], -1.0, stopped=True)])
    assert path.low_r[3] == pytest.approx(-0.5)          # entry day low 95
    assert path.close_r[3] == pytest.approx(-0.4)        # entry day close 96
    assert path.low_r[4] == pytest.approx(-1.0)          # stopped at 90; the low of 89 came after the exit
    assert path.balance_r[4] == pytest.approx(-1.0)


def test_cap_limits_simultaneous_positions():
    same_day = [trade(3, 100.0, 10.0, [(95.0, 96.0), (89.0, 89.5)], -1.0, stopped=True) for _ in range(4)]
    path = run(same_day)
    assert len(path.accepted) == 3
    assert 0.01 * path.low_r[4] == pytest.approx(-0.03)  # three stops on the same day at 1 % risk


def test_slot_is_busy_on_exit_day():
    first = trade(10, 100.0, 10.0, [(99.0, 99.0)] * 3, 0.1, stopped=False)       # days 10..12
    on_exit_day = trade(12, 100.0, 10.0, [(99.0, 99.0)] * 2, 0.1, stopped=False)
    day_after = trade(13, 100.0, 10.0, [(99.0, 99.0)] * 2, 0.1, stopped=False)
    path = run([first, on_exit_day, day_after], max_open=1)
    assert sorted(t.entry_day for t in path.accepted) == [10, 13]


def test_random_choice_among_simultaneous_signals_varies():
    candidates = [trade(0, 100.0, 10.0, [(99.0, 99.0)], float(i), stopped=False) for i in range(10)]
    chosen = {run(candidates, max_open=1).accepted[0].r}
    by_day = group_by_entry_day(candidates)
    for seed in range(1, 30):
        chosen.add(simulate(by_day, 0.01, 0, 5, np.random.default_rng(seed), 1).accepted[0].r)
    assert len(chosen) > 1


def test_evaporating_open_profit_is_not_a_daily_loss():
    # +9 R open profit at the first close, then the trade is stopped next day at -1 R
    t = trade(3, 100.0, 1.0, [(99.5, 109.0), (99.71, 100.5), (98.9, 99.0)], -1.0, stopped=True)
    path = run([t])
    assert path.close_r[3] == pytest.approx(9.0)
    assert path.low_r[4] == pytest.approx(-0.29)         # loss against the midnight balance, not against +9 R
    equity_based_drop = 0.01 * (path.low_r[4] - path.close_r[3])
    assert equity_based_drop == pytest.approx(-0.0929)   # what a close-to-low reading would (wrongly) call a 9.29 % day
    assert run_phase(path, 0.01, NO_MIN_DAYS, target=9.99)[0] == TIMEOUT


def test_gap_through_stop_is_filled_at_stop_known_limitation():
    # day 2 opens at 85, below the stop at 90: a real fill would be -1.5 R, the model books -1.0 R
    path = run([trade(3, 100.0, 10.0, [(99.0, 94.0), (84.0, 84.5)], -1.0, stopped=True)])
    assert path.low_r[4] == pytest.approx(-1.0)
    assert path.balance_r[4] == pytest.approx(-1.0)


def test_day_with_several_trades():
    a = trade(10, 100.0, 10.0, [(98.0, 105.0), (101.0, 104.0), (109.0, 119.0)], 2.0, stopped=False)
    b = trade(11, 50.0, 5.0, [(49.0, 49.5), (44.0, 44.5)], -1.0, stopped=True)
    c = trade(12, 20.0, 2.0, [(19.4, 19.8), (19.9, 21.0)], 0.5, stopped=False)
    path = run([a, b, c])
    assert len(path.accepted) == 3
    assert path.close_r[11] == pytest.approx(0.3) and path.low_r[11] == pytest.approx(-0.1)
    assert path.balance_r[12] == pytest.approx(1.0)     # A +2, B -1
    assert path.close_r[12] == pytest.approx(0.9)       # + C open at -0.1
    assert path.low_r[12] == pytest.approx(-0.4)        # A 0.9 + B -1.0 + C -0.3 against midnight balance 0
    assert path.balance_r[13] == pytest.approx(1.5)
    assert path.low_r[13] == pytest.approx(0.95)        # balance 1.0 + C worst point -0.05


def make_path(n=10, low=None, close=None, balance=None, entries=None):
    zeros = np.zeros(n)
    return DailyPath(close_r=zeros.copy() if close is None else np.asarray(close, float),
                     low_r=zeros.copy() if low is None else np.asarray(low, float),
                     balance_r=zeros.copy() if balance is None else np.asarray(balance, float),
                     entries=np.ones(n, int) if entries is None else np.asarray(entries, int), accepted=[])


def test_daily_limit_boundary():
    low = np.zeros(10)
    low[1] = -5.0                                        # exactly -5 % at 1 % risk
    assert run_phase(make_path(low=low), 0.01, NO_MIN_DAYS, 0.10) == (DAILY, 1)
    low[1] = -4.99
    assert run_phase(make_path(low=low), 0.01, NO_MIN_DAYS, 0.10)[0] == TIMEOUT


def test_static_drawdown_over_several_days():
    # -4 % per day: the daily limit is never hit, the static 10 % drawdown is hit on day 3
    loss = np.r_[0.0, -4.0, -8.0, -12.0, np.full(6, -12.0)]
    path = make_path(low=loss, close=loss, balance=loss)
    assert run_phase(path, 0.01, NO_MIN_DAYS, 0.10) == (DRAWDOWN, 3)


def test_daily_limit_base_initial_vs_midnight_balance():
    # midnight balance +20 %, worst point of next day -5.5 % of initial capital
    balance = np.r_[20.0, np.full(9, 20.0)]
    low = balance.copy()
    low[1] = 14.5
    path = make_path(low=low, close=balance, balance=balance)
    assert run_phase(path, 0.01, NO_MIN_DAYS, 9.99) == (DAILY, 1)        # 1.145 <= 1.20 - 0.05
    midnight = ChallengeRules(daily_loss_base=DAILY_BASE_MIDNIGHT, min_trading_days=0)
    assert run_phase(path, 0.01, midnight, 9.99)[0] == TIMEOUT          # 1.145 > 1.20 * 0.95


def test_breach_and_target_on_same_day_counts_as_breach():
    path = make_path(low=np.r_[0.0, -6.0, np.zeros(8)], close=np.r_[0.0, 12.0, np.zeros(8)])
    assert run_phase(path, 0.01, NO_MIN_DAYS, 0.10) == (DAILY, 1)


def test_minimum_trading_days_delays_the_pass():
    close = np.r_[0.0, np.full(9, 12.0)]
    entries = np.zeros(10, int)
    entries[[0, 5]] = 1
    path = make_path(close=close, low=np.zeros(10), entries=entries)
    assert run_phase(path, 0.01, ChallengeRules(min_trading_days=1), 0.10) == (PASS, 1)
    assert run_phase(path, 0.01, ChallengeRules(min_trading_days=2), 0.10) == (PASS, 5)


def steady_winners(n_days):
    """One one-day trade per day at +0.25 R (exactly representable, no float noise at the target)."""
    return [Trade(d, d, 0.25, np.array([0.25]), np.array([0.0])) for d in range(n_days)]


def test_two_phases_each_start_flat():
    rules = ChallengeRules(max_days_per_phase=100)
    candidates = group_by_entry_day(steady_winners(300))
    outcome, phase, days = run_challenge(candidates, 0.01, rules, 0, np.random.default_rng(0))
    assert (outcome, phase, days) == (PASS, None, 40 + 20)   # 0.25 %/day: 40 days to +10 %, 20 days to +5 %
    results = evaluate(steady_winners(300), 0.01, rules, start_days=[0, 31, 59], n_repeats=2)
    assert summarize(results)["pass_rate"] == 1.0 and summarize(results)["median_days_to_pass"] == 60


def test_no_trades_times_out():
    rules = ChallengeRules(max_days_per_phase=30)
    assert run_challenge({}, 0.01, rules, 0, np.random.default_rng(0)) == (TIMEOUT, 1, 30)


def test_trade_open_at_window_end_contributes_only_open_profit():
    t = trade(1, 100.0, 10.0, [(99.0, 105.0)] * 5, 0.5, stopped=False)        # days 1..5
    path = run([t], n_days=3)
    assert path.balance_r[-1] == 0.0
    assert path.close_r[-1] == pytest.approx(0.5)


def test_trade_rejects_inconsistent_paths():
    with pytest.raises(ValueError):
        Trade(0, 2, 1.0, np.zeros(2), np.zeros(3))
