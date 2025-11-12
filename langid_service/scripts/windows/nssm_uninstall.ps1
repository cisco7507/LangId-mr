<#
nssm_uninstall.ps1
Removes the LangId API Windows service and optional firewall rule.
RUN AS ADMINISTRATOR
#>

param(
  [string]$ServiceName = "LangIdAPI",
  [int]   $Port        = 8080,
  [switch]$RemoveFirewall = $true
)

$ErrorActionPreference = "Stop"

# Find nssm
$nssmCmd = Get-Command "nssm.exe" -ErrorAction SilentlyContinue
if ($nssmCmd) { $nssm = $nssmCmd.Source } else { $nssm = $null }
if (-not $nssm) {
  $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
  $local = Join-Path $scriptDir "nssm.exe"
  if (Test-Path $local) { $nssm = $local } else { Write-Error "nssm.exe not found."; }
}

# Stop and remove
& $nssm stop   $ServiceName  2>$null
& $nssm remove $ServiceName confirm

# Firewall
if ($RemoveFirewall) {
  $ruleName = "LangId API $Port"
  $rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
  if ($rule) { Remove-NetFirewallRule -DisplayName $ruleName | Out-Null }
}

Write-Host "Service '$ServiceName' removed."