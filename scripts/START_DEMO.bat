@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ==============================================================================
:: Voice-Assisted Banking Kiosk - Portable Windows Demo Launcher
:: ==============================================================================
:: 100% Location-Independent & Portable:
:: - Derived dynamically from %~dp0 (never hardcoded paths)
:: - Version-aware Python interpreter detection (Python 3.11 prioritized, 3.10-3.12 supported)
:: - Explicitly prevents Python 3.14/3.13 source compilation issues (no Visual Studio needed)
:: - Self-healing project-local virtual environment (.venv)
:: - Automatic winget installation offer if Python 3.11 is missing
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

:: Discover compatible Python executable (Python 3.11 prioritized, 3.10-3.12 supported)
:: Python 3.14 (and 3.13+) is explicitly rejected due to lack of prebuilt binary wheels.
set "SYSTEM_PY="
set "DETECTED_PY_VER="

:: Priority 1: Check py launcher for Python 3.11
py -3.11 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.11"
    goto :python_selected
)

:: Priority 2: Check py launcher for Python 3.10
py -3.10 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.10"
    goto :python_selected
)

:: Priority 3: Check py launcher for Python 3.12
py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=py -3.12"
    goto :python_selected
)

:: Priority 4: Check if 'python' in PATH is a compatible version (3.10 to 3.12)
python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "SYSTEM_PY=python"
    goto :python_selected
)

:: Priority 5: Check common Windows installation paths for Python 3.11
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe""
        goto :python_selected
    )
)
if exist "%ProgramFiles%\Python311\python.exe" (
    "%ProgramFiles%\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY="%ProgramFiles%\Python311\python.exe""
        goto :python_selected
    )
)
if exist "C:\Python311\python.exe" (
    "C:\Python311\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "SYSTEM_PY="C:\Python311\python.exe""
        goto :python_selected
    )
)

:: If we reached here, no compatible Python (3.10-3.12) was found.
:: Check if an incompatible Python (e.g. 3.14) exists so we can give a clear diagnostic message.
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
    echo Python !DETECTED_PY_VER! is not currently supported by required native biometric
    echo and Windows binary packages (such as winsdk, onnxruntime, insightface).
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

:: Check if winget is available to offer automatic installation
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
            set "SYSTEM_PY="%LOCALAPPDATA%\Programs\Python\Python311\python.exe""
            goto :python_selected
        )
        py -3.11 -c "import sys" >nul 2>&1
        if not errorlevel 1 (
            set "SYSTEM_PY=py -3.11"
            goto :python_selected
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

:python_selected
for /f "tokens=*" %%v in ('!SYSTEM_PY! --version 2^>^&1') do set "PY_VER_STR=%%v"
echo   [OK] Detected compatible Python: !PY_VER_STR! (!SYSTEM_PY!)

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
    REM Validate that existing .venv is executable AND runs a supported Python version (3.10 to 3.12)
    "%VENV_PY%" -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo   [Notice] Existing .venv is using an unsupported or outdated Python version.
        echo   [Notice] Rebuilding virtual environment with !PY_VER_STR!...
        rmdir /s /q "%VENV_DIR%" >nul 2>&1
        if exist "%RUNTIME_DIR%\.py_setup_done" del "%RUNTIME_DIR%\.py_setup_done" >nul 2>&1
        set "NEED_VENV_CREATE=1"
    )
)

if "!NEED_VENV_CREATE!"=="1" (
    echo [Python] Using !PY_VER_STR!
    echo [Python] Creating virtual environment (.venv)...
    !SYSTEM_PY! -m venv "%VENV_DIR%"
    if not exist "%VENV_PY%" (
        echo.
        echo ==============================================================================
        echo  ERROR: FAILED TO CREATE PYTHON VIRTUAL ENVIRONMENT
        echo ==============================================================================
        echo Python could not initialize .venv in: "%PROJECT_ROOT%"
        echo Command: !SYSTEM_PY! -m venv "%VENV_DIR%"
        echo.
        pause
        popd
        exit /b 1
    )
    echo   [OK] Virtual environment created successfully.
)

:: Verify python version inside virtual environment
for /f "tokens=*" %%v in ('"%VENV_PY%" --version 2^>^&1') do echo   [Python] Environment interpreter: %%v

:: Verify and install missing dependencies via setup_env.py
if not exist "%RUNTIME_DIR%\.py_setup_done" (
    echo [Python] Installing dependencies...
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
