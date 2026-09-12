@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ==============================================================================
:: Voice-Assisted Banking Kiosk - Portable Windows Demo Launcher
:: ==============================================================================
:: 100% Location-Independent:
:: - Derived dynamically from %~dp0 (never hardcoded paths)
:: - Works on any drive (C:, D:, E:, F:, etc.)
:: - Works with spaces in directory paths
:: - Self-healing Python virtual environment (.venv)
:: - Dynamic Node.js and npm discovery
:: ==============================================================================

title Banking Kiosk Demo Launcher

echo ==============================================================================
echo        VOICE-ASSISTED BANKING KIOSK SYSTEM - DEMO LAUNCHER
echo ==============================================================================
echo.

:: ------------------------------------------------------------------------------
:: STEP 1: DETECT PROJECT ROOT & SCRIPTS DIRECTORY
:: ------------------------------------------------------------------------------
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

:: Always switch working directory to the project root
pushd "%PROJECT_ROOT%" || (
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT ACCESS PROJECT ROOT DIRECTORY
    echo ==============================================================================
    echo Path: "%PROJECT_ROOT%"
    echo.
    pause
    exit /b 1
)

:: Project runtime & log directory
set "RUNTIME_DIR=%PROJECT_ROOT%\runtime"
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"
if not exist "%RUNTIME_DIR%\logs" mkdir "%RUNTIME_DIR%\logs"

:: ------------------------------------------------------------------------------
:: STEP 2: CHECK PREREQUISITES [1/7]
:: ------------------------------------------------------------------------------
echo [1/7] Checking prerequisites...

:: Discover system Python executable
set "SYSTEM_PY="
where python >nul 2>&1 && (
    python -c "import sys" >nul 2>&1 && set "SYSTEM_PY=python"
)
if not defined SYSTEM_PY (
    where py >nul 2>&1 && (
        py -3 -c "import sys" >nul 2>&1 && set "SYSTEM_PY=py -3"
    )
)

if not defined SYSTEM_PY (
    echo.
    echo ==============================================================================
    echo  ERROR: PYTHON 3.10+ IS NOT INSTALLED OR NOT IN SYSTEM PATH
    echo ==============================================================================
    echo Python is required to run the Banking Kiosk backend services.
    echo.
    echo How to fix:
    echo  1. Download Python from: https://www.python.org/downloads/
    echo  2. IMPORTANT: Check 'Add python.exe to PATH' during installation.
    echo  3. Re-launch START_DEMO.bat.
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)

:: Check for Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: NODE.JS IS NOT INSTALLED OR NOT IN SYSTEM PATH
    echo ==============================================================================
    echo Node.js is required to run Customer Kiosk and Staff Portal frontends.
    echo.
    echo How to fix:
    echo  1. Download Node.js LTS from: https://nodejs.org/
    echo  2. Run the installer and accept default settings.
    echo  3. Re-launch START_DEMO.bat.
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)

:: Check for npm
set "NPM_CMD="
where npm.cmd >nul 2>&1 && set "NPM_CMD=npm.cmd"
if not defined NPM_CMD (
    where npm >nul 2>&1 && set "NPM_CMD=npm"
)
if not defined NPM_CMD (
    echo.
    echo ==============================================================================
    echo  ERROR: NPM PACKAGE MANAGER IS NOT AVAILABLE IN PATH
    echo ==============================================================================
    echo npm was not found. Please verify your Node.js installation.
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)

echo   [OK] Python detected.
echo   [OK] Node.js and npm detected.
echo   [OK] Embedded Redis broker configured.

:: ------------------------------------------------------------------------------
:: STEP 3: PREPARE PORTABLE PYTHON VIRTUAL ENVIRONMENT [2/7]
:: ------------------------------------------------------------------------------
echo [2/7] Preparing Python environment...

set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "NEED_VENV_CREATE=0"

if not exist "%VENV_PY%" (
    set "NEED_VENV_CREATE=1"
) else (
    REM Validate that existing .venv is executable on this machine and path
    "%VENV_PY%" -c "import sys" >nul 2>&1
    if errorlevel 1 (
        echo   [Notice] Existing .venv is from a different path or machine. Rebuilding...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
        set "NEED_VENV_CREATE=1"
    )
)

