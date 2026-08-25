@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE=C:\Users\295461\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
"%PYTHON_EXE%" src\experiments\cppb_blind_review_ui.py
if errorlevel 1 pause
