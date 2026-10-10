$ErrorActionPreference = "Stop"

# Avoid OpenBLAS contention across uvicorn workers
$env:OMP_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:HF_HUB_OFFLINE = "1"

$projectRoot = $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$testingRoot = Join-Path $projectRoot "frontend-test"
$vectorStoreRoot = Join-Path $projectRoot "vector_store"
$venvActivate = Join-Path $projectRoot "venv\Scripts\Activate.ps1"

$backendEnv = Join-Path $backendRoot ".env"
$frontendEnv = Join-Path $frontendRoot ".env"
$testingEnv = Join-Path $testingRoot ".env"

if (-not (Test-Path $backendEnv)) {
    $exampleEnv = Join-Path $projectRoot ".env.example"
    if (Test-Path $exampleEnv) {
        Copy-Item $exampleEnv $backendEnv
        Write-Host "[env] Created backend/.env from .env.example"
    } else {
        New-Item -ItemType File -Path $backendEnv -Force | Out-Null
        Write-Host "[env] Created backend/.env for local configuration"
    }
}

function Get-BackendEnvValue {
    param([string]$Name)
    $value = ""
    $pattern = '^\s*' + [regex]::Escape($Name) + '\s*=(.*)$'
    if (Test-Path -LiteralPath $backendEnv) {
        foreach ($line in Get-Content -LiteralPath $backendEnv) {
            if ($line -match $pattern) {
                $value = $Matches[1].Trim()
            }
        }
    }
    if ($value.Length -ge 2) {
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
    }
    return $value
}

function Set-BackendEnvValue {
    param([string]$Name, [string]$Value)
    $lines = @()
    if (Test-Path -LiteralPath $backendEnv) {
        $lines = @(Get-Content -LiteralPath $backendEnv)
    }
    $pattern = '^\s*' + [regex]::Escape($Name) + '\s*='
    $found = $false
    for ($index = 0; $index -lt $lines.Count; $index++) {
        if ($lines[$index] -match $pattern) {
            $lines[$index] = "$Name=$Value"
            $found = $true
        }
    }
    if (-not $found) {
        $lines += "$Name=$Value"
    }
    Set-Content -LiteralPath $backendEnv -Value $lines -Encoding UTF8
}

function Test-PlaceholderValue {
    param([string]$Value)
    return [string]::IsNullOrWhiteSpace($Value) -or
        $Value -match '(?i)(SETUP_REQUIRED|YOUR_|REPLACE_WITH|CHANGE_ME|CHANGEME|example\.com)'
}

function Test-SafeJwtSecret {
    param([string]$Value)
    return (-not (Test-PlaceholderValue $Value)) -and
        ($Value.Length -ge 32) -and
        ($Value -notmatch '(?i)^(secret|password|changeme|development|dev|jwtsecret)')
}

function Test-SafeManagerEmail {
    param([string]$Value)
    return (-not (Test-PlaceholderValue $Value)) -and
        ($Value -match '^[^@\s]+@[^@\s]+\.[^@\s]+$')
}

function Test-SafeManagerPassword {
    param([string]$Value)
    if ((Test-PlaceholderValue $Value) -or $Value.Length -lt 12 -or
        $Value -ne $Value.Trim() -or $Value.Contains('#') -or
        $Value.Contains('"') -or $Value.Contains("'") -or
        $Value.Contains("`r") -or $Value.Contains("`n")) {
        return $false
    }
    return $Value -notmatch '(?i)^(manager@123|password|admin|changeme|changeit|letmein|welcome|qwerty|123456)'
}

function New-RandomJwtSecret {
    $bytes = New-Object byte[] 32
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $random.GetBytes($bytes)
        return [Convert]::ToBase64String($bytes)
    } finally {
        [Array]::Clear($bytes, 0, $bytes.Length)
        $random.Dispose()
    }
}

function Read-ManagerPassword {
    $securePassword = Read-Host "Manager password (at least 12 characters; input is hidden)" -AsSecureString
    $passwordPointer = [IntPtr]::Zero
    try {
        $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    } finally {
        if ($passwordPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
        }
        $securePassword.Dispose()
    }
}

function Initialize-AuthEnvironment {
    $managerEmail = Get-BackendEnvValue "SEED_MANAGER_EMAIL"
    if (-not (Test-SafeManagerEmail $managerEmail)) {
        Write-Host "[auth] Configure a personal manager account for this local clone."
        do {
            $managerEmail = (Read-Host "Manager email").Trim()
            if (-not (Test-SafeManagerEmail $managerEmail)) {
                Write-Host "[auth] Enter a valid, non-placeholder email address."
            }
        } while (-not (Test-SafeManagerEmail $managerEmail))
        Set-BackendEnvValue "SEED_MANAGER_EMAIL" $managerEmail
    }

    $jwtSecret = Get-BackendEnvValue "JWT_SECRET"
    if (-not (Test-SafeJwtSecret $jwtSecret)) {
        $jwtSecret = New-RandomJwtSecret
        Set-BackendEnvValue "JWT_SECRET" $jwtSecret
        Write-Host "[auth] Generated a local JWT secret and saved it in backend/.env."
    }

    $managerPassword = Get-BackendEnvValue "SEED_MANAGER_PASSWORD"
    if (-not (Test-SafeManagerPassword $managerPassword)) {
        do {
            $managerPassword = Read-ManagerPassword
            if (-not (Test-SafeManagerPassword $managerPassword)) {
                Write-Host "[auth] Password rejected. Use at least 12 characters and avoid common defaults."
            }
        } while (-not (Test-SafeManagerPassword $managerPassword))
        Set-BackendEnvValue "SEED_MANAGER_PASSWORD" $managerPassword
    }

    if (-not (Test-SafeJwtSecret $env:JWT_SECRET)) {
        $env:JWT_SECRET = $jwtSecret
    }
    if (-not (Test-SafeManagerPassword $env:SEED_MANAGER_PASSWORD)) {
        $env:SEED_MANAGER_PASSWORD = $managerPassword
    }
    if (-not (Test-SafeManagerEmail $env:SEED_MANAGER_EMAIL)) {
        $env:SEED_MANAGER_EMAIL = $managerEmail
    }
}

