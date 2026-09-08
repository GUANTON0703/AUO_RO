@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"
echo ========================================
echo ROtxt Feature Update Tool
echo ========================================
echo.

if not exist ".git\" (
    echo [ERROR] Git repository not found. Put this file in the ROtxt project root.
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Install Git for Windows first.
    pause
    exit /b 1
)

echo Stop the ROtxt server first so the database is not being written to.
choice /C YN /N /M "Continue? [Y/N]: "
if errorlevel 2 exit /b 0

git diff --quiet
if errorlevel 1 (
    echo [ERROR] You have uncommitted code changes. Update stopped so they are not overwritten.
    git status --short
    pause
    exit /b 1
)

git diff --cached --quiet
if errorlevel 1 (
    echo [ERROR] You have staged but uncommitted changes. Update stopped so they are not overwritten.
    git status --short
    pause
    exit /b 1
)

rem Resolve the database path. Default rotxt.db, or ROTXT_DB_PATH from .env if set.
set "DB_FILE=rotxt.db"
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims== " %%A in (".env") do (
        if /I "%%~A"=="ROTXT_DB_PATH" set "DB_FILE=%%~B"
    )
)
set "DB_FILE=%DB_FILE:"=%"
set "DB_FILE=%DB_FILE:/=\%"
if not defined DB_FILE set "DB_FILE=rotxt.db"

set "STAMP="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-Date).ToString('yyyyMMdd-HHmmss')" 2^>nul`) do set "STAMP=%%I"
if not defined STAMP set "STAMP=%RANDOM%%RANDOM%"
set "BACKUP_DIR=backups\feature-update-%STAMP%"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
if not exist "%BACKUP_DIR%" (
    echo [ERROR] Could not create backup folder %BACKUP_DIR%. Update stopped.
    pause
    exit /b 1
)

echo [1/3] Backing up local player data (%DB_FILE%)...
set "BACKUP_OK=1"
set "BACKUP_DONE=0"
if exist "%DB_FILE%"     ( copy /Y "%DB_FILE%"     "%BACKUP_DIR%\" >nul && set "BACKUP_DONE=1" || set "BACKUP_OK=0" )
if exist "%DB_FILE%-wal" ( copy /Y "%DB_FILE%-wal" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if exist "%DB_FILE%-shm" ( copy /Y "%DB_FILE%-shm" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if "%BACKUP_OK%"=="0" (
    echo [ERROR] Backup failed. Update stopped. Your player data is untouched.
    pause
    exit /b 1
)
if "%BACKUP_DONE%"=="0" (
    echo [WARN] No database found at %DB_FILE%. Nothing to back up ^(first run?^).
    echo        If you expected save data here, close this window and check ROTXT_DB_PATH in .env.
    choice /C YN /N /M "Continue anyway? [Y/N]: "
    if errorlevel 2 exit /b 0
)
echo Backup location: %BACKUP_DIR%

echo [2/3] Pulling updates from GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo [ERROR] Update failed. Your player data and settings are untouched.
    pause
    exit /b 1
)

echo [3/3] Updating Python packages...
where uv >nul 2>&1
if errorlevel 1 (
    echo [WARN] uv not found. Skipped package sync. Install uv and rerun this file if new packages are needed.
) else (
    uv sync
    if errorlevel 1 (
        echo [ERROR] uv sync failed. Code is updated but packages may be incomplete.
        pause
        exit /b 1
    )
)

echo.
echo Done. %DB_FILE%, .env and local player data were not overwritten by GitHub.
echo Run start_server.bat to start the server again.
pause
exit /b 0
