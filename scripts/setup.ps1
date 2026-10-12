# This script sets up Rozmarra on Windows.
# Please run it from the repository folder with this command:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

foreach ($tool in @('uv', 'node', 'npm')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "The tool '$tool' is not installed. Please see the README for the installation steps."
    }
}

Write-Host 'Installing the backend packages with uv ...'
Push-Location (Join-Path $root 'backend')
try { uv sync } finally { Pop-Location }

Write-Host 'Installing the dashboard packages with npm ...'
Push-Location (Join-Path $root 'frontend')
try { npm ci } finally { Pop-Location }

Write-Host 'Rozmarra is set up. Please run scripts\run_demo.ps1 to start the demo.'
