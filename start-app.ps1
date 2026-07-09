$ErrorActionPreference = "Stop"

# Avoid OpenBLAS contention across uvicorn workers
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:HF_HUB_OFFLINE = "1"

$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$venvActivate = Join-Path $projectRoot "venv\Scripts\Activate.ps1"

function Stop-IfUsingPort {
    param([int]$Port)

    $lines = netstat -ano -p tcp | findstr ":$Port"
    if ($LASTEXITCODE -eq 0 -and $lines) {
        $targetPid = ($lines -split "\s+") | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1
        if ($targetPid) {
            Write-Host "Stopping process $targetPid using port $Port..."
            taskkill /PID $targetPid /F | Out-Null
        }
    }
}

Set-Location $projectRoot

# 1. Auth DB is an in-process JSON file (backend/data/users.json).
#    Make sure the directory exists; recreate a clean file on demand.
$dataDir = Join-Path $backendRoot "data"
$usersFile = Join-Path $dataDir "users.json"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
if (-not (Test-Path $usersFile)) {
    "[]" | Set-Content -Path $usersFile -Encoding UTF8
}
Write-Host "[db] in-process auth store at $usersFile (no external Mongo)."

# 2. Clear stale processes from common app ports.
Stop-IfUsingPort -Port 4000
Stop-IfUsingPort -Port 8000
Stop-IfUsingPort -Port 5173

# 3. Start Ollama on the original default port unless it is already up.
function Test-PortOpen($port) { try { $c = New-Object System.Net.Sockets.TcpClient; $c.BeginConnect("127.0.0.1",$port,$null,$null) | Out-Null; Start-Sleep -Milliseconds 200; return $c.Connected } catch { return $false } }
if (-not (Test-PortOpen 11434)) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama serve" -WindowStyle Normal
} else {
    Write-Host "[ollama] already listening on :11434; reusing it."
}

# 4. Pull the Llama model used by the scenario matrix.
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ollama pull llama3.2" -WorkingDirectory $projectRoot

# 5. Create the Python venv if needed and (re)install requirements.
if (-not (Test-Path $venvActivate)) {
    py -m venv "$projectRoot\venv"
}
if (-not (Test-Path $venvActivate)) {
    throw "Failed to create the Python virtual environment at $venvActivate"
}

# Only install when the marker file is missing so restarts stay fast.
$reqsStamp = Join-Path $projectRoot ".requirements.sha"
$currentHash = (Get-FileHash (Join-Path $projectRoot "requirements.txt")).Hash
$storedHash = ""
if (Test-Path $reqsStamp) { $storedHash = (Get-Content $reqsStamp -Raw).Trim() }
if ($currentHash -ne $storedHash) {
    Write-Host "[pip] installing requirements.txt..."
    . "$venvActivate"; & python -m pip install -r (Join-Path $projectRoot "requirements.txt")
    $currentHash | Set-Content -Path $reqsStamp
} else {
    Write-Host "[pip] requirements.txt unchanged; skipping install."
}

# 6. Start the Python FastAPI analyzer on :8000.
# New: 4 workers, bounded in-flight analyzes, 90s hard timeout
$uvicornCmd = ". '$venvActivate'; `$env:ANALYZE_MAX_INFLIGHT='4'; `$env:ANALYZE_TIMEOUT_S='90'; uvicorn api:api --host 127.0.0.1 --port 8000 --workers 4"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $uvicornCmd -WorkingDirectory $projectRoot

# 7. Start the Node auth API (Express + in-process JSON store) on :4000.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backendRoot'; npm run dev" -WorkingDirectory $projectRoot

# 8. Start the React frontend on :5173.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendRoot'; npm run dev" -WorkingDirectory $projectRoot

Write-Host ""
Write-Host "Stack starting. Wait ~10s for each window to settle."
Write-Host "  FastAPI (Ollama): http://127.0.0.1:8000"
Write-Host "  Auth API:         http://localhost:4000"
Write-Host "  React UI:         http://localhost:5173"
Write-Host "  Ollama:           http://127.0.0.1:11434"



