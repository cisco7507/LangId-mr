[CmdletBinding()]
param(
  [string]$ServiceName   = "LangIdDashboard",
  [string]$DashboardDir  = "",
  [int]   $Port          = 3000,
  [string]$LogDir        = "C:\LangId-Data\logs",
  [string]$NssmPath      = ""
)

function Fail($m){ Write-Error $m; exit 1 }

Write-Host "==> Validating inputs..." -ForegroundColor Cyan
## Determine script root robustly (works when script is executed in different ways)
$scriptPath = $MyInvocation.MyCommand.Path
if (-not $scriptPath) { $scriptPath = $PSCommandPath }
if (-not $scriptPath) { $scriptPath = $PSScriptRoot }
if ($scriptPath) { $scriptRoot = Split-Path -Parent $scriptPath } else { $scriptRoot = (Get-Location).ProviderPath }

if (-not $DashboardDir) {
  # Default to the parent directory of this script (launch-script -> dashboard)
  $candidate = Resolve-Path -Path (Join-Path $scriptRoot "..") -ErrorAction SilentlyContinue
  if ($candidate) { $DashboardDir = $candidate.ProviderPath } else { $DashboardDir = Join-Path $scriptRoot ".." }
}

if (-not (Test-Path $DashboardDir)) {
  Write-Warning "DashboardDir '$DashboardDir' does not exist. Installer will continue but may not work as expected."
}

$buildPath = Join-Path $DashboardDir "build"
$indexHtml = Join-Path $buildPath "index.html"

# Ensure dependencies are installed
if (-not (Test-Path (Join-Path $DashboardDir "node_modules"))) {
  Write-Host "==> node_modules not found. Running 'npm install'..." -ForegroundColor Cyan
  $npmCmd = Get-Command npm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
  if ($npmCmd) {
    Push-Location $DashboardDir
    try { & $npmCmd install } finally { Pop-Location }
  } else {
    Write-Warning "npm not found. Cannot install dependencies."
  }
}

# Ensure build exists and is valid
if (-not (Test-Path $indexHtml)) {
  Write-Warning "Build artifact ($indexHtml) not found. Attempting to build..."
  
  # Check for npm/node, install via NVM if missing
  $npmCmd = Get-Command npm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
  
  if (-not $npmCmd) {
    Write-Host "==> npm not found. Checking for NVM..." -ForegroundColor Cyan
    $nvmCmd = Get-Command nvm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
    
    if (-not $nvmCmd) {
      Write-Host "    NVM not found. Installing nvm-windows..." -ForegroundColor Yellow
      $nvmUrl = "https://github.com/coreybutler/nvm-windows/releases/download/1.1.12/nvm-setup.exe"
      $nvmInstaller = Join-Path $env:TEMP "nvm-setup.exe"
      
      # Ensure TLS 1.2+ is used (crucial for GitHub)
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      
      try {
        Write-Host "    Downloading NVM from $nvmUrl ..."
        Invoke-WebRequest -Uri $nvmUrl -OutFile $nvmInstaller -UseBasicParsing -UserAgent "PowerShell-Downloader"
        Start-Process -FilePath $nvmInstaller -ArgumentList "/SILENT" -Wait
        Write-Host "    NVM installed." -ForegroundColor Green
        
        # Refresh env vars
        $env:NVM_HOME = [System.Environment]::GetEnvironmentVariable("NVM_HOME", "Machine")
        $env:NVM_SYMLINK = [System.Environment]::GetEnvironmentVariable("NVM_SYMLINK", "Machine")
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
      } catch {
        Write-Warning "Failed to install NVM: $($_.Exception.Message)"
      }
      if (Test-Path $nvmInstaller) { Remove-Item $nvmInstaller -Force }
    }

    # Check NVM again
    $nvmCmd = Get-Command nvm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
    if ($nvmCmd) {
      $nodeVer = Read-Host "Enter Node.js version to install (default: 22.13.1)"
      if ([string]::IsNullOrWhiteSpace($nodeVer)) { $nodeVer = "22.13.1" }
      
      Write-Host "    Installing Node.js v$nodeVer..." -ForegroundColor Cyan
      & nvm install $nodeVer
      & nvm use $nodeVer
      
      # Refresh env again
      $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
      $npmCmd = Get-Command npm -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
    }
  }

  if ($npmCmd) {
    Write-Host "==> Running 'npm run build' in $DashboardDir" -ForegroundColor Cyan
    try {
      Push-Location $DashboardDir
      & $npmCmd run build
      Pop-Location
      if (-not (Test-Path $indexHtml)) { Fail "Build failed: index.html not found in $buildPath" }
      Write-Host "    Build succeeded." -ForegroundColor Green
    } catch {
      try { Pop-Location } catch {}
      Fail "npm build failed: $($_.Exception.Message)"
    }
  } else {
    Fail "npm not found. Cannot build dashboard."
  }
} else {
  Write-Host "    Found valid build: $indexHtml" -ForegroundColor Green
}

Write-Host "==> Locating NSSM..." -ForegroundColor Cyan
if (-not $NssmPath) { $NssmPath = Get-Command nssm.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1 }
if (-not $NssmPath) {
  foreach($p in @(
    "C:\nssm\nssm.exe",
    "C:\tools\nssm\nssm.exe",
    "C:\Program Files\nssm\win64\nssm.exe",
    "C:\Program Files (x86)\nssm\win64\nssm.exe"
  )){ if(Test-Path $p){ $NssmPath = $p; break } }
}
if (-not $NssmPath) { Fail "nssm.exe not found. Install NSSM or pass -NssmPath." }
Write-Host "    NSSM: $NssmPath"

