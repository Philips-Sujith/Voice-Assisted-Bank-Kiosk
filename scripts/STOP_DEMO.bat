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

set "CURR_DIR=%~dp0"
if "%CURR_DIR:~-1%"=="\" if not "%CURR_DIR:~-2%"==":\" set "CURR_DIR=%CURR_DIR:~0,-1%"

if exist "%CURR_DIR%\launcher_service.py" goto :DIR_IN_SCRIPTS
if exist "%CURR_DIR%\scripts\launcher_service.py" goto :DIR_IN_ROOT

:: Fallback
set "PROJECT_ROOT=%CURR_DIR%"
set "SCRIPTS_DIR=%CURR_DIR%"
goto :PATHS_DONE

:DIR_IN_SCRIPTS
set "SCRIPTS_DIR=%CURR_DIR%"
pushd "%CURR_DIR%\.."
set "PROJECT_ROOT=!CD!"
popd
goto :PATHS_DONE

:DIR_IN_ROOT
set "PROJECT_ROOT=%CURR_DIR%"
set "SCRIPTS_DIR=%CURR_DIR%\scripts"
goto :PATHS_DONE

:PATHS_DONE
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

:: Fallback if python is unavailable: Only terminate tracked PIDs from runtime
echo Notice: Python environment not found for launcher_service.
if exist "%PROJECT_ROOT%\runtime\pids" (
    echo Cleaning up tracked Bank processes...
    for %%f in ("%PROJECT_ROOT%\runtime\pids\*.json") do (
        for /f "tokens=2 delims=:, " %%p in ('findstr /i "\"pid\"" "%%f"') do (
            taskkill /f /t /pid %%p >nul 2>&1
        )
        del /f /q "%%f" >nul 2>&1
    )
)

:CLEANUP
if exist "%PROJECT_ROOT%\runtime\demo_pids.json" del /q "%PROJECT_ROOT%\runtime\demo_pids.json" >nul 2>&1


popd
echo.
echo All demo services have terminated.
echo You can run START_DEMO.bat to restart anytime.
echo.
ping 127.0.0.1 -n 3 >nul 2>&1
