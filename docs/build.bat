@echo off
setlocal EnableExtensions

set "DOCS_DIR=%~dp0"
set "BUILD_DIR=%DOCS_DIR%build"

pushd "%DOCS_DIR%" >nul || exit /b 1

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"

call :resolve_tool PDFLATEX_BIN PDFLATEX pdflatex.exe "C:\Program Files\MiKTeX\miktex\bin\x64\pdflatex.exe"
if errorlevel 1 goto :fail

call :build_one experiment_progress
if errorlevel 1 goto :fail

call :build_one revision_suggestions
if errorlevel 1 goto :fail

echo [INFO] Documentation build finished.
popd >nul
exit /b 0

:resolve_tool
set "%~1="
call set "TOOL_FROM_ENV=%%%~2%%"
if defined TOOL_FROM_ENV if exist "%TOOL_FROM_ENV%" set "%~1=%TOOL_FROM_ENV%"

if not defined %~1 (
    for /f "delims=" %%I in ('where.exe %~3 2^>nul') do if not defined %~1 set "%~1=%%I"
)

if not defined %~1 if exist "%~4" set "%~1=%~4"

if not defined %~1 (
    echo [ERROR] Could not find %~3. Add it to PATH or set %~2.
    exit /b 1
)

call echo [INFO] Using %~3: %%%~1%%
exit /b 0

:build_one
set "DOC_NAME=%~1"
set "SOURCE_FILE=%DOCS_DIR%%DOC_NAME%.tex"
set "PDF_FILE=%BUILD_DIR%\%DOC_NAME%.pdf"

if not exist "%SOURCE_FILE%" (
    echo [ERROR] Source file not found: %SOURCE_FILE%
    exit /b 1
)

echo [INFO] Building %DOC_NAME%.tex into %BUILD_DIR%...
call :run_pdflatex "%SOURCE_FILE%"
if errorlevel 1 (
    echo [ERROR] First pdflatex pass failed for %DOC_NAME%.tex.
    exit /b 1
)

call :run_pdflatex "%SOURCE_FILE%"
if errorlevel 1 (
    echo [ERROR] Second pdflatex pass failed for %DOC_NAME%.tex.
    exit /b 1
)

if not exist "%PDF_FILE%" (
    echo [ERROR] Expected PDF not found: %PDF_FILE%
    exit /b 1
)

copy /Y "%PDF_FILE%" "%DOCS_DIR%%DOC_NAME%.pdf" >nul
if errorlevel 1 (
    echo [ERROR] Failed to copy %DOC_NAME%.pdf to %DOCS_DIR%.
    exit /b 1
)

echo [INFO] Copied %DOC_NAME%.pdf to docs\.
exit /b 0

:run_pdflatex
"%PDFLATEX_BIN%" -interaction=nonstopmode -halt-on-error -file-line-error -output-directory="%BUILD_DIR%" "%~1"
exit /b %errorlevel%

:fail
popd >nul 2>nul
exit /b 1
