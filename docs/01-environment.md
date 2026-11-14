# 环境与最小控制器

Windows，Webots R2025a，内置 MinGW g++ 14.2，CPython 3.12.13。使用 tools/build.ps1 编译 smoke，使用 README 所列 Webots 批处理命令启动 worlds/smoke.wbt。监督器连续调用五次 step(4)，实测秒数为 0.004、0.008、0.012、0.016、0.020，进程退出码 0。物理步长 2 ms。

分析环境在仓库内的 .venv 中创建。可使用 uv venv --python 3.12 .venv 和 uv pip install --python .venv/Scripts/python.exe -r requirements.txt 复现。该阶段提交可用 git log -- docs/01-environment.md 定位。
