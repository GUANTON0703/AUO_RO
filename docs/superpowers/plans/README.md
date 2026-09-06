# ROtxt v1 實作路線圖

本目錄一份計畫做一個子系統，每份自己能跑、能測。依賴順序如下，**上游沒完成不要動下游**。

| # | 計畫 | 產出 | 依賴 | 檔名 |
|---|---|---|---|---|
| 1 | 地基 ✅ | 能註冊/登入/建角色的伺服器（60 測試綠）| — | `2026-09-06-01-foundation.md` |
| 2 | 資料管線 ✅ | v1 資料集（42 怪/8 MVP/26 卡/33 裝備/32 技能）+ schema + 載入驗證（97 測試綠）| 1 | `2026-09-06-02-content-pipeline.md` |
| 3 | 戰鬥引擎 ✅ | 回合制戰鬥 + 批次掛機模擬（141 測試綠，自審過）| 2 | `2026-09-06-03-combat-engine.md` |
| 4 | 掛機結算器 | 在線 tick + 離線混合結算 | 3 | `2026-09-06-04-idle-settlement.md` |
| 5 | 養成 | 雙等級 / 加點 / 技能樹 / 轉職任務 | 3, 4 | 待寫 |
| 6 | 打寶 | 掉落 / 裝備 / 卡片 / 精煉 | 2, 4 | 待寫 |
| 7 | 經濟 | Zeny / NPC 商店 / 倉庫 | 6 | 待寫 |
| 8 | MVP | 冷卻挑戰 / 王戰 | 3, 6 | 待寫 |
| 9 | 社交 | 排行榜 / 交易 / 聊天 / 公會殼 | 1, 6 | 待寫 |
| 10 | 客戶端 | rich TUI，接上全部 API | 1–9 | 待寫 |
| 11 | 部署 | Dockerfile / J1900 容器 / DB 備份 | 10 | 待寫 |

## 規則

- **後面的計畫等前面做完再寫細節**——實作過程會產生影響下游的決定，提前寫會過時。
- 每份計畫用 `superpowers:subagent-driven-development` 或 `executing-plans` 逐任務執行。
- **審核政策（2026-09-06 起，不用 codex）**：
  1. 分批執行時，每批做完跑 `uv run pytest -q` + 掃一眼 diff，抓粗的破壞。
  2. 階段收尾一次自行審核——認真讀全階段程式，對照計畫與設計查邏輯 bug、邊界條件、命名，修完重跑測試綠燈才算完成。
  3. 不跑 `/codex-review`（脈絡重載成本高）。使用者要的話再單獨開。
- 設計依據：`docs/設計.md`（2026-09-06 grill 結論，MATK 已在 v1）。
- 抽象決策記進 `docs/抽象清單.md`。

## 技術基準（所有計畫共用）

- Python 3.12，`uv` 管理依賴（`pyproject.toml` + `uv.lock`）
- 伺服器：FastAPI + uvicorn
- DB：SQLite，WAL 模式
- 密碼：passlib[bcrypt]
- 設定：pydantic-settings
- 資料模型：pydantic v2（`shared/`，server 與 client 共用）
- 客戶端 TUI：rich
- 測試：pytest + httpx（TestClient）
- 部署：Docker → J1900
