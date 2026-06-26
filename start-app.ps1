$projectRoot = "D:\trigyn\trigyn project\AI-recruiter-screening-system-"
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$venvActivate = Join-Path $projectRoot "venv\Scripts\Activate.ps1"

function Stop-IfUsingPort {
    param([int]$Port)

    $lines = netstat -ano -p tcp | findstr ":$Port"
    if ($LASTEXITCODE -eq 0 -and $lines) {
        $targetPid = ($lines -split '\s+') | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1
        if ($targetPid) {
            Write-Host "Stopping process $targetPid using port $Port..."
            taskkill /PID $targetPid /F | Out-Null
        }
    }
}

Set-Location $projectRoot

# 1. Start MongoDB if it is not already running
docker start recruiter-mongo 2>$null

# 2. Clear stale processes from common app ports
Stop-IfUsingPort -Port 4000
Stop-IfUsingPort -Port 8000
Stop-IfUsingPort -Port 5173

# 3. Start Ollama server in a new terminal
Start-Process powershell `
    -ArgumentList '-NoExit', '-Command', '$env:OLLAMA_HOST="127.0.0.1:12000"; ollama serve'
    
# 4. Pull the Llama model
Start-Process powershell -ArgumentList '-NoExit', '-Command', 'ollama pull llama3.2' -WorkingDirectory $projectRoot

# 5. Create the Python venv if needed and install requirements
if (-not (Test-Path $venvActivate)) {
    py -m venv "$projectRoot\venv"
}

Start-Process powershell -ArgumentList '-NoExit', '-Command', "& '$venvActivate'; pip install -r requirements.txt" -WorkingDirectory $projectRoot

# 6. Start the Python API in a new terminal
Start-Process powershell -ArgumentList '-NoExit', '-Command', "& '$venvActivate'; uvicorn api:api --host 127.0.0.1 --port 8000" -WorkingDirectory $projectRoot

# 7. Start the Node backend in a new terminal
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$backendRoot'; npm run dev" -WorkingDirectory $projectRoot

# 8. Start the frontend in a new terminal
Start-Process powershell -ArgumentList '-NoExit', '-Command', "Set-Location '$frontendRoot'; npm run dev" -WorkingDirectory $projectRoot