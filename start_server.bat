@echo off
setlocal
cd /d "%~dp0"
echo Starting ROtxt server...
uv run python -m server
pause