Write-Host "==> Ensuring 'serve' is installed..." -ForegroundColor Cyan
# Try to find serve.cmd first (Windows global bin)
$serveCmd = Get-Command serve.cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
if (-not $serveCmd) {
  # Some shells resolve just 'serve'
  $serveCmd = Get-Command serve -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
}

if (-not $serveCmd) {
  npm i -g serve | Out-Null
  $serveCmd = Get-Command serve.cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
  if (-not $serveCmd) { $serveCmd = Get-Command serve -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1 }
}

# As a last resort, use node + serve.js path
$useNodeServeJs = $false
if (-not $serveCmd) {
  # locate node
  $nodeExe = Get-Command node.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
  if (-not $nodeExe) {
    $nodeCandidate = "C:\Program Files\nodejs\node.exe"
    if (Test-Path $nodeCandidate) { $nodeExe = $nodeCandidate }
  }
  if (-not $nodeExe) { Fail "node.exe not found. Install Node.js (or add to PATH)." }

  # Try to locate serve.js under global prefix
  $npmPrefix = (& npm config get prefix).Trim()
  if (-not $npmPrefix) { Fail "Unable to determine npm global prefix." }
  $serveJs = Join-Path $npmPrefix "node_modules\serve\bin\serve.js"
  if (-not (Test-Path $serveJs)) {
    npm i -g serve | Out-Null
  }
  if (-not (Test-Path $serveJs)) {
    Fail "'serve' CLI not found after install. Check npm permissions and retry."
  }
  $useNodeServeJs = $true
}

Write-Host "    Using: " -NoNewline
if ($useNodeServeJs) { Write-Host "node + serve.js shim" } else { Write-Host $serveCmd }

Write-Host "==> Preparing logs..." -ForegroundColor Cyan
## Try to create the configured log dir; if that fails, fall back to writable locations.
$logCreated = $false
try {
  New-Item -ItemType Directory -Force -Path $LogDir -ErrorAction Stop | Out-Null
  $logCreated = $true
} catch {
  Write-Warning "Unable to create log dir '$LogDir': $($_.Exception.Message)"
}
if (-not $logCreated) {
  $fallback1 = Join-Path $DashboardDir "logs"
  try { New-Item -ItemType Directory -Force -Path $fallback1 -ErrorAction Stop | Out-Null; $LogDir = $fallback1; $logCreated = $true } catch {}
}
if (-not $logCreated) {
  $fallback2 = Join-Path $env:USERPROFILE "LangIdDashboard\logs"
  try { New-Item -ItemType Directory -Force -Path $fallback2 -ErrorAction Stop | Out-Null; $LogDir = $fallback2; $logCreated = $true } catch {}
}
if (-not $logCreated) { Write-Warning "Logs directory could not be created; service will be installed but logs may not be available." }

$stdoutLog = Join-Path $LogDir "dashboard_stdout.log"
$stderrLog = Join-Path $LogDir "dashboard_stderr.log"

# Remove existing service if present
& $NssmPath status $ServiceName 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
  Write-Host "==> Removing existing service..." -ForegroundColor Yellow
  & $NssmPath stop $ServiceName | Out-Null
  Start-Sleep -Seconds 2
  & $NssmPath remove $ServiceName confirm | Out-Null
  Start-Sleep -Seconds 1
}

Write-Host "==> Installing service '$ServiceName'..." -ForegroundColor Cyan
if ($useNodeServeJs) {
  # node serve.js …
  $nodeExe = Get-Command node.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source | Select-Object -First 1
  if (-not $nodeExe) { Fail "node.exe not found (unexpected)."}
  $args = @($serveJs, "-s","build","-l",$Port,"--no-clipboard","--single")
  & $NssmPath install $ServiceName $nodeExe $args | Out-Null
} else {
  # serve.cmd directly
  $args = @("-s","build","-l",$Port,"--no-clipboard","--single")
  & $NssmPath install $ServiceName $serveCmd $args | Out-Null
}

& $NssmPath set $ServiceName AppDirectory $DashboardDir | Out-Null
& $NssmPath set $ServiceName AppStdout   $stdoutLog   | Out-Null
& $NssmPath set $ServiceName AppStderr   $stderrLog   | Out-Null
& $NssmPath set $ServiceName AppRotateFiles 1         | Out-Null
& $NssmPath set $ServiceName AppRotateOnline 1        | Out-Null
& $NssmPath set $ServiceName AppRotateBytes 10485760  | Out-Null
& $NssmPath set $ServiceName AppNoConsole 1           | Out-Null
& $NssmPath set $ServiceName Start SERVICE_AUTO_START | Out-Null
& $NssmPath set $ServiceName AppExit Default Restart  | Out-Null
& $NssmPath set $ServiceName AppRestartDelay 5000     | Out-Null

Write-Host "==> Opening firewall (TCP $Port)..." -ForegroundColor Cyan
$ruleName = "LangIdDashboard_TCP_$Port"
if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
}

Write-Host "==> Starting service..." -ForegroundColor Cyan
& $NssmPath start $ServiceName | Out-Null

Write-Host ""
Write-Host "✅ Dashboard service installed." -ForegroundColor Green
Write-Host "   URL:  http://localhost:$Port"
Write-Host "   Logs: $stdoutLog / $stderrLog"