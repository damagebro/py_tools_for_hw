@echo off
setlocal
set "SCRIPT_DIR=%~dp0.."
python -B "%SCRIPT_DIR%\src\hw_tool.py" %*
exit /b %ERRORLEVEL%
