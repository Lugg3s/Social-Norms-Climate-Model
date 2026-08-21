import numpy as np

from trajectory_classification import classify, count_extrema


def test_count_extrema_uses_only_tail():
    trajectory = np.array([0.0, 1.0, 0.0, 1.0, 0.2, 0.3, 0.4, 0.5])
    assert count_extrema(trajectory, tail_frac=0.5) == 0


def test_classify_strong_oscillation():
    trajectory = np.array([0.5, 0.6, 0.4, 0.6, 0.4, 0.6, 0.4, 0.6, 0.4])
    assert classify(trajectory, tail_frac=0.0) == "stark oszillierend"


def test_classify_damped_oscillation():
    trajectory = np.array([0.5, 0.6, 0.4, 0.55, 0.45, 0.5])
    assert classify(trajectory, tail_frac=0.0) == "gedaempft oszillierend"


def test_classify_collapse():
    assert classify(np.array([0.2, 0.1, 0.04]), tail_frac=0.0) == "Kollaps auf 0"


def test_classify_full_s_curve():
    assert classify(np.array([0.2, 0.6, 0.96]), tail_frac=0.0) == "volle S-Kurve auf 1"


def test_classify_intermediate_state():
    assert classify(np.array([0.2, 0.4, 0.7]), tail_frac=0.0) == "Zwischenzustand"
