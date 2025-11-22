<#
nssm_install.ps1  — Production installer for LangIdAPI (Windows Service)

RUN AS ADMINISTRATOR:

  Set-ExecutionPolicy RemoteSigned -Scope Process -Force
  cd C:\path\to\repo\langid_service\scripts\windows
  .\nssm_install.ps1 -ServiceName LangIdAPI

WHAT THIS DOES:
  - Automates NSSM installation (downloads if missing)
  - Automates Python installation (prompts for version if missing)
  - Automates Virtual Environment setup (prompts for path)
  - Installs/updates an NSSM service that runs your venv’s Python DIRECTLY
  - Sets env vars for production, log files, auto-start, and firewall
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

  [string]$ClusterConfig = "",    # Path to cluster_config.json

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

if (-not (Test-IsAdmin)) {
    Write-Warning "This script requires Administrator privileges to install services and modify system settings."
    Write-Warning "Please run PowerShell as Administrator."
    exit 1
}

# Paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = (Resolve-Path (Join-Path $scriptDir "..\..")).Path   # langid_service dir
$repoRoot  = (Resolve-Path (Join-Path $root "..")).Path           # LangId-mr (parent) dir

# --- 1. NSSM Setup ---
Write-Host "--- Checking NSSM ---" -ForegroundColor Cyan
$nssmCmd = Get-Command "nssm.exe" -ErrorAction SilentlyContinue

if (-not $nssmCmd) {
    $localNssm = Join-Path $scriptDir "nssm.exe"
    if (Test-Path $localNssm) {
        Write-Host "Found local nssm.exe at $localNssm"
        $nssmPath = $localNssm
    } else {
        Write-Host "NSSM not found. Downloading..."
        $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
        $nssmZip = Join-Path $env:TEMP "nssm.zip"
        $nssmExtractDir = Join-Path $env:TEMP "nssm_extract"
        
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip
        Expand-Archive -Path $nssmZip -DestinationPath $nssmExtractDir -Force
        
        # Assume 64-bit architecture
        $nssmSource = Join-Path $nssmExtractDir "nssm-2.24\win64\nssm.exe"
        Copy-Item -Path $nssmSource -Destination $localNssm -Force
        
        Write-Host "NSSM downloaded and placed at $localNssm"
        $nssmPath = $localNssm
        
        # Cleanup
        Remove-Item $nssmZip -Force
        Remove-Item $nssmExtractDir -Recurse -Force
    }
    
    # Add to current PATH so we can use it immediately
    $env:Path += ";$scriptDir"
    $nssm = "nssm.exe"
} else {
    Write-Host "NSSM is already installed and in PATH."
    $nssm = "nssm.exe"
}


# --- 2. Python Setup ---
Write-Host "`n--- Checking Python ---" -ForegroundColor Cyan
try {
    $pyVersion = python --version 2>&1
    Write-Host "Found Python: $pyVersion"
} catch {
    Write-Host "Python not found in PATH."
    $installPy = Read-Host "Do you want to download and install Python now? (Y/N)"
    if ($installPy -eq 'Y') {
        $targetVer = Read-Host "Enter Python version to install (default: 3.12.0)"
        if ([string]::IsNullOrWhiteSpace($targetVer)) { $targetVer = "3.12.0" }
        
        Write-Host "Downloading Python $targetVer..."
        $pyInstallerUrl = "https://www.python.org/ftp/python/$targetVer/python-$targetVer-amd64.exe"
        $pyInstaller = Join-Path $env:TEMP "python_installer.exe"
        
        try {
            Invoke-WebRequest -Uri $pyInstallerUrl -OutFile $pyInstaller
            Write-Host "Installing Python (Global, PrependPath)... This may take a minute."
            # Install silently, for ALL USERS (InstallAllUsers=1), adding to PATH (PrependPath=1)
            # This installs to C:\Program Files\PythonXXX by default
            Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
            Write-Host "Python installed successfully."
            
            # Refresh PATH from registry so we can use it immediately
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        } catch {
            Write-Error "Failed to download or install Python. Please install manually."
            exit 1
        } finally {
            if (Test-Path $pyInstaller) { Remove-Item $pyInstaller -Force }
        }
    } else {
        Write-Error "Python is required. Please install it and re-run this script."
        exit 1
    }
}

# --- 3. Virtual Environment Setup ---
Write-Host "`n--- Checking Virtual Environment ---" -ForegroundColor Cyan

