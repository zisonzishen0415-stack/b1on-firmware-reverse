#!/usr/bin/env pwsh
# 一键重建 TMS320C6000 Ghidra 模块:
#   1) 运行语料生成器(需要 TI dis6x 的 .dis 与 .bin 输入)
#   2) 用 Ghidra 的 sleigh 编译
#   3) 安装到 Ghidra/Processors/TMS320C6000
#
# 用法:
#   pwsh build_all.ps1 -GhidraRoot C:\path\to\ghidra_12.1.2_PUBLIC

param(
    [Parameter(Mandatory = $true)]
    [string]$GhidraRoot,
    [string]$RepoRoot = (Split-Path $PSScriptRoot -Parent)
)

$ErrorActionPreference = "Stop"
$lang = Join-Path $RepoRoot "processor\TMS320C6000\data\languages"
$gen  = Join-Path $RepoRoot "tools\gen"

Push-Location $gen
try {
    Write-Host "[1/3] generating slaspec + rebuilt image..."
    & python gen_sleigh.py
    if ($LASTEXITCODE -ne 0) { throw "gen_sleigh.py failed" }
}
finally { Pop-Location }

Push-Location $lang
try {
    Write-Host "[2/3] compiling SLEIGH..."
    & (Join-Path $GhidraRoot "support\sleigh.bat") TMS320C6000.slaspec TMS320C6000.sla
    if ($LASTEXITCODE -ne 0) { throw "sleigh compile failed" }
}
finally { Pop-Location }

$dst = Join-Path $GhidraRoot "Ghidra\Processors\TMS320C6000"
New-Item -ItemType Directory -Force -Path (Join-Path $dst "data\languages") | Out-Null
Copy-Item "$lang\*" (Join-Path $dst "data\languages\") -Force
if (-not (Test-Path (Join-Path $dst "Module.manifest"))) {
    New-Item -ItemType File -Path (Join-Path $dst "Module.manifest") | Out-Null
}
Write-Host "[3/3] module installed at $dst"
