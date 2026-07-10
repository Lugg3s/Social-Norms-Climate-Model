# Interesting plots for evaluation might be: 
# Rate of social learning (kappa) against net cost of mitigation (Beta) (from the paper)
# Mitigators


import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from model_equations import *

plt.rcParams.update({
    "font.size": 16,
    "axes.titlesize": 16,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
})


_RUN_OUTPUT_DIR = None


def _get_run_output_dir():
    global _RUN_OUTPUT_DIR
    if _RUN_OUTPUT_DIR is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _RUN_OUTPUT_DIR = Path("plots") / timestamp
        _RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _RUN_OUTPUT_DIR



def plot_emissions(scenarios=None):
    pass


def plot_temperature(scenarios=None, results=None):
    """Plot temperature and mitigation trajectories.

    If `results` is provided, it must map scenario names to simulation results
    and no simulations are run inside this function.
    """
    fig, (ax, ax_x) = plt.subplots(1, 2, figsize=(14, 6), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.82, bottom=0.12, top=0.95, wspace=0.25)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
    ax.set_ylim(top=5)
    ax.set_xlim(1900, 2200)

    ax_x.set_xlabel("Time (year)", fontsize=16)
    ax_x.set_ylabel("X", fontsize=16)
    ax_x.set_xlim(1900, 2200)
    ax_x.set_ylim(0, 1)

    if results is None:
        model_equations = load_scenarios()
        if scenarios:
            model_equations = {k: v for k, v in model_equations.items() if k in scenarios}
        results = {}
        for scenario_name in model_equations:
            print(f"Simulating scenario: {scenario_name}")
            results[scenario_name] = simulate(scenario_name)
    elif scenarios:
        results = {name: result for name, result in results.items() if name in scenarios}

    for scenario_name, result in results.items():
        ax.plot(result.t + 1800, result.T, label=scenario_name)
        ax_x.plot(result.t + 1800, result.x, label=scenario_name)

    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    output_dir = _get_run_output_dir()
    plt.savefig(output_dir / "all_scenarios.png", dpi=300)
    plt.show()


def plot_temperature_sensitivity(parameter_name, parameter_values, scenarios=None, save_prefix="temperature_sensitivity"):
    """Plot temperature and mitigation trajectories for one parameter sweep.

    A separate figure is created for each scenario. Each figure keeps the same
    axes and inset layout as `plot_temperature()` and overlays the trajectories
    produced by the different parameter values.
    """
    scenarios_dict = load_scenarios()
    if scenarios:
        scenarios_dict = {k: v for k, v in scenarios_dict.items() if k in scenarios}

    for scenario_name, scenario_params in scenarios_dict.items():
        fig, (ax, ax_x) = plt.subplots(1, 2, figsize=(14, 6), sharex=True)
        fig.subplots_adjust(left=0.08, right=0.82, bottom=0.12, top=0.95, wspace=0.25)
        ax.set_xlabel("Time (year)", fontsize=16)
        ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
        ax.set_ylim(top=5)
        ax.set_xlim(1900, 2200)

        ax_x.set_xlabel("Time (year)", fontsize=16)
        ax_x.set_ylabel("X", fontsize=16)
        ax_x.set_xlim(1900, 2200)
        ax_x.set_ylim(0, 1)

        for parameter_value in parameter_values:
            run_params = {**scenario_params, parameter_name: parameter_value}
            print(f"Simulating {scenario_name} with {parameter_name}={parameter_value}")
            result = simulate(run_params)
            label = f"{parameter_name}={parameter_value}"
            ax.plot(result.t + 1800, result.T, label=label)
            ax_x.plot(result.t + 1800, result.x, label=label)

        ax.set_title(f"{scenario_name}: sensitivity over {parameter_name}")
        handles, labels = ax.get_legend_handles_labels()
        fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
        output_dir = _get_run_output_dir()
        fig.savefig(output_dir / f"{save_prefix}_{scenario_name.replace(' ', '_').replace('/', '_')}.png", dpi=300)
        plt.show()


def plot_contour(x_values, y_values, z_values, x_label, y_label, title, colorbar_label, contour_color="k"):
    """Render a pcolormesh of `z_values` over `x_values` and `y_values`,
    add contour lines and a colorbar with labels."""
    x_mesh, y_mesh = np.meshgrid(x_values, y_values)
    plt.figure(figsize=(8, 6))
    plt.pcolormesh(x_mesh, y_mesh, z_values, shading="auto")
    plt.colorbar(label=colorbar_label)
    contour = plt.contour(x_mesh, y_mesh, z_values, colors=contour_color, linewidths=0.5)
    plt.clabel(contour, inline=True, fontsize=8)
    plt.xlabel(x_label, fontsize=16)
    plt.ylabel(y_label, fontsize=16)
    plt.title(title, fontsize=12)
    plt.show()