# Ask user for venv path, default to .venv in repo
$defaultVenv = Join-Path $root ".venv"
$venvPathInput = Read-Host "Enter path for virtual environment (default: $defaultVenv)"
if ([string]::IsNullOrWhiteSpace($venvPathInput)) {
    $venvDir = $defaultVenv
} else {
    $venvDir = $venvPathInput
}

$venvPy = Join-Path $venvDir "Scripts\python.exe"

if (-not $SkipVenvSetup) {
    if (-not (Test-Path $venvDir)) {
        Write-Host "Creating virtual environment at $venvDir..."
        python -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to create virtual environment."
            exit 1
        }
    } else {
        Write-Host "Virtual environment already exists at $venvDir"
    }

    if (-not (Test-Path $venvPy)) {
        Write-Error "Virtual environment python not found at $venvPy"
        exit 1
    }

    Write-Host "Installing dependencies from requirements.txt..."
    & $venvPy -m pip install -U pip wheel setuptools
    & $venvPy -m pip install -r (Join-Path $root "requirements.txt")
}

# --- 4. Service Installation (Existing Logic) ---
Write-Host "`n--- Configuring Service '$ServiceName' ---" -ForegroundColor Cyan

$appDir    = $repoRoot
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

# Preload Whisper Model
Write-Host "Preloading Whisper model '$ModelSize'..."
$env:CT2_TRANSLATORS_CACHE = $CacheDir

# (Simplified preload check logic for brevity, assuming standard usage)
# Running a quick check/download via python script
& $venvPy -c "
from faster_whisper import WhisperModel
import os
print(f'Checking model $ModelSize in $CacheDir...')
try:
    m = WhisperModel('$ModelSize', device='$Device', compute_type='$Compute', download_root=r'$CacheDir')
    print('Model loaded/downloaded successfully.')
except Exception as e:
    print(f'Error loading model: {e}')
    exit(1)
"

if ($LASTEXITCODE -ne 0) {
    Write-Warning "Model preload failed. Check logs/output."
}

# Service Install/Update
$exists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

if ($exists) {
  Write-Host "Service '$ServiceName' exists. Removing old version..."
  # Attempt stop, ignore errors if already stopped
  & $nssm stop $ServiceName 2>&1 | Out-Null
  & $nssm remove $ServiceName confirm
  Write-Host "Old service removed."
}

Write-Host ("Installing NSSM service '{0}' on {1}:{2}" -f $ServiceName, $BindHost, $Port)
# Use langid_service.app.main:app and run from repoRoot
& $nssm install $ServiceName $venvPy `
  "-m uvicorn langid_service.app.main:app --host $BindHost --port $Port --app-dir `"$repoRoot`""

# Core settings
& $nssm set $ServiceName AppDirectory $appDir
& $nssm set $ServiceName AppStdout    $stdoutLog
& $nssm set $ServiceName AppStderr    $stderrLog
& $nssm set $ServiceName Start        SERVICE_AUTO_START
& $nssm set $ServiceName AppStopMethodSkip 0
& $nssm set $ServiceName AppThrottle  1500

if ($LogonUser -and $LogonPass) {
  & $nssm set $ServiceName ObjectName "$LogonUser" "$LogonPass"
}

# Environment
$envPairs = @(
  "USE_MOCK_DETECTOR=0",
  "WHISPER_MODEL_SIZE=$ModelSize",
  "WHISPER_DEVICE=$Device",
  "WHISPER_COMPUTE=$Compute",
  "MAX_WORKERS=$MaxWorkers",
  "CT2_TRANSLATORS_CACHE=$CacheDir",
  "APP_HOST=$BindHost",
  "APP_PORT=$Port",
  "PYTHONPATH=$repoRoot"
)

if ($ClusterConfig) {
  $envPairs += "LANGID_CLUSTER_CONFIG_FILE=$ClusterConfig"
}

foreach ($kv in $envPairs) {
  & $nssm set $ServiceName AppEnvironmentExtra $kv
}

# Start/Restart
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

# Firewall
if ($OpenFirewall) {
    $ruleName = "LangId API $Port"
    $existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $existingRule) {
      New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
      Write-Host "Firewall rule created: $ruleName"
    } else {
      Write-Host "Firewall rule already present: $ruleName"
    }
}

Write-Host "Done."
Write-Host ("Status: nssm status {0}" -f $ServiceName)
Write-Host ("Health: http://{0}:{1}/healthz" -f $BindHost, $Port)