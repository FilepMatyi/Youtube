$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    Write-Error "A helyi Python-környezet hiányzik. Először futtasd a README.md Windows telepítési lépéseit."
    exit 1
}

& $pythonExe -m streamlit run (Join-Path $projectRoot "app.py") --server.address localhost
