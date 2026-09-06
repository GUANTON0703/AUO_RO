# ROtxt 交接文件

> 最後更新：2026-09-06。這份是「接手的人 5 分鐘看完就能繼續」的現況總表。
> 詳細設計看 `docs/設計.md`，各階段計畫看 `docs/superpowers/plans/`。

---

## 一句話

文字版 RO 仙境傳說（掛機練等打寶轉職，給朋友玩的多人伺服器）。**v1 的 11 個階段全部做完、本機可玩**，正在做「客戶端改版」（第 12 階段，UX 修正），**卡在半路、有壞掉的測試**。

---

## 現況

| 項目 | 狀態 |
|---|---|
| repo | `H:\創業\ROtxt`，git master，118 個 commit |
| 最後一個「全綠」commit | **`f92a099`**（316 測試通過） |
| HEAD | `b501c53` = **WIP，未完成，`tests/test_client_flow.py` 會 hang** |
| 測試框架 | pytest，`uv run pytest -q`（全套約 45 秒；conftest 有 bcrypt + 載入 content 所以啟動慢） |
| 本機能不能玩 | 能（用 `f92a099` 的狀態）：`uv run python -m server` + `uv run python -m client` |
| 有沒有部署 | **沒有**。Dockerfile / compose / 備份 script / runbook 都寫好了，還沒上 J1900 |

### 程式規模
- 74 個程式檔（`server/` `shared/` `client/`）、55 個測試檔、9 個資料檔（`data/*.json`）
- v1 內容：42 隻雜怪 / 8 隻 MVP / 8 張地圖 / 13 職業 / 32 技能 / 33 裝備 / 26 卡片 / 10 道具

---

## 已完成（1~11 階段，全綠、可跑）

| # | 階段 | 做了什麼 |
|---|---|---|
| 1 | 地基 | FastAPI + SQLite(WAL)。邀請碼註冊、登入拿 token、一帳號 3 角色。`server/admin.py invite` 產碼 |
| 2 | 資料管線 | 內容 schema（pydantic，`shared/content.py`）+ v1 資料集。名冊照 ludens、戰鬥數值用等級公式產生、卡片走經典風格。載入器驗證所有引用完整性 |
| 3 | 戰鬥引擎 | `server/combat/`：回合制、Pre-Renewal 物理+魔法公式、技能/狀態效果、`simulate_fight` + 批次 `simulate_grind`。純函式庫不碰 DB/時間 |
| 4 | 掛機結算器 | `server/settlement/`：`settle()` 一個入口。離線統計投影、在線逐場模擬、安全網撤退、自動補品、掉落保底、SP/HP 場間回復。在線離線期望值校準 0.6 |
| 5 | 養成 | `server/progression/`：等級曲線、`build_player_combatant`（角色→戰鬥數值）、加點(Pre-Renewal 成本)/技能點/轉職 API、掛機 API（`/api/hunt/start\|stop\|status`）。`GET /api/characters/{id}/sheet` 回衍生戰鬥數值 |
| 6 | 打寶 | `character_items`(堆疊) + `character_equipment`(實例化)。掉落自動入袋、equip/unequip/socket/refine API、精煉成功率表 + 失敗降級、掛機讀最終數值 + 嗑背包補品 |
| 7 | 經濟 | 全域 NPC 商店（買賣）、帳號共用倉庫、洗點/洗技能（開發免費）、建角色發起手裝（小刀 + 10 紅藥 + 5 蒼蠅翼） |
| 8 | MVP | 8 隻王冷卻挑戰、逐回合王戰、中途逃（回合開頭血線判定）、贏拿掉落×3 + 經驗 + Zeny、輸扣 1.5% 經驗。`server/mvp/` + `/api/mvp` + client `mvp` 選單 |
| 9 | 社交 | 排行榜（等級/Zeny/卡數/精煉，SQL 白名單）、面對面交易（雙方放桌 + 都確認才原子互換、改桌作廢確認）、世界頻道聊天（輪詢）、公會（建/入/退/交棒/解散、公會頻道）。client `rank/trade/guild/chat` |
| 10 | 客戶端 | `client/` rich TUI REPL。ApiClient 包所有端點、SessionStore 存 token(`~/.rotxt`)、狀態面板、掛機觀看模式、引導式選單。Windows 終端相容（UTF-8 + ANSI）。`scripts/play.py` 一鍵起 server+client |
| 11 | 部署（檔案就緒） | `Dockerfile` / `compose.yaml` / `deploy/backup.sh` + systemd timer / `docs/部署.md` runbook。**還沒真的部署** |

### 也做了的正式硬化
- `server/app.py` 的 `on_event` → lifespan（deprecation warning 從 130+ 降到 2）
- 掛機 status 併發防護：`server/api/hunt.py` `_settle_current` 交易內「認領」時間戳，兩個 status 同時進來只結算一次

---

## 進行中：第 12 階段「客戶端改版」（⚠️ 未完成）

