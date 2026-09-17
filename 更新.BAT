@echo off
pushd "\\tw100049089\ml8bc1\助工\個人\冠豪\01\ROtxt-main"

if not exist ".git" (
    echo [ERROR] Git repository not found
    popd
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git not found. Install Git for Windows.
    popd
    pause
    exit /b 1
)

echo Current directory: %cd%
echo.
echo ROtxt Feature Update Tool
echo.
echo Important: ROtxt server must be STOPPED before update.
echo.
choice /C YN /N /M "Continue? [Y/N]: "
if errorlevel 2 (
    popd
    exit /b 0
)

echo.
echo [1/3] Backing up database...
set "DB_FILE=rotxt.db"
if not exist "backups" mkdir "backups"
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do set mydate=%%c%%a%%b
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do set mytime=%%a%%b
set "BACKUP_DIR=backups\feature-update-%mydate%-%mytime%"
mkdir "%BACKUP_DIR%"

if exist "%DB_FILE%" copy /Y "%DB_FILE%" "%BACKUP_DIR%\"
if exist "%DB_FILE%-wal" copy /Y "%DB_FILE%-wal" "%BACKUP_DIR%\"
if exist "%DB_FILE%-shm" copy /Y "%DB_FILE%-shm" "%BACKUP_DIR%\"

echo Backup completed: %BACKUP_DIR%
echo.

echo [2/3] Pulling from GitHub...
git pull --ff-only origin main
if errorlevel 1 (
    echo [ERROR] Git pull failed.
    popd
    pause
    exit /b 1
)
echo Git pull completed.
echo.

echo [3/3] Updating packages...
where uv >nul 2>&1
if not errorlevel 1 uv sync

echo.
echo ========================================
echo Update completed successfully!
echo ========================================
echo Next: Restart ROtxt server.
echo.
popd
pause
exit /b 0