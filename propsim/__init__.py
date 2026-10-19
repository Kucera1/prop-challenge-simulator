"""Prop-firm challenge simulator: tests trading rules against challenge rules on synthetic data."""
from .bootstrap import block_bootstrap_mean_ci
from .costs import cost_in_r, net_r
from .rules import ChallengeRules
from .simulation import evaluate, monthly_start_days, run_challenge, run_phase, simulate, summarize
from .synthetic import generate_trades
from .trades import Trade, group_by_entry_day

__all__ = ["ChallengeRules", "Trade", "block_bootstrap_mean_ci", "cost_in_r", "evaluate", "generate_trades",
           "group_by_entry_day", "monthly_start_days", "net_r", "run_challenge", "run_phase", "simulate", "summarize"]
