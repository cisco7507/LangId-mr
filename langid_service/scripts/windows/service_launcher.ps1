# service_launcher.ps1 — run API from repo root using the venv's Python
$ErrorActionPreference = "Stop"

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location -LiteralPath $root

# Point explicitly to the venv's Python
$venvScripts = Join-Path $root ".venv\Scripts"
$venvPy      = Join-Path $venvScripts "python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) { throw "Venv Python not found at $venvPy" }

# Reasonable defaults if not provided by service env
if (-not $env:APP_HOST)              { $env:APP_HOST = "0.0.0.0" }
if (-not $env:APP_PORT)              { $env:APP_PORT = "8080" }
if (-not $env:USE_MOCK_DETECTOR)     { $env:USE_MOCK_DETECTOR  = "0" }
if (-not $env:WHISPER_MODEL_SIZE)    { $env:WHISPER_MODEL_SIZE = "tiny" }
if (-not $env:WHISPER_DEVICE)        { $env:WHISPER_DEVICE     = "cpu" }
if (-not $env:WHISPER_COMPUTE)       { $env:WHISPER_COMPUTE    = "int8" }
if (-not $env:CT2_TRANSLATORS_CACHE) { $env:CT2_TRANSLATORS_CACHE = Join-Path $root ".ctranslate2_cache" }

# Ensure folders
$null = New-Item -ItemType Directory -Force -Path (Join-Path $root "logs")
$null = New-Item -ItemType Directory -Force -Path (Join-Path $root "storage\input")
$null = New-Item -ItemType Directory -Force -Path (Join-Path $root "storage\output")
$null = New-Item -ItemType Directory -Force -Path $env:CT2_TRANSLATORS_CACHE

# Run the server via the venv's Python and our runner script
$runner = Join-Path $root "scripts\windows\run_server.py"
& $venvPy $runner