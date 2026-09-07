# ROtxt（E:\AUO）配置與啟動說明

本文件針對把 ROtxt 複製到 Windows `E:\AUO` 後的執行方式：

- Python FastAPI 作為後端
- CMD 終端客戶端與瀏覽器共用同一個後端
- 僅允許同一個區域網路連線
- 使用全新的 SQLite 資料庫，不搬移 J1900 舊資料
- 透過 IP 與 port 連線，例如 `http://192.168.1.20:8000`

## 一、需要安裝的環境

### 必要軟體

- Windows 10/11
- Python 3.12 以上（建議 Python 3.12 或 3.13）
- Git（只有需要更新程式碼時才需要）

### Python 套件

在 `E:\AUO` 建立虛擬環境後安裝：

```cmd
cd /d E:\AUO
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" "pydantic-settings>=2.6" "passlib>=1.7.4" "bcrypt==4.0.1" "httpx>=0.27" "rich>=13"
python -m pip install "pytest>=8.3"
```

若電腦只有其他 Python 版本，可把 `py -3.12` 改成該版本；專案要求 Python `>=3.12`。

也可以使用 `uv` 管理環境：

```cmd
cd /d E:\AUO
uv sync
```

兩種方式擇一即可，不需要同時使用。

## 二、初始化全新資料庫

不要從 J1900 複製以下檔案：

```text
rotxt.db
rotxt.db-wal
rotxt.db-shm
```

第一次啟動時，ROtxt 會依照設定自動建立新的 SQLite 資料庫。資料庫位置由 `.env` 的 `ROTXT_DB_PATH` 決定。

## 三、建立設定檔

在 `E:\AUO` 建立 `.env`：

```env
ROTXT_SERVER_HOST=0.0.0.0
ROTXT_SERVER_PORT=8000
ROTXT_DB_PATH=E:/AUO/rotxt.db
ROTXT_TOKEN_TTL_HOURS=720
ROTXT_STAT_RESET_FREE=false
ROTXT_SKILL_RESET_FREE=false
ROTXT_OFFLINE_EFFICIENCY=0.6
ROTXT_OFFLINE_CAP_HOURS=8
ROTXT_OPEN_INVITE_CODE=請改成自己的邀請碼
```

注意：

- `0.0.0.0` 代表接受區網連線，不能改成 `127.0.0.1`，否則其他電腦無法連入。
- `ROTXT_SERVER_PORT` 可改成其他未被占用的 port；以下範例以 `8000` 為準。
- `ROTXT_DB_PATH` 使用正斜線，Windows Python 可正常讀取。
- `.env` 只放本機設定，不要提交到 Git。

## 四、啟動 Python 後端

開啟 CMD：

```cmd
cd /d E:\AUO
.venv\Scripts\activate
python -m server
```

若使用 `uv`：

```cmd
cd /d E:\AUO
uv run python -m server
```

看到類似以下訊息即代表後端已啟動：

```text
Uvicorn running on http://0.0.0.0:8000
```

這個 CMD 視窗要保持開啟。關閉視窗會停止後端。

## 五、確認本機網頁

同一台電腦的瀏覽器開啟：

```text
http://127.0.0.1:8000
```

或：

```text
http://localhost:8000
```

健康檢查：

```cmd
curl http://127.0.0.1:8000/health
```

預期回應：

```json
{"status":"ok"}
```

## 六、讓區網其他裝置連線

### 取得本機區網 IP

另開一個 CMD：

```cmd
ipconfig
```

找出目前使用中的網路介面之 `IPv4 Address`，例如：

```text
192.168.1.20
```

### 瀏覽器連線

手機或同一區網的其他電腦開啟：

```text
http://192.168.1.20:8000
```

### Windows 防火牆

第一次啟動若 Windows 防火牆詢問，允許 Python 在「私人網路」通訊。

若其他裝置仍連不上，以系統管理員 CMD 建立入站規則：

```cmd
netsh advfirewall firewall add rule name="ROtxt LAN 8000" dir=in action=allow protocol=TCP localport=8000 profile=private
```

若 `.env` 改了 port，防火牆規則的 `localport` 也要一起改。

## 七、CMD 終端客戶端連線

後端先在 CMD 視窗啟動後，再開第二個 CMD：

```cmd
cd /d E:\AUO
.venv\Scripts\activate
python -m client --server http://127.0.0.1:8000
```

若 CMD client 在另一台區網電腦：

```cmd
python -m client --server http://192.168.1.20:8000
```

第一次遊玩流程：

1. 使用邀請碼註冊帳號
2. 登入
3. 建立角色
4. 開始遊玩

之後 client 會記住 server URL，可直接執行：

```cmd
python -m client
```

若要切換伺服器，重新指定 `--server` 即可。

## 八、產生一次性邀請碼

在第三個 CMD 執行：

```cmd
cd /d E:\AUO
.venv\Scripts\activate
python -m server.admin invite --count 10
```

每組邀請碼預設使用一次。若已設定 `ROTXT_OPEN_INVITE_CODE`，該公開邀請碼可依設定直接供註冊使用；正式給朋友遊玩時，建議只發一次性邀請碼。

檢查內容資料：

```cmd
python -m server.admin content check
```

## 九、測試安裝是否完整

```cmd
cd /d E:\AUO
.venv\Scripts\activate
python -m pytest -q
```

若使用 `uv`：

```cmd
uv run pytest -q
```

## 十、停止與重新啟動

- 停止後端：在 server CMD 按 `Ctrl+C`
- 重新啟動：再次執行 `python -m server`
- 清除全新測試資料：停止後端，再刪除 `rotxt.db`、`rotxt.db-wal`、`rotxt.db-shm`，下次啟動會重新建立資料庫

刪除資料庫會清除該環境的所有帳號、角色與遊戲進度，只適合全新測試環境使用。

## 十一、常見問題

### 瀏覽器顯示無法連線

依序確認：

1. server CMD 是否仍在執行
2. IP 是否為目前電腦的區網 IPv4
3. URL 的 port 是否與 `.env` 相同
4. Windows 防火牆是否允許該 port
5. 兩台裝置是否真的連到同一個區域網路

### CMD client 連不到

確認 `--server` 使用完整網址，例如：

```cmd
python -m client --server http://192.168.1.20:8000
```

不要只輸入 IP，也不要在網址最後漏掉 port。

### 修改網頁後沒有看到新畫面

瀏覽器可能使用快取，按 `Ctrl+F5` 強制重新整理。若修改的是 Python 後端，必須先停止再重新啟動 server。
