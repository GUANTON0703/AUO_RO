# ROtxt 交接給 CC

最後更新：2026-09-06

## 接手目標

接續目前 ROtxt 文字版 RO 遊戲的功能開發與單機測試。使用者要求以繁體中文操作、盡量使用單字快捷鍵，且本階段採「分段後集中自我審核」，不要每輪呼叫 Claude。

## 目前狀態

- 專案：`H:\創業\ROtxt`
- 分支：`master`
- 最新 commit：`eb7b4fa fix: accumulate hunt progress and rotate map targets`
- 前一相關 commit：`93f8674 fix: improve sell labels and hunt watcher errors`
- 測試：`uv run pytest --disable-warnings -q` → **340 passed, 2 warnings**
- 工作區在本次交接前應保持乾淨；接手後先執行 `git status --short`。
- 尚未部署到 J1900。

## 本次對話已完成的功能

### 掛機與即時畫面

- `client/watch.py` 掛機觀看預設約每 1 秒輪詢一次。
- 角色狀態與掛機狀態置頂並排顯示。
- HP、SP、Base EXP、Job EXP、Zeny 與掛機進度會持續刷新。
- 即時戰鬥紀錄固定最多顯示 10 行，面板高度固定，不會因訊息過多把其他資訊推走。
- `v` 在沒有掛機時收到伺服器 409，會顯示「目前沒有正在掛機，請先按 h 開始掛機」，不再誤報「結算失敗」。
- 掛機狀態中的找怪、蒼蠅翼、Boss 飛走等事件會顯示在戰鬥紀錄。

### 掛機累計與地圖怪物

- `characters` 新增掛機場次累計欄位：
  - `hunt_kills`
  - `hunt_base_exp`
  - `hunt_job_exp`
  - `hunt_zeny`
  - `hunt_seconds`
- `server/db/connection.py` 會在既有 SQLite DB 自動補欄位。
- 每次 `/api/hunt/status` 回傳的是本次掛機場次的累計擊殺、經驗、金錢與時間，不是單次 1 秒增量。
- `h` 現在只選地圖，不再要求玩家選單一怪物。
- 伺服器會在該地圖可打怪物之間輪替，並遵守掛機策略的 include/exclude 設定。
- 並發 status 仍使用時間戳認領機制，避免同一段時間重複結算。

### 商店與中文顯示

- 賣出清單顯示中文物品名、持有數量、NPC 單價與全部賣出可得 Zeny。
- 賣出完成後顯示已賣出物品與獲得金額。
- `/api/shop` 回傳 `sell_price`。
- 物品、裝備、怪物掉落與裝備條件查詢功能已加入；未達成條件會標示紅色。

### GM 與遊戲管理

- 帳號 `GM遊戲管理者` 已在本機資料庫設定成 GM 角色；本機帳號 username 曾使用 `1409313`。
- GM API：調整角色金錢、Base/Job 經驗、經驗倍率、掉寶倍率、查看線上玩家。
- CLI：`uv run python -m server.admin grant-gm <username>`。
- Server 設定表支援 `experience_multiplier`、`drop_multiplier`。

### 其他已加入功能

- 掛機策略 API：指定要打/不打的怪、Boss 是否飛走、自動喝水、自動買水、自動賣物等設定欄位。
- `start_server.bat`：啟動伺服器。
- `start_client.bat`：啟動客戶端。

## 重要檔案

- `server/api/hunt.py`：掛機開始、停止、狀態、累計、怪物輪替。
- `server/repositories/characters.py`：掛機欄位初始化、累計更新、目標輪替。
- `server/db/schema.sql`：SQLite schema。
- `server/db/connection.py`：既有資料庫欄位 migration。
- `server/settlement/engine.py`：掛機戰鬥結算與事件。
- `server/settlement/strategy.py`：掛機策略與隨機事件。
- `client/watch.py`：即時掛機畫面。
- `client/render.py`：狀態面板、戰鬥紀錄、中文內容渲染。
- `client/app.py`：快捷鍵與主迴圈。
- `client/menus.py`：加點、商店、裝備、內容查詢、掛機設定。

## 已知限制與後續優先順序

1. 先用 `start_server.bat` 與 `start_client.bat` 單機實測：確認掛機時間持續增加、擊殺/EXP/Zeny 累加、地圖怪物會輪替、10 行紀錄不溢出。
2. 目前掛機策略中的自動買水、批次賣物欄位已有 API/資料結構，但完整自動採購與出售流程仍需補完並測試。
3. 目前每個玩家每秒查詢一次 status 就會觸發一次 SQLite 結算寫入。10 人約每秒 10 次寫入，開發規模應可運作，但正式多人化前要做 10 人壓測；人數增加後應考慮背景結算、降低輪詢或批次寫入。
4. `clear_hunt_state()` 保留本次場次累計值，新的 `start_hunt()` 才會歸零；確認 UI 的停止摘要仍能正確顯示最後累計值。
5. 尚未做 J1900 部署；部署前必須先取得使用者確認，並遵守 `HANDOFF.md` 的提交、備份與部署規則。

## 建議接手流程

```powershell
Set-Location 'H:\創業\ROtxt'
git status --short
uv run pytest --disable-warnings -q
```

單機啟動：

```text
雙擊 start_server.bat
雙擊 start_client.bat
```

若要修改程式：先補回歸測試，再分段實作；每個段落完成後集中自我審核一次。完成一段程式修改後，明確檔案加入 git、檢查 staged 清單沒有 token/secret/.env，再 commit 並附上 `Co-Authored-By: Codex <noreply@openai.com>`。
