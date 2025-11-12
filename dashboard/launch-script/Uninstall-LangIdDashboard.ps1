param(
  [string]$ServiceName = "LangIdDashboard",
  [string]$NssmPath = ""
)

if (-not $NssmPath) { $NssmPath = (Get-Command nssm.exe -ErrorAction SilentlyContinue)?.Source }
if (-not $NssmPath) { throw "nssm.exe not found. Pass -NssmPath or put it in PATH." }

& $NssmPath stop $ServiceName 2>$null | Out-Null
Start-Sleep -Seconds 2
& $NssmPath remove $ServiceName confirm | Out-Null

Write-Host "Removed service $ServiceName."