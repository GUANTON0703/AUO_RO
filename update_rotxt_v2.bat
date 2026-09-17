@echo off
setlocal EnableDelayedExpansion

REM Change to the directory where this batch file is located
cd /d "%~dp0"

echo ========================================
echo ROtxt Feature Update Tool
echo ========================================
echo.
echo Current directory: %cd%
echo.

REM Check if .git folder exists
if not exist ".git" (
    echo [ERROR] Git repository not found.
    echo Please ensure this file is in the ROtxt project root directory.
    pause
    exit /b 1
)

REM Check if Git is installed
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Please install Git for Windows first.
    echo Download from: https://git-scm.com/download/win
    pause
    exit /b 1
)

echo Git check: OK
echo.
echo Important: Please ensure the ROtxt server has been STOPPED.
echo Updating while the server is running may cause data corruption.
echo.
choice /C YN /N /M "Do you want to continue? [Y/N]: "
if errorlevel 2 exit /b 0

REM Check for uncommitted changes
git diff --quiet
if errorlevel 1 (
    echo [ERROR] Found uncommitted code changes in working directory.
    echo To prevent data loss, update has been stopped.
    echo.
    echo Uncommitted changes:
    git status --short
    echo.
    echo Options:
    echo   1. Commit your changes: git add . ^&^& git commit -m "your message"
    echo   2. Discard changes: git checkout .
    echo   3. Stash changes: git stash
    pause
    exit /b 1
)

REM Check for staged but uncommitted changes
git diff --cached --quiet
if errorlevel 1 (
    echo [ERROR] Found staged but uncommitted changes.
    echo To prevent data loss, update has been stopped.
    echo.
    git status --short
    pause
    exit /b 1
)

echo All git checks passed.
echo.

REM Determine database file path
set "DB_FILE=rotxt.db"
if exist ".env" (
    for /f "usebackq eol=# tokens=1* delims==" %%A in (".env") do (
        if /I "%%A"=="ROTXT_DB_PATH" (
            set "DB_FILE=%%B"
        )
    )
)

REM Remove quotes and fix slashes
for /f "tokens=*" %%x in ("%DB_FILE%") do set "DB_FILE=%%~x"
set "DB_FILE=!DB_FILE:/=\!"

if not defined DB_FILE set "DB_FILE=rotxt.db"

echo Database file: !DB_FILE!
echo.

REM Create backup directory with timestamp
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)
set "BACKUP_DIR=backups\feature-update-!mydate!-!mytime!"

if not exist "backups" mkdir "backups"
if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"

if not exist "!BACKUP_DIR!" (
    echo [ERROR] Failed to create backup directory: !BACKUP_DIR!
    pause
    exit /b 1
)

echo.
echo [1/3] Backing up player database...
echo Backup location: !BACKUP_DIR!
echo.

set "BACKUP_OK=1"
set "BACKUP_DONE=0"

if exist "!DB_FILE!" (
    copy /Y "!DB_FILE!" "!BACKUP_DIR!" >nul
    if errorlevel 1 (
        set "BACKUP_OK=0"
    ) else (
        set "BACKUP_DONE=1"
    )
)

if exist "!DB_FILE!-wal" (
    copy /Y "!DB_FILE!-wal" "!BACKUP_DIR!" >nul
    if errorlevel 1 set "BACKUP_OK=0"
)

if exist "!DB_FILE!-shm" (
    copy /Y "!DB_FILE!-shm" "!BACKUP_DIR!" >nul
    if errorlevel 1 set "BACKUP_OK=0"
)

if "!BACKUP_OK!"=="0" (
    echo [ERROR] Backup failed. Update stopped.
    echo Your original player database has not been modified.
    pause
    exit /b 1
)

if "!BACKUP_DONE!"=="0" (
    echo [WARNING] Database file not found: !DB_FILE!
    echo Nothing to backup (first run?).
    echo If you expected a save file, check ROTXT_DB_PATH in .env
    echo.
    choice /C YN /N /M "Continue anyway? [Y/N]: "
    if errorlevel 2 exit /b 0
)

echo Backup completed successfully.
echo.

REM Step 2: Pull from GitHub
echo [2/3] Updating code from GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo [ERROR] Git pull failed. Your player database and settings remain unchanged.
    pause
    exit /b 1
)
echo Git pull completed successfully.
echo.

REM Step 3: Update Python packages
echo [3/3] Updating Python packages...
where uv >nul 2>&1
if errorlevel 1 (
    echo [WARNING] uv package manager not found.
    echo Skipping package sync. If new packages are needed, install uv first:
    echo   pip install uv
) else (
    uv sync
    if errorlevel 1 (
        echo [ERROR] uv sync failed. Code is updated but packages may be incomplete.
        pause
        exit /b 1
    )
    echo uv sync completed successfully.
)

echo.
echo ========================================
echo Update completed successfully!
echo ========================================
echo.
echo - Database file (!DB_FILE!), .env, and player data were NOT modified.
echo - Backup saved to: !BACKUP_DIR!
echo - Code updated from GitHub main branch.
echo.
echo Next step: Restart the ROtxt server by running start_server.bat
echo.
pause
exit /b 0
