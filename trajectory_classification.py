from __future__ import annotations

import numpy as np


def count_extrema(traj, tail_frac=0.5):
    """Zaehlt lokale Extrema im letzten Teil der Trajektorie -> Oszillationsindikator."""
    tail = traj[int(len(traj) * tail_frac):]
    diffs = np.diff(tail)
    sign_changes = np.sum((diffs[:-1] * diffs[1:]) < 0)
    return sign_changes


def classify(traj, tail_frac=0.5):
    e = count_extrema(traj, tail_frac)
    final_x = traj[-1]
    if e >= 6:
        return "stark oszillierend"
    if e >= 2:
        return "gedaempft oszillierend"
    if final_x < 0.05:
        return "Kollaps auf 0"
    if final_x > 0.95:
        return "volle S-Kurve auf 1"
    return "Zwischenzustand"
