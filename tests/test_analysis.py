import numpy as np
import pytest

from dequint.analyze import interval, paired_interval


def test_undefined_conditional_metrics_have_no_usable_pairs():
    assert paired_interval([np.nan] * 10, [np.nan] * 10) == (0, None, None, None)
    assert interval([]) == (None, None, None)


def test_metric_specific_finite_pair_counts():
    count, mean, low, high = paired_interval([1, 2, np.nan, 8], [0, 1, 3, np.nan])
    assert count == 2
    assert mean == low == high == pytest.approx(1)
