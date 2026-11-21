# Opens the backend and the frontend in two PowerShell windows.
$here = $PSScriptRoot
Start-Process powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","`"$here\run-backend.ps1`""
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit","-ExecutionPolicy","Bypass","-File","`"$here\run-frontend.ps1`""
Write-Host "Backend: http://localhost:8000/docs    Frontend: http://localhost:5173"
