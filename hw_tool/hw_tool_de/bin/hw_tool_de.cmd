@echo off
setlocal
set "SCRIPT_DIR=%~dp0.."
if defined PYTHON (
    set "PYTHON_CMD=%PYTHON%"
) else (
    set "PYTHON_CMD=python"
)
"%PYTHON_CMD%" -B "%SCRIPT_DIR%\src\hw_tool_de.py" %*
if errorlevel 1 exit /b %errorlevel%
