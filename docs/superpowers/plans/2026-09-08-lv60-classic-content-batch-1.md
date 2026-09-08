# Lv1–60 經典內容第一批 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 擴充 Lv1–60 的經典練功地區、怪物與可用卡片，並維持生成資料、內容載入與平衡測試一致。

**Architecture:** 所有新增怪物先寫入 `data/monsters.src.json` 的 `gen: true` 條目，由既有 `scripts/build_monsters.py` 產生 `data/monsters.json`。地圖只引用已生成的怪物 ID；卡片的 slot 與 effect 必須是現有 `shared/content.py` 和戰鬥引擎支援的格式。

**Tech Stack:** Python 3、pytest、Pydantic、JSON、FastAPI 資料載入器。

---

### Task 1: 為第一批內容建立可回歸的資料契約

**Files:**
- Modify: `tests/test_data_files_valid.py`
- Modify: `tests/test_build_monsters.py`
- Test: `tests/test_data_files_valid.py`

- [ ] **Step 1: 寫出會失敗的第一批內容測試**

在 `tests/test_data_files_valid.py` 加入：

```python
def test_lv60_classic_batch_one_maps_and_cards_exist():
    c = content.load_content()
    for map_id in ("sunken_ship_1f", "sphinx_1f", "orc_dungeon_2f"):
        assert map_id in c.maps
    for card_id in ("pirate_skeleton_card", "pasana_card", "orc_skeleton_card"):
        assert card_id in c.cards
```

- [ ] **Step 2: 驗證測試正確失敗**

Run: `uv run pytest tests/test_data_files_valid.py::test_lv60_classic_batch_one_maps_and_cards_exist -q`

Expected: FAIL，缺少 `sunken_ship_1f`、`sphinx_1f` 或對應卡片。

- [ ] **Step 3: 補生成器資料契約測試**

在 `tests/test_build_monsters.py` 加入：

```python
def test_generated_classic_batch_one_monsters_keep_required_drops():
    source = json.loads((build_monsters.DATA / "monsters.src.json").read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in source}
    for monster_id in ("pirate_skeleton", "pasana", "orc_skeleton"):
        assert entries[monster_id]["gen"] is True
        assert entries[monster_id]["drops"]
```

- [ ] **Step 4: 驗證第二個測試正確失敗**

Run: `uv run pytest tests/test_build_monsters.py::test_generated_classic_batch_one_monsters_keep_required_drops -q`

Expected: FAIL，`pirate_skeleton` 尚不存在。

- [ ] **Step 5: Commit**

```bash
git add tests/test_data_files_valid.py tests/test_build_monsters.py
git commit -m "test: define Lv60 classic content batch contract"
```

### Task 2: 新增沉沒之船與斯芬克斯路線

**Files:**
- Modify: `data/maps.json`
- Modify: `data/monsters.src.json`
- Modify: `data/cards.json`
- Modify: `data/items.json`
- Modify: `data/monsters.json` (generated)
- Test: `tests/test_data_files_valid.py`

- [ ] **Step 1: 在 `data/maps.json` 新增地圖**

加入 `sunken_ship_1f`（Lv25–42，普隆德拉系）與 `sphinx_1f`（Lv32–48，夢羅克系）；各自包含 4–5 隻同級怪，`unlock_base_level` 分別為 24 與 32。

- [ ] **Step 2: 在 `data/monsters.src.json` 新增怪物與掉落**

新增沉沒之船的 `pirate_skeleton`、`pirate_ship`、`mimic`、`sword_fish`，以及斯芬克斯的 `pasana`、`side_winder`、`minorous`、`ancient_mummy`。所有條目使用：

```json
{
  "id": "pirate_skeleton",
  "name": "海賊骷髏",
  "gen": true,
  "level": 30,
  "element": "undead",
  "race": "undead",
  "size": "medium",
  "role": "normal",
  "drops": [{"item_id": "skel_bone", "rate": 0.45}, {"item_id": "pirate_skeleton_card", "rate": 0.002}]
}
```

每隻怪至少有一種既有或同批新增材料，以及其對應卡片。

- [ ] **Step 3: 補上可生效的卡片與材料**

在 `data/cards.json` 以既有欄位格式新增卡片，僅使用 `flat_stat`、`percent_stat`、`element_resist`、`race_damage`、`weapon_element` 或 `on_hit_proc`。在 `data/items.json` 新增掉落材料，且 `npc_buy` 為 `null`、`npc_sell` 為正整數。

