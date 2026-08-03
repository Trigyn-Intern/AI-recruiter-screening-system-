<#
.SYNOPSIS
  Run the AI Recruiter scenario matrix and write reports/report.html.

.DESCRIPTION
  Thin wrapper around tests/ui/run_scenario_matrix.py. The Python runner
  boots Ollama, FastAPI, the auth API, and the React dev server, then runs
  pytest with --junit-xml pointing at <repo>/reports/junit.json.

  This script then calls tests/render_report.py to convert the JUnit JSON
  into a structured HTML report at <repo>/reports/report.html. The file
  is overwritten on each run.

  No skills/ dependency.

.PARAMETER Filter
  Comma- or whitespace-separated list of scenario ids to run. Empty runs
  every scenario in tests/data/scenarios.yaml.

.EXAMPLE
  pwsh tests/run.ps1
  pwsh tests/run.ps1 -Filter python_ml_llama32
  pwsh tests/run.ps1 -Filter "python_ml_llama32,frontend_react_llama32"
#>
param(
    [string]$Filter = ""
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------
$projectRoot   = Split-Path -Parent $PSScriptRoot
$testsRoot     = Join-Path $projectRoot "tests"
$integrationRoot = Join-Path $testsRoot "integration"
$runner        = Join-Path $integrationRoot "run_scenario_matrix.py"
$renderer      = Join-Path $testsRoot "render_report.py"
$reportsDir    = Join-Path $projectRoot "reports"
$logDir        = Join-Path $reportsDir "logs"
$junitPath     = Join-Path $reportsDir "junit.json"
$reportPath    = Join-Path $reportsDir "report.html"
$scenarioYaml  = Join-Path $testsRoot "data\scenarios.yaml"

New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
New-Item -ItemType Directory -Path $logDir     -Force | Out-Null

# Delete old reports to prevent reusing cached/stale data
if (Test-Path $junitPath) { Remove-Item -Path $junitPath -Force }
if (Test-Path $reportPath) { Remove-Item -Path $reportPath -Force }

# ------------------------------------------------------------
# Python interpreter
# ------------------------------------------------------------
$pythonExe = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    $pythonExe = "python"
}

if (-not (Test-Path $runner))    { throw "Runner not found at $runner." }
if (-not (Test-Path $renderer))  { throw "Renderer not found at $renderer." }
if (-not (Test-Path $scenarioYaml)) { throw "Scenario config not found at $scenarioYaml." }

# ------------------------------------------------------------
# Build the runner argv
# ------------------------------------------------------------
$runnerArgs = @(
    $runner,
    "--log-dir", $logDir,
    "--junit",   $junitPath
)

if ($Filter) {
    $runnerArgs += @("--filter", $Filter)
}

$cmdLine = "$pythonExe " + ($runnerArgs | ForEach-Object { if ($_ -match "\s") { '"' + $_ + '"' } else { $_ } }) -join " "
Write-Host "[run.ps1] Executing: $cmdLine" -ForegroundColor Cyan

$exit = 0
try {
    # Temporarily set ErrorActionPreference to Continue for native command execution
    # in case PSNativeCommandUseErrorActionPreference is enabled in PowerShell 7.
    $oldPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    
    & $pythonExe $runnerArgs[0] $runnerArgs[1..($runnerArgs.Length-1)]
    $exit = $LASTEXITCODE
    
    $ErrorActionPreference = $oldPreference
} catch {
    $exit = $LASTEXITCODE
    if ($exit -eq 0) { $exit = 1 }
    $ErrorActionPreference = $oldPreference
}

if ($exit -ne 0) {
    Write-Host ""
    Write-Host "Runner failed with exit code $exit." -ForegroundColor Red
    Write-Host "Service logs are available in $logDir." -ForegroundColor Yellow
    # We do NOT exit here, so that the report can be generated with the test failures.
}

if (-not (Test-Path $junitPath)) {
    throw "JUnit JSON was not produced at $junitPath. Cannot generate report."
}

# ------------------------------------------------------------
# Render report.html
# ------------------------------------------------------------
Write-Host ""
Write-Host "[run.ps1] Generating HTML report at $reportPath..." -ForegroundColor Cyan

$renderArgs = @(
    $renderer,
    "--junit", $junitPath,
    "--yaml", $scenarioYaml,
    "--output", $reportPath
)
if ($Filter) {
    $renderArgs += @("--filter", $Filter)
} else {
    $renderArgs += @("--filter", "(all)")
}

& $pythonExe $renderArgs[0] $renderArgs[1..($renderArgs.Length-1)]
if ($LASTEXITCODE -ne 0) {
    throw "Renderer failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
if ($exit -eq 0) {
    Write-Host "Execution Successful!" -ForegroundColor Green
} else {
    Write-Host "Execution Finished with Test Failures!" -ForegroundColor Red
}
Write-Host "Report: $reportPath" -ForegroundColor Green
Write-Host "JUnit:  $junitPath" -ForegroundColor Gray
Write-Host "Logs:   $logDir" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Green

if ($exit -ne 0) {
    exit $exit
}

