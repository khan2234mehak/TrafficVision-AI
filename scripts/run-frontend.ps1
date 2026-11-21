# Starts the React dev server on http://localhost:5173
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) { npm install }
npm run dev
