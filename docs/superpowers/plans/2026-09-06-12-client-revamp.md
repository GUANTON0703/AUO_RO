# 客戶端改版 Implementation Plan（v1.1）

> **For agentic workers:** superpowers:subagent-driven-development。不跑 codex；分批跑測試 + 收尾自審。

**Goal:** 修使用者本機試玩回報的 5 點——(1) 全選單化、少打字 (2) 掛機打不過要給建議 (3) 加點介面顯示每屬性成本 + 剩餘點數、用選的 (4) 角色狀態常駐置頂 (5) 掛機看得到戰鬥過程。

**Architecture:** 主要是客戶端重構 + 一個伺服器小改（在線結算把逐回合戰鬥事件帶回來）。主迴圈改成「清畫面 → 印置頂狀態 → 選單 → 執行 → 回圈」。所有 ID 輸入改成編號選擇。

---

## 設計決策

1. **置頂狀態**：每次回主選單 `console.clear()` → 印 `status_panel` → 印「上一個動作的輸出」→ 印選單。狀態面板永遠在最上面。
2. **選單化**：主選單單鍵（`1`~`9` + 字母），子選單編號選擇。`_choose(console, title, rows, allow_back=True)` 通用函式取代所有「輸入 xxx_id」。只有這幾處保留自由輸入：角色名、聊天內容、公會名、加點/買賣的「數量」。
3. **加點**：互動式配點器。列六屬性 + 各自 `+1 需 N 點`（`server.progression.stats.raise_cost`）+ 剩餘點數（`stat_points_available`）。選編號 +1、即時重畫、`0` 完成 → 一次 `api.allocate_stats(累計增量)`。
4. **在線戰鬥事件**：`_settle_literal` 蒐集每場 `simulate_fight` 的 events，回傳時取**最後 ~60 條**放進 `SettlementResult.events` 前面（KillBatch/稀有掉落/撤退在後）。離線統計路徑不變（沒有逐場，只有統計）。
5. **新手指引**：選完角色後，若六屬性總和 ≤ 8（幾乎沒加點）→ 印指引面板。掛機結算 `retreated and kills == 0` → 依 `retreat_reason` 給具體建議。
6. **觀看模式**：`watch_hunt` 照舊每 5 秒 poll，但現在 events 含戰鬥過程，`event_lines` 已能渲染 attack/skill/kill。撤退時印建議 + 自動結束觀看。

---

## Task 1: 伺服器——在線結算帶回戰鬥事件

**Files:** Modify `server/settlement/engine.py`; Test `tests/test_settlement_engine.py`（追加）

- [ ] **Step 1: 追加失敗測試**

```python
def test_online_settlement_includes_combat_events():
    c = load_content()
    r = settle(_hero(), c.get_monster("green_cotton_worm"), elapsed_seconds=40,
               cfg=HuntConfig(), rng=random.Random(0), offline=False, pity_in={})
    kinds = {e.kind for e in r.events}
    assert "attack" in kinds or "skill" in kinds   # 有逐回合戰鬥
    assert "kill" in kinds                          # 逐場擊殺標記
    assert any(e.kind == "kill_batch" for e in r.events)  # 仍有統計


def test_offline_settlement_has_no_per_round_events():
    c = load_content()
    r = settle(_hero(), c.get_monster("poring"), elapsed_seconds=3600,
               cfg=HuntConfig(), rng=random.Random(0), offline=True, pity_in={})
    assert not any(e.kind in ("attack", "skill") for e in r.events)
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 改 `_settle_literal`**——迴圈裡 `r = simulate_fight(...)` 之後 `combat_events.extend(r.events)`（`r.events` 含該場的 attack/skill/kill）。組 `events` 時：`events = combat_events[-60:] + [KillBatchEvent(...)] + _rare_drop_events(...) + [PotionUsedEvent] + [RetreatEvent]`。

- [ ] **Step 4: 跑通過**——確認離線路徑（`_settle_statistical`）沒被動到、既有結算測試綠
- [ ] **Step 5: Commit** `git commit -m "feat: 在線掛機結算帶回逐回合戰鬥事件"`

---

## Task 2: 客戶端——選擇器與置頂狀態

**Files:** Modify `client/app.py`, `client/render.py`; Test `tests/test_client_flow.py`

- [ ] **Step 1: `client/render.py` 加 `choose_table(title, rows)`**——`rows` 是 `[(label, value)]`，回一個 rich Table（第一欄編號、第二欄 label），純渲染。

- [ ] **Step 2: `client/app.py` 加 `_choose(console, title, rows, *, allow_back=True) -> value|None`**

```python
def _choose(console, title, rows, *, allow_back=True):
    """rows: [(label, value)]。印編號選單，回選中的 value；allow_back 時 0 回 None。"""
    if not rows:
        console.print("[dim](沒有可選項目)[/dim]")
        return None
    console.print(f"[bold]{title}[/bold]")
    for i, (label, _) in enumerate(rows, 1):
        console.print(f"  [cyan]{i}[/cyan]) {label}")
    if allow_back:
        console.print("  [cyan]0[/cyan]) 返回")
    while True:
        raw = Prompt.ask("選擇").strip()
        if raw == "0" and allow_back:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            return rows[int(raw) - 1][1]
        console.print("[red]請輸入清單上的編號[/red]")
