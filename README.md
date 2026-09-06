# ROtxt — 文字版 RO 仙境傳說

## 開發

    uv sync
    uv run pytest
    uv run python -m server        # 起伺服器 http://127.0.0.1:8000

## 產邀請碼

    uv run python -m server.admin invite --count 5

## 玩

一鍵（自動起伺服器再開客戶端）：

    uv run python scripts/play.py

或分開跑：

    uv run python -m server                              # 終端 A
    uv run python -m client --server http://127.0.0.1:8000   # 終端 B

客戶端每個畫面最上面固定顯示角色狀態面板。主選單輸入指令代號（`h` 掛機、`v` 查看掛機、`stop` 結算、`stats` 加點、`skills` 學技能、`equip` 裝備、`refine` 精煉、`socket` 鑲卡、`shop` 商店、`storage` 倉庫、`job` 轉職、`mvp` MVP 王、`rank` 排行榜、`trade` 交易、`guild` 公會、`chat` 聊天、`i` 背包、`s` 狀態、`help`、`q` 離開）。

子選單一律用編號選擇，不用再手打 id：例如 `stats` 是配點器（顯示每屬性 +1 成本與剩餘點數，選編號 +1、`0` 完成後一次送出）、`shop` 先選買/賣再選商品、`mvp` 選王再選撤退血線。只有角色名、聊天內容、公會名、買賣/加點的「數量」需要自由輸入。

新角色幾乎沒加點時會先看到新手指引；掛機打不過而撤退時，結算下方會給對應的具體建議。掛機後進觀看模式，看得到逐回合攻擊/擊殺，按 Enter 離開觀看（掛機在伺服器繼續）。

設計文件：`docs/設計.md`。實作計畫：`docs/superpowers/plans/`。
