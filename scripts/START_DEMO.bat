@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ==============================================================================
:: Voice-Assisted Banking Kiosk - Portable Windows Demo Launcher
:: ==============================================================================
:: 100% Location-Independent, Safe, and Robust:
:: - Derived dynamically from script location (never hardcoded paths)
:: - Version-aware Python interpreter detection (Python 3.11 prioritized, 3.10-3.12 supported)
:: - Explicitly prevents Python 3.14/3.13 source compilation issues (no Visual Studio needed)
:: - Self-healing project-local virtual environment (.venv)
:: - Automatic winget installation offer if Python 3.11 is missing
:: - Dynamic Node.js and npm discovery
:: - Bulletproof CMD batch syntax (no fragile nested parenthesized blocks)
:: ==============================================================================

title Banking Kiosk Demo Launcher

echo ==============================================================================
echo        VOICE-ASSISTED BANKING KIOSK SYSTEM - DEMO LAUNCHER
echo ==============================================================================
echo.

:: ------------------------------------------------------------------------------
:: STEP 0: DETECT PROJECT ROOT & SCRIPTS DIRECTORY
:: ------------------------------------------------------------------------------
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
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT ACCESS PROJECT ROOT DIRECTORY
    echo ==============================================================================
    echo Path: "%PROJECT_ROOT%"
    echo.
    pause
    exit /b 1
)

set "RUNTIME_DIR=%PROJECT_ROOT%\runtime"
if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"
if not exist "%RUNTIME_DIR%\logs" mkdir "%RUNTIME_DIR%\logs"

:: ------------------------------------------------------------------------------
:: STEP 1: CHECK PREREQUISITES [1/7]
:: ------------------------------------------------------------------------------
echo [1/7] Checking prerequisites...

set "SYSTEM_PY="
set "DETECTED_PY_VER="

:: Priority 1: Check py launcher for Python 3.11
py -3.11 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.11"
    goto :PYTHON_SELECTED
)

:: Priority 2: Check py launcher for Python 3.10
py -3.10 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.10"
    goto :PYTHON_SELECTED
)

:: Priority 3: Check py launcher for Python 3.12
py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.12"
    goto :PYTHON_SELECTED
)

:: Priority 4: Check if 'python' in PATH is a compatible version (3.10 to 3.12)
python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=python"
    goto :PYTHON_SELECTED
)

:: Priority 5: Check common Windows installation paths for Python 3.11
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        goto :PYTHON_SELECTED
    )
)
if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY=%ProgramFiles%\Python311\python.exe"
        goto :PYTHON_SELECTED
    )
)
if exist "C:\Python311\python.exe" (
    "C:\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY=C:\Python311\python.exe"
        goto :PYTHON_SELECTED
    )
)

:: No compatible Python found - inspect what version exists for diagnostic
for /f "tokens=*" %%v in ('py -3 -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "DETECTED_PY_VER=%%v"
if not defined DETECTED_PY_VER (
    for /f "tokens=*" %%v in ('python -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "DETECTED_PY_VER=%%v"
)

echo.
echo ==============================================================================
if defined DETECTED_PY_VER (
    echo  ERROR: INCOMPATIBLE PYTHON VERSION DETECTED (Python !DETECTED_PY_VER!)
    echo ==============================================================================
    echo This project requires Python 3.11 (Python 3.10 to 3.12 supported).
    echo Python !DETECTED_PY_VER! is not supported by native biometric and Windows binary wheels.
) else (
    echo  ERROR: PYTHON 3.11 IS NOT INSTALLED OR NOT IN SYSTEM PATH
    echo ==============================================================================
    echo This project requires Python 3.11 (Python 3.10 to 3.12 supported).
    echo Python is required to run the Banking Kiosk backend services.
)
echo.
echo IMPORTANT:
echo  - Do NOT install Visual Studio, MSVC, or CMake C++ build tools.
echo  - Simply using Python 3.11 provides pre-built binary wheels for
echo    all dependencies with zero compilation needed.
echo ==============================================================================

:: Check winget
set "HAS_WINGET=0"
where winget >nul 2>&1 && set "HAS_WINGET=1"
if not "!HAS_WINGET!"=="1" (
    if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe" set "HAS_WINGET=1"
)

if "!HAS_WINGET!"=="1" (
    echo.
    echo Windows Package Manager (winget) is available on this computer.
    set /p "WINGET_PROMPT=Would you like to install Python 3.11 automatically via winget? [Y/N]: "
    if /i "!WINGET_PROMPT!"=="Y" (
        echo.
        echo Installing Python 3.11 via Windows Package Manager...
        winget install Python.Python.3.11 --accept-source-agreements --accept-package-agreements
        echo.
        echo Checking for newly installed Python 3.11...
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
            set "SYSTEM_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
            goto :PYTHON_SELECTED
        )
        py -3.11 -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            set "SYSTEM_PY=py -3.11"
            goto :PYTHON_SELECTED
        )
        echo.
        echo Python 3.11 was installed! Please close and reopen this terminal window
        echo or run START_DEMO.bat again so PATH updates take effect.
        pause
        popd
        exit /b 0
    )
)

