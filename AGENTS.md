# ROtxt — Agent 開發方法

給所有在這個 repo 工作的 AI agent（Claude Code、Codex 等）。這是文字版 RO 休閒遊戲，朋友在玩，沒有金流、可隨時 hotfix。因此「上線一個 bug」成本很低，追求快速迭代，不追求零風險。

## 核心原則：先問清楚，再動手

規格有真正的分岔、而且只有使用者能拍板（他的偏好、他的設計取捨、程式碼裡查不到的資訊）→ 停下來問一個聚焦的問題，附建議選項，等回答再做。

不要猜一個看起來合理的解法然後往上疊。猜錯就是整段重做，浪費 token 跟時間。使用者寧可現在回一句話，也不想事後審一個做錯的實作。

有明顯預設值、或翻程式碼能確認的，自己決定、講一句、往下走。不要為了每個小選擇停下來。

## 修改流程

1. 先看 git 狀態，確認 baseline，不要把無關改動拖進來。
2. 一個 batch 只做一個子功能，3–5 個相關檔案。不要把 migration + 戰鬥引擎 + 技能資料 + API + 前端混在一批。
3. 先找到真正的呼叫路徑，只讀需要的函式跟測試，不要每次掃大檔案或整個 repo。
4. 最小 diff。不要順手重構、不要加用不到的抽象層。
5. 不要手改大量資料檔。資料集會長大的，用 source 檔 + 生成腳本（怪物 `build_monsters.py`、技能 `build_skills.py`）。
6. 新功能程式放對應的 `screen-*.js`，只有共用邏輯回 `screens.js`。

## 驗證分層（不預設寫測試）

| 改動類型 | 測試 | 上線後驗證 |
|---|---|---|
| 純數值 / 字串（改掉落率、改名稱） | 無 | 給使用者一句進遊戲的檢查步驟 |
| 新增內容（怪 / 卡 / 裝備） | 只跑現有 validator（`check_content.py`、`test_data_files_valid.py`） | 進遊戲看 |
| 邏輯改動（戰鬥、API、結算） | 只在「用玩的看不出數字對錯」的地方寫針對性測試（機率、傷害公式、費用） | 給使用者檢查步驟 **加預期數值**：例：「+4 隨機精煉約每 10 次失敗 4 次、一次要 10000 Zeny」 |
| schema / migration / 跨系統 | 維持完整嚴謹度，針對性測試 + 仔細自審 diff | 測過才上 |

完整 pytest 在 batch 結束跑一次就好，開發中只跑相關測試。

## 不要做的事

- **不要為定義清楚的 bug 修正寫 design / plan 文件。** commit message 講清楚就夠。設計先行只在需求真的模糊時才划算（2026-09-09：codex 為 4 個明確的小修正寫了 77 行設計 + 846 行 TDD 計畫，燒完 5 小時額度只做完 1 項）。
- **不要跑自我審核回合。** 小改動不需要 review loop。發現 bug 時，只讀相關的那幾個檔案去查，不要重掃整個 repo。
- 不要把 codex 自我審核當預設步驟塞進流程。

## 指令

```
uv sync
uv run pytest                      # 全測試
uv run python -m server            # 本機伺服器 127.0.0.1:8000
sh deploy/push.sh                  # 部署 J1900（git archive HEAD → docker rebuild → health check）
```

Windows 區網機自己更新：repo 根目錄的 `更新功能.bat` / `update.bat`。

## Worktree

一個任務開一個 worktree，做完合併就清掉（`git worktree remove` + `git branch -d`）。不要留一堆殘留 worktree。

設計文件：`docs/設計.md`。
