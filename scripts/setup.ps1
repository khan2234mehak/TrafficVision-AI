<# TrafficVision AI - one-time setup for Windows PowerShell.
   Run from the project root:   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
   Options:  -SkipWeights   skip the YOLO weights download
             -Model yolo11s.pt  choose another model #>
param([switch]$SkipWeights, [string]$Model = "yolo11n.pt")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Write-Host "[missing] $cmd - $hint" -ForegroundColor Red; exit 1 } }
Need "python" "Install Python 3.10-3.12 from https://www.python.org/downloads/ and tick 'Add python.exe to PATH'."
Need "node" "Install Node.js 18+ (LTS) from https://nodejs.org/."
$pyv = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "Python $pyv, Node $(node --version)" -ForegroundColor Cyan
if ([version]$pyv -lt [version]"3.10" -or [version]$pyv -ge [version]"3.13") { Write-Host "[warning] Python 3.10-3.12 is recommended (you have $pyv). PyTorch wheels may be missing for newer versions." -ForegroundColor Yellow }

Write-Host "`n[1/4] Python virtual environment + dependencies (PyTorch is large, this can take several minutes)..." -ForegroundColor Green
if (-not (Test-Path "backend\.venv")) { python -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Write-Host "`n[2/4] Environment file..." -ForegroundColor Green
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created .env from .env.example" }

Write-Host "`n[3/4] YOLO weights..." -ForegroundColor Green
if ($SkipWeights) { Write-Host "Skipped. Run later:  backend\.venv\Scripts\python.exe scripts\download_weights.py" }
else { & backend\.venv\Scripts\python.exe scripts\download_weights.py $Model; if ($LASTEXITCODE -ne 0) { Write-Host "Weights download failed - see the message above." -ForegroundColor Yellow } }

Write-Host "`n[4/4] Frontend dependencies..." -ForegroundColor Green
Push-Location frontend
npm install
Pop-Location

Write-Host "`nSetup complete. Start the app with:  powershell -ExecutionPolicy Bypass -File scripts\run-all.ps1" -ForegroundColor Cyan
Write-Host "Then open http://localhost:5173  (demo login: admin@trafficvision.demo / Admin@12345)"
