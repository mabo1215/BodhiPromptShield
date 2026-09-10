@echo off
setlocal
cd /d "%~dp0"
rem Resolve an interpreter without hard-coding a machine-specific path: prefer
rem the Windows launcher, then whatever "python" resolves to on PATH.
set "PYTHON_EXE=py"
where py >nul 2>&1 || set "PYTHON_EXE=python"
"%PYTHON_EXE%" experiments\cppb_blind_review_ui.py
if errorlevel 1 pause
