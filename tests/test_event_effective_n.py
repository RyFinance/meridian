import numpy as np
import pytest

from research.amendment4.event_effective_n import event_effective_n


def test_sparse_event_cap_and_overlap():
    rng = np.random.default_rng(11)
    x = rng.normal(size=160)
    groups = np.repeat(np.arange(20), 8)
    base = event_effective_n(x, groups, 2964.9)
    overlap = event_effective_n(x, groups, 2964.9, overlap_multiplicity=2)
    assert base["effective_n"] <= 160
    assert overlap["effective_n"] <= base["effective_n"]
    assert overlap["effective_n"] <= 80


def test_clustered_events_reduce_effective_n():
    rng = np.random.default_rng(12)
    x = np.repeat(rng.normal(size=20), 8) + 0.01 * rng.normal(size=160)
    result = event_effective_n(x, np.repeat(np.arange(20), 8), 2964.9)
    assert result["cluster_D"] > 4
    assert result["effective_n"] < 40


def test_invalid_cluster_structure_is_refused():
    with pytest.raises(ValueError):
        event_effective_n([.1, .2, .3], [0, 0, 0], 100)
