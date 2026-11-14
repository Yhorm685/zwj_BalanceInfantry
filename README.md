# BalanceInfantry · 任务 03(a)

Webots R2025a 单杆倒立摆小车。环境检查命令见下方。首次运行需先在 PowerShell 中构建控制器。

```powershell
.\tools\build.ps1 smoke
& "$env:WEBOTS_HOME\msys64\mingw64\bin\webots.exe" --batch --mode=fast --stdout --stderr worlds/smoke.wbt
```
