"""Time responses and robustness plots for the Webots cart-pole measurements."""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


COLORS = {"pid": "#0072B2", "lqr": "#D55E00"}
STYLES = {"pid": "-", "lqr": "--"}
MARKERS = {"pid": "o", "lqr": "s"}
RATIOS = ((0.8, "#009E73", "--"), (1.0, "#50575E", "-"), (1.2, "#CC79A7", "-."))
PARAM_TITLES = {"cart_mass": "Cart mass", "rod_mass": "Rod mass", "length": "Rod length"}
SCENE_TITLES = {"initial": "Release from 5°", "step": "0.2 m position step", "pulse": "2 N force pulse"}


def save(fig, output, name):
    fig.savefig(output / f"{name}.png", dpi=300, facecolor="white")
    fig.savefig(output / f"{name}.svg", metadata={"Date": None}, facecolor="white")
    plt.close(fig)


def format_axis(axis):
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", linewidth=0.55, color="#D3D8DA")
    axis.set_axisbelow(True)
    axis.margins(x=0)


def pulse_span(axis):
    axis.axvspan(2.0, 2.1, color="#E3D8A8", alpha=0.75, linewidth=0, zorder=0)


def nominal_figure(output, nominal, algorithms):
    fig, axes = plt.subplots(3, 3, sharex=True, figsize=(10.4, 6.9), layout="constrained")
    by_row = (("x_m", "Position (m)"), ("theta_rad", "Tilt (°)"), ("force_N", "Control force (N)"))
    for col, (scene, title) in enumerate(SCENE_TITLES.items()):
        axes[0, col].set_title(title, loc="left", fontweight="bold")
        for row, (key, ylabel) in enumerate(by_row):
            axis = axes[row, col]
            format_axis(axis)
            if scene == "pulse":
                pulse_span(axis)
            elif scene == "step":
                axis.axvline(2, color="#9BA1A4", linewidth=0.85, zorder=0)
            if row == 0:
                target = nominal[algorithms[0], scene].trace
                axis.step(target["time_s"], target["reference_m"], where="post", color="#777777",
                          linestyle=":", linewidth=1.4, label="Target")
            for alg in algorithms:
                d = nominal[alg, scene].trace
                value = d[key]
                if key == "theta_rad":
                    value = np.rad2deg(value)
                axis.plot(d["time_s"], value, color=COLORS[alg], ls=STYLES[alg], lw=1.4, label=alg.upper())
            axis.set_xlim(0, 14)
            if col == 0:
                axis.set_ylabel(ylabel)
            if row == 2:
                axis.set_xlabel("Simulation time (s)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncols=3, frameon=False, loc="outside lower center")
    save(fig, output, "nominal")


def perturb_figure(output, runs, nominal, parameters, algorithms):
    fig, axes = plt.subplots(2, 3, sharex=True, sharey="row", figsize=(10.4, 4.8), layout="constrained")
    for row, alg in enumerate(algorithms):
        for col, (key, base) in enumerate(parameters.items()):
            axis = axes[row, col]
            format_axis(axis)
            pulse_span(axis)
            if row == 0:
                axis.set_title(PARAM_TITLES[key], loc="left", fontweight="bold")
            if row == 1:
                axis.set_xlabel("Simulation time (s)")
            if col == 0:
                axis.set_ylabel(f"{alg.upper()} tilt (°)")
            for ratio, color, style in RATIOS:
                if ratio == 1:
                    run = nominal[alg, "pulse"]
                else:
                    run = next(r for r in runs if r.config["algorithm"] == alg and "perturb" in r.config["groups"]
                               and np.isclose(r.config[key], base * ratio))
                axis.plot(run.trace["time_s"], np.rad2deg(run.trace["theta_rad"]), color=color,
                          ls=style, lw=1.4, label=f"{ratio:.0%} of nominal")
            axis.set_xlim(0, 14)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncols=3, frameon=False, loc="outside lower center")
    save(fig, output, "perturbations")


def scan_figure(output, runs, algorithms, nominal_length):
    fig, (peak, settle, outcome) = plt.subplots(3, sharex=True, figsize=(7.6, 6.4), layout="constrained",
                                                height_ratios=(3, 3, 1.25))
    for axis in (peak, settle, outcome):
        format_axis(axis)
        axis.axvline(100, color="#A0AAB0", ls=":", lw=1, zorder=0)
    shapes = {"settled": "o", "unsettled": "^", "unstable": "X"}
    for alg in algorithms:
        group = sorted((r for r in runs if "scan" in r.config["groups"] and r.config["algorithm"] == alg),
                       key=lambda r: r.config["length"])
        lengths = np.array([r.config["length"] / nominal_length * 100 for r in group])
        for axis, metric in ((peak, "peak_angle_deg"), (settle, "settling_s")):
            values = [np.nan if r.metrics[metric] is None else r.metrics[metric] for r in group]
            axis.plot(lengths, values, color=COLORS[alg], ls=STYLES[alg], lw=1.0, marker=MARKERS[alg],
                      markersize=5.4, markerfacecolor="white", label=alg.upper())
        for i, run in enumerate(group):
            outcome.scatter(lengths[i], alg.upper(), marker=shapes[run.metrics["status"]], s=42,
                            color=COLORS[alg], edgecolors="#333333", linewidths=0.4)
    peak.set_ylabel("Peak |tilt| (°)")
    settle.set_ylabel("Recovery time (s)")
    peak.legend(frameon=False, ncols=2)
    peak.set_title("Rod-length sweep under a 0.2 N·s impulse", loc="left", fontweight="bold")
    outcome.set_ylabel("Outcome")
    outcome.set_yticks([0, 1], [a.upper() for a in algorithms])
    outcome.set_ylim(-0.5, 1.5)
    outcome.set_xticks(np.arange(50, 151, 10))
    outcome.set_xlim(46, 154)
    outcome.set_xlabel("Rod length (% of 0.60 m)")
    labels = {"settled": "Settled", "unsettled": "Outside settling criterion", "unstable": "Unstable"}
    handles = [Line2D([], [], linestyle="none", marker=m, color="#515A5E", label=labels[s]) for s, m in shapes.items()]
    fig.legend(handles=handles, ncols=3, frameon=False, loc="outside lower center")
    save(fig, output, "length-scan")


def draw_figures(output, runs, nominal, parameters, algorithms):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 11,
                         "axes.labelsize": 9.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
                         "legend.fontsize": 9, "svg.fonttype": "none", "svg.hashsalt": "balance-infantry"})
    nominal_figure(output, nominal, algorithms)
    perturb_figure(output, runs, nominal, parameters, algorithms)
    scan_figure(output, runs, algorithms, parameters["length"])
