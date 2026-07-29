<#
.SYNOPSIS
  Run an OWASP ZAP baseline scan against the local AI Recruiter stack.

.DESCRIPTION
  Thin wrapper around the ZAP Docker image. The runner does the
  following:

    1. Confirms Docker Desktop is running.
    2. Pulls the zaproxy/zap-stable image if not present.
    3. Verifies the local app stack is up on the expected ports.
    4. Runs zap-baseline.py against one or more URLs.
    5. Writes the HTML report to reports/zap/zap-baseline-report.html.

.PARAMETER Target
  URL to scan. Default: http://host.docker.internal:5173 (the React
  frontend). Other useful values: http://host.docker.internal:4000
  (Express auth API), http://host.docker.internal:8000 (FastAPI).

.PARAMETER ReportName
  Stem for the output HTML file. Default: zap-baseline-report.

.EXAMPLE
  pwsh scripts/run-zap.ps1
  pwsh scripts/run-zap.ps1 -Target "http://host.docker.internal:4000"
  pwsh scripts/run-zap.ps1 -Target "http://host.docker.internal:8000" -ReportName zap-fastapi
#>
param(
    [string]$Target = "http://host.docker.internal:5173",
    [string]$ReportName = "zap-baseline-report"
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# Prerequisite 1: Docker Desktop must be running
# ------------------------------------------------------------
Write-Host "[zap] checking Docker Desktop..."
$dockerInfo = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[zap] FAIL: Docker is not running."
    Write-Host "[zap] start Docker Desktop and re-run this script."
    Write-Host "[zap] on Windows: open Docker Desktop from the Start menu."
    Write-Host "[zap] on macOS:   open Docker from Applications."
    Write-Host "[zap] on Linux:   sudo systemctl start docker"
    Write-Host ""
    exit 1
}
Write-Host "[zap] Docker is running"

# ------------------------------------------------------------
# Prerequisite 2: the local app stack must be up
# ------------------------------------------------------------
foreach ($pair in @(
    @{ Name = "FastAPI";  Url = "http://127.0.0.1:8000/health" },
    @{ Name = "Auth API"; Url = "http://127.0.0.1:4000/api/health" },
    @{ Name = "Frontend"; Url = "http://127.0.0.1:5173" }
)) {
    $ok = $false
    try {
        $null = Invoke-WebRequest -Uri $pair.Url -UseBasicParsing -TimeoutSec 2
        $ok = $true
    } catch {}
    if (-not $ok) {
        Write-Host ""
        Write-Host "[zap] FAIL: $($pair.Name) is not responding at $($pair.Url)"
        Write-Host "[zap] start the stack first:  pwsh start-app.ps1"
        Write-Host "[zap] then re-run this script."
        Write-Host ""
        exit 1
    }
}
Write-Host "[zap] app stack is up"

# ------------------------------------------------------------
# Prerequisite 3: pull the ZAP image if missing
# ------------------------------------------------------------
$image = "zaproxy/zap-stable"
$haveImage = docker images --format "{{.Repository}}:{{.Tag}}" | Select-String -SimpleMatch $image
if (-not $haveImage) {
    Write-Host "[zap] pulling $image..."
    docker pull $image
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[zap] FAIL: docker pull failed"
        exit 1
    }
}
Write-Host "[zap] image $image is present"

# ------------------------------------------------------------
# Run the baseline scan
# ------------------------------------------------------------
$reportDir = Join-Path (Get-Location) "reports/zap"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$htmlOut = Join-Path $reportDir "$ReportName.html"

Write-Host "[zap] running baseline scan against $Target"
Write-Host "[zap] report will be at: $htmlOut"

docker run --rm `
    -v "${reportDir}:/zap/wrk/:rw" `
    -t zaproxy/zap-stable `
    zap-baseline.py `
    -t $Target `
    -r "$ReportName.html" `
    -I

if ($LASTEXITCODE -ne 0) {
    Write-Host "[zap] FAIL: ZAP scan exited $LASTEXITCODE"
    Write-Host "[zap] report (if any): $htmlOut"
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[zap] PASS - report at: $htmlOut"
Write-Host "[zap] open with: Start-Process $htmlOut"
