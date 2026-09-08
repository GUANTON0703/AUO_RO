@echo off
chcp 65001 >nul
setlocal EnableExtensions

cd /d "%~dp0"
echo ========================================
echo ROtxt 功能更新工具
echo ========================================
echo.

if not exist ".git\" (
    echo [錯誤] 找不到 Git 儲存庫。請確認本檔案放在 ROtxt 專案根目錄。
    pause
    exit /b 1
)

where git >nul 2>&1
if errorlevel 1 (
    echo [錯誤] 找不到 Git，請先安裝 Git for Windows。
    pause
    exit /b 1
)

echo 請先確認 ROtxt 伺服器已停止，避免更新時資料庫仍在寫入。
choice /C YN /N /M "是否繼續？[Y/N]："
if errorlevel 2 exit /b 0

git diff --quiet
if errorlevel 1 (
    echo [錯誤] 目前有尚未提交的程式修改，為避免覆蓋它們，更新已停止。
    git status --short
    pause
    exit /b 1
)

git diff --cached --quiet
if errorlevel 1 (
    echo [錯誤] 目前有已暫存但尚未提交的修改，為避免覆蓋它們，更新已停止。
    git status --short
    pause
    exit /b 1
)

rem 決定資料庫路徑。預設 rotxt.db，若 .env 有設 ROTXT_DB_PATH 就用那個。
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
    echo [錯誤] 無法建立備份資料夾 %BACKUP_DIR%，更新已停止。
    pause
    exit /b 1
)

echo [1/3] 備份本機玩家資料（%DB_FILE%）...
set "BACKUP_OK=1"
set "BACKUP_DONE=0"
if exist "%DB_FILE%"     ( copy /Y "%DB_FILE%"     "%BACKUP_DIR%\" >nul && set "BACKUP_DONE=1" || set "BACKUP_OK=0" )
if exist "%DB_FILE%-wal" ( copy /Y "%DB_FILE%-wal" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if exist "%DB_FILE%-shm" ( copy /Y "%DB_FILE%-shm" "%BACKUP_DIR%\" >nul || set "BACKUP_OK=0" )
if "%BACKUP_OK%"=="0" (
    echo [錯誤] 備份失敗，更新已停止。本機玩家資料未被更動。
    pause
    exit /b 1
)
if "%BACKUP_DONE%"=="0" (
    echo [警告] 在 %DB_FILE% 找不到資料庫，沒有東西可備份（第一次執行？）。
    echo        若你認為這裡應該有存檔，請關掉視窗檢查 .env 的 ROTXT_DB_PATH。
    choice /C YN /N /M "仍要繼續？[Y/N]："
    if errorlevel 2 exit /b 0
)
echo 備份位置：%BACKUP_DIR%

echo [2/3] 從 GitHub 更新功能...
git pull --ff-only origin main
if errorlevel 1 (
    echo [錯誤] 更新失敗。原本的玩家資料與設定仍保留在原位置。
    pause
    exit /b 1
)

echo [3/3] 更新 Python 套件...
where uv >nul 2>&1
if errorlevel 1 (
    echo [警告] 找不到 uv，略過套件同步；若功能需要新套件，請先安裝 uv 後再執行本檔。
) else (
    uv sync
    if errorlevel 1 (
        echo [錯誤] uv sync 失敗，程式碼已更新但套件可能尚未完整更新。
        pause
        exit /b 1
    )
)

echo.
echo 更新完成。%DB_FILE%、.env 與本機玩家資料未被 GitHub 覆蓋。
echo 請重新執行 start_server.bat 啟動伺服器。
pause
exit /b 0
