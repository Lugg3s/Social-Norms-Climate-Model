"""Shared input and output locations, independent of the working directory."""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
PLOTS_DIR = PROJECT_ROOT / "plots"
RUNS_DIR = Path(r"E:\Masterarbeit\Runs")
SENSITIVITY_RESULTS_DIR = Path(r"E:\Masterarbeit\Sensitivity")
PROFILING_RESULTS_DIR = PROJECT_ROOT / "support" / "profiling_results"
