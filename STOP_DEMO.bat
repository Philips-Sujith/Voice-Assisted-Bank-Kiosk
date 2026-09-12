@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ==============================================================================
:: Voice-Assisted Banking Kiosk - Portable Windows Demo Stopper
:: ==============================================================================
:: Safely shuts down all running processes associated with the Banking Kiosk demo:
::   - Module 1: Customer Kiosk (port 5173)
::   - Module 2: Voice AI (port 8002)
::   - Module 3: Central Backend (port 8000)
::   - Module 4: Face Authentication (port 8003)
::   - Module 5: Security QR (port 8001)
::   - Module 6: Staff Portal (port 5174)
::   - Redis Protocol Broker (port 6379)
:: ==============================================================================

title Banking Kiosk Demo Stopper

:: Determine project root dynamically from BAT location
set "PROJECT_ROOT=%~dp0"
if "%PROJECT_ROOT:~-1%"=="\" if not "%PROJECT_ROOT:~-2%"==":\" set "PROJECT_ROOT=%PROJECT_ROOT:~0,-1%"

pushd "%PROJECT_ROOT%" || (
    echo ERROR: Could not access project directory: "%PROJECT_ROOT%"
    pause
    exit /b 1
)

:: Locate directory containing launcher_service.py
set "ACTIVE_DIR=%PROJECT_ROOT%"
if not exist "%ACTIVE_DIR%\launcher_service.py" (
    if exist "%PROJECT_ROOT%\Bank_fixed_patch\launcher_service.py" (
        set "ACTIVE_DIR=%PROJECT_ROOT%\Bank_fixed_patch"
    )
)

:: Locate Python executable
set "PYTHON_EXE="
if exist "%ACTIVE_DIR%\.venv\Scripts\python.exe" (
    "%ACTIVE_DIR%\.venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%ACTIVE_DIR%\.venv\Scripts\python.exe"
)
if not defined PYTHON_EXE if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    "%PROJECT_ROOT%\.venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
)
if not defined PYTHON_EXE (
    where python >nul 2>&1 && set "PYTHON_EXE=python"
)
if not defined PYTHON_EXE (
    where py >nul 2>&1 && set "PYTHON_EXE=py -3"
)

if defined PYTHON_EXE (
    if exist "%ACTIVE_DIR%\launcher_service.py" (
        pushd "%ACTIVE_DIR%"
        "%PYTHON_EXE%" "%ACTIVE_DIR%\launcher_service.py" stop
        popd
        goto :CLEANUP
    )
)

:: Fallback if python or launcher_service is unavailable:
echo Cleaning up demo services using port matching...
for %%P in (6379 8001 8003 8000 8002 5174 5173) do (
    for /f "tokens=5" %%a in ('netstat -a -n -o ^| findstr /r ":%%P\>"') do (
        if not "%%a"=="0" (
            echo Stopping process on port %%P (PID %%a)...
            taskkill /f /t /pid %%a >nul 2>&1
        )
    )
)

:CLEANUP
:: Clean up runtime files
if exist "%ACTIVE_DIR%\runtime\demo_pids.json" del /q "%ACTIVE_DIR%\runtime\demo_pids.json" >nul 2>&1
if exist "%PROJECT_ROOT%\runtime\demo_pids.json" del /q "%PROJECT_ROOT%\runtime\demo_pids.json" >nul 2>&1
if exist "%ACTIVE_DIR%\.runtime\demo_pids.json" del /q "%ACTIVE_DIR%\.runtime\demo_pids.json" >nul 2>&1

popd
echo.
echo All demo services have terminated.
echo You can run START_DEMO.bat to restart anytime.
echo.
ping 127.0.0.1 -n 3 >nul 2>&1
