import numpy as np
import pytest

from propsim import ChallengeRules, block_bootstrap_mean_ci, cost_in_r, generate_trades, monthly_start_days, net_r


def test_cost_is_scaled_by_stop_distance():
    # 0.2 % of price with a stop 10 % away is 0.02 R, not 0.002 R
    assert cost_in_r(0.002, 0.10) == pytest.approx(0.02)
    assert net_r(1.0, 0.002, 0.10) == pytest.approx(0.98)
    assert np.allclose(net_r([1.0, -1.0], 0.001, [0.01, 0.05]), [0.9, -1.02])
    with pytest.raises(ValueError):
        cost_in_r(0.001, 0.0)


def test_bootstrap_constant_values_give_zero_width():
    mean, lower, upper = block_bootstrap_mean_ci(np.full(50, 0.3), np.arange(50) // 5)
    assert mean == pytest.approx(0.3) and lower == pytest.approx(0.3) and upper == pytest.approx(0.3)


def test_bootstrap_is_reproducible_and_contains_the_mean():
    rng = np.random.default_rng(1)
    values, blocks = rng.normal(0.1, 1.0, 400), np.repeat(np.arange(40), 10)
    first = block_bootstrap_mean_ci(values, blocks, seed=7)
    assert first == block_bootstrap_mean_ci(values, blocks, seed=7)
    assert first[1] < first[0] < first[2]


def test_block_bootstrap_is_wider_than_iid_when_blocks_are_correlated():
    rng = np.random.default_rng(2)
    block_effect = np.repeat(rng.normal(0.0, 1.0, 30), 10)          # trades in one month move together
    values = block_effect + rng.normal(0.0, 0.2, 300)
    _, lo_block, hi_block = block_bootstrap_mean_ci(values, np.repeat(np.arange(30), 10))
    _, lo_iid, hi_iid = block_bootstrap_mean_ci(values, np.arange(300))
    assert hi_block - lo_block > 2 * (hi_iid - lo_iid)


def test_generator_is_reproducible_and_stays_inside_the_data():
    a = generate_trades(500, seed=3)
    b = generate_trades(500, seed=3)
    assert [(t.entry_day, t.exit_day, t.r) for t in a] == [(t.entry_day, t.exit_day, t.r) for t in b]
    assert all(t.exit_day < 500 for t in a)
    assert all(t.r >= -1.0 - 0.001 / 0.02 - 1e-12 for t in a)       # never worse than the stop plus the max cost


def test_generator_costs_shift_each_trade_by_cost_over_stop():
    gross = generate_trades(500, cost_pct=0.0, seed=4)
    net = generate_trades(500, cost_pct=0.001, seed=4)
    diff = np.array([g.r - n.r for g, n in zip(gross, net)])
    assert len(gross) == len(net)
    assert np.all((diff >= 0.001 / 0.06 - 1e-12) & (diff <= 0.001 / 0.02 + 1e-12))


def test_generator_edge_knob_moves_average_r():
    weak = np.mean([t.r for t in generate_trades(4000, drift=-0.05, seed=5)])
    strong = np.mean([t.r for t in generate_trades(4000, drift=0.10, seed=5)])
    assert strong > weak + 0.2


def test_monthly_starts_leave_room_for_all_phases():
    starts = monthly_start_days(1000, ChallengeRules(max_days_per_phase=100), origin="2000-01-01")
    assert starts[:3] == [0, 31, 60]                                 # 2000 is a leap year
    assert all(s + 200 <= 1000 for s in starts) and starts[-1] + 200 + 31 > 1000
