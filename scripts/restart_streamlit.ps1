# Restart Streamlit without PowerShell NUL redirection issues.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\restart_streamlit.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot | Out-Null

$venvActivate = Join-Path $repoRoot "samajh-env\Scripts\Activate.ps1"
if (Test-Path $venvActivate) {
    & $venvActivate
}

# Stop any existing Streamlit processes (ignore if none running)
Get-Process streamlit -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Start the app
streamlit run frontend/streamlit_omni_app_v2.py --logger.level=error
