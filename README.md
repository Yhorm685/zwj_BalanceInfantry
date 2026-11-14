# 任务 03(a) · Webots 单杆倒立摆小车

一辆沿水平导轨移动的小车，靠左右推力扶正一根自由摆杆。项目在 Webots R2025a 中比较串级 PID 和离散 LQR：34 个正式工况全部满足联合位置与摆角恢复判据。标称 0.2 m 阶跃中 PID 更快，标称外力脉冲下 LQR 的峰值偏角更小。

[看 LQR 录屏](evidence/video/demo-lqr.mp4) · [看 PID 录屏](evidence/video/demo-pid.mp4) · [看曲线与指标](docs/results.md)

## 第一次打开 Webots

1. 在 Windows 的项目目录打开 PowerShell。用 Webots 自带的 C++ 编译器构建控制器。此步在新下载的仓库执行一次，之后修改 C++ 源码时重新执行。

   ```powershell
   .\tools\build.ps1 balance
   ```

   若提示找不到 Webots，在这个 PowerShell 设置 `$env:WEBOTS_HOME = 'D:\Webots'`，路径填实际安装位置。本项目的分析依赖只在下方复现实验时使用。
2. 打开 Webots，选择 **File → Open World…**，打开 [worlds/balance.wbt](worlds/balance.wbt)，再选择 **Simulation → Real-time**。蓝色的是小车，黄色的是摆杆。白色刻线是起点，橙色刻线是 0.2 m 目标。左上角显示算法、目标位置、小车位置和摆角，直立时摆角接近 0°。
3. 默认使用 LQR。开始时摆杆从 5° 倾斜处释放，小车先移动去扶杆。到 **3 s**，小车接到 0.2 m 的位置目标；到 **8 s**，车体受到持续 0.1 s 的水平推力。之后小车保持在目标附近。要从头再看，选 **File → Reload World**，再按实时播放。[Webots R2025a 界面说明](https://github.com/cyberbotics/webots/blob/R2025a/docs/guide/the-user-interface.md)
4. 要在相同输入下看 PID，用 Python 生成 PID 演示副本，再用 **File → Open World…** 打开命令输出的路径。该命令仅使用 Python 标准库。

   ```powershell
   python tools/world.py pid
   ```

## 复现实验

在同一项目目录，准备 CPython 3.12 环境。下例使用 `uv`。

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
.\tools\build.ps1 balance
.\.venv\Scripts\python.exe tools/model.py
.\.venv\Scripts\python.exe tools/design_lqr.py
.\.venv\Scripts\python.exe tools/run.py --open
.\.venv\Scripts\python.exe tools/check_plant.py
.\.venv\Scripts\python.exe tools/run.py --jobs 3
.\.venv\Scripts\python.exe tools/analyze.py
```

只跑一组可使用 `tools/run.py --case pid-step`；录制演示用 `tools/run.py --movie pid` 或 `tools/run.py --movie lqr`。这些命令前使用同一 Python 解释器。运行器默认将 CSV 写入相应证据目录；`--out` 可指定独立输出目录。已下载原始 CSV 时，可以单独运行分析脚本重建报告和图片。默认 world 可以通过 `tools/check_default.py` 自动运行到第 14 s 并校验。

**正式实验的事件在 2 s 单独触发**，包括阶跃和外力脉冲。录屏把两种事件依次放在同一场景，让观众在 14 s 内同时观察偏角恢复、移动和抗扰动。正式比较取独立场景的原始数据。

## 交付与证据

| 内容 | 入口 |
| --- | --- |
| 质量、几何、惯量、模型推导及控制框图 | [物理模型](docs/model.md) |
| 控制律、参数整定与 C++ 实现 | [串级 PID](docs/pid.md) · [离散 LQR](docs/lqr.md) · [源代码](controllers/balance/) |
| 试验输入、误差带、状态与失稳判据 | [实验协议](experiments/protocol.md) · [逐项配置](experiments/manifest.json) |
| 34 个工况的原始数据、曲线、鲁棒性和算法比较 | [原始轨迹](evidence/raw/) · [汇总 CSV](evidence/summary.csv) · [分析报告](docs/results.md) |
| 首次构建、模型、两种算法与复现验证记录 | [环境](docs/01-environment.md) · [开环](docs/02-plant-check.md) · [PID](docs/03-pid-validation.md) · [LQR](docs/04-lqr-validation.md) · [交付复核](docs/05-reproduction.md) |
| 真实 AI 对话记录 | [脱敏删节导出](evidence/sessions/task03a.md) |

所有实验均来自 Webots 仿真。杆长扫描覆盖 0.30–0.90 m 的 11 个离散测试点，步幅 0.06 m。每个算法的标称脉冲及两组杆长摄动同时用于扫描，因此正式运行数为每种算法 17 次。