function Assert-SafeAuthEnvironment {
    $fileJwtSecret = Get-BackendEnvValue "JWT_SECRET"
    $fileManagerPassword = Get-BackendEnvValue "SEED_MANAGER_PASSWORD"
    $fileManagerEmail = Get-BackendEnvValue "SEED_MANAGER_EMAIL"
    $jwtSecret = if ($env:JWT_SECRET) { $env:JWT_SECRET } else { $fileJwtSecret }
    $managerPassword = if ($env:SEED_MANAGER_PASSWORD) { $env:SEED_MANAGER_PASSWORD } else { $fileManagerPassword }
    $managerEmail = if ($env:SEED_MANAGER_EMAIL) { $env:SEED_MANAGER_EMAIL } else { $fileManagerEmail }

    if (-not (Test-SafeJwtSecret $fileJwtSecret) -or
        -not (Test-SafeManagerPassword $fileManagerPassword) -or
        -not (Test-SafeManagerEmail $fileManagerEmail) -or
        -not (Test-SafeJwtSecret $jwtSecret) -or
        -not (Test-SafeManagerPassword $managerPassword) -or
        -not (Test-SafeManagerEmail $managerEmail)) {
        throw "Authentication settings are missing or unsafe. No auth service was started; review backend/.env and run this launcher again."
    }
}

Initialize-AuthEnvironment

if (-not (Test-Path $frontendEnv)) {
    "VITE_API_URL=http://localhost:4000`nVITE_FASTAPI_URL=http://localhost:8000`n" | Set-Content -Path $frontendEnv -Encoding UTF8
    Write-Host "[env] Created frontend/.env with the default local API URLs"
}
if (-not (Test-Path $testingEnv)) {
    "VITE_API_URL=http://localhost:4000`nVITE_FASTAPI_URL=http://localhost:8000`n" | Set-Content -Path $testingEnv -Encoding UTF8
    Write-Host "[env] Created frontend-test/.env with the default local API URLs"
}

New-Item -ItemType Directory -Path $vectorStoreRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backendRoot "data") -Force | Out-Null

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

function Test-PortOpen($port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.BeginConnect("127.0.0.1", $port, $null, $null) | Out-Null
        Start-Sleep -Milliseconds 200
        return $c.Connected
    } catch {
        return $false
    }
}

function Install-NodeDeps {
    param([string]$Name, [string]$Dir)
    if (-not (Test-Path (Join-Path $Dir "package.json"))) {
        Write-Host "[npm] skipping $Name (no package.json at $Dir)."
        return
    }
    if (Test-Path (Join-Path $Dir "node_modules")) {
        Write-Host "[npm] $Name dependencies already installed; skipping."
        return
    }
    Write-Host "[npm] installing $Name dependencies in $Dir..."
    Push-Location $Dir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed for $Name (exit $LASTEXITCODE)."
        }
    } finally {
        Pop-Location
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
Stop-IfUsingPort -Port 5173
Stop-IfUsingPort -Port 5174
Stop-IfUsingPort -Port 8000

# 3. Start Ollama on the original default port unless it is already up.
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

# 5b. Install Node dependencies for auth API, recruiter app, and testing dashboard.
Install-NodeDeps -Name "auth API"          -Dir $backendRoot
Install-NodeDeps -Name "recruiter frontend" -Dir $frontendRoot
Install-NodeDeps -Name "testing dashboard"  -Dir $testingRoot

# 6. Start the Python FastAPI analyzer on :8000.
# Use the venv interpreter explicitly so it does not accidentally run against
# a different Python install. The app object is api:api.
$uvicornCmd = ". '$venvActivate'; `$env:ANALYZE_MAX_INFLIGHT='4'; `$env:ANALYZE_TIMEOUT_S='90'; python -m uvicorn api:api --host 127.0.0.1 --port 8000 --workers 4"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $uvicornCmd -WorkingDirectory $projectRoot

# 7. Start the Node auth API (Express + in-process JSON store) on :4000.
Assert-SafeAuthEnvironment
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$backendRoot'; npm run dev" -WorkingDirectory $projectRoot

# 8. Start the React recruiter frontend on :5173.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendRoot'; npm run dev" -WorkingDirectory $projectRoot

# 9. Start the React testing dashboard on :5174.
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$testingRoot'; npm run dev" -WorkingDirectory $projectRoot

Write-Host ""
Write-Host "Stack starting. Wait ~10s for each window to settle."
Write-Host "  FastAPI (Ollama): http://127.0.0.1:8000"
Write-Host "  Auth API:         http://localhost:4000"
Write-Host "  Recruiter UI:     http://localhost:5173"
Write-Host "  Testing UI:       http://localhost:5174"
Write-Host "  Ollama:           http://127.0.0.1:11434"


#uvicorn api:api --reload --host 0.0.0.0 --port 8000
#for reload