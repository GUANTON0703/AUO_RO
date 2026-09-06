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

客戶端指令：`h` 掛機、`stop` 結算、`s` 狀態、`i` 背包、`stats`/`skills`/`equip`/`refine`/`socket`/`shop`/`storage`/`job` 選單、`help`、`q` 離開。掛機後進觀看模式，按 Enter 離開觀看（掛機在伺服器繼續）。

設計文件：`docs/設計.md`。實作計畫：`docs/superpowers/plans/`。
