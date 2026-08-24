param(
    [string]$Config = "configs/development.json",
    [string]$TobiiHostname = "",
    [ValidateSet("tcp", "udp")]
    [string]$TobiiRtspTransport = "tcp",
    [switch]$TobiiGazeOnly,
    [string]$Python = "",
    [switch]$BrainCo,
    [switch]$NoBrainCo,
    [switch]$C3PolicyV2
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

if ($BrainCo -and $NoBrainCo) {
    throw "Use either -BrainCo or -NoBrainCo, not both."
}

if ($C3PolicyV2) {
    if ($PSBoundParameters.ContainsKey("Config")) {
        throw "Use either -Config or -C3PolicyV2, not both."
    }
    $Config = "configs/development_c3_v2.json"
}
$env:PYTHONUTF8 = "1"
$env:PYTHONFAULTHANDLER = "1"

# VS Code and already-open PowerShell windows do not automatically receive
# user environment variables written after they were launched.
if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_API_KEY)) {
    $env:DASHSCOPE_API_KEY = [Environment]::GetEnvironmentVariable(
        "DASHSCOPE_API_KEY", "User"
    )
}
if ([string]::IsNullOrWhiteSpace($env:DASHSCOPE_MODEL)) {
    $env:DASHSCOPE_MODEL = [Environment]::GetEnvironmentVariable(
        "DASHSCOPE_MODEL", "User"
    )
}

if (-not $Python) {
    $Candidates = @(
        (Join-Path $ProjectRoot ".venv-win\Scripts\python.exe"),
        (Join-Path (Split-Path $ProjectRoot -Parent) ".venv-win\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    )
    $Python = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}

if (-not $Python) {
    throw "No Windows Python environment found. Create .venv-win as documented in docs/USAGE.md, or specify python.exe with -Python."
}

if (-not (Test-Path -LiteralPath $Python)) {
    throw "The interpreter specified by -Python does not exist: $Python"
}

$Arguments = @(
    "-X",
    "faulthandler",
    "-m",
    "recon_pipeline.cli",
    "--config",
    $Config,
    "--tobii",
    "--tobii-rtsp-transport",
    $TobiiRtspTransport
)

if ($TobiiHostname) {
    $Arguments += @("--tobii-hostname", $TobiiHostname)
}

if ($TobiiGazeOnly) {
    $Arguments += "--tobii-gaze-only"
}

# Formal runs require EEG, so BrainCo is enabled by default.  Keep -BrainCo as
# a backwards-compatible explicit flag and require -NoBrainCo for diagnostics.
if (-not $NoBrainCo) {
    $Arguments += "--brainco"
}

Push-Location -LiteralPath $ProjectRoot
try {
    & $Python @Arguments
    $ProcessExitCode = $LASTEXITCODE
    if ($ProcessExitCode -ne 0) {
        Write-Warning "Recon pipeline exited unexpectedly (process exit code: $ProcessExitCode)."
    }
    exit $ProcessExitCode
}
finally {
    Pop-Location
}