**起因**：使用者本機試玩，回報 5 個 UX 問題：
1. 多用快捷鍵，盡量不要打字
2. 一進去掛機就打不過結束——要給建議「優先做什麼」
3. 加點介面：每個屬性每階段需求不同，要顯示每屬性 +1 需幾點 + 剩餘點數，用選的不要打數字
4. 角色狀態要常駐置頂在畫面上方
5. 掛機想看到戰鬥過程（不是只有擊殺統計）

**計畫**：`docs/superpowers/plans/2026-09-06-12-client-revamp.md`

**已完成（commit `97800d8` / `ca99a9f` / `f92a099`，全綠 316 測試）：**
- Task 1：`_settle_literal` 帶回逐回合戰鬥事件（在線掛機看得到打鬥）。離線統計路徑沒動
- Task 2：`_choose()` 選擇器 + 主迴圈重構成「每輪清畫面 → 印置頂狀態面板 → 印指令」+ `client/render.py` 加 `choose_table`
- Task 3：`stats_menu` 重寫成互動配點器（列六屬性 + 各自 +1 成本 + 剩餘點數，選編號 +1 即時重畫，`0` 完成後一次送出）

**未完成（WIP commit `b501c53`，未提交前的變更被我打包進去了，有壞測試）：**
- Task 4：其餘選單（skills/equip/refine/socket/shop/storage/job/mvp/trade/guild）改編號選擇——**程式寫了大半**（`client/menus.py` 改了 265 行、新增 `client/ui.py`），但 **`tests/test_client_flow.py` 會 hang**（幾乎確定是某個選單 `while True` 迴圈的 monkeypatch `Prompt.ask` 沒餵「結束」答案，測試無限重問）
- Task 5：新手指引面板 + 撤退建議（`retreat_advice`）——部分寫了
- Task 6：手動試玩驗證（`scripts/revamp_check.py` 已建 85 行但沒跑過）、README 更新、標記階段完成

---

## 目前的錯誤 / 要注意的

1. **🔴 `tests/test_client_flow.py` hang**（HEAD `b501c53`）。接手第一件事：找出哪個 menu 測試的 monkeypatch 沒給結束值（`_choose` 亂輸入會重問、menu 的 `while True` 要有 `0`/`back` 出口）。改對之後 `uv run pytest -q` 應該回到全綠。
2. **`docs/superpowers/plans/README.md` 第 42 行把階段 12 標成 ✅ 自審過**——那是 WIP 子代理樂觀寫的，**不是真的**。階段 12 還沒完成。
3. **平衡是「堪玩」不是「調好」**：
   - 低等 MVP（森林守衛等）養好的同級玩家打贏只剩 ~10-15% 血，偏刺激。低等 3 隻可再 −10% ATK
   - 裸裝新角色打同級怪安全網很快切——設計上要先 gear up + 挑對怪，但新手指引沒做完前體驗差（正是第 12 階段要修的）
   - boss HP 倍率 `monster_stats.py` `_ROLE["boss"]` 從 12 一路調到 3.5 才平衡（因為玩家 HP 曲線在低等偏低）
4. **正式上線後改 schema 要真 migration**：目前全是 `CREATE TABLE IF NOT EXISTS`，開發期靠砍 `rotxt.db` 重建。上線後不能這樣，要寫 ALTER/migration。列 v1.1 必做
5. **一帳號只操作第一隻角色**：hunt/shop/inventory/mvp/trade/guild 端點都寫死「帳號第一隻角色」。多角色操作要動伺服器端把 character_id 帶進端點——v1.5
6. **`characters` 表的 `stat_points` / `skill_points` 欄位是 dead code**（改用從等級動態算），之後 cleanup migration 拿掉

---

## 待辦（依優先序）

### 立刻（接手第一步）
- [ ] 修 `tests/test_client_flow.py` 的 hang，回到全綠
- [ ] 修正 `plans/README.md` 階段 12 的假 ✅
- [ ] 做完第 12 階段 Task 4-6：其餘選單改編號、新手指引、撤退建議、`scripts/revamp_check.py` 跑過、docs

### 接著（給朋友玩前）
- [ ] 第 11 階段 Task 6：真的部署上 J1900
  - 要使用者決定子網域（建議 `rotxt.guanton07.com`，在 NPM 上加 A record）
  - 流程在 `docs/部署.md`：rsync 原始碼 → J1900 `docker build` → `docker compose up -d` → NPM proxy host + SSL → 備份 timer → 產邀請碼
  - 部署是「對外動作」，做前要使用者 go
- [ ] 產首批邀請碼、記進 vault `記憶\帳號與服務.md`
- [ ] 從外網用 client 連一次驗證整條流程

### v1.1（上線後）
- [ ] schema migration 機制（不能再砍 db）
- [ ] 平衡調參（用真人回饋）：MVP 低等 ATK、新角色前期體驗
- [ ] 多角色操作（端點帶 character_id）
- [ ] 洗卡道具、精煉保護卷
- [ ] `stat_points`/`skill_points` dead 欄位 cleanup