echo.
echo Manual Installation Instructions:
echo  1. Download Python 3.11 installer from:
echo     https://www.python.org/downloads/release/python-3119/
echo  2. Run the installer and check the box: 'Add python.exe to PATH'.
echo  3. Re-launch START_DEMO.bat.
echo.
pause
popd
exit /b 1

:PYTHON_SELECTED
set "PY_VER_STR="
if "!SYSTEM_PY:~0,3!"=="py " (
    for /f "tokens=*" %%v in ('!SYSTEM_PY! --version 2^>^&1') do set "PY_VER_STR=%%v"
) else (
    for /f "tokens=*" %%v in ('"!SYSTEM_PY!" --version 2^>^&1') do set "PY_VER_STR=%%v"
)
echo   [OK] Detected compatible Python: !PY_VER_STR! (!SYSTEM_PY!)

:: Check for Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: NODE.JS IS NOT INSTALLED OR NOT IN SYSTEM PATH
    echo ==============================================================================
    echo Node.js is required to run Customer Kiosk and Teller Portal frontends.
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

echo   [OK] Node.js and npm detected.
echo   [OK] Embedded Redis broker configured.

:: ------------------------------------------------------------------------------
:: STEP 2: PREPARE PORTABLE PYTHON VIRTUAL ENVIRONMENT [2/7]
:: ------------------------------------------------------------------------------
echo [2/7] Preparing Python environment...

set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"

if not exist "%VENV_PY%" goto :CREATE_VENV

:: Validate that existing .venv is functional and using Python 3.10-3.12
"%VENV_PY%" -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 goto :VENV_VALID

echo   [Notice] Existing virtual environment is invalid or using an unsupported Python version.
echo   [Notice] Rebuilding virtual environment...
if exist "%RUNTIME_DIR%\.py_setup_done" del /f /q "%RUNTIME_DIR%\.py_setup_done" >nul 2>&1
rmdir /s /q "%VENV_DIR%" >nul 2>&1

:CREATE_VENV
echo   [Python] Initializing virtual environment in .venv...
if "!SYSTEM_PY:~0,3!"=="py " (
    !SYSTEM_PY! -m venv "%VENV_DIR%"
) else (
    "!SYSTEM_PY!" -m venv "%VENV_DIR%"
)

if not exist "%VENV_PY%" (
    echo.
    echo ==============================================================================
    echo  ERROR: FAILED TO CREATE PYTHON VIRTUAL ENVIRONMENT
    echo ==============================================================================
    echo Could not create virtual environment in: "%VENV_DIR%"
    echo.
    echo Possible causes:
    echo  - Missing venv module in Python installation
    echo  - Antivirus or permission restrictions in project directory
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)
echo   [OK] Virtual environment created successfully.

:VENV_VALID
for /f "tokens=*" %%v in ('"%VENV_PY%" --version 2^>^&1') do echo   [OK] Virtual environment interpreter: %%v

:: ------------------------------------------------------------------------------
:: STEP 3: INSTALL PYTHON DEPENDENCIES [3/7]
:: ------------------------------------------------------------------------------
echo [3/7] Installing Python dependencies...