```

- [ ] **Step 3: `client/app.py` 主迴圈重構**

```python
_MENU = [
    ("h", "掛機"), ("v", "查看掛機"), ("stop", "停止掛機"),
    ("stats", "加點"), ("skills", "學技能"), ("equip", "裝備"),
    ("refine", "精煉"), ("socket", "鑲卡"), ("shop", "商店"),
    ("storage", "倉庫"), ("job", "轉職"), ("mvp", "MVP 王"),
    ("rank", "排行榜"), ("trade", "交易"), ("guild", "公會"), ("chat", "聊天"),
    ("q", "離開"),
]

def _render_screen(console, api, character, last_output):
    console.clear()
    console.print(status_panel(_merge_sheet(api, _current_character(api, character))))
    if last_output:
        console.print(last_output)
    cols = "　".join(f"[cyan]{k}[/cyan] {label}" for k, label in _MENU)
    console.print(Panel(cols, title="指令", expand=False))
```

主迴圈：`_render_screen(...)` → `cmd = Prompt.ask(">").strip().lower()` → 分派。每個分派把它要顯示的東西 capture 成 `last_output`（或直接印，下一輪 clear 前會看到——簡單起見：指令執行時直接 `console.print`，執行完 `Prompt.ask("按 Enter 繼續")` 停一下讓使用者看，再回圈 clear）。

> **關鍵**：指令執行後 `Prompt.ask("\n[dim]按 Enter 回主選單[/dim]", default="")` 暫停，讓使用者看完輸出再清畫面。掛機觀看模式本身有自己的停止機制不用這個。

- [ ] **Step 4: 測試**——`_choose` 的 monkeypatch 測試（選 2 回第 2 個 value、選 0 回 None、亂輸入重問）
- [ ] **Step 5: Commit** `git commit -m "feat: 客戶端選擇器與置頂狀態畫面"`

---

## Task 3: 客戶端——加點配點器

**Files:** Modify `client/menus.py`; Test `tests/test_client_flow.py`

- [ ] **Step 1: 追加失敗測試**

```python
def test_stats_menu_shows_costs_and_batches(monkeypatch):
    from client.menus import stats_menu
    calls = {}
    class FakeApi:
        def allocate_stats(self, cid, deltas): calls["deltas"] = deltas; return {"stat_str": 1 + deltas.get("str", 0)}
    # 依序選 str, str, 完成
    answers = iter(["1", "1", "0"])
    monkeypatch.setattr("client.menus.Prompt.ask", lambda *a, **k: next(answers))
    from rich.console import Console
    stats_menu(FakeApi(), {"id": 1, "base_level": 20,
                           "stat_str": 1, "stat_agi": 1, "stat_vit": 1,
                           "stat_int": 1, "stat_dex": 1, "stat_luk": 1},
               Console())
    assert calls["deltas"] == {"str": 2}
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 重寫 `stats_menu`**