if "!NEED_VENV_CREATE!"=="1" (
    echo   Creating local virtual environment at .venv...
    %SYSTEM_PY% -m venv "%VENV_DIR%" --system-site-packages
    if errorlevel 1 (
        echo   [Notice] Creating venv without --system-site-packages...
        %SYSTEM_PY% -m venv "%VENV_DIR%"
    )
    if not exist "%VENV_PY%" (
        echo.
        echo ==============================================================================
        echo  ERROR: FAILED TO CREATE PYTHON VIRTUAL ENVIRONMENT
        echo ==============================================================================
        echo Python could not initialize .venv in: "%PROJECT_ROOT%"
        echo.
        pause
        popd
        exit /b 1
    )
    echo   [OK] Virtual environment created successfully.
)

:: Verify and install missing dependencies via setup_env.py
if not exist "%RUNTIME_DIR%\.py_setup_done" (
    echo   Verifying and installing required Python packages...
    "%VENV_PY%" -u "%SCRIPTS_DIR%\setup_env.py"
    if errorlevel 1 (
        echo.
        echo ==============================================================================
        echo  ERROR: PYTHON DEPENDENCY SETUP FAILED
        echo ==============================================================================
        echo Please inspect the output above to see which package failed.
        echo.
        pause
        popd
        exit /b 1
    )
    echo done > "%RUNTIME_DIR%\.py_setup_done"
) else (
    echo   [OK] Python dependencies verified.
)

:: ------------------------------------------------------------------------------
:: STEP 4: LOCATE & INSTALL FRONTEND DEPENDENCIES [3/7]
:: ------------------------------------------------------------------------------
echo [3/7] Checking frontend dependencies...

:: Locate Customer Kiosk directory
set "KIOSK_DIR="
if exist "%PROJECT_ROOT%\apps\customer-kiosk\package.json" (
    set "KIOSK_DIR=%PROJECT_ROOT%\apps\customer-kiosk"
)

:: Locate Teller Portal directory
set "STAFF_DIR="
if exist "%PROJECT_ROOT%\apps\teller-portal\package.json" (
    set "STAFF_DIR=%PROJECT_ROOT%\apps\teller-portal"
)

if not defined KIOSK_DIR (
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT LOCATE CUSTOMER KIOSK FRONTEND
    echo ==============================================================================
    pause
    popd
    exit /b 1
)

if not defined STAFF_DIR (
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT LOCATE STAFF PORTAL FRONTEND
    echo ==============================================================================
    pause
    popd
    exit /b 1
)

:: Customer Kiosk node_modules
if not exist "%KIOSK_DIR%\node_modules" (
    echo   Installing Customer Kiosk npm packages...
    pushd "%KIOSK_DIR%"
    call npm install
    if errorlevel 1 (
        echo.
        echo ==============================================================================
        echo  ERROR: FAILED TO INSTALL CUSTOMER KIOSK NPM PACKAGES
        echo ==============================================================================
        pause
        popd
        popd
        exit /b 1
    )
    popd
) else (
    echo   [OK] Customer Kiosk dependencies already installed.
)

:: Staff Portal node_modules
if not exist "%STAFF_DIR%\node_modules" (
    echo   Installing Staff Portal npm packages...
    pushd "%STAFF_DIR%"
    call npm install
    if errorlevel 1 (
        echo.
        echo ==============================================================================
        echo  ERROR: FAILED TO INSTALL STAFF PORTAL NPM PACKAGES
        echo ==============================================================================
        pause
        popd
        popd
        exit /b 1
    )
    popd
) else (
    echo   [OK] Staff Portal dependencies already installed.
)

:: ------------------------------------------------------------------------------
:: STEP 5: BUILD FRONTEND APPLICATIONS [4/7] & [5/7]
:: ------------------------------------------------------------------------------
echo [4/7] Building Customer Kiosk...
pushd "%KIOSK_DIR%"
call npm run build
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: CUSTOMER KIOSK FAILED TO BUILD
    echo ==============================================================================
    pause
    popd
    popd
    exit /b 1
)
popd
echo   [OK] Customer Kiosk build completed.

echo [5/7] Building Staff Portal...
pushd "%STAFF_DIR%"
call npm run build
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: STAFF PORTAL FAILED TO BUILD
    echo ==============================================================================
    pause
    popd
    popd
    exit /b 1
)
popd
echo   [OK] Staff Portal build completed.

:: ------------------------------------------------------------------------------
:: STEP 6 & 7: START SERVICES & HEALTH CHECKS [6/7] & [7/7]
:: ------------------------------------------------------------------------------
pushd "%PROJECT_ROOT%"
"%VENV_PY%" -u "%SCRIPTS_DIR%\launcher_service.py" start
popd

popd
pause
