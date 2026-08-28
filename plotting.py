import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from pathlib import Path
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from model_equations import *
import shutil
# from agent_model_equation_anara import *

plt.rcParams.update({
    "font.size": 16,
    "axes.titlesize": 16,
    "axes.labelsize": 16,
    "xtick.labelsize": 14,
    "ytick.labelsize": 14,
    "legend.fontsize": 14,
})


_RUN_OUTPUT_DIR = None
TIME_ZERO_YEAR = 1800


def _get_run_output_dir():
    global _RUN_OUTPUT_DIR
    if _RUN_OUTPUT_DIR is None:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _RUN_OUTPUT_DIR = Path("plots") / timestamp
        _RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return _RUN_OUTPUT_DIR


def _store_scenario_json():
    """
    Store the complete scenario.json file in the output directory for reproducibility.
    """
    output_dir = _get_run_output_dir()
    scenario_file = Path("scenarios.json")
    if scenario_file.exists():
        destination_file = Path(output_dir / "scenario.json")
        if not destination_file.exists():
            shutil.copy(scenario_file, destination_file)


def _is_dynamic_social_norm(scenario_params):
    return scenario_params.get("social_norm") == "dynamic social norm"


def plot_emissions(include_scenarios=None, exclude_scenarios=None):
    pass


""""def _collect_legend_handles_labels(*axes):
    handles = []
    labels = []
    seen = set()
    for axis in axes:
        axis_handles, axis_labels = axis.get_legend_handles_labels()
        for handle, label in zip(axis_handles, axis_labels):
            if label in seen:
                continue
            seen.add(label)
            handles.append(handle)
            labels.append(label)
    return handles, labels
"""

