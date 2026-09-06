# ROtxt v1 實作路線圖

本目錄一份計畫做一個子系統，每份自己能跑、能測。依賴順序如下，**上游沒完成不要動下游**。

| # | 計畫 | 產出 | 依賴 | 檔名 |
|---|---|---|---|---|
| 1 | 地基 | 能註冊/登入/建角色的伺服器 | — | `2026-09-06-01-foundation.md` |
| 2 | 資料管線 | v1 結構化遊戲資料檔 + schema 驗證 | 1 | 待寫 |
| 3 | 戰鬥引擎 | 可單獨測的回合制戰鬥函式庫 | 2 | 待寫 |
| 4 | 掛機結算器 | 在線 tick + 離線混合結算 | 3 | 待寫 |
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
- 每個階段結束跑 `/codex-review` 到 LGTM。
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
