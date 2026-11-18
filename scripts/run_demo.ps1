# This script starts the Rozmarra API and the doctor dashboard on Windows.
# Please run scripts\setup.ps1 once before you run this script:
#   powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1
# The dashboard then opens at http://localhost:5173. Press Ctrl+C to stop both.
# For a presentation, add -Production. The script then builds the dashboard once and serves the
# built files, which load faster and do not compile anything while the audience watches:
#   powershell -ExecutionPolicy Bypass -File scripts\run_demo.ps1 -Production

param([switch]$Production)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path (Join-Path $root 'frontend\node_modules'))) {
    throw 'The dashboard packages are missing. Please run scripts\setup.ps1 first.'
}

Write-Host 'Starting the Rozmarra API at http://127.0.0.1:8000 ...'
$api = Start-Process -FilePath 'uv' -ArgumentList @('run', 'rozmarra', 'serve') `
    -WorkingDirectory (Join-Path $root 'backend') -NoNewWindow -PassThru

try {
    # The dashboard starts only when the API answers, so that the first screen has its data.
    $ready = $false
    for ($i = 0; $i -lt 90; $i++) {
        if ($api.HasExited) { throw 'The Rozmarra API stopped. Please read the messages above.' }
        try {
            Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        }
        catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'The Rozmarra API did not start within 90 seconds.' }
    Write-Host 'The Rozmarra API is running.'

    Push-Location (Join-Path $root 'frontend')
    if ($Production) {
        Write-Host 'Building the dashboard ...'
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'The dashboard build failed. Please read the messages above.' }
        # The preview server passes /api to the Rozmarra API in the same way as the dev server.
        Write-Host 'Serving the built dashboard at http://localhost:5173 ...'
        npm run preview -- --port 5173 --strictPort --open
    }
    else {
        Write-Host 'Starting the dashboard at http://localhost:5173 ...'
        npm run dev -- --open
    }
}
finally {
    Pop-Location -ErrorAction SilentlyContinue
    if ($api -and -not $api.HasExited) {
        # The API runs as a child of uv, so the whole process tree is stopped.
        taskkill /PID $api.Id /T /F | Out-Null
    }
    Write-Host 'The Rozmarra API and the dashboard have stopped.'
}
