@echo off
setlocal

cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_BIN=.venv\Scripts\python.exe"
) else (
  set "PYTHON_BIN=python"
)

"%PYTHON_BIN%" -m cli.install_runtime_deps --quiet
if errorlevel 1 exit /b %errorlevel%

"%PYTHON_BIN%" -m cli.main analyze %*
endlocal
