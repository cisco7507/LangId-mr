@echo off
REM -----------------------------------------------------------------
REM Submit-LangIdJob.bat
REM Wrapper to call Submit-LangIdJob.ps1 with the same semantics:
REM   - Silent JSON output
REM   - human_intervention flag
REM   - OutputDir support
REM -----------------------------------------------------------------

REM Require at least the FilePath
if "%~1"=="" (
    echo Usage: %~nx0 FilePath [ApiBaseUrl] [OutputDir]
    exit /b 1
)

setlocal ENABLEDELAYEDEXPANSION

REM Positional args
set "FILEPATH=%~1"
set "APIBASE=%~2"
set "OUTDIR=%~3"

REM Default API base if not provided
if "%APIBASE%"=="" (
    set "APIBASE=http://agn-vntg-ls01.production.ctv.ca:8080"
)

REM Locate the PS1 next to this BAT
set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%Submit-LangIdJob.ps1"

if not exist "%PS1%" (
    echo ERROR: PowerShell script not found: "%PS1%"
    endlocal
    exit /b 1
)

REM Call PowerShell with ExecutionPolicy bypassed for this script only.
REM We keep it silent; the PS1 will emit a single JSON object.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass ^
  -File "%PS1%" ^
  -FilePath "%FILEPATH%" ^
  -ApiBaseUrl "%APIBASE%" ^
  -OutputDir "%OUTDIR%"

set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%