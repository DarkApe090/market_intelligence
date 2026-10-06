# Arranca base de dados, Ollama, backend e frontend (cada um na sua janela).
$root = $PSScriptRoot

docker compose -f "$root\docker-compose.yml" up -d

$ollama = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
if ((Test-Path $ollama) -and -not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    Start-Process $ollama -ArgumentList 'serve' -WindowStyle Minimized
}

Push-Location "$root\backend"
.\.venv\Scripts\python.exe -m alembic upgrade head
Pop-Location

Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload"
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$root\frontend'; npm run dev"

Write-Host 'Frontend: http://localhost:5173  |  API: http://localhost:8000/docs'
