$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $root
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyinstallerExe = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
Set-Location $root

if (-not (Test-Path $pythonExe)) {
    throw "가상환경이 없습니다. 먼저 프로젝트 루트에서 .venv를 준비하세요."
}

& $pythonExe -m pip install pyinstaller

& $pyinstallerExe `
  --noconfirm `
  --clean `
  --onefile `
  --name delivery-menu `
  --add-data "templates;templates" `
  app.py

Write-Host ""
Write-Host "빌드 완료: $root\dist\delivery-menu.exe"
