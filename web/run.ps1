# Starts the Learnix web app: FastAPI (8000) + Vite (5173).
# Usage:  powershell -ExecutionPolicy Bypass -File web\run.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Start-Process -FilePath "$root\api\.venv\Scripts\python.exe" `
  -ArgumentList "-m","uvicorn","main:app","--host","127.0.0.1","--port","8000" `
  -WorkingDirectory "$root\api"

if (-not (Test-Path "$root\ui\node_modules")) {
  Push-Location "$root\ui"; npm install; Pop-Location
}
Push-Location "$root\ui"
npm run dev
Pop-Location