if exist "%RUNTIME_DIR%\.py_setup_done" goto :DEPS_VERIFIED

echo   [Python] Installing and verifying backend packages and neural models...
"%VENV_PY%" -u "%SCRIPTS_DIR%\setup_env.py"
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: PYTHON DEPENDENCY SETUP FAILED
    echo ==============================================================================
    echo Please review the diagnostic messages above.
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)
echo done > "%RUNTIME_DIR%\.py_setup_done"
goto :DEPS_DONE

:DEPS_VERIFIED
echo   [OK] Python dependencies and biometric models are up to date.

:DEPS_DONE

:: ------------------------------------------------------------------------------
:: STEP 4: PREPARE FRONTEND DEPENDENCIES [4/7]
:: ------------------------------------------------------------------------------
echo [4/7] Preparing frontend...

set "KIOSK_DIR=%PROJECT_ROOT%\apps\customer-kiosk"
set "STAFF_DIR=%PROJECT_ROOT%\apps\teller-portal"

if not exist "%KIOSK_DIR%\package.json" (
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT LOCATE CUSTOMER KIOSK FRONTEND
    echo ==============================================================================
    echo Expected path: "%KIOSK_DIR%\package.json"
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)

if not exist "%STAFF_DIR%\package.json" (
    echo.
    echo ==============================================================================
    echo  ERROR: COULD NOT LOCATE TELLER PORTAL FRONTEND
    echo ==============================================================================
    echo Expected path: "%STAFF_DIR%\package.json"
    echo ==============================================================================
    echo.
    pause
    popd
    exit /b 1
)

:: Customer Kiosk node_modules
if exist "%KIOSK_DIR%\node_modules" goto :KIOSK_MODULES_OK
echo   Installing Customer Kiosk packages (npm install)...
pushd "%KIOSK_DIR%"
call !NPM_CMD! install
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: FAILED TO INSTALL CUSTOMER KIOSK PACKAGES
    echo ==============================================================================
    echo Please check your internet connection and Node.js / npm installation.
    echo ==============================================================================
    echo.
    pause
    popd
    popd
    exit /b 1
)
popd
:KIOSK_MODULES_OK
echo   [OK] Customer Kiosk dependencies ready.

:: Teller Portal node_modules
if exist "%STAFF_DIR%\node_modules" goto :STAFF_MODULES_OK
echo   Installing Teller Portal packages (npm install)...
pushd "%STAFF_DIR%"
call !NPM_CMD! install
if errorlevel 1 (
    echo.
    echo ==============================================================================
    echo  ERROR: FAILED TO INSTALL TELLER PORTAL PACKAGES
    echo ==============================================================================
    echo Please check your internet connection and Node.js / npm installation.
    echo ==============================================================================
    echo.
    pause
    popd
    popd
    exit /b 1
)
popd
:STAFF_MODULES_OK
echo   [OK] Teller Portal dependencies ready.

:: ------------------------------------------------------------------------------
:: STEP 5: PREPARE INFRASTRUCTURE [5/7]
:: ------------------------------------------------------------------------------
echo [5/7] Preparing infrastructure...

if not exist "%RUNTIME_DIR%" mkdir "%RUNTIME_DIR%"
if not exist "%RUNTIME_DIR%\logs" mkdir "%RUNTIME_DIR%\logs"

:: Remove stale demo_pids.json if no services from it are actually running
if exist "%RUNTIME_DIR%\demo_pids.json" (
    "%VENV_PY%" -c "import json, os, psutil; p=r'%RUNTIME_DIR%\demo_pids.json'; os.path.exists(p) and not any(psutil.pid_exists(pid) for pid in json.load(open(p)).values() if isinstance(pid, int)) and os.remove(p)" >nul 2>&1
)

echo   [OK] Runtime environment and log directory initialized.

:: ------------------------------------------------------------------------------
:: STEP 6 & 7: START SERVICES & VERIFY SYSTEM [6/7] & [7/7]
:: ------------------------------------------------------------------------------
pushd "%PROJECT_ROOT%"
"%VENV_PY%" -u "%SCRIPTS_DIR%\launcher_service.py" start
popd

popd
pause
