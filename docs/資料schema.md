# 資料 Schema 說明

所有 schema 定義在 `shared/content.py`（pydantic v2）。資料檔在 `data/*.json`，一類一檔，由 `server/content/load_content()` 載入 + 驗證 + 建索引。

驗證 `uv run python -m server.admin content check` 或 `uv run pytest tests/test_data_files_valid.py`。

---

## 列舉

| 列舉 | 值 |
|---|---|
| `Element` | neutral, water, earth, fire, wind, poison, holy, shadow, ghost, undead |
| `Race` | animal, plant, insect, demon, undead, demihuman, angel, dragon, formless, fish |
| `Size` | small, medium, large（ludens 的「超大型」併入 large） |
| `Stat` | str, agi, vit, int, dex, luk |
| `MonsterRole` | glass, normal, tank, boss |

ludens 用詞對照：聖靈系→`angel`、精靈系→`formless`、人形系→`demihuman`、不死系→`undead`、幽靈系→視情況 `undead`/`formless`。

---

## CombatStats

| 欄位 | 型別 | 說明 |
|---|---|---|
| max_hp / max_sp | int | 生命 / 魔力上限 |
| atk / matk | int | 物理 / 魔法攻擊 |
| defense | int | 硬防（百分比減傷）。欄位名避開 python `def` |
| mdef | int | 魔法防禦 |
| hit / flee | int | 命中 / 迴避 |
| aspd | int | 每 100 ≈ 一次普攻/回合的基準。換算延到戰鬥引擎階段 |
| crit | int | 暴擊值 |

## MonsterDef（`data/monsters.json`）

`id, name, level, element, race, size, role, base_exp, job_exp, stats(CombatStats), drops(list[DropEntry]), is_mvp, lore`

## MvpDef（`data/mvps.json`，繼承 MonsterDef）

額外：`cooldown_hours`(int≥1)、`home_map_id`(str，必須存在於 maps)。`role` 固定 `boss`、`is_mvp` 固定 true。

## DropEntry

`item_id`（指向 items / equipment / cards 任一）、`rate`(0<x≤1)、`min_qty`、`max_qty`。Zeny 獎勵不走這裡，延到戰鬥/經濟階段。

## MapDef（`data/maps.json`）

`id, name, town(prontera|morroc), level_range([lo,hi]), monster_ids, mvp_id(可 null), unlock_base_level`

一張圖 `mvp_id` 至多一隻；`home_map_id` 不要求唯一（一張圖可以是多隻 MVP 的家，但只有一隻掛在 `mvp_id` 當代表）。

## JobDef（`data/jobs.json`）

`id, name, tier(novice|first|second), parent_id, change_job_level, hp_per_level(float), sp_per_level(float), skill_ids`

`change_job_level` = 轉入此職所需的「前職 Job Level」。一轉 10、二轉 40。

## SkillDef（`data/skills.json`）

`id, name, job_id, kind(active|passive), max_level(1-10), sp_cost(list[int]), cooldown_s, effects(list[dict]), idle_default(dict)`

- `effects` 目前是 `list[dict]`，未型別化。戰鬥引擎階段會改成 discriminated union 並回頭驗證。
- 目前用的 effect type：`physical_hit`, `magic_hit`, `aoe`, `heal_hp`, `heal_sp`, `buff`, `debuff`, `passive_stat`, `proc`
- 各級數值用 list 長度 = max_level（例 `"power_pct": [130,145,160,175,190]`）
- `idle_default`：掛機預設優先序。`{"enabled": bool, "trigger": str, "priority": int}`
  - trigger：`every_turn` / `hp_below_50` / `hp_below_30` / `sp_available` / `cooldown_ready` / `passive`
  - priority：輸出技高、補技中、buff 低、passive 0

## EquipmentDef（`data/equipment.json`）

`id, name, slot(weapon|offhand|head|armor|garment|shoes|accessory), rarity(common|fine|legendary), stats(dict), refinable(bool), card_slots(0-4), job_ids(list，空=全職), required_level`

`stats` dict：`{"atk": N}` `{"def": N}` `{"matk": N}` `{"max_hp": N}` `{"flee": N}` 等。

## CardDef（`data/cards.json`）

`id, name, monster_id(必須存在), slot(7 選 1), drop_rate(0<x≤1), effects(list[dict])`

經典 RO 風格獨特效果（不是口袋版數值棒）。effect type：
- `flat_stat`：`{"type":"flat_stat","stat":"max_hp","amount":100}`
- `percent_stat`：`{"type":"percent_stat","stat":"max_hp","pct":15}`
- `element_resist`：`{"type":"element_resist","element":"earth","pct":15}`
- `race_damage`：`{"type":"race_damage","race":"demihuman","pct":20}`
- `on_hit_proc` / `on_kill_proc`：`{"type":"on_hit_proc","chance_pct":5,"effect":"stun"}`

## ItemDef（`data/items.json`）

`id, name, kind(consumable|material|misc), effects(list[dict]), npc_buy(int 或 null), npc_sell(int≥0)`

## ElementChart（`data/element_chart.json`）

`{"table": {"攻方屬性": {"守方屬性": 倍率}}}`。只列非 1.0 的組合，`multiplier(atk, def)` 未列到的回 1.0。

**v1 建好但不啟用**——戰鬥引擎 v1 一律當中性 1.0，v1.5 才套用。

---

## v1 資料量

monsters 14 / mvps 6 / maps 8 / jobs 13（新手 + 6 一轉 + 6 二轉骨架）/ skills 32（新手 2 + 6 職×5）/ equipment 33 / cards 16 / items 10。