### v1.5（設計文件明訂延後）
- [ ] 屬性相剋倍率啟用（`data/element_chart.json` 已建，`formulas.py` 留了 `element_multiplier` 參數）
- [ ] 圖鑑收集加成
- [ ] 網頁前端（同一套 ApiClient 概念換 fetch，NPM 已預留 Websockets Support）
- [ ] 卡片的 element_resist / race_damage / proc 效果（要戰鬥引擎支援）
- [ ] proc 型技能（二段攻擊、偷竊、致命毒擊中毒）——目前戰鬥引擎收到當 no-op

### v2（設計文件明訂）
- [ ] 副本（含組隊）
- [ ] 三轉 / 轉生
- [ ] 寵物 / 傭兵 / 隊友
- [ ] 系統寄賣交易所、公會副本 / 公會技能
- [ ] MVP 專屬機制（範圍、召喚、階段）

---

## 重要決策（完整版看 `docs/設計.md` 跟 vault `重要決策紀錄.md`）

1. **掛機遊戲，不是即時 MUD**。核心是「離線也長」。曾評估 chippolot/romud（Go 即時 MUD）當基底，否決——類型相反
2. **client-server 從第一版就是**，狀態全在伺服器、惰性結算（不跑全域 tick，J1900 省資源）
3. **帳號用邀請碼 + 帳密**，不用 IP。一帳號 3 角色
4. **傳統 RO 職業樹**（非口袋版「武器即職業」），v1 到二轉。Base 上限 50
5. **Pre-Renewal 公式骨架**，簡化版（衍生數值用公式不查表）。屬性相剋 v1.5
6. **還原原則**：數值與結果高還原，模擬過程可抽象。每個抽象點記 `docs/抽象清單.md`（目前 24 項：ASPD→回合攻擊次數、離線統計投影、自然回血、中途逃血線判定…）
7. **審核政策改自行審核，不跑 codex**（每輪重載脈絡是 token 大坑）。分批跑測試 + 階段收尾認真讀程式。記在 `plans/README.md`
8. **MATK / 魔法傷害在 v1**（原本排 v1.5，但法師線沒 MATK 等於職業壞掉）
9. v1 社交只做排行榜 + 交易 + 聊天 + 公會殼，**不做 PvP、不做組隊副本**

---

## 怎麼跑起來

```bash
# 先切回全綠狀態（或修好 HEAD 的 hang）
cd H:\創業\ROtxt
git stash   # 或 git checkout f92a099 -- . 看情況

uv sync
uv run pytest -q                          # 應該 316 passed（f92a099）
uv run python -m server                    # 起伺服器 :8000
# 另一個終端
uv run python -m server.admin invite --count 5   # 產邀請碼
uv run python -m client                    # 玩

# 或一鍵
uv run python scripts/play.py
```

示範腳本（不用起 server，直接跑函式）：
`scripts/combat_demo.py` / `hunt_demo.py` / `loot_demo.py` / `settlement_demo.py`

---

## 檔案地圖

```
server/
  app.py            FastAPI app factory（lifespan 初始化 DB）
  config.py         Settings（env 前綴 ROTXT_）
  admin.py          CLI：invite / content check
  db/               connection.py（get_connection / transaction）、schema.sql
  auth/             passwords / invites / tokens / dependencies
  api/              accounts characters progression hunt inventory shop storage mvp
                    leaderboard trade chat guild（每個一個 router）
  repositories/     accounts characters inventory storage mvp trade chat guild leaderboard
  content/          load_content() + monster_stats.baseline()
  combat/           formulas engine skills status combatant events grind
  settlement/       engine（settle / _settle_literal / _settle_statistical）config economy profile drops events
  progression/      __init__（build_player_combatant）levels stats skills
  mvp/              challenge
  loot/             refine
shared/
  models.py         AccountPublic / CharacterPublic / JobId
  content.py        所有內容 schema（MonsterDef / MapDef / SkillDef / EquipmentDef / CardDef …）
client/
  __main__.py app.py api.py config.py auth_flow.py render.py watch.py menus.py chat.py
  ui.py（WIP，Task 4 新增）
data/               *.json（monsters/mvps/maps/jobs/skills/equipment/cards/items/element_chart）
docs/
  設計.md            25 題 grill 結論（權威）
  資料schema.md 資料來源.md 抽象清單.md 部署.md
  superpowers/plans/ 12 份計畫 + README（路線圖）
```

---

## J1900 部署資訊（來自 vault `記憶\主機與連線.md`）

- `ssh root@10.0.4.33` 免密碼，J1900 有 docker 26.1.5
- 服務放 `/srv/`，NPM（nginx-proxy-manager）在 `/srv/npm` 管反代 + Let's Encrypt，管理介面 `http://10.0.4.33:81`
- 本機**沒有 docker**，所以部署是 rsync 原始碼上去在 J1900 build
- compose 把 port 綁 `127.0.0.1:8010`，對外走 NPM
