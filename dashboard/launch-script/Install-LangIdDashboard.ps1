[CmdletBinding()]
param(
  [string]$ServiceName   = "LangIdDashboard",
  [string]$DashboardDir  = "C:\LangId\dashboard",
  [int]   $Port          = 3000,
  [string]$LogDir        = "D:\LangId-Data\logs",
  [string]$NssmPath      = ""
)

function Fail($m){ Write-Error $m; exit 1 }

Write-Host "==> Validating inputs..." -ForegroundColor Cyan
$buildPath = Join-Path $DashboardDir "build"
if (-not (Test-Path $buildPath)) {
  Fail "Build folder not found: $buildPath. Run 'npm run build' first."
}

Write-Host "==> Locating NSSM..." -ForegroundColor Cyan
if (-not $NssmPath) { $NssmPath = (Get-Command nssm.exe -ErrorAction SilentlyContinue)?.Source }
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
$serveCmd = (Get-Command serve.cmd -ErrorAction SilentlyContinue)?.Source
if (-not $serveCmd) {
  # Some shells resolve just 'serve'
  $serveCmd = (Get-Command serve -ErrorAction SilentlyContinue)?.Source
}

if (-not $serveCmd) {
  npm i -g serve | Out-Null
  $serveCmd = (Get-Command serve.cmd -ErrorAction SilentlyContinue)?.Source
  if (-not $serveCmd) { $serveCmd = (Get-Command serve -ErrorAction SilentlyContinue)?.Source }
}

# As a last resort, use node + serve.js path
$useNodeServeJs = $false
if (-not $serveCmd) {
  # locate node
  $nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue)?.Source
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
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
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
  $nodeExe = (Get-Command node.exe -ErrorAction SilentlyContinue)?.Source
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