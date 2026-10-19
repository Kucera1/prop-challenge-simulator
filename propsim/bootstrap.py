"""Block bootstrap confidence interval for the average R per trade.

Trades closed in the same period (e.g. the same month) share market conditions, so
they are not independent. Resampling whole blocks instead of single trades keeps
that dependence and gives a wider, more honest interval than the naive one.
"""
import numpy as np


def block_bootstrap_mean_ci(values, block_labels, n_boot=5000, ci=0.90, seed=0):
    """Returns (mean, lower, upper) for the mean of `values`.

    block_labels assigns each value to a block (e.g. 'YYYY-MM' of the exit date).
    Each bootstrap sample draws as many blocks as there are, with replacement, and
    pools all their values.
    """
    values = np.asarray(values, dtype=float)
    block_labels = np.asarray(block_labels)
    if len(values) != len(block_labels):
        raise ValueError("values and block_labels must have the same length")
    if len(values) == 0:
        raise ValueError("no values")
    blocks = [values[block_labels == b] for b in np.unique(block_labels)]
    sums = np.array([b.sum() for b in blocks])
    sizes = np.array([len(b) for b in blocks])
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(blocks), size=(n_boot, len(blocks)))
    means = sums[picks].sum(axis=1) / sizes[picks].sum(axis=1)
    tail = (1.0 - ci) / 2.0 * 100.0
    lower, upper = np.percentile(means, [tail, 100.0 - tail])
    return float(values.mean()), float(lower), float(upper)