```python
from server.progression.stats import raise_cost, stat_points_available, STAT_KEYS, STAT_MAX

_STAT_ZH = {"str": "力量", "agi": "敏捷", "vit": "體質",
            "int": "智力", "dex": "靈巧", "luk": "幸運"}


def stats_menu(api, character, console):
    cur = {k: character.get(f"stat_{k}", 1) for k in STAT_KEYS}
    pending = {k: 0 for k in STAT_KEYS}
    base_level = character.get("base_level", 1)

    while True:
        spent = sum(_cost_run(cur[k], cur[k] + pending[k]) for k in STAT_KEYS)
        avail = stat_points_available(base_level, cur) - spent
        console.print(f"\n可用點數：[bold]{avail}[/bold]")
        rows = []
        for i, k in enumerate(STAT_KEYS, 1):
            v = cur[k] + pending[k]
            cost = raise_cost(v)
            afford = "" if (avail >= cost and v < STAT_MAX) else "  [dim](點數不足)[/dim]" if v < STAT_MAX else "  [dim](已滿)[/dim]"
            console.print(f"  [cyan]{i}[/cyan]) {_STAT_ZH[k]} {v}　→ +1 需 {cost} 點{afford}")
        console.print("  [cyan]0[/cyan]) 完成")
        raw = Prompt.ask("加哪個").strip()
        if raw == "0":
            break
        if raw.isdigit() and 1 <= int(raw) <= 6:
            k = STAT_KEYS[int(raw) - 1]
            v = cur[k] + pending[k]
            if v < STAT_MAX and avail >= raise_cost(v):
                pending[k] += 1
            else:
                console.print("[red]加不了[/red]")
        else:
            console.print("[red]輸入 1-6 或 0[/red]")

    deltas = {k: n for k, n in pending.items() if n > 0}
    if not deltas:
        console.print("沒有加點。")
        return
    try:
        api.allocate_stats(character["id"], deltas)
        console.print(f"[green]已加：{deltas}[/green]")
    except Exception as exc:
        console.print(f"[red]加點失敗：{exc}[/red]")


def _cost_run(frm, to):
    return sum(raise_cost(v) for v in range(frm, to))
```

> `_cost_run` = 從 frm 加到 to 的總花費。`stat_points_available` 已扣「目前已花的」，這裡再扣「本次 pending 要花的」。

- [ ] **Step 4: 跑通過**
- [ ] **Step 5: Commit** `git commit -m "feat: 客戶端加點配點器（顯示成本與剩餘點數）"`

---

## Task 4: 客戶端——其餘選單改編號選擇

**Files:** Modify `client/menus.py`

把這些選單裡「輸入 xxx_id」全換成 `_choose`（從 `client.app` import，或把 `_choose` 移到 `client/render.py` 或新 `client/ui.py` 避免循環 import——建議放 `client/ui.py`）：
- `skills_menu`：列本職技能（名稱 + 目前等級 + `+1 需 1 點` + 剩餘技能點）→ 選編號學
- `equip_menu`：列背包裝備（`#id 名稱 +refine`）→ 選要穿的；再列已裝備部位 → 選要卸的
- `refine_menu`：列可精煉裝備（+目前精煉 + 需要的礦/Zeny + 成功率%）→ 選 → 確認
- `socket_menu`：列有空孔裝備 → 選；列背包的卡 → 選
- `shop_menu`：買——列商品（編號）→ 選 → 問數量；賣——列背包可賣的 → 選 → 問數量
- `storage_menu`：存/取用 `_choose` 選物品
- `jobchange_menu`：列可轉職業 → 選
- `mvp_menu`：列 MVP（可挑戰的標「可」、冷卻的標剩餘時間）→ 只有「可」的能選 → 選血線%（給 `[1] 15%(建議) [2] 30% [3] 硬拚` 三選一，不要打數字）
- `trade_menu` / `guild_menu`：選項也改編號

- [ ] **Step 1: 建 `client/ui.py`** 放 `_choose` + `choose_table`（app.py 跟 menus.py 都 import 它）
- [ ] **Step 2: 逐一改上述選單**——每個都用 `_choose`，數量用 `IntPrompt.ask` 但給 default
- [ ] **Step 3: 現有 menu 測試調整**（monkeypatch 的答案序列要配合新的編號流程）
- [ ] **Step 4: 跑通過**
- [ ] **Step 5: Commit** `git commit -m "feat: 客戶端選單全面改編號選擇"`

---

## Task 5: 客戶端——新手指引與撤退建議

**Files:** Modify `client/app.py`, `client/render.py`, `client/watch.py`

- [ ] **Step 1: `client/render.py` 加 `newbie_hint_panel()` 與 `retreat_advice(reason: str) -> str`**

