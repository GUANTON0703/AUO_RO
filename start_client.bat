@echo off
setlocal
cd /d "%~dp0"
echo Starting ROtxt client...
uv run python -m client
pause