- [ ] **Step 4: 重新生成怪物資料並驗證內容**

Run: `uv run python scripts/build_monsters.py && uv run python scripts/build_monsters.py --check && uv run pytest tests/test_build_monsters.py tests/test_data_files_valid.py -q`

Expected: `monsters.json 同步 OK`，所有測試 PASS。

- [ ] **Step 5: Commit**

```bash
git add data/maps.json data/monsters.src.json data/monsters.json data/cards.json data/items.json tests/test_data_files_valid.py tests/test_build_monsters.py
git commit -m "feat: add sunken ship and sphinx Lv60 content"
```

### Task 3: 新增獸人地城深層與等級帶平衡驗證

**Files:**
- Modify: `data/maps.json`
- Modify: `data/monsters.src.json`
- Modify: `data/cards.json`
- Modify: `data/items.json`
- Modify: `data/monsters.json` (generated)
- Modify: `tests/test_data_files_valid.py`
- Test: `tests/test_combat_grind.py`

- [ ] **Step 1: 寫等級帶路線測試**

在 `tests/test_data_files_valid.py` 加入：

```python
def test_lv60_ranges_have_two_distinct_hunt_maps():
    c = content.load_content()
    for level in (10, 20, 30, 40, 50, 60):
        available = [m for m in c.maps.values()
                     if m.level_range[0] <= level <= m.level_range[1]]
        assert len(available) >= 2, level
```

- [ ] **Step 2: 驗證測試失敗或記錄現有缺口**

Run: `uv run pytest tests/test_data_files_valid.py::test_lv60_ranges_have_two_distinct_hunt_maps -q`

Expected: PASS 或顯示缺少的等級帶；若既有資料已通過，保留測試作為回歸保護。

- [ ] **Step 3: 在 `data/maps.json` 加入 `orc_dungeon_2f`**

地圖等級帶為 Lv45–60、解鎖 Lv44；怪物包含 `orc_skeleton`、`high_orc`、`orc_archer`、`zenorc`，避免與現有 `orc_dungeon` 只有相同名單。

- [ ] **Step 4: 補怪物、卡片與材料，重新生成**

新增 `zenorc` 及缺少的對應卡片／材料；若 `orc_skeleton`、`high_orc` 已存在，保留原 ID 與掉落，避免破壞既有角色。執行：

```bash
uv run python scripts/build_monsters.py
uv run python scripts/build_monsters.py --check
uv run pytest tests/test_data_files_valid.py tests/test_build_monsters.py tests/test_combat_grind.py -q
```

- [ ] **Step 5: 模擬代表性角色的安全撤退**

Run: `uv run pytest tests/test_settlement_engine.py tests/test_combat_integration.py -q`

Expected: PASS；如果新增怪物需要超出現有 `glass`、`normal`、`tank` 的強度分類，不以手調超高數值繞過，而是拆出獨立平衡任務。

- [ ] **Step 6: Commit**

```bash
git add data/maps.json data/monsters.src.json data/monsters.json data/cards.json data/items.json tests/test_data_files_valid.py
git commit -m "feat: add deep orc dungeon Lv60 route"
```

### Task 4: 第一批整合驗證與部署

**Files:**
- Verify: `data/maps.json`
- Verify: `data/monsters.src.json`
- Verify: `data/monsters.json`
- Verify: `data/cards.json`
- Verify: `tests/`

- [ ] **Step 1: 跑完整測試與資料生成檢查**

Run: `uv run python scripts/build_monsters.py --check && uv run pytest -q`

Expected: 完整測試 PASS，產生檔無差異。

- [ ] **Step 2: 審核未部署的差異**

Run: `codex review --uncommitted`；若本批已分 commit，改用 `codex review --base ef974bd`。

Expected: 無 Critical／High；有問題時修正後重跑審核，最多三輪。

- [ ] **Step 3: 部署與 smoke check**

Run: `sh deploy/push.sh`

Expected: J1900 回覆 health endpoint OK。接著以線上 catalog 確認 `sunken_ship_1f`、`sphinx_1f`、`orc_dungeon_2f` 與對應卡片已載入。

- [ ] **Step 4: 建立部署回滾點**

Run:

```bash
git status --short
git log -1 --oneline
```

Expected: 工作區乾淨，且部署內容已包含在已提交 commit；不要以 `git add -A` 或 `git add .` 建立提交。
