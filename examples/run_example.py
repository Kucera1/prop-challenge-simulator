"""Example: synthetic trades -> average R with a block-bootstrap interval -> challenge pass rates.

Run from the repository root:
    python examples/run_example.py
    python examples/run_example.py --drift 0.0      # no edge before costs
"""
import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from propsim import ChallengeRules, block_bootstrap_mean_ci, evaluate, generate_trades, monthly_start_days, summarize  # noqa: E402

ORIGIN = "2000-01-01"           # synthetic calendar; only used to group trades and starts by month
RISK_LEVELS = (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02)
LINE_COLOR = "#2a78d6"
INK, MUTED_INK = "#0b0b0b", "#52514e"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", type=int, default=8, help="length of the synthetic history")
    p.add_argument("--signals-per-day", type=float, default=0.4)
    p.add_argument("--drift", type=float, default=0.03, help="edge knob: daily drift of a trade in R")
    p.add_argument("--cost-pct", type=float, default=0.001, help="round-trip cost as a fraction of price")
    p.add_argument("--max-open", type=int, default=3, help="limit of simultaneous positions")
    p.add_argument("--repeats", type=int, default=10, help="random replays of each monthly start")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "output" / "example.png")
    return p.parse_args()


def main():
    args = parse_args()
    n_days = 365 * args.years
    rules = ChallengeRules()
    trades = generate_trades(n_days, signals_per_day=args.signals_per_day, drift=args.drift,
                             cost_pct=args.cost_pct, seed=args.seed)

    calendar = pd.date_range(ORIGIN, periods=n_days, freq="D")
    exit_month = calendar[[t.exit_day for t in trades]].strftime("%Y-%m")
    mean_r, low_r, high_r = block_bootstrap_mean_ci([t.r for t in trades], exit_month, seed=args.seed)
    print(f"Synthetic trades: {len(trades)}, average R after costs {mean_r:+.3f} "
          f"(90 % block-bootstrap interval by exit month {low_r:+.3f} .. {high_r:+.3f})")

    starts = monthly_start_days(n_days, rules, ORIGIN)
    print(f"Rules: {rules}")
    print(f"Monthly starts: {len(starts)}, random replays per start: {args.repeats}\n")
    print(f"{'risk/trade':>10} {'P(pass)':>8} {'median days':>12} {'daily loss':>11} {'max DD':>7} {'timeout':>8}")
    rows, results_by_risk = [], {}
    for risk in RISK_LEVELS:
        results = evaluate(trades, risk, rules, starts, args.repeats, args.seed, args.max_open)
        s = summarize(results)
        results_by_risk[risk] = results
        rows.append(s)
        print(f"{risk:>10.2%} {s['pass_rate']:>8.1%} {s['median_days_to_pass']:>12.0f} "
              f"{s['n_daily_loss']:>11} {s['n_max_drawdown']:>7} {s['n_timeout']:>8}")

    best = max(RISK_LEVELS, key=lambda r: rows[RISK_LEVELS.index(r)]["pass_rate"])
    plot(rows, results_by_risk[best], best, args.out)
    print(f"\nHighest pass rate at {best:.2%} risk per trade. Chart saved to {args.out}")


def plot(rows, best_results, best_risk, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"axes.edgecolor": MUTED_INK, "axes.labelcolor": INK, "xtick.color": MUTED_INK,
                         "ytick.color": MUTED_INK, "axes.spines.top": False, "axes.spines.right": False})
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2))

    left.plot([r * 100 for r in RISK_LEVELS], [s["pass_rate"] * 100 for s in rows],
              color=LINE_COLOR, linewidth=2, marker="o", markersize=7)
    left.set(title="Probability of passing both phases", xlabel="Risk per trade (% of initial capital)",
             ylabel="Pass rate (%)", ylim=(0, 100))
    left.grid(axis="y", color="#e4e3df", linewidth=0.8)

    days = best_results.loc[best_results["outcome"] == "pass", "days"]
    right.hist(days, bins=20, color=LINE_COLOR, edgecolor="white", linewidth=1)
    if len(days):
        right.axvline(days.median(), color=INK, linewidth=1, linestyle="--")
        right.annotate(f"median {days.median():.0f} days", (days.median(), right.get_ylim()[1] * 0.92),
                       xytext=(6, 0), textcoords="offset points", color=INK, fontsize=9)
    right.set(title=f"Days to pass at {best_risk:.2%} risk (passed runs only)", xlabel="Calendar days",
              ylabel="Runs")
    right.grid(axis="y", color="#e4e3df", linewidth=0.8)

    fig.text(0.01, 0.01, "Synthetic data only. Not modelled: slippage, gaps through the stop, margin stop-out.",
             color=MUTED_INK, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
