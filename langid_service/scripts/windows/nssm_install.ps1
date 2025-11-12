<#
nssm_install.ps1  — Production installer for LangIdAPI (Windows Service)

RUN AS ADMINISTRATOR:

  Set-ExecutionPolicy RemoteSigned -Scope Process -Force
  cd C:\Users\gsp\langid_service_windows_with_ci\langid_service\scripts\windows
  .\nssm_install.ps1 -ServiceName LangIdAPI

PREREQS (recommended):
  - Install a **desktop** (non-Store) x64 Python (e.g. C:\Program Files\Python311\python.exe)
  - Disable Windows Store Python aliases (Settings → Apps → App execution aliases → off for python/python3)
  - Install NSSM (e.g. `choco install nssm -y`) or put nssm.exe next to this script

WHAT THIS DOES:
  - Ensures logs/ and storage/ folders
  - Creates/updates .venv and installs requirements (unless -SkipVenvSetup)
  - Installs/updates an NSSM service that runs your venv’s Python DIRECTLY:
      "<repo>\.venv\Scripts\python.exe" -m uvicorn app.main:app --host <BindHost> --port <Port> --app-dir "<repo>"
    (This avoids the uvicorn.exe shim and Windows Store python path issues.)
  - Sets env vars for production (real detector), log files, auto-start, and firewall

TROUBLESHOOT:
  - Check logs\service.err.log / logs\service.out.log
  - `nssm get <ServiceName> Application|AppParameters|AppDirectory`
  - Uninstall: `nssm stop <ServiceName>` then `nssm remove <ServiceName> confirm`
#>

param(
  [string]$ServiceName = "LangIdAPI",
  [string]$BindHost    = "0.0.0.0",
  [int]   $Port        = 8080,

  [switch]$SkipVenvSetup = $false,

  [string]$ModelSize = "base",    # tiny|base|small|...
  [string]$Device    = "cpu",     # cpu|cuda (Windows CPU recommended here)
  [string]$Compute   = "int8",    # int8|int8_float16|float16|float32
  [int]   $MaxWorkers = 2,

  [string]$CacheDir = "",         # default: <repo>\.ctranslate2_cache

  [string]$LogonUser = "",        # optional: DOMAIN\user
  [string]$LogonPass = "",

  [switch]$OpenFirewall = $true
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
  try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  } catch { return $false }
}

# Paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = (Resolve-Path (Join-Path $scriptDir "..\..")).Path   # repo root

$venvDir   = Join-Path $root ".venv"
$venvPy    = Join-Path $venvDir "Scripts\python.exe"

$appDir    = $root
$logsDir   = Join-Path $root "logs"
$stdoutLog = Join-Path $logsDir "service.out.log"
$stderrLog = Join-Path $logsDir "service.err.log"

if (-not $CacheDir -or $CacheDir.Trim() -eq "") {
  $CacheDir = Join-Path $root ".ctranslate2_cache"
}

# Ensure folders
$null = New-Item -ItemType Directory -Force -Path $logsDir
$null = New-Item -ItemType Directory -Force -Path (Join-Path $root "storage\input")
$null = New-Item -ItemType Directory -Force -Path (Join-Path $root "storage\output")
$null = New-Item -ItemType Directory -Force -Path $CacheDir

# Locate nssm.exe
$nssmCmd = Get-Command "nssm.exe" -ErrorAction SilentlyContinue
if ($nssmCmd) { $nssm = $nssmCmd.Source } else { $nssm = $null }
if (-not $nssm) {
  $local = Join-Path $scriptDir "nssm.exe"
  if (Test-Path $local) {
    $nssm = $local
    Write-Host "Using local nssm.exe at $nssm"
  } else {
    Write-Error "nssm.exe not found. Install NSSM (choco install nssm -y) or place nssm.exe next to this script."
  }
}

# Create / update venv + pip deps
if (-not $SkipVenvSetup) {
  if (-not (Test-Path $venvDir)) {
    Write-Host "Creating venv at $venvDir"
    $py = (Get-Command python -ErrorAction SilentlyContinue)
    if (-not $py) {
      # fallback to a typical python.org install path
      $pyPath = "C:\Program Files\Python311\python.exe"
      if (!(Test-Path $pyPath)) {
        Write-Error "Python not found in PATH or at $pyPath. Install desktop Python 3.11 x64 and retry."
      }
      & $pyPath -m venv $venvDir
    } else {
      & $py.Source -m venv $venvDir
    }
  }

  if (-not (Test-Path $venvPy)) {
    Write-Error "Venv Python not found at $venvPy"
  }

  Write-Host "Installing dependencies from requirements.txt"
  & $venvPy -m pip install -U pip wheel setuptools
  & $venvPy -m pip install -r (Join-Path $root "requirements.txt")
}

# Verify venv python
if (-not (Test-Path $venvPy)) {
  Write-Error "Venv Python missing at $venvPy"
}

# --- Preload Whisper model into the cache so first service start is fast ---
Write-Host "Preloading Whisper model '$ModelSize' (device=$Device, compute=$Compute)..."

# Ensure the cache dir env var is set for the preload process
$env:CT2_TRANSLATORS_CACHE = $CacheDir

