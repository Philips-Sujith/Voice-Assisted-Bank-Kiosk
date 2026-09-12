@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ==============================================================================
:: Voice-Assisted Banking Kiosk - Portable Windows Demo Stopper
:: ==============================================================================
:: Safely shuts down all running processes associated with the Banking Kiosk demo:
::   - Customer Kiosk (port 5173)
::   - Voice Service (port 8002)
::   - Banking API (port 8000)
::   - Identity Service (port 8003)
::   - Security Service (port 8001)
::   - Teller Portal (port 5174)
::   - Redis Protocol Broker (port 6379)
:: ==============================================================================

title Banking Kiosk Demo Stopper

:: Determine project root and scripts directory dynamically
set "CURR_DIR=%~dp0"
if "%CURR_DIR:~-1%"=="\" if not "%CURR_DIR:~-2%"==":\" set "CURR_DIR=%CURR_DIR:~0,-1%"

if exist "%CURR_DIR%\launcher_service.py" (
    set "SCRIPTS_DIR=%CURR_DIR%"
    pushd "%CURR_DIR%\.."
    set "PROJECT_ROOT=!CD!"
    popd
) else if exist "%CURR_DIR%\scripts\launcher_service.py" (
    set "PROJECT_ROOT=%CURR_DIR%"
    set "SCRIPTS_DIR=%CURR_DIR%\scripts"
) else (
    set "PROJECT_ROOT=%CURR_DIR%"
    set "SCRIPTS_DIR=%CURR_DIR%"
)

pushd "%PROJECT_ROOT%" || (
    echo ERROR: Could not access project directory: "%PROJECT_ROOT%"
    pause
    exit /b 1
)

:: Locate Python executable
set "PYTHON_EXE="
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
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
    if exist "%SCRIPTS_DIR%\launcher_service.py" (
        pushd "%PROJECT_ROOT%"
        "%PYTHON_EXE%" "%SCRIPTS_DIR%\launcher_service.py" stop
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
