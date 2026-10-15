"""Small deterministic test fixture, not a socio-climate simulation."""
from pathlib import Path
import argparse
from datetime import datetime
import json

import numpy as np
import pandas as pd
from SALib.sample import sobol

from analysis.regression_trees.regression_tree_analysis import TARGETS, TreeConfig, run_analysis
from utils.paths import PLOTS_DIR


def write_demo(directory: Path, base_sample_size: int = 32) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    problem = {"num_vars": 2, "names": ["beta", "temperature_factor"],
               "bounds": [[0.0, 1.0], [0.0, 1.0]]}
    X = sobol.sample(problem, base_sample_size, calc_second_order=False, seed=42)
    samples = pd.DataFrame(X, columns=problem["names"])
    samples.insert(0, "sample_index", np.arange(len(samples)))
    beta, temperature_factor = X.T
    oscillating = temperature_factor >= 0.4
    damping = np.where(beta >= 0.6, 0.2, -0.2)
    damping[(beta >= 0.4) & (beta < 0.6)] = 0.0
    initial = np.where(oscillating, 0.25, np.nan)
    final = np.where(oscillating, initial * np.exp(-damping), np.nan)
    final_x = 0.2 + 0.6 * (temperature_factor >= 0.5) + 0.1 * (beta >= 0.5)
    x_mean = 0.15 + 0.5 * (temperature_factor >= 0.5) + 0.1 * (beta >= 0.5)
    reached = final_x >= 0.8
    outputs = pd.DataFrame({
        "sample_index": np.arange(len(samples)), "status": "completed",
        "final_x": final_x, "x_mean": x_mean,
        "final_temperature": 4.0 - 3.0 * final_x,
        "cumulative_emissions": 1000.0 * (1.0 - x_mean),
        "first_time_x95": np.where(reached, 260.0 + 60.0 * beta, 0.0),
        "bool_x95": reached, "oscillation_occurrence": oscillating,
        "oscillations_per_500_years": np.where(oscillating, 4 * 500.0 / 600.0, 0.0),
        "n_oscillations": np.where(oscillating, 4, 0),
        "median_period": np.where(oscillating, 12.0 + 20.0 * (beta >= 0.6), np.nan),
        "oscillation_amplitude": np.where(oscillating, 0.15 + 0.1 * (beta >= 0.5), 0.0),
        "amplitude_initial": initial, "amplitude_final": final,
        "damping_index": np.where(oscillating, damping, 0.0),
        "damping_rate": np.where(oscillating, damping / 100, np.nan),
        "n_prominent_half_cycles": np.where(oscillating, 8, 0),
    })
    metadata = {"scenario": "Deterministic tree demo", "problem": problem,
                "base_sample_size": base_sample_size, "simulation_time": 600,
                "outputs_for_ranking": [],
                "oscillations_per_500_years_definition": {
                    "minimum_complete_cycles": 2,
                    "method": "zero_below_minimum_otherwise_scaled_complete_cycle_count"},
                "data_kind": "Synthetic known-rule fixture; NOT an actual socio-climate simulation",
                "known_rules": {"final_x": "0.2 + 0.6*(temperature_factor >= 0.5) + 0.1*(beta >= 0.5)",
                                "median_period": "12 + 20*(beta >= 0.6), defined only if temperature_factor >= 0.4"}}
    samples.to_csv(directory / "samples.csv", sep=";", index=False)
    outputs.to_csv(directory / "simulation_outputs.csv", sep=";", index=False)
    (directory / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return directory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=PLOTS_DIR / "regression_tree_example")
    args = parser.parse_args()
    root = args.output_root / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    source = write_demo(root / "synthetic_input")
    run_analysis(source, root / "synthetic_results", TARGETS, config=TreeConfig())
    print(f"Saved deterministic demo: {root}")