# A more robust detector: look recursively for typical CTranslate2 artifacts
function Test-ModelCached([string]$CacheRoot) {
  if (-not (Test-Path -LiteralPath $CacheRoot)) { return $false }
  $markers = @('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt')
  $hits = Get-ChildItem -LiteralPath $CacheRoot -Recurse -ErrorAction SilentlyContinue `
    | Where-Object { $markers -contains $_.Name }
  return ($hits.Count -gt 0)
}

if (-not (Test-ModelCached -CacheRoot $CacheDir)) {
  Write-Host "Model not found in cache dir: $CacheDir ; downloading… (one-time)"
  # Force Faster-Whisper to put the converted model under our cache dir
  & $venvPy -c @"
from faster_whisper import WhisperModel
import os
m = WhisperModel("$ModelSize", device="$Device", compute_type="$Compute", download_root=r"$CacheDir")
# Touch the pipeline to ensure the model is fully realized (some backends lazy-load)
# Transcribe 10ms of silence just to trigger full load without extra cost.
import numpy as np, soundfile as sf, tempfile
sr=16000
wav = (np.zeros(int(0.01*sr), dtype=np.float32), sr)
# Write a tiny temp file because transcribe expects a path/bytes-like for certain flows
with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
    sf.write(f.name, wav[0], wav[1]); path=f.name
# This call forces model to be ready; we ignore outputs
_ = list(m.transcribe(path, vad_filter=False, beam_size=1, temperature=0))
"@ 2>&1 | Tee-Object -Variable _preloadLogs | Out-Null

  if ($LASTEXITCODE -ne 0) {
    Write-Warning "Model preload returned code $LASTEXITCODE"
    # Print last few lines if something went wrong
    if ($_preloadLogs) { ($_preloadLogs | Select-Object -Last 20) | ForEach-Object { Write-Warning $_ } }
  }

  if (-not (Test-ModelCached -CacheRoot $CacheDir)) {
    # Show where Faster-Whisper might have written instead, to help debugging:
    $alt1 = Join-Path $env:LOCALAPPDATA "CTranslate2"
    $alt2 = Join-Path $env:LOCALAPPDATA "huggingface\hub"
    Write-Warning "Cache still not detected under: $CacheDir"
    Write-Warning "You can inspect possible alternate caches:"
    Write-Warning "  $alt1"
    Write-Warning "  $alt2"
    throw "Whisper model '$ModelSize' did not appear in cache '$CacheDir'. Check internet access, disk perms, or try another size."
  }
  Write-Host "Model '$ModelSize' cached successfully in: $CacheDir"
} else {
  Write-Host "Model already present in cache: $CacheDir"
}
# --- end preload ---
# Helper: does service exist?
function Test-ServiceExists([string]$Name) {
  $svc = Get-Service -Name $Name -ErrorAction SilentlyContinue
  if ($svc) { return $true } else { return $false }
}
$exists = Test-ServiceExists -Name $ServiceName

# Install or update service — IMPORTANT: run python -m uvicorn (not uvicorn.exe)
if (-not $exists) {
  Write-Host ("Installing NSSM service '{0}' on {1}:{2}" -f $ServiceName, $BindHost, $Port)
  & $nssm install $ServiceName $venvPy `
    "-m uvicorn app.main:app --host $BindHost --port $Port --app-dir `"$root`""
} else {
  Write-Host "Service '$ServiceName' exists. Updating configuration..."
  & $nssm set $ServiceName Application  $venvPy
  & $nssm set $ServiceName AppParameters "-m uvicorn app.main:app --host $BindHost --port $Port --app-dir `"$root`""
}

# Core settings
& $nssm set $ServiceName AppDirectory $appDir
& $nssm set $ServiceName AppStdout    $stdoutLog
& $nssm set $ServiceName AppStderr    $stderrLog
& $nssm set $ServiceName Start        SERVICE_AUTO_START
& $nssm set $ServiceName AppStopMethodSkip 0
& $nssm set $ServiceName AppThrottle  1500

# Optional: run under a specific service account
if ($LogonUser -and $LogonPass) {
  & $nssm set $ServiceName ObjectName "$LogonUser" "$LogonPass"
}

# Environment — set each key separately (works on PS 5.1/7 and all NSSM builds)
$envPairs = @(
  "USE_MOCK_DETECTOR=0",
  "WHISPER_MODEL_SIZE=$ModelSize",
  "WHISPER_DEVICE=$Device",
  "WHISPER_COMPUTE=$Compute",
  "MAX_WORKERS=$MaxWorkers",
  "CT2_TRANSLATORS_CACHE=$CacheDir",
  "APP_HOST=$BindHost",
  "APP_PORT=$Port"
)
foreach ($kv in $envPairs) {
  & $nssm set $ServiceName AppEnvironmentExtra $kv
}

# Start or restart service
try {
  if (-not $exists) {
    Write-Host "Starting service '$ServiceName'..."
    & $nssm start $ServiceName
  } else {
    Write-Host "Restarting service '$ServiceName'..."
    & $nssm restart $ServiceName
  }
} catch {
  Write-Warning "Service start/restart error: $($_.Exception.Message)"
}

# Open firewall if admin
if ($OpenFirewall) {
  if (Test-IsAdmin) {
    $ruleName = "LangId API $Port"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existingRule) {
      New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
      Write-Host "Firewall rule created: $ruleName"
    } else {
      Write-Host "Firewall rule already present: $ruleName"
    }
  } else {
    Write-Warning "Not elevated. Skipping firewall rule. Re-run as Administrator or add -OpenFirewall:$false."
  }
}

Write-Host "Done."
Write-Host ("Status: nssm status {0}" -f $ServiceName)
Write-Host ("Health: http://{0}:{1}/healthz" -f $BindHost, $Port)