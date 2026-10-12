# This script starts the Rozmarra API and the doctor dashboard on Windows.
# Please run scripts\setup.ps1 once before you run this script:
#   powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
# The dashboard then opens at http://localhost:5173. Press Ctrl+C to stop both.

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

Write-Host 'Starting the Rozmarra API at http://127.0.0.1:8000 ...'
$api = Start-Process -FilePath 'uv' -ArgumentList @('run', 'rozmarra', 'serve') `
    -WorkingDirectory (Join-Path $root 'backend') -NoNewWindow -PassThru

try {
    Write-Host 'Starting the dashboard at http://localhost:5173 ...'
    Push-Location (Join-Path $root 'frontend')
    npm run dev
}
finally {
    Pop-Location
    if ($api -and -not $api.HasExited) {
        # The API runs as a child of uv, so the whole process tree is stopped.
        taskkill /PID $api.Id /T /F | Out-Null
    }
    Write-Host 'The Rozmarra API and the dashboard have stopped.'
}
