# Starts the FastAPI backend on http://localhost:8000  (API docs: /docs)
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Host "Run scripts\setup.ps1 first." -ForegroundColor Red; exit 1 }
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
