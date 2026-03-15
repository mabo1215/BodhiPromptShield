@echo off
REM IBPPSVM src runner: create .venv if missing, activate, install deps, run all code.
REM Usage: double-click or from repo root: run_src.bat

cd /d "%~dp0"

if not exist ".venv" (
    echo Creating virtual environment at .venv ...
    python -m venv .venv
    if errorlevel 1 ( echo Failed to create .venv & exit /b 1 )
    echo Done.
) else (
    echo Using existing .venv
)

call .venv\Scripts\activate.bat
if errorlevel 1 ( echo Failed to activate .venv & exit /b 1 )

echo Installing dependencies from src/requirements.txt ...
pip install -q -r src\requirements.txt
if errorlevel 1 ( echo pip install failed & exit /b 1 )
echo Done.

echo.
python src\run_all.py
if errorlevel 1 ( echo run_all.py failed & exit /b 1 )

echo.
echo All done.
exit /b 0
