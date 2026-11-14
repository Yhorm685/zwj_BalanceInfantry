"""Rebuild task 03(a) results from the run manifest and Webots telemetry."""

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from response_figures import draw_figures


SAMPLE_PERIOD = 0.004
PARAMETERS = {"cart_mass": 1.0, "rod_mass": 0.2, "length": 0.6}
ALGORITHMS = ("pid", "lqr")
COLUMNS = ("time_s", "reference_m", "x_m", "v_m_s", "theta_rad", "omega_rad_s", "force_N", "external_N")
ZH_STATUS = {"settled": "已恢复", "unsettled": "观察窗内未恢复", "unstable": "失稳"}
ZH_SCENARIO = {"initial": "5° 初偏角", "step": "位置阶跃", "pulse": "外力脉冲"}


@dataclass
class Run:
    config: dict
    trace: np.ndarray
    metrics: dict

    @property
    def name(self):
        return self.config["id"]


def changed_parameters(config):
    return [key for key, value in PARAMETERS.items() if not np.isclose(config[key], value)]


def load_trace(path, config):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = next(csv.reader(stream))
        if tuple(header) != COLUMNS:
            raise ValueError(f"{path}: unexpected header {header}")
        data = np.loadtxt(stream, delimiter=",", dtype=[(name, "f8") for name in COLUMNS], ndmin=1)

    t = data["time_s"]
    if not len(t) or abs(t[0]) > 1e-6 or not np.isfinite(t).all():
        raise ValueError(f"{path}: invalid time origin or non-finite time")
    if not np.allclose(np.diff(t), SAMPLE_PERIOD, rtol=0, atol=1e-6):
        raise ValueError(f"{path}: missing or irregular samples")
    if t[-1] > config["duration"] + 1e-6:
        raise ValueError(f"{path}: samples run past configured duration")
    if np.any(np.abs(data["force_N"][np.isfinite(data["force_N"])]) > 10.00001):
        raise ValueError(f"{path}: motor command exceeds 10 N")
    scenario = config["scenario"]
    ref = np.where((scenario == "step") & (t >= 2 - 1e-8), 0.2, 0.0)
    ext = np.where((scenario == "pulse") & (t >= 2 - 1e-8) & (t < 2.1 - 1e-8), 2.0, 0.0)
    # At the terminal sample there is no next integration interval.
    if not np.allclose(data["reference_m"][:-1], ref[:-1], atol=1e-7):
        raise ValueError(f"{path}: position reference disagrees with scenario")
    if not np.allclose(data["external_N"][:-1], ext[:-1], atol=1e-7):
        raise ValueError(f"{path}: external force disagrees with scenario")
    return data


def measure(config, data):
    t, x, theta = data["time_s"], data["x_m"], np.rad2deg(data["theta_rad"])
    error = x - data["reference_m"]
    act = data["force_N"]
    finite = np.logical_and.reduce([np.isfinite(data[col]) for col in COLUMNS])
    failed = ~finite | (np.abs(theta) >= 30) | (np.abs(x) >= 1.5)
    scenario = config["scenario"]
    event = 0.0 if scenario == "initial" else 2.0
    recovery_origin = 2.1 if scenario == "pulse" else event
    status, settle, reason = "unsettled", None, ""
    if failed.any():
        i = np.flatnonzero(failed)[0]
        reasons = []
        if not finite[i]:
            reasons.append("nonfinite")
        if abs(theta[i]) >= 30:
            reasons.append("tilt")
        if abs(x[i]) >= 1.5:
            reasons.append("travel")
        status, reason = "unstable", "+".join(reasons)
    elif abs(t[-1] - config["duration"]) > 1e-6:
        raise ValueError(f"{config['id']}: truncated at {t[-1]} s without a failure sample")
    else:
        first = np.searchsorted(t, recovery_origin - 1e-8)
        outside = np.flatnonzero((np.abs(error[first:]) > 0.01) | (np.abs(theta[first:]) > 1))
        index = first + (outside[-1] + 1 if len(outside) else 0)
        if index < len(t) and t[-1] - t[index] >= 0.5 - 1e-8:
            settle = max(0.0, t[index] - recovery_origin)
            status = "settled"
    observed = finite & (t >= event - 1e-8)
    intervals = observed[:-1]
    max_abs = lambda values: float(np.max(np.abs(values[observed]))) if np.any(observed) else None
    tail = (t >= config["duration"] - 0.5 - 1e-8) & finite
    force_rms = float(np.sqrt(np.mean(act[:-1][intervals] ** 2))) if intervals.any() else None
    overshoot = None
    if scenario == "step" and observed.any():
        overshoot = max(0.0, float(np.max(x[observed]) - 0.2) / 0.2 * 100)
    return {
        "status": status, "failure_reason": reason, "end_s": float(t[-1]), "samples": len(t),
        "settling_s": settle, "peak_angle_deg": max_abs(theta), "peak_abs_x_m": max_abs(x),
        "overshoot_pct": overshoot,
        "tail_mean_error_m": float(np.mean(error[tail])) if status != "unstable" and tail.any() else None,
        "peak_force_N": max_abs(act), "rms_force_N": force_rms,
        "saturated_s": float(np.count_nonzero(intervals & (np.abs(act[:-1]) >= 10 - 1e-6)) * SAMPLE_PERIOD),
        "impulse_Ns": float(np.sum(data["external_N"][:-1] * np.diff(t))),
    }