```python
def newbie_hint_panel() -> Panel:
    return Panel(
        "你的角色還很弱，建議依序：\n"
        "  1. [cyan]stats[/cyan] 加點——先把 力量 和 體質 拉到 10 以上\n"
        "  2. [cyan]skills[/cyan] 學技能——先點主力輸出技（劍士→爆裂波動）\n"
        "  3. [cyan]shop[/cyan] 商店——買紅色藥水補血\n"
        "  4. [cyan]h[/cyan] 掛機——去「東門村郊」打最弱的怪",
        title="新手指引", border_style="yellow",
    )


_ADVICE = {
    "戰鬥中被擊倒": "這裡的怪太強。先 stats 加點提升力量/體質，或換更低等的地圖，或 shop 買裝備。",
    "打不過這裡的怪": "完全打不動。回東門村郊打最弱的怪，或先加點、買武器。",
    "沒有補品，血量見底": "帶紅色藥水再來（shop 買），或打更弱的怪讓自然回血跟得上。",
    "補品用盡，血量見底": "補品不夠。多買幾瓶紅色藥水，或換更好打的怪。",
    "補品用盡": "補品不夠。多買幾瓶紅色藥水。",
}

def retreat_advice(reason: str) -> str:
    return _ADVICE.get(reason, "換個地方打打看，或先提升角色數值。")
```

- [ ] **Step 2: `client/app.py`**——選完角色後，若 `sum(六屬性) <= 8` → `console.print(newbie_hint_panel())`（暫停等 Enter）
- [ ] **Step 3: `client/watch.py`**——撤退分支：`console.print(hunt_summary(status))` 後 `console.print(f"[yellow]建議：{retreat_advice(status.get('retreat_reason', ''))}[/yellow]")`
- [ ] **Step 4: `hunt_summary`**（render.py）——`retreated` 時把 `retreat_reason` 印出來（目前可能沒印）
- [ ] **Step 5: 測試**——`retreat_advice` 對已知 reason 回對應建議、未知 reason 回預設
- [ ] **Step 6: Commit** `git commit -m "feat: 新手指引與掛機撤退建議"`

---

## Task 6: 自審 + 手動試玩 + 文件

- [ ] **Step 1: 全套 `uv run pytest -q` 綠**
- [ ] **Step 2: 手動試玩**（in-process TestClient 腳本模擬一連串選單操作，或真的起 server 手玩）——驗證：
  - 一進去看到新手指引
  - `stats` 選 1 加力量，看到剩餘點數變化、成本隨屬性值上升
  - 加完力量體質，`h` 掛機東門村郊，觀看模式看得到「你攻擊綠棉蟲 → N 傷害 / 擊殺」
  - 沒加點就掛機 → 撤退 + 看到建議
  - 每個畫面最上面都有角色狀態
- [ ] **Step 3: 自審**——`client/` 全部：
  - `console.clear()` 後狀態面板一定重印（不會有「狀態消失」的畫面）
  - `_choose` 在空清單、亂輸入、返回 都正確
  - 循環 import（`ui.py` ← `app.py` / `menus.py`）沒問題
  - 加點配點器的 `avail` 計算：`stat_points_available` 已扣已花的、`_cost_run` 扣 pending 的，不會重複扣
  - 觀看模式事件太多時 `event_lines` 的截斷有生效
- [ ] **Step 4: 更新 `README.md` 的「## 玩」章節**——反映新的選單操作
- [ ] **Step 5: 更新 `docs/superpowers/plans/README.md`**——加一列「12 客戶端改版 ✅」
- [ ] **Step 6: Commit** `git commit -m "docs: 客戶端改版完成"`

---

## Self-Review（寫計畫時）

**對照使用者回報：**
1. 多用快捷鍵少打字 → Task 2（主選單單鍵）+ Task 4（子選單全 `_choose` 編號）✓
2. 掛機打不過給建議 → Task 5（`retreat_advice` + 新手指引）✓
3. 加點用選的、顯示成本 + 剩餘 → Task 3（配點器）✓
4. 角色狀態常駐置頂 → Task 2（`_render_screen` 每輪 clear + 狀態面板）✓
5. 掛機看得到過程 → Task 1（在線結算帶回戰鬥事件）+ Task 5（觀看模式渲染）✓

**Placeholder scan：** Task 4 用條列列出 8 個選單的改法，pattern 統一（`_choose` 取代 ID 輸入），不逐一貼完整程式碼——這些是機械性重構，實作者照 `_choose` 介面改即可。

**已知後續：** 真 Live 分割面板（狀態固定、下方捲動）要 `textual` 或 `rich.Live` + prompt_toolkit，v1.1 的 clear-and-reprint 是夠用的近似。網頁版是最終解。
