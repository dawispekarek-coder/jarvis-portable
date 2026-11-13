@echo off
rem START_JARVIS.cmd — double-click entry point for portable Jarvis.
rem Launches the companion UI (browser window) + starts the DevinBridge
rem daemon if it isn't running. Shows errors instead of flashing away.
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python 3.10+ not found on PATH.
    echo Install it from https://www.python.org/downloads/ and tick
    echo "Add python.exe to PATH" during setup, then run this again.
    pause
    exit /b 1
)

echo Launching Jarvis companion UI...
start "" %PY% launch_companion.pyw

rem DevinBridge daemon: start only if not already running
powershell -NoProfile -Command "if (-not (Get-CimInstance Win32_Process -Filter \"CommandLine like '%%DevinBridge.daemon%%'\" -ErrorAction SilentlyContinue)) { Start-Process -FilePath '%PY: =%' -ArgumentList '-m','DevinBridge.daemon' -WorkingDirectory '%CD%' -WindowStyle Hidden }" 2>nul

echo.
echo UI should open in your browser at http://127.0.0.1:7430
echo If nothing opens after ~30s, run: powershell -ExecutionPolicy Bypass -File setup.ps1
echo.
