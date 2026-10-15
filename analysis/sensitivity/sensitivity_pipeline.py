"""Run the usual Sobol CLI, then regression trees on its saved results.

This separate entry point leaves sensitivity_analysis.py unchanged, so adding
postprocessing cannot change the code loaded by existing simulation workers.
All command-line arguments are the ordinary sensitivity-analysis arguments.
"""
from datetime import datetime
from pathlib import Path
from time import monotonic

import analysis.sensitivity.sensitivity_analysis as sensitivity
from analysis.regression_trees.regression_tree_analysis import TreeConfig, run_analysis


def pipeline_runner(sobol_runner):
    def run(scenario_names, run_root, config, overwrite_existing=True):
        result = sobol_runner(scenario_names, run_root, config,
                              overwrite_existing=overwrite_existing)
        started = monotonic()
        output_dir = Path(run_root) / "regression_trees" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        print(f"Starting regression trees from saved sensitivity results: {run_root}", flush=True)
        try:
            reports = run_analysis(Path(run_root), output_dir,
                                   config=TreeConfig(seed=config.seed))
        except Exception:
            print(f"Regression-tree postprocessing failed. Completed sensitivity results remain saved in {run_root}.", flush=True)
            raise
        fitted = sum(report["status"] == "fitted" for report in reports)
        print(f"Regression trees completed in {monotonic() - started:.1f} seconds: "
              f"{fitted}/{len(reports)} targets fitted. Results: {output_dir}", flush=True)
        return result
    return run


def main():
    original = sensitivity._run_scenarios
    # Scope the callback to this entry point; the source module and workers are
    # unchanged. The callback runs inside the existing console/log context.
    sensitivity._run_scenarios = pipeline_runner(original)
    try:
        sensitivity.main()
    finally:
        sensitivity._run_scenarios = original


if __name__ == "__main__":
    main()
