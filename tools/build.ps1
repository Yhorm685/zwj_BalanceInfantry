param([ValidateSet('smoke','balance')][string]$Controller = 'balance', [switch]$OpenLoopOnly)
$ErrorActionPreference = 'Stop'
$webots = $env:WEBOTS_HOME
if (-not $webots) { throw 'Set WEBOTS_HOME to the Webots R2025a installation directory.' }
$bin = Join-Path $webots 'msys64/mingw64/bin'
$source = Join-Path $PSScriptRoot "../controllers/$Controller"
$argsList = @('-std=c++17', '-O2', '-Wall', '-Wextra', "-I$webots/include/controller/cpp", "-I$webots/include/controller/c", "$source/$Controller.cpp", "-L$webots/lib/controller", '-lCppController', '-lController', '-o', "$source/$Controller.exe")
if ($OpenLoopOnly) { $argsList = @('-DOPEN_LOOP_ONLY=1') + $argsList }
$previousPath = $env:PATH
try {
    $env:PATH = "$bin;$previousPath"
    & "$bin/g++.exe" @argsList
    if ($LASTEXITCODE -ne 0) { throw "Build failed ($LASTEXITCODE)" }
} finally {
    $env:PATH = $previousPath
}
Write-Output "Built $Controller with Webots C++17 toolchain"
