@echo off
setlocal
cd /d "%~dp0"
echo Starting ROtxt server...
if not exist ".venv\Scripts\python.exe" (
    echo Python virtual environment not found.
    echo Run: py -3.12 -m venv .venv
    echo Then install the packages listed in docs\AUO配置說明.md
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m server %*
pause
