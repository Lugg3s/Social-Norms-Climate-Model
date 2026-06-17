# Interesting plots for evaluation might be: 
# Rate of social learning (kappa) against net cost of mitigation (Beta) (from the paper)
# Mitigators


import numpy as np
import matplotlib.pyplot as plt
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



def plot_emissions(scenarios=None):
    pass


def plot_temperature(scenarios=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
    ax.set_ylim(top=5)
    ax.set_xlim(1900, 2200)

    inset_ax = inset_axes(
        ax,
        width="30%",
        height="30%",
        bbox_to_anchor=(-0.25, 0, 1, 1),
        bbox_transform=ax.transAxes,
        loc="center",
    )
    # inset_ax.set_xlim(2000, 2075)
    inset_ax.set_xlim(1900, 2200)
    inset_ax.set_xlabel("Time (year)", fontsize=14)
    inset_ax.set_ylabel("X", fontsize=14)

    model_equations = load_scenarios()
    if scenarios:
         model_equations = {k: v for k, v in model_equations.items() if k in scenarios}
    for scenario_name, _ in model_equations.items():
        print(f"Simulating scenario: {scenario_name}")
        t, _, _, _, _, T, x = simulate(scenario_name)
        ax.plot(t + 1800, T, label=scenario_name)
        inset_ax.plot(t + 1800, x, label=scenario_name)

    ax.legend(loc="upper left", fontsize=14)
    plt.tight_layout()
    plt.savefig("all_scenarios.png", dpi=300, bbox_inches="tight")
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
