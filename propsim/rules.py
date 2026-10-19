"""Configurable rules of a two-phase prop-firm challenge.

All amounts are fractions of the initial account size (0.10 = 10 %).
The defaults mirror a common industry template; none of them are hard-coded
anywhere else, so any firm's rules can be expressed by changing this object.
"""
from dataclasses import dataclass

# Limit based on the initial capital: breach when equity <= midnight balance - limit * initial.
DAILY_BASE_INITIAL = "initial"
# Limit based on the midnight balance itself: breach when equity <= midnight balance * (1 - limit).
DAILY_BASE_MIDNIGHT = "midnight_balance"


@dataclass(frozen=True)
class ChallengeRules:
    phase_targets: tuple[float, ...] = (0.10, 0.05)
    daily_loss_limit: float = 0.05
    daily_loss_base: str = DAILY_BASE_INITIAL
    max_drawdown: float = 0.10          # static: measured from the initial balance, never trails
    min_trading_days: int = 4           # days with at least one new entry, counted per phase
    max_days_per_phase: int = 365       # calendar days; unresolved phase = "timeout" (counts as not passed)

    def __post_init__(self):
        if self.daily_loss_base not in (DAILY_BASE_INITIAL, DAILY_BASE_MIDNIGHT):
            raise ValueError(f"unknown daily_loss_base: {self.daily_loss_base!r}")
        if not self.phase_targets:
            raise ValueError("at least one phase target is required")