def validate_cases(runs):
    """Reject a report claiming coverage when any required physical case is missing."""
    result = {}
    for alg in ALGORITHMS:
        selected = [r for r in runs if r.config["algorithm"] == alg]
        for scenario in ZH_SCENARIO:
            matches = [r for r in selected if r.config["scenario"] == scenario and not changed_parameters(r.config)]
            if len(matches) != 1:
                raise ValueError(f"Expected one nominal {alg}/{scenario} run, found {len(matches)}")
            result[alg, scenario] = matches[0]
        sweep = [r for r in selected if "scan" in r.config["groups"]]
        ratios = sorted(r.config["length"] / PARAMETERS["length"] for r in sweep)
        if len(ratios) != 11 or not np.allclose(ratios, np.arange(5, 16) / 10):
            raise ValueError(f"{alg}: incomplete or duplicate rod length scan")
        if any(set(changed_parameters(r.config)) - {"length"} or r.config["scenario"] != "pulse" for r in sweep):
            raise ValueError(f"{alg}: scan must use a pulse and vary only rod length")
        perturb = [r for r in selected if "perturb" in r.config["groups"]]
        found = []
        for r in perturb:
            changed = changed_parameters(r.config)
            if len(changed) != 1 or r.config["scenario"] != "pulse":
                raise ValueError(f"{r.name}: expected a single-parameter pulse test")
            key = changed[0]
            found.append((key, round(r.config[key] / PARAMETERS[key], 8)))
        if sorted(found) != sorted((k, v) for k in PARAMETERS for v in (0.8, 1.2)):
            raise ValueError(f"{alg}: incomplete or duplicate parameter perturbations")
    return result


def fmt(value, places=3):
    return "—" if value is None else f"{value:.{places}f}"


def scan_ranges(ratios):
    """Group neighbouring measured percent values; keep gaps between runs."""
    groups = []
    for point in sorted(ratios):
        if groups and point == groups[-1][-1] + 10:
            groups[-1].append(point)
        else:
            groups.append([point])
    return "、".join(f"{a[0]}%" if len(a) == 1 else f"{a[0]}%–{a[-1]}%" for a in groups) or "无"


