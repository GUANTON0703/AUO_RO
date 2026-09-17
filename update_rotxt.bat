@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "\\tw100049089\ml8bc1\助工\個人\冠豪\01\ROtxt-main"
echo ========================================
echo ROtxt Feature Update Tool
echo ========================================
echo.

if not exist ".git\" (
    echo [ERROR] Git repository not found. Please ensure this file is in the ROtxt project root directory.
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Please install Git for Windows first.
    pause
    exit /b 1
)

echo Please ensure the ROtxt server has been stopped to avoid database writes during update.
choice /C YN /N /M "Continue? [Y/N]: "
if errorlevel 2 exit /b 0

git diff --quiet
if errorlevel 1 (
    echo [ERROR] There are uncommitted code changes. Update stopped to prevent overwriting them.
    git status --short
    pause
    exit /b 1
)

git diff --cached --quiet
if errorlevel 1 (
    echo [ERROR] There are staged but uncommitted changes. Update stopped to prevent overwriting them.
    git status --short
    pause
    exit /b 1
)

rem Determine database file path. Default is rotxt.db, or use ROTXT_DB_PATH from .env if set.
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
    echo [ERROR] Failed to create backup directory %BACKUP_DIR%. Update stopped.
    pause
    exit /b 1
)

echo [1/3] Backing up player database (%DB_FILE%)...
set "BACKUP_OK=1"
set "BACKUP_DONE=0"
if exist "%DB_FILE%"     ( copy /Y "%DB_FILE%"     "%BACKUP_DIR%\" >nul && set "BACKUP_DONE=1" || set "BACKUP_OK=0" )
if exist "%DB_FILE%-wal" ( copy /Y "%DB_FILE%-wal" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if exist "%DB_FILE%-shm" ( copy /Y "%DB_FILE%-shm" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if "%BACKUP_OK%"=="0" (
    echo [ERROR] Backup failed. Update stopped. Local player database was not modified.
    pause
    exit /b 1
)
if "%BACKUP_DONE%"=="0" (
    echo [WARNING] Database file %DB_FILE% not found. Nothing to back up (first run?).
    echo           If you believe there should be a save file here, close this window and check ROTXT_DB_PATH in .env.
    choice /C YN /N /M "Continue anyway? [Y/N]: "
    if errorlevel 2 exit /b 0
)
echo Backup location: %BACKUP_DIR%

echo [2/3] Updating features from GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo [ERROR] Update failed. Original player database and settings remain in their original location.
    pause
    exit /b 1
)

echo [3/3] Updating Python packages...
where uv >nul 2>&1
if errorlevel 1 (
    echo [WARNING] uv not found. Skipping package sync. If new packages are needed, please install uv and run this script again.
) else (
    uv sync
    if errorlevel 1 (
        echo [ERROR] uv sync failed. Code has been updated but packages may not be fully updated.
        pause
        exit /b 1
    )
)

echo.
echo Update complete. %DB_FILE%, .env, and local player data were not overwritten by GitHub.
echo Please restart start_server.bat to launch the server.
pause
exit /b 0
