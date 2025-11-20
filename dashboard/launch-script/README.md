# Install-LangIdDashboard.ps1 — Installer for Windows (NSSM)

This document explains how to use the `Install-LangIdDashboard.ps1` script to install the dashboard `build/` directory as a Windows service using NSSM (the Non-Sucking Service Manager).

If you're starting from scratch, follow the steps under "Quick start".

## Purpose

The installer script performs these tasks:
- Ensures `serve` (the static file server) is available and uses it to serve `build/`.
- Installs a Windows service (via `nssm`) that runs `serve -s build -l <port>`.
- Configures service parameters (AppDirectory, stdout/stderr, restart behavior).
- Opens a Windows firewall rule for the chosen TCP port.
- Attempts to build the dashboard automatically if a `build/` directory is missing and `npm` is available.
- Tries multiple locations for logs if the configured `-LogDir` is not writable.

## Quick start (recommended)

1. Ensure prerequisites are installed:
   - Node.js and `npm` (v18+ recommended)
   - `nssm.exe` available (install separately or pass `-NssmPath`)
   - Run PowerShell as Administrator when installing the service (to open firewall and register service)

2. Build the dashboard and install the service:

```powershell
cd C:\Users\gsp\Projects\LangId-mr\dashboard
npm install
npm run build
cd .\launch-script
# Run installer (recommended: from an elevated PowerShell)
.\Install-LangIdDashboard.ps1 -DashboardDir 'C:\Users\gsp\Projects\LangId-mr\dashboard' -LogDir 'C:\Users\gsp\Projects\LangId-mr\dashboard\logs'
```

If you omit `-DashboardDir` the script will attempt to detect the dashboard directory as the parent of the `launch-script` folder.

## Usage / Flags

- `-DashboardDir <path>`
  - Path to the `dashboard` folder which contains `build/` (default: parent of the script).
- `-LogDir <path>`
  - Preferred log directory for `stdout` / `stderr`. If creation fails the script falls back to `${DashboardDir}\logs` and then to `%USERPROFILE%\LangIdDashboard\logs`.
- `-Port <number>`
  - TCP port to serve the dashboard on (default `3000`).
- `-NssmPath <path>`
  - Path to `nssm.exe`. If not provided the script looks for `nssm` in PATH and a few common locations.
- `-ServiceName <name>`
  - Service name to register under Windows Service Control Manager (default `LangIdDashboard`).

Example (no admin required to run the script, but some actions may fail without it):

```powershell
.\Install-LangIdDashboard.ps1 -DashboardDir 'C:\path\to\dashboard' -LogDir 'C:\path\to\logs' -Port 3000
```

## Auto-build behavior

If the `build/` folder is missing, the script will try to run `npm run build` in the `DashboardDir` if `npm` is available in PATH. If `npm` is not found or if the build fails, the installer will continue but the service will serve a missing `build` directory and return 404s.

If you prefer to control building manually, run `npm run build` yourself before invoking the installer.

## Permissions and Administrator privileges

- Creating a Windows service, opening firewall ports, and writing to system locations often require Administrator privileges. For a smooth install, run PowerShell as Administrator.
- If the script cannot create the configured `-LogDir` it will attempt writable fallbacks. You can also pass a `-LogDir` that you know is writable by the installing account.

## Verifying installation

- Check service status (NSSM):

```powershell
& 'C:\Program Files\nssm\nssm.exe' status LangIdDashboard
# or
Get-Service -Name LangIdDashboard
```

- Inspect NSSM parameters:

```powershell
& 'C:\Program Files\nssm\nssm.exe' get LangIdDashboard AppDirectory
& 'C:\Program Files\nssm\nssm.exe' get LangIdDashboard AppParameters
& 'C:\Program Files\nssm\nssm.exe' get LangIdDashboard AppStdout
```

- Check that `build/` exists and contains `index.html`:

```powershell
Test-Path .\build\index.html
```

- If you get a 404 when curling the site, the `build/` folder is likely missing or empty.

## Troubleshooting

- 404 responses for `/` or other static paths:
  - Confirm `build/index.html` exists. If not, run `npm run build` in the `dashboard` folder.

- `Access to the path 'D:\LangId-Data' is denied.` or similar when creating logs:
  - Either run the installer as Administrator or pass a `-LogDir` you control. The script will try fallbacks automatically.

- `nssm.exe not found`:
  - Install NSSM or pass `-NssmPath` with the full path to `nssm.exe`.

- `node.exe` or `npm` not found:
  - Ensure Node.js is installed and added to PATH.

- To uninstall the service:

```powershell
# Use the included uninstall script
cd .\launch-script
.\Uninstall-LangIdDashboard.ps1
```

## Security note

The installer opens a firewall rule to allow inbound TCP connections on the configured port. Only run this on trusted hosts and ensure firewall rules match your security policy.

---

If you want the installer to be non-destructive (no firewall change, no service registration) add a feature request and I can add flags to disable specific actions.