def write_report(path, runs, nominal):
    lines = [
        "# 倒立摆小车仿真实验结果", "",
        f"共分析 {len(runs)} 次 Webots 运行。每条曲线来自一次确定性运行。"
        "两种算法共用 4 ms 采样、±10 N 控制力限幅和相同初始条件。"
        "原始记录与实验参数可按运行编号对应。[原始 CSV](../evidence/raw/) · "
        "[工况清单](../experiments/manifest.json) · [完整指标表](../evidence/summary.csv)", "",
        "## 验收口径", "",
        "- 每次观察 14 s。位置误差≤0.01 m 且绝对摆角≤1°，连续保持到观察结束并至少保持 0.5 s，记为已恢复。"
        "调节时间从初始释放、阶跃生效或脉冲撤除起算。其余完成全窗的运行记为观察窗内未恢复。",
        "- 遇到绝对摆角≥30°、绝对位移≥1.5 m 或非有限值即判失稳，保留已观测数据。"
        "图中提前终止的曲线只画至最后一个有效样本。",
        "- 峰值从事件开始计，控制力均方根按同一段采样时间计算。"
        "末段误差取完整运行最后 0.5 s 的位置减目标均值。正超调以 0.2 m 阶跃幅值为分母。", "",
        "## 标称模型", "",
        "| 工况 | 算法 | 状态 | 调节时间 (s) | 峰值摆角 (°) | 最大绝对位移 (m) | 峰值控制力 (N) | 均方根控制力 (N) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for scene, label in ZH_SCENARIO.items():
        for alg in ALGORITHMS:
            m = nominal[alg, scene].metrics
            vals = [fmt(m[k]) for k in ("settling_s", "peak_angle_deg", "peak_abs_x_m", "peak_force_N", "rms_force_N")]
            lines.append(f"| {label} | {alg.upper()} | {ZH_STATUS[m['status']]} | " + " | ".join(vals) + " |")
    lines.extend(["", "阶跃在 2.000 s 生效。"])
    for alg in ALGORITHMS:
        m = nominal[alg, "step"].metrics
        lines.append(f"{alg.upper()} 的正超调为 {fmt(m['overshoot_pct'], 2)}%，"
                     f"末段有符号平均位置误差为 {fmt(m['tail_mean_error_m'], 6)} m。")
    impulse = [fmt(nominal[a, "pulse"].metrics["impulse_Ns"]) for a in ALGORITHMS]
    lines.extend(["", "![标称初始释放、阶跃和外力脉冲下的位置、摆角及控制力](../evidence/figures/nominal.png)", "",
                  "灰色点线为位置目标。竖线标出阶跃时刻，浅色区标出 2 N 水平外力从 2.000 到 2.100 s 的作用时间。"
                  f"按相邻采样时刻间隔积分，PID 和 LQR 记录的外力冲量分别为 {impulse[0]} 与 {impulse[1]} N·s。", "",
                  "## 单参数摄动", "",
                  "保持两组控制增益固定，分别改变实际小车质量、杆质量和杆长，各运行一次相同的外力脉冲。"
                  "每个面板给出相同算法的三条实测角度曲线。", "",
                  "![六组质量及长度摄动的角响应](../evidence/figures/perturbations.png)", "",
                  "| 参数比例 | 算法 | 状态 | 峰值摆角 (°) | 恢复用时 (s) |", "| --- | --- | --- | ---: | ---: |"])
    parameter_names = {"cart_mass": "小车质量", "rod_mass": "杆质量", "length": "杆长"}
    for key, name in parameter_names.items():
        for r in sorted((r for r in runs if "perturb" in r.config["groups"] and changed_parameters(r.config) == [key]),
                        key=lambda r: (r.config[key], ALGORITHMS.index(r.config["algorithm"]))):
            m = r.metrics
            lines.append(f"| {name} {r.config[key] / PARAMETERS[key]:.0%} | {r.config['algorithm'].upper()} "
                         f"| {ZH_STATUS[m['status']]} | {fmt(m['peak_angle_deg'])} | {fmt(m['settling_s'])} |")

    lines.extend(["", "## 杆长扫描与算法选择", "",
                  "在相同脉冲下将杆长从 0.30 m 扫到 0.90 m，间隔 0.06 m。标称长度为 0.60 m。"
                  "下表按占标称长度的百分比列出相邻试验点；点间隔为 10 个百分点。结论只覆盖这些离散长度与本次扰动。", "",
                  "| 算法 | 已恢复的试验点 | 观察窗内未恢复 | 失稳 |", "| --- | --- | --- | --- |"])
    for alg in ALGORITHMS:
        sweep = [r for r in runs if r.config["algorithm"] == alg and "scan" in r.config["groups"]]
        cells = [scan_ranges([round(r.config["length"] / 0.6 * 100) for r in sweep if r.metrics["status"] == state])
                 for state in ZH_STATUS]
        lines.append(f"| {alg.upper()} | " + " | ".join(cells) + " |")
    lines.extend(["", "![杆长扫描的峰值偏角、恢复时间与结果分类](../evidence/figures/length-scan.png)", ""])
    for scene, criterion, unit, label in (("step", "settling_s", "s", "阶跃调节时间"),
                                          ("pulse", "peak_angle_deg", "°", "标称扰动峰值摆角"),
                                          ("pulse", "rms_force_N", "N", "标称扰动均方根控制力")):
        a, b = [nominal[alg, scene].metrics for alg in ALGORITHMS]
        measured = f"PID {fmt(a[criterion])} {unit}，LQR {fmt(b[criterion])} {unit}"
        if all(m["status"] == "settled" for m in (a, b)):
            best = "PID" if a[criterion] < b[criterion] else "LQR"
            preference = "两者相当" if abs(a[criterion] - b[criterion]) < 0.001 else f"{best} 更低"
            measured += f"，{preference}"
        lines.append(f"- {label}为 {measured}。")
    lines.extend(["", "串级 PID 便于分别调整位置环和姿态环。离散 LQR 利用线性模型联合权衡四个状态与输入。"])
    candidates = [alg for alg in ALGORITHMS if all(nominal[alg, s].metrics["status"] == "settled" for s in ZH_SCENARIO)]
    if candidates:
        ordered = sorted(candidates, key=lambda a: nominal[a, "step"].metrics["settling_s"])
        if len(ordered) == 2 and abs(nominal[ordered[0], "step"].metrics["settling_s"]
                                     - nominal[ordered[1], "step"].metrics["settling_s"]) < SAMPLE_PERIOD / 2:
            lines.append("以标称位置阶跃的调节时间为指标，两种算法在采样分辨率内并列；上述控制力与脉冲结果可进一步区分用途。")
        else:
            best = ordered[0]
            lines.append(f"对于以标称位置跟踪为主的任务，优先选用 {best.upper()}。"
                         f"该算法通过三项标称恢复判据，位置阶跃调节时间为 {fmt(nominal[best, 'step'].metrics['settling_s'])} s。"
                         "换装不同长度的摆杆时，应另按扫描表选择。")
    else:
        lines.append("本次两种算法均未通过全部标称恢复判据，应先对未恢复或失稳工况重新整定。")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="project containing manifest and CSVs")
    parser.add_argument("--out", type=Path, help="output project root (default: input root)")
    args = parser.parse_args()
    root, out = args.root, args.out or args.root
    manifest = json.loads((root / "experiments/manifest.json").read_text(encoding="utf-8-sig"))
    runs = []
    for config in manifest:
        if config["algorithm"] not in ALGORITHMS or config["scenario"] not in ZH_SCENARIO:
            continue
        if config["duration"] != 14:
            raise ValueError(f"{config['id']}: formal scenarios require a 14 s horizon")
        data = load_trace(root / "evidence/raw" / (config["id"] + ".csv"), config)
        runs.append(Run(config, data, measure(config, data)))
    if len({r.name for r in runs}) != len(runs):
        raise ValueError("Duplicate run ID")
    nominal = validate_cases(runs)
    (out / "evidence/figures").mkdir(parents=True, exist_ok=True)
    (out / "docs").mkdir(parents=True, exist_ok=True)
    with (out / "evidence/summary.csv").open("w", newline="", encoding="utf-8") as f:
        config_fields = ["id", "algorithm", "scenario", "cart_mass", "rod_mass", "length", "initial_angle_deg", "duration", "groups"]
        writer = csv.DictWriter(f, fieldnames=[*config_fields, *runs[0].metrics])
        writer.writeheader()
        for r in runs:
            row = {k: r.config[k] for k in config_fields}
            row["groups"] = ",".join(row["groups"])
            writer.writerow(row | {k: (f"{v:.10g}" if isinstance(v, float) else v) for k, v in r.metrics.items()})
    draw_figures(out / "evidence/figures", runs, nominal, PARAMETERS, ALGORITHMS)
    write_report(out / "docs/results.md", runs, nominal)
    print(f"Analyzed {len(runs)} Webots runs -> {out.resolve()}")


if __name__ == "__main__":
    main()
