"""Batch-runner entry point with trajectory-based phase classification.

The existing batch-runner implementation is kept in ``_batch_runner_impl.py``.
Only the phase-map classification is replaced here so that regimes are
classified directly from the tail of each saved x trajectory.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

import _batch_runner_impl as _impl
from _batch_runner_impl import *  # noqa: F401,F403
from trajectory_classification import classify, count_extrema


PHASE_ORDER = [
    "Kollaps auf 0",
    "volle S-Kurve auf 1",
    "Zwischenzustand",
    "gedaempft oszillierend",
    "stark oszillierend",
]

PHASE_COLORS = {
    "Kollaps auf 0": "#d62728",
    "volle S-Kurve auf 1": "#ff7f0e",
    "Zwischenzustand": "#2ca02c",
    "gedaempft oszillierend": "#1f77b4",
    "stark oszillierend": "#9467bd",
}


def _classify_saved_run(record: pd.Series, tail_frac: float = 0.5) -> str:
    run_dir = record.get("run_dir")
    if not isinstance(run_dir, str):
        return "Zwischenzustand"

    time_series_path = Path(run_dir) / "time_series.csv"
    if not time_series_path.exists():
        return "Zwischenzustand"

    frame = pd.read_csv(time_series_path, usecols=["x"])
    trajectory = pd.to_numeric(frame["x"], errors="coerce").dropna().to_numpy(dtype=float)
    if trajectory.size == 0:
        return "Zwischenzustand"

    return classify(trajectory, tail_frac=tail_frac)


def save_phase_map_for_two_parameters(
    summary_df: pd.DataFrame,
    group_dir: Path,
    x_param: str,
    y_param: str,
    tail_frac: float = 0.5,
) -> None:
    """Save a phase map using direct classification of each x trajectory."""
    required_columns = {"run_dir", x_param, y_param}
    if not required_columns.issubset(summary_df.columns):
        return

    phase_df = summary_df.copy()
    phase_df["phase"] = phase_df.apply(
        lambda row: _classify_saved_run(row, tail_frac=tail_frac),
        axis=1,
    )

    pivot = phase_df.pivot_table(
        index=y_param,
        columns=x_param,
        values="phase",
        aggfunc="first",
    ).sort_index(axis=0).sort_index(axis=1)

    if pivot.empty:
        return

    phase_to_idx = {label: idx for idx, label in enumerate(PHASE_ORDER)}
    phase_array = np.vectorize(
        lambda label: phase_to_idx.get(str(label), phase_to_idx["Zwischenzustand"])
    )(pivot.to_numpy())

    cmap = matplotlib.colors.ListedColormap([PHASE_COLORS[label] for label in PHASE_ORDER])
    fig, ax = _impl.plt.subplots(figsize=(10, 7))
    image = ax.imshow(
        phase_array,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=0,
        vmax=len(PHASE_ORDER) - 1,
    )

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(
        [_impl.format_value_for_slug(value) for value in pivot.columns],
        rotation=45,
        ha="right",
    )
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([_impl.format_value_for_slug(value) for value in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"Phase map over {x_param} and {y_param}")

    cbar = fig.colorbar(image, ax=ax, ticks=list(range(len(PHASE_ORDER))))
    cbar.ax.set_yticklabels(PHASE_ORDER)
    cbar.set_label("Phase regime")

    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_phase_map_{x_param}_vs_{y_param}.png", dpi=300)
    _impl.plt.close(fig)


# The existing comparison pipeline resolves this function from the implementation
# module at runtime, so replacing it here updates all existing batch workflows.
_impl.save_phase_map_for_two_parameters = save_phase_map_for_two_parameters


if __name__ == "__main__":
    _impl.main()