def plot_temperature(include_scenarios=None, exclude_scenarios=None, results=None, show_x_auxiliary=False, simulation_time=400, simulate_only_x=False, fig_name=None):
    """Plot temperature and mitigation trajectories.
    If `results` is provided, it must map scenario names to simulation results
    and no simulations are run inside this function.
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.82, bottom=0.12, top=0.95, wspace=0.25)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
    ax.set_ylim(top=5)
    ax.set_xlim(1900, TIME_ZERO_YEAR + simulation_time)

    if results is None:
        model_equations = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)
        results = {}
        for scenario_name in model_equations:
            print(f"Simulating scenario: {scenario_name}")
            results[scenario_name] = simulate(scenario_name, simulation_time=simulation_time, simulate_only_x=False)["simulation"]
    elif include_scenarios or exclude_scenarios:
        selected_scenarios = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)
        results = {name: result for name, result in results.items() if name in selected_scenarios}

    scenario_parameters = load_scenarios()

    for scenario_name, result in results.items():
        ax.plot(result.t + TIME_ZERO_YEAR, result.T, label=scenario_name)

    # handles, labels = _collect_legend_handles_labels(ax, ax_x)
    # fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    fig.legend(loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    output_dir = _get_run_output_dir()
    if fig_name is None:
        fig_name = "temperature.png"
    plt.savefig(output_dir / fig_name, dpi=300)
    _store_scenario_json()
    plt.show()


def plot_x(include_scenarios=None, exclude_scenarios=None, results=None, show_x_auxiliary=False, simulate_only_x=False, simulation_time=400, fig_name=None):
    """Plot the mitigation share x over time.

    If `results` is provided, it must be a mapping of scenario names to result
    objects. This matches `plot_temperature()` and keeps the API consistent.
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Fraction of mitigators (X)", fontsize=16)
    ax.set_ylim(-1.1, 1.1)
    ax.set_xlim(1900, TIME_ZERO_YEAR + simulation_time)

    if results is None:
        model_equations = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)
        results = {}
        for scenario_name in model_equations:
            print(f"Simulating scenario: {scenario_name}")
            results[scenario_name] = simulate(
                scenario_name,
                simulation_time=simulation_time,
                simulate_only_x=simulate_only_x,
            )["simulation"]
    elif include_scenarios or exclude_scenarios:
        selected_scenarios = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)
        if isinstance(results, dict) and "simulation" in results:
            results = results["simulation"]
        results = {name: result for name, result in results.items() if name in selected_scenarios}

    scenario_parameters = load_scenarios()

    for scenario_name, result in results.items():
        ax.plot(result.t + TIME_ZERO_YEAR, result.x, label=scenario_name)
        if show_x_auxiliary and _is_dynamic_social_norm(scenario_parameters.get(scenario_name, {})):
            ax.plot(result.t + TIME_ZERO_YEAR, result.x_p, linestyle="--", label=f"{scenario_name} x_p")
        if show_x_auxiliary and _is_dynamic_social_norm(scenario_parameters.get(scenario_name, {})):
            ax.plot(result.t + TIME_ZERO_YEAR, result.x_ref, linestyle=":", label=f"{scenario_name} x_ref")

    fig.legend(loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    output_dir = _get_run_output_dir()
    if fig_name is None:
        fig_name = "x.png"
    plt.savefig(output_dir / fig_name, dpi=300)
    _store_scenario_json()
    plt.show()


def plot_x_sensitivity(
    parameter_name,
    parameter_values,
    include_scenarios=None,
    exclude_scenarios=None,
    save_prefix="x_sensitivity",
    show_x_auxiliary=False,
    simulation_time=400,
    simulate_only_x=False,
):
    """Plot x-trajectories for a parameter sweep.

    A separate figure is created for each scenario and all parameter values for
    that scenario are plotted on the same axes.
    """
    scenarios_dict = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)

    for scenario_name, scenario_params in scenarios_dict.items():
        fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
        ax.set_xlabel("Time (year)", fontsize=16)
        ax.set_ylabel("Fraction of mitigators (X)", fontsize=16)
        ax.set_ylim(-1.1, 1.1)
        ax.set_xlim(1900, TIME_ZERO_YEAR + simulation_time)
        ax.set_title(f"{scenario_name}: sensitivity over {parameter_name}")

        for parameter_value in parameter_values:
            run_params = {**scenario_params, parameter_name: parameter_value}
            print(f"Simulating {scenario_name} with {parameter_name}={parameter_value}")
            result = simulate(
                run_params,
                simulation_time=simulation_time,
                simulate_only_x=simulate_only_x,
            )["simulation"]
            label = f"{parameter_name}={parameter_value}"
            ax.plot(result.t + TIME_ZERO_YEAR, result.x, label=label)

            if show_x_auxiliary and _is_dynamic_social_norm(run_params):
                ax.plot(result.t + TIME_ZERO_YEAR, result.x_p, linestyle="--", label=f"{label} x_p")
                ax.plot(result.t + TIME_ZERO_YEAR, result.x_ref, linestyle=":", label=f"{label} x_ref")

        fig.legend(loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
        output_dir = _get_run_output_dir()
        fig.savefig(
            output_dir / f"{save_prefix}_{scenario_name.replace(' ', '_').replace('/', '_')}.png",
            dpi=300,
        )
        _store_scenario_json()
        plt.show()


def plot_temperature_sensitivity(
    parameter_name,
    parameter_values,
    include_scenarios=None,
    exclude_scenarios=None,
    save_prefix="temperature_sensitivity",
    show_x_auxiliary=False,
    simulation_time=400,
    simulate_only_x=False
):
    """Plot temperature trajectories for one parameter sweep.

    A separate figure is created for each scenario; all parameter values for that
    scenario are plotted together on the same axes.
    """
    scenarios_dict = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)

    for scenario_name, scenario_params in scenarios_dict.items():
        fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
        fig.subplots_adjust(left=0.08, right=0.82, bottom=0.12, top=0.95, wspace=0.25)
        ax.set_xlabel("Time (year)", fontsize=16)
        ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
        ax.set_ylim(top=5)
        ax.set_xlim(1900, TIME_ZERO_YEAR + simulation_time)
        ax.set_title(f"{scenario_name}: sensitivity over {parameter_name}")

        for parameter_value in parameter_values:
            run_params = {**scenario_params, parameter_name: parameter_value}
            print(f"Simulating {scenario_name} with {parameter_name}={parameter_value}")
            result = simulate(
                run_params,
                simulation_time=simulation_time,
                simulate_only_x=simulate_only_x,
            )["simulation"]
            label = f"{parameter_name}={parameter_value}"
            ax.plot(result.t + TIME_ZERO_YEAR, result.T, label=label)

        fig.legend(loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
        output_dir = _get_run_output_dir()
        fig.savefig(
            output_dir / f"{save_prefix}_{scenario_name.replace(' ', '_').replace('/', '_')}.png",
            dpi=300,
        )
        _store_scenario_json()
        plt.show()


def plot_temperature_sensitivity_2d(
    x_parameter_name,
    x_parameter_values,
    y_parameter_name,
    y_parameter_values,
    include_scenarios=None,
    exclude_scenarios=None,
    save_prefix="temperature_sensitivity_2d",
    simulation_time=400,
    cmap="viridis",
    simulate_only_x=False,
):
    """Plot a 2D parameter sweep with final temperature anomaly as the color field.

    A separate figure is created for each scenario. The first parameter maps to
    the x-axis and the second parameter maps to the y-axis. Each cell in the
    heatmap stores the temperature anomaly at the final simulated timestep.
    """
    scenarios_dict = load_scenarios(include=include_scenarios, exclude=exclude_scenarios)

    x_values = list(x_parameter_values)
    y_values = list(y_parameter_values)

    for scenario_name, scenario_params in scenarios_dict.items():
        temperature_grid = np.empty((len(y_values), len(x_values)), dtype=float)
        amount_of_simulations = len(x_values) * len(y_values)
        for y_index, y_value in enumerate(y_values):
            for x_index, x_value in enumerate(x_values):
                run_params = {
                    **scenario_params,
                    x_parameter_name: x_value,
                    y_parameter_name: y_value,
                }
                print(f"Running simulation {y_index * len(x_values) + x_index + 1}/{amount_of_simulations} for scenario {scenario_name} with {x_parameter_name}={x_value}, {y_parameter_name}={y_value}")
                result = simulate(run_params, simulation_time=simulation_time, simulate_only_x=simulate_only_x)["simulation"]
                # temperature_grid[y_index, x_index] = np.max(result.T)
                temperature_grid[y_index, x_index] = result.T[-1]


        fig, ax = plt.subplots(figsize=(10, 7))
        mesh = ax.pcolormesh(
            x_values,
            y_values,
            temperature_grid,
            shading="auto",
            cmap=cmap,
        )
        ax.set_xlabel(x_parameter_name)
        ax.set_ylabel(y_parameter_name)
        ax.set_title(
            f"{scenario_name}: temperature anomaly at last timestep over {x_parameter_name} and {y_parameter_name}"
        )
        colorbar = fig.colorbar(mesh, ax=ax)
        colorbar.set_label("Final temperature anomaly")

        output_dir = _get_run_output_dir()
        fig.savefig(
            output_dir / f"{save_prefix}_{scenario_name.replace(' ', '_').replace('/', '_')}.png",
            dpi=300,
        )
        _store_scenario_json()
        plt.show()


def plot_social_norms(scenarios=None, exclude_scenarios=None, results=None, show_x_auxiliary=False, simulation_time=400, simulate_only_x=False):
    """Plot temperature and mitigation trajectories.

    If `results` is provided, it must map scenario names to simulation results
    and no simulations are run inside this function.
    """
    fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Social norm value", fontsize=16)
    ax.set_ylim(-1.1, 1.1)
    ax.set_xlim(1900, TIME_ZERO_YEAR + simulation_time)

    def _extract_series(item):
        if isinstance(item, dict):
            if "social_norm_term" in item:
                series = item["social_norm_term"]
            elif "simulation" in item and hasattr(item["simulation"], "t"):
                series = item["simulation"].x
            else:
                series = item

            time = None
            if "simulation" in item and hasattr(item["simulation"], "t"):
                time = item["simulation"].t
            return time, series

        if hasattr(item, "t") and hasattr(item, "x"):
            return item.t, item.x

        return None, item

    def _to_numeric_series(series):
        return np.array([np.nan if value is None else value for value in series], dtype=float)

    if results is None:
        model_equations = load_scenarios(
        include=scenarios,
        exclude=exclude_scenarios,
    )
        results = {}
        for scenario_name in model_equations:
            print(f"Simulating scenario: {scenario_name}")
            results[scenario_name] = simulate(
                scenario_name,
                simulation_time=simulation_time,
                simulate_only_x=simulate_only_x
            )["simulation"]
    # if results is None:
    #     model_equations = load_scenarios(include=scenarios, exclude=exclude_scenarios)
    #     results = {}
    #     for scenario_name in model_equations:
    #         print(f"Simulating scenario: {scenario_name}")
    #         results[scenario_name] = simulate(scenario_name, simulation_time=simulation_time)
    elif scenarios or exclude_scenarios:
        selected_scenarios = load_scenarios(include=scenarios, exclude=exclude_scenarios)
        results = {name: result for name, result in results.items() if name in selected_scenarios}

    for scenario_name, result in results.items():
        time, series = _extract_series(result)
        series = _to_numeric_series(series)
        if time is None:
            time = np.linspace(TIME_ZERO_YEAR, TIME_ZERO_YEAR + simulation_time, len(series))
        else:
            time = time + TIME_ZERO_YEAR
        if not np.all(np.isnan(series)):
            ax.plot(time, series, label=scenario_name)
        
    fig.legend(loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    output_dir = _get_run_output_dir()
    plt.savefig(output_dir / "social_norm_value.png", dpi=300)
    _store_scenario_json()
    plt.show()


# def plot_contour(x_values, y_values, z_values, x_label, y_label, title, colorbar_label, contour_color="k"):
#     """Render a pcolormesh of `z_values` over `x_values` and `y_values`,
#     add contour lines and a colorbar with labels."""
#     x_mesh, y_mesh = np.meshgrid(x_values, y_values)
#     plt.figure(figsize=(8, 6))
#     plt.pcolormesh(x_mesh, y_mesh, z_values, shading="auto")
#     plt.colorbar(label=colorbar_label)
#     contour = plt.contour(x_mesh, y_mesh, z_values, colors=contour_color, linewidths=0.5)
#     plt.clabel(contour, inline=True, fontsize=8)
#     plt.xlabel(x_label, fontsize=16)
#     plt.ylabel(y_label, fontsize=16)
#     plt.title(title, fontsize=12)
#     plt.show()
