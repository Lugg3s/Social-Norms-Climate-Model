"""Historical numerical/phase checks of four influential saved parameter sets.

No CLI arguments. Uses archived parameters/settings, writes only this review.
Run: python -m support.reviews.sample_size_2048.probe_influential_oscillations
"""
import json
import os
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from time import monotonic

import numpy as np
import pandas as pd

from analysis.simulation_metrics import compute_oscillation_metrics
from model.model_equations import simulate
from .diagnose_oscillation_uncertainty import ROOT, DEST


CASES = [("Descriptive,_injunctive,_dynamic2", 9480),
         ("Descriptive,_injunctive,_dynamic2", 9489),
         ("Descriptive,_injunctive,_dynamic2", 3524),
         ("Descriptive,_injunctive,_dynamic", 7583)]
VARIANTS = {"saved_settings": {},
            "dense_history": {"output_points_per_year": 200},
            "refined_coupling": {"coupling_interval": .025, "output_points_per_year": 200}}


def window(t, x, left, right):
    keep = (t > left) & (t < right)
    return np.r_[left, t[keep], right], np.r_[np.interp(left, t, x), x[keep], np.interp(right, t, x)]


def probe(job):
    folder, index, variant = job
    started = monotonic()
    source = ROOT / folder
    metadata = json.loads((source / "metadata.json").read_text(encoding="utf-8"))
    params = json.loads((source / "parameters.json").read_text(encoding="utf-8"))
    samples = pd.read_csv(source / "samples.csv", sep=";")
    saved = pd.read_csv(source / "simulation_outputs.csv", sep=";").iloc[index]
    params.update({name: float(samples.iloc[index][name]) for name in metadata["problem"]["names"]})
    settings = {**metadata["simulation_settings"], "simulation_time": 620, **VARIANTS[variant]}
    name = folder + f"_{index}_{variant}"
    archive = DEST / (name + ".npz")
    cached = archive.exists()
    if cached:
        with np.load(archive, allow_pickle=False) as data:
            context = json.loads(str(data["metadata_json"].item()))
            if context != {"parameters": params, "settings": settings}:
                raise ValueError(f"Saved probe has different inputs/settings: {archive}")
            t, x, temperature = data["t"].copy(), data["x"].copy(), data["T"].copy()
    else:
        result = simulate(extension=params, **settings, verbose=False)
        t, x = np.asarray(result["simulation"].t), np.asarray(result["simulation"].x)
        temperature = np.asarray(result["simulation"].T)
    tt, xx = window(t, x, 0, 600)
    metrics = compute_oscillation_metrics(tt, xx)
    post_t, post_x = window(t, x, 217, 600)
    filtered = compute_oscillation_metrics(post_t, post_x, filter_minor_reversals=True)
    record = dict(folder=folder, sample_index=index, variant=variant,
                  coupling_interval=settings["coupling_interval"], output_points_per_year=settings["output_points_per_year"],
                  saved_cycles=saved.n_oscillations, cycles=metrics["n_oscillations"],
                  saved_filtered_cycles=saved.classification_complete_cycles,
                  filtered_post_cycles=filtered["n_oscillations"],
                  median_period=metrics["median_period"], saved_median_period=saved.median_period,
                  final_x=float(xx[-1]), saved_final_x=float(saved.final_x),
                  end100_range=float(np.ptp(x[(t >= 500) & (t <= 600)])),
                  elapsed_seconds=monotonic() - started, reused_probe_archive=cached)
    record = {key: value.item() if isinstance(value, np.generic) else value for key, value in record.items()}
    DEST.mkdir(exist_ok=True)
    if not cached:
        np.savez_compressed(archive, t=t, x=x, T=temperature,
                            metadata_json=np.asarray(json.dumps({"parameters": params, "settings": settings})))
    (DEST / (name + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
    phase = []
    period = metrics["median_period"]
    if np.isfinite(period):
        for shift in np.linspace(0, min(period, 10), 21):
            wt, wx = window(t, x, 500 + shift, 600 + shift)
            detected = compute_oscillation_metrics(wt, wx)
            full_t, full_x = window(t, x, 0, 600 + shift)
            full = compute_oscillation_metrics(full_t, full_x)
            phase.append(dict(folder=folder, sample_index=index, variant=variant, shift=shift,
                              cycles_in_100_years=detected["n_oscillations"],
                              full_history_cycles=full["n_oscillations"], end_x=float(wx[-1]),
                              full_history_rate=full["n_oscillations"] * 500 / (600 + shift),
                              median_period=detected["median_period"],
                              start=500 + shift, end=600 + shift))
    # Exact same numerical trajectory, sampled on progressively coarser grids.
    observation = []
    for spacing in (.05, .1, .25, .5):
        times = np.arange(0, 600 + spacing / 2, spacing)
        value = compute_oscillation_metrics(times, np.interp(times, t, x))
        observation.append(dict(folder=folder, sample_index=index, variant=variant,
                                grid_spacing=spacing, cycles=value["n_oscillations"]))
    return record, phase, observation


def main():
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    records, phases, observations = [], [], []
    with ProcessPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(probe, (folder, index, variant)): (folder, index, variant)
                for folder, index in CASES for variant in VARIANTS}
        for future in as_completed(jobs):
            record, phase, observation = future.result()
            records.append(record)
            phases.extend(phase)
            observations.extend(observation)
            pd.DataFrame(records).to_csv(DEST / "numerical_probes.csv", sep=";", index=False)
            pd.DataFrame(phases).to_csv(DEST / "phase_windows.csv", sep=";", index=False)
            pd.DataFrame(observations).to_csv(DEST / "observation_grid.csv", sep=";", index=False)
            print(record, flush=True)
    plot_phase_windows(pd.DataFrame(phases))


def plot_phase_windows(frame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    subset = frame[(frame.sample_index == 9480) & (frame.variant == "saved_settings")].sort_values("shift")
    axes[0].plot(subset["shift"], subset.end_x * 100, marker=".")
    axes[0].set_ylabel("x at the window end (%)")
    axes[1].plot(subset["shift"], subset.cycles_in_100_years, marker=".")
    axes[1].set_ylabel("Complete cycles (100 years)")
    axes[1].set_xlabel("Window shift (years)")
    axes[1].set_ylim(24, 28)
    fig.suptitle("End phase changes x, while the cycle count remains 26\n"
                 "Descriptive, injunctive, dynamic2 | sample 9480 | saved settings")
    fig.tight_layout()
    fig.savefig(DEST / "phase_check.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
