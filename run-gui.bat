@echo off
REM ===============================================================
REM   vlogger GUI launcher  --  FRC Valor 6800
REM
REM   Double-click this file to set up a local virtual environment
REM   (first run only) and launch the Streamlit GUI in a browser.
REM
REM   Requires Python 3.10 or newer to be installed and on PATH
REM   (or installed via the python.org installer with the "py"
REM   launcher option enabled).
REM ===============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ================================================================
echo   vlogger GUI launcher  --  FRC Valor 6800
echo ================================================================
echo.

REM ---- 1. Locate a Python interpreter ----------------------------
set "PYTHON_CMD="
where /q py 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where /q python 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo ERROR: Python is not installed or not on PATH.
    echo.
    echo   Install Python 3.10 or newer from:
    echo     https://www.python.org/downloads/
    echo.
    echo   During install, check "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM ---- 2. Verify Python version ---------------------------------
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: Python 3.10 or newer is required. Found:
    %PYTHON_CMD% --version
    echo.
    pause
    exit /b 1
)

REM ---- 3. Create virtual environment if missing -----------------
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo.
)

set "VENV_PY=.venv\Scripts\python.exe"

REM ---- 4. Install / update dependencies -------------------------
REM Pip skips already-satisfied packages quickly, so this is a no-op
REM after the first run unless requirements.txt has been updated.
echo Checking dependencies ...
"%VENV_PY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VENV_PY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies. See messages above.
    pause
    exit /b 1
)

REM ---- 5. Launch Streamlit --------------------------------------
echo.
echo Launching vlogger GUI ...
echo (Press Ctrl+C in this window to stop the server.)
echo.
"%VENV_PY%" -m streamlit run gui/app.py

REM Don't auto-close on exit so the user can see any error messages
echo.
pause
endlocal
