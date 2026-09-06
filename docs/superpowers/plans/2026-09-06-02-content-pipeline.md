# 資料管線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 訂死遊戲內容的資料 schema，產出 v1 的結構化資料集（怪物 / 地圖 / MVP / 掉落 / 職業 / 技能 / 裝備 / 卡片 / 道具），並提供載入 + 驗證 + 查詢的模組。

**Architecture:** 資料放 `data/*.json`，一類一檔。`shared/content.py` 用 pydantic v2 定義所有 schema（欄位一次到位、照最終還原度）。`server/content/` 載入 JSON、驗證、快取、提供查詢函式。怪物戰鬥數值用 `server/content/monster_stats.py` 的等級基準公式產生後寫死進 JSON（可逐隻手調）。

**Tech Stack:** 沿用地基階段（Python 3.12 / uv / pydantic v2 / pytest）。

---

## 關鍵決策（本階段確立，記進 `docs/資料來源.md`）

1. **名冊權威 = ludens（`guide.ludens.com.tw/ro-pocket`）。** 怪物的名字、等級、種族(系)、屬性、體型、出沒地圖、MVP 名單、卡片名單一律照 ludens 的繁中用詞。地圖結構照 ludens 的「普隆德拉野外-XXX / 夢羅克野外-XXX」。
2. **戰鬥數值 = 等級基準公式產生。** 兩站都沒公布怪物 HP/ATK/DEF。用 `monster_stats.py` 的公式依等級算基準值，再乘「角色定位係數」（tank / normal / glass / boss），校準成早期怪接近 Pre-Renewal 手感。產出的最終數值寫死進 `data/monsters.json`，日後不對就直接改該筆。
3. **卡片效果 = 經典 RO 風格的獨特效果**，不採口袋版的純數值棒。schema 把效果設計成「結構化效果清單」——`flat_stat`（純數值加成）是其中一種效果型別，`on_hit_proc` / `conditional` / `resist` 是其他型別。v1 只填得少，改方向不用動 schema。
4. **技能效果**同樣是結構化清單，但**執行邏輯延到「戰鬥引擎」階段**。本階段只定義資料。
5. **屬性相剋表**放 `data/element_chart.json`，本階段就建（16 屬性組合的倍率），但**套用延到 v1.5**——戰鬥引擎 v1 讀到中性一律 1.0。先有資料不啟用。

---

## 檔案結構

```
ROtxt/
  data/
    element_chart.json      # 屬性相剋倍率表（攻方屬性 × 守方屬性）
    monsters.json           # v1 雜怪 ~14 隻
    mvps.json               # v1 MVP ~6 隻（結構同 monster + mvp 專屬欄位）
    maps.json               # v1 地圖 8 張
    jobs.json               # 7 職（新手 + 6 一轉）+ 6 二轉的骨架
    skills.json             # 6 職 × 5 技能 = 30（新手 2 個基礎）
    equipment.json          # ~30 件
    cards.json              # ~16 張
    items.json              # 消耗品 + 材料（補血補魔、精煉礦、傳送翼…）
  shared/
    content.py              # 所有 pydantic schema + 列舉
  server/
    content/
      __init__.py           # load_content() / 查詢函式 / 快取
      monster_stats.py      # 等級基準數值公式
    admin.py                # 加 `content check` 子指令
  docs/
    資料schema.md           # schema 欄位說明（給人看）
    資料來源.md             # 每塊資料哪來的、v2 擴充流程
  tests/
    test_content_schema.py
    test_monster_stats.py
    test_content_loader.py
    test_data_files_valid.py # 載入真實 data/*.json 全部驗證通過
    test_admin_content.py
```

---

## Task 1: 內容 schema 列舉與基礎型別

**Files:**
- Create: `shared/content.py`
- Test: `tests/test_content_schema.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_content_schema.py`**

```python
from shared.content import Element, Race, Size, Stat


def test_element_has_16_ro_elements():
    expected = {
        "neutral", "water", "earth", "fire", "wind", "poison",
        "holy", "shadow", "ghost", "undead",
    }
    assert expected <= {e.value for e in Element}


def test_race_covers_ludens_families():
    # ludens 用詞：動物系/植物系/昆蟲系/惡魔系/不死系/人形系/天使系(聖靈系)/龍族/無形/魚貝
    families = {
        "animal", "plant", "insect", "demon", "undead",
        "demihuman", "angel", "dragon", "formless", "fish",
    }
    assert families <= {r.value for r in Race}


def test_size_is_small_medium_large():
    assert {s.value for s in Size} >= {"small", "medium", "large"}


def test_stat_enum_has_six_primary():
    assert {s.value for s in Stat} == {"str", "agi", "vit", "int", "dex", "luk"}
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'shared.content'`

- [ ] **Step 3: 寫實作 `shared/content.py`（先只放列舉）**

```python
from enum import Enum


class Element(str, Enum):
    NEUTRAL = "neutral"
    WATER = "water"
    EARTH = "earth"
    FIRE = "fire"
    WIND = "wind"
    POISON = "poison"
    HOLY = "holy"
    SHADOW = "shadow"
    GHOST = "ghost"
    UNDEAD = "undead"


class Race(str, Enum):
    ANIMAL = "animal"      # 動物系
    PLANT = "plant"        # 植物系
    INSECT = "insect"      # 昆蟲系
    DEMON = "demon"        # 惡魔系
    UNDEAD = "undead"      # 不死系
    DEMIHUMAN = "demihuman"  # 人形系
    ANGEL = "angel"       # 天使系 / 聖靈系
    DRAGON = "dragon"      # 龍族
    FORMLESS = "formless"  # 無形 / 精靈系
    FISH = "fish"         # 魚貝系


class Size(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Stat(str, Enum):
    STR = "str"
    AGI = "agi"
    VIT = "vit"
    INT = "int"
    DEX = "dex"
    LUK = "luk"
```

> 註：ludens 有「超大型」，我們併進 `large`；「聖靈系/精靈系」對應 `angel`/`formless`，建資料時逐筆判斷。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: PASS（4 個）

- [ ] **Step 5: Commit**

```bash
git add shared/content.py tests/test_content_schema.py
git commit -m "feat: 內容 schema 列舉（屬性/種族/體型/主屬性）"
```

---

## Task 2: 戰鬥數值 schema（CombatStats / MonsterDef）

**Files:**
- Modify: `shared/content.py`
- Test: `tests/test_content_schema.py`（新增）

- [ ] **Step 1: 追加失敗測試到 `tests/test_content_schema.py`**

```python
def test_combat_stats_round_trip():
    from shared.content import CombatStats

    cs = CombatStats(max_hp=50, max_sp=0, atk=8, matk=0, defense=0, mdef=0,
                     hit=1, flee=1, aspd=100, crit=0)
    assert CombatStats.model_validate(cs.model_dump()) == cs


def test_monster_def_requires_core_fields():
    from shared.content import MonsterDef, CombatStats, Element, Race, Size

    m = MonsterDef(
        id="poring", name="波利", level=1, element=Element.EARTH,
        race=Race.ANGEL, size=Size.MEDIUM, role="glass",
        base_exp=2, job_exp=1,
        stats=CombatStats(max_hp=50, max_sp=0, atk=8, matk=0, defense=0,
                          mdef=0, hit=1, flee=1, aspd=100, crit=0),
        drops=[], is_mvp=False,
    )
    assert m.id == "poring"
    assert MonsterDef.model_validate(m.model_dump()) == m


def test_drop_entry_rate_is_fraction():
    from shared.content import DropEntry
    import pytest

    DropEntry(item_id="jellopy", rate=0.5)
    with pytest.raises(Exception):
        DropEntry(item_id="jellopy", rate=1.5)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'CombatStats'`

- [ ] **Step 3: 追加實作到 `shared/content.py`**

```python
from typing import Literal

from pydantic import BaseModel, Field

MonsterRole = Literal["tank", "normal", "glass", "boss"]


class CombatStats(BaseModel):
    max_hp: int = Field(ge=1)
    max_sp: int = Field(ge=0)
    atk: int = Field(ge=0)
    matk: int = Field(ge=0)
    defense: int = Field(ge=0)   # 硬防（百分比減傷用），欄位名避開 python 保留字
    mdef: int = Field(ge=0)
    hit: int = Field(ge=0)
    flee: int = Field(ge=0)
    aspd: int = Field(ge=1)      # 每 100 = 一次普攻 / 回合的基準；換算見戰鬥引擎階段
    crit: int = Field(ge=0)


class DropEntry(BaseModel):
    item_id: str
    rate: float = Field(gt=0.0, le=1.0)   # 0~1 機率；卡片這種低機率也照這個欄位
    min_qty: int = Field(default=1, ge=1)
    max_qty: int = Field(default=1, ge=1)


class MonsterDef(BaseModel):
    id: str
    name: str
    level: int = Field(ge=1)
    element: Element
    race: Race
    size: Size
    role: MonsterRole
    base_exp: int = Field(ge=0)
    job_exp: int = Field(ge=0)
    stats: CombatStats
    drops: list[DropEntry] = Field(default_factory=list)
    is_mvp: bool = False
    lore: str = ""
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: PASS（7 個）

- [ ] **Step 5: Commit**

```bash
git add shared/content.py tests/test_content_schema.py
git commit -m "feat: 戰鬥數值與怪物 schema"
```

---

## Task 3: 其餘 schema（地圖 / MVP / 職業 / 技能 / 裝備 / 卡片 / 道具 / 相剋表）

**Files:**
- Modify: `shared/content.py`
- Test: `tests/test_content_schema.py`（新增）

- [ ] **Step 1: 追加失敗測試**

```python
def test_map_def():
    from shared.content import MapDef

    m = MapDef(id="prontera_east_gate", name="普隆德拉野外-東門村郊",
               town="prontera", level_range=[1, 12],
               monster_ids=["green_cotton_worm", "mad_bunny"],
               mvp_id=None, unlock_base_level=1)
    assert m.town == "prontera"


def test_skill_def_effects_are_structured():
    from shared.content import SkillDef

    s = SkillDef(
        id="bash", name="爆裂波動", job_id="swordman", kind="active",
        max_level=10, sp_cost=[8, 8, 9, 9, 10], cooldown_s=0,
        effects=[{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
        idle_default={"enabled": True, "trigger": "every_turn", "priority": 1},
    )
    assert s.kind == "active"


def test_card_effect_flat_stat_and_proc():
    from shared.content import CardDef

    c = CardDef(
        id="poring_card", name="波利卡片", monster_id="poring",
        slot="armor", drop_rate=0.001,
        effects=[
            {"type": "flat_stat", "stat": "max_hp", "amount": 100},
            {"type": "on_kill_proc", "chance_pct": 100, "effect": "heal_hp", "amount": 5},
        ],
    )
    assert c.slot == "armor"


def test_equipment_slot_and_refine():
    from shared.content import EquipmentDef

    e = EquipmentDef(
        id="knife", name="小刀", slot="weapon", rarity="common",
        stats={"atk": 17}, refinable=True, card_slots=1,
        job_ids=["novice", "swordman", "thief"], required_level=1,
    )
    assert e.refinable is True


def test_element_chart_multiplier_lookup():
    from shared.content import ElementChart

    chart = ElementChart(table={"fire": {"earth": 1.5, "water": 0.5, "fire": 0.25}})
    assert chart.multiplier("fire", "earth") == 1.5
    assert chart.multiplier("fire", "wind") == 1.0   # 未列 = 中性
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'MapDef'`

- [ ] **Step 3: 追加實作到 `shared/content.py`**

```python
class MapDef(BaseModel):
    id: str
    name: str
    town: Literal["prontera", "morroc"]
    level_range: list[int] = Field(min_length=2, max_length=2)
    monster_ids: list[str] = Field(default_factory=list)
    mvp_id: str | None = None
    unlock_base_level: int = Field(ge=1)


class MvpDef(MonsterDef):
    cooldown_hours: int = Field(ge=1)
    home_map_id: str


class SkillDef(BaseModel):
    id: str
    name: str
    job_id: str
    kind: Literal["active", "passive"]
    max_level: int = Field(ge=1, le=10)
    sp_cost: list[int] = Field(default_factory=list)
    cooldown_s: float = 0.0
    effects: list[dict] = Field(default_factory=list)   # 型別化延到戰鬥引擎階段
    idle_default: dict = Field(default_factory=dict)


class JobDef(BaseModel):
    id: str
    name: str
    tier: Literal["novice", "first", "second"]
    parent_id: str | None = None
    change_job_level: int = Field(default=10, ge=1)   # 轉入此職所需的前職 Job Level
    hp_per_level: float = Field(gt=0)
    sp_per_level: float = Field(ge=0)
    skill_ids: list[str] = Field(default_factory=list)


class EquipmentDef(BaseModel):
    id: str
    name: str
    slot: Literal["weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"]
    rarity: Literal["common", "fine", "legendary"]
    stats: dict = Field(default_factory=dict)
    refinable: bool = True
    card_slots: int = Field(default=0, ge=0, le=4)
    job_ids: list[str] = Field(default_factory=list)   # 空 = 全職可用
    required_level: int = Field(default=1, ge=1)


class CardDef(BaseModel):
    id: str
    name: str
    monster_id: str
    slot: Literal["weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"]
    drop_rate: float = Field(gt=0.0, le=1.0)
    effects: list[dict] = Field(default_factory=list)


class ItemDef(BaseModel):
    id: str
    name: str
    kind: Literal["consumable", "material", "misc"]
    effects: list[dict] = Field(default_factory=list)
    npc_buy: int | None = None    # NPC 售價（None = NPC 不賣）
    npc_sell: int = Field(default=0, ge=0)


class ElementChart(BaseModel):
    table: dict[str, dict[str, float]] = Field(default_factory=dict)

    def multiplier(self, attacker: str, defender: str) -> float:
        return self.table.get(attacker, {}).get(defender, 1.0)
```

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_content_schema.py -v`
Expected: PASS（12 個）

- [ ] **Step 5: Commit**

```bash
git add shared/content.py tests/test_content_schema.py
git commit -m "feat: 地圖/MVP/職業/技能/裝備/卡片/道具/相剋表 schema"
```

---

## Task 4: 怪物戰鬥數值基準公式

**Files:**
- Create: `server/content/__init__.py`（空，本 Task 只放）
- Create: `server/content/monster_stats.py`
- Test: `tests/test_monster_stats.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_monster_stats.py`**

```python
from server.content.monster_stats import baseline

# 校準目標（Pre-Renewal 手感）：
#  Lv1 glass（波利級）：HP 40~60、ATK 6~12、DEF 0
#  Lv1 之後大致線性偏指數，Lv50 normal 怪 HP 數千、ATK 數十


def test_lv1_glass_is_poring_ish():
    s = baseline(level=1, role="glass")
    assert 40 <= s.max_hp <= 60
    assert 5 <= s.atk <= 14
    assert s.defense == 0


def test_tank_has_more_hp_and_def_than_glass():
    g = baseline(level=20, role="glass")
    t = baseline(level=20, role="tank")
    assert t.max_hp > g.max_hp
    assert t.defense >= g.defense


def test_stats_increase_with_level():
    lo = baseline(level=5, role="normal")
    hi = baseline(level=45, role="normal")
    assert hi.max_hp > lo.max_hp * 5
    assert hi.atk > lo.atk


def test_boss_role_scales_hard():
    n = baseline(level=30, role="normal")
    b = baseline(level=30, role="boss")
    assert b.max_hp >= n.max_hp * 8


def test_returns_valid_combat_stats():
    from shared.content import CombatStats

    assert isinstance(baseline(level=10, role="normal"), CombatStats)
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_monster_stats.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 寫實作 `server/content/monster_stats.py`**

```python
from shared.content import CombatStats, MonsterRole

# 角色定位係數：(hp, atk, def, flee)
_ROLE = {
    "glass":  (0.7, 1.3, 0.0, 1.2),
    "normal": (1.0, 1.0, 0.5, 1.0),
    "tank":   (1.8, 0.8, 1.5, 0.7),
    "boss":   (12.0, 2.0, 2.0, 1.0),
}


def baseline(level: int, role: MonsterRole) -> CombatStats:
    hp_mult, atk_mult, def_mult, flee_mult = _ROLE[role]

    # 基準：Lv1 約 HP 50 / ATK 8；隨等級指數偏線性成長
    hp_base = 30 + 20 * level + 0.9 * level**2
    atk_base = 5 + 1.6 * level
    def_base = 0.6 * level
    hit_base = level + 1
    flee_base = level + 5
    matk_base = 3 + 1.2 * level
    mdef_base = 0.3 * level

    return CombatStats(
        max_hp=max(1, round(hp_base * hp_mult)),
        max_sp=0,
        atk=max(0, round(atk_base * atk_mult)),
        matk=max(0, round(matk_base * (1.4 if role == "boss" else 1.0))),
        defense=max(0, round(def_base * def_mult)),
        mdef=max(0, round(mdef_base)),
        hit=max(0, round(hit_base * (1.5 if role == "boss" else 1.0))),
        flee=max(0, round(flee_base * flee_mult)),
        aspd=110 if role == "boss" else 100,
        crit=5 if role == "boss" else 0,
    )
```

> 建 `data/monsters.json` 時對每隻怪呼叫 `baseline(level, role)` 取起點，再手動微調寫死進 JSON。JSON 存最終值，不存公式。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_monster_stats.py -v`
Expected: PASS（5 個）。若校準測試沒過，調 `hp_base` / `atk_base` 係數直到 Lv1 glass 落在 HP 40~60、ATK 5~14。

- [ ] **Step 5: Commit**

```bash
git add server/content/__init__.py server/content/monster_stats.py tests/test_monster_stats.py
git commit -m "feat: 怪物戰鬥數值基準公式"
```

---

## Task 5: 內容載入器

**Files:**
- Modify: `server/content/__init__.py`
- Test: `tests/test_content_loader.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_content_loader.py`**

```python
import json

import pytest

from server import content


@pytest.fixture
def tiny_data(tmp_path):
    (tmp_path / "monsters.json").write_text(json.dumps([
        {"id": "poring", "name": "波利", "level": 1, "element": "earth",
         "race": "angel", "size": "medium", "role": "glass",
         "base_exp": 2, "job_exp": 1,
         "stats": {"max_hp": 50, "max_sp": 0, "atk": 8, "matk": 0, "defense": 0,
                   "mdef": 0, "hit": 1, "flee": 6, "aspd": 100, "crit": 0},
         "drops": [{"item_id": "jellopy", "rate": 0.7}], "is_mvp": False}
    ], ensure_ascii=False), encoding="utf-8")
    (tmp_path / "maps.json").write_text(json.dumps([
        {"id": "prontera_east_gate", "name": "東門村郊", "town": "prontera",
         "level_range": [1, 12], "monster_ids": ["poring"], "mvp_id": None,
         "unlock_base_level": 1}
    ], ensure_ascii=False), encoding="utf-8")
    for name in ["mvps", "skills", "jobs", "equipment", "cards", "items"]:
        (tmp_path / f"{name}.json").write_text("[]", encoding="utf-8")
    (tmp_path / "element_chart.json").write_text('{"table": {}}', encoding="utf-8")
    return tmp_path


def test_load_and_lookup(tiny_data):
    c = content.load_content(tiny_data)
    assert c.get_monster("poring").name == "波利"
    assert c.get_map("prontera_east_gate").town == "prontera"
    assert [m.id for m in c.monsters_on_map("prontera_east_gate")] == ["poring"]


def test_unknown_id_raises(tiny_data):
    c = content.load_content(tiny_data)
    with pytest.raises(KeyError):
        c.get_monster("nonexistent")


def test_referential_integrity_checked(tiny_data):
    # 地圖引用不存在的怪 → 載入時就爆
    (tiny_data / "maps.json").write_text(json.dumps([
        {"id": "m", "name": "x", "town": "prontera", "level_range": [1, 2],
         "monster_ids": ["ghost_monster"], "mvp_id": None, "unlock_base_level": 1}
    ], ensure_ascii=False), encoding="utf-8")
    with pytest.raises(content.ContentError):
        content.load_content(tiny_data)


def test_default_load_reads_repo_data_dir():
    c = content.load_content()   # 不給路徑 → 讀 repo 的 data/
    assert len(c.monsters) >= 10
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_content_loader.py -v`
Expected: FAIL — `AttributeError: module 'server.content' has no attribute 'load_content'`

- [ ] **Step 3: 寫實作 `server/content/__init__.py`**

```python
import json
from dataclasses import dataclass, field
from pathlib import Path

from shared.content import (
    CardDef, ElementChart, EquipmentDef, ItemDef, JobDef, MapDef,
    MonsterDef, MvpDef, SkillDef,
)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ContentError(Exception):
    pass


def _read(path: Path) -> list | dict:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Content:
    monsters: dict[str, MonsterDef] = field(default_factory=dict)
    mvps: dict[str, MvpDef] = field(default_factory=dict)
    maps: dict[str, MapDef] = field(default_factory=dict)
    jobs: dict[str, JobDef] = field(default_factory=dict)
    skills: dict[str, SkillDef] = field(default_factory=dict)
    equipment: dict[str, EquipmentDef] = field(default_factory=dict)
    cards: dict[str, CardDef] = field(default_factory=dict)
    items: dict[str, ItemDef] = field(default_factory=dict)
    element_chart: ElementChart = field(default_factory=ElementChart)

    def get_monster(self, mid: str) -> MonsterDef:
        if mid in self.monsters:
            return self.monsters[mid]
        return self.mvps[mid]

    def get_map(self, map_id: str) -> MapDef:
        return self.maps[map_id]

    def get_job(self, job_id: str) -> JobDef:
        return self.jobs[job_id]

    def monsters_on_map(self, map_id: str) -> list[MonsterDef]:
        return [self.get_monster(m) for m in self.maps[map_id].monster_ids]


def _index(models, key="id") -> dict:
    return {getattr(m, key): m for m in models}


def load_content(data_dir: Path | None = None) -> Content:
    d = Path(data_dir) if data_dir else _DATA_DIR
    try:
        c = Content(
            monsters=_index(MonsterDef(**x) for x in _read(d / "monsters.json")),
            mvps=_index(MvpDef(**x) for x in _read(d / "mvps.json")),
            maps=_index(MapDef(**x) for x in _read(d / "maps.json")),
            jobs=_index(JobDef(**x) for x in _read(d / "jobs.json")),
            skills=_index(SkillDef(**x) for x in _read(d / "skills.json")),
            equipment=_index(EquipmentDef(**x) for x in _read(d / "equipment.json")),
            cards=_index(CardDef(**x) for x in _read(d / "cards.json")),
            items=_index(ItemDef(**x) for x in _read(d / "items.json")),
            element_chart=ElementChart(**_read(d / "element_chart.json")),
        )
    except Exception as exc:
        raise ContentError(f"資料載入失敗：{exc}") from exc

    _check_integrity(c)
    return c


def _check_integrity(c: Content) -> None:
    all_monsters = set(c.monsters) | set(c.mvps)
    for m in c.maps.values():
        for mid in m.monster_ids:
            if mid not in all_monsters:
                raise ContentError(f"地圖 {m.id} 引用不存在的怪物 {mid}")
        if m.mvp_id and m.mvp_id not in c.mvps:
            raise ContentError(f"地圖 {m.id} 引用不存在的 MVP {m.mvp_id}")
    for mvp in c.mvps.values():
        if mvp.home_map_id not in c.maps:
            raise ContentError(f"MVP {mvp.id} 的 home_map_id {mvp.home_map_id} 不存在")
    for card in c.cards.values():
        if card.monster_id not in all_monsters:
            raise ContentError(f"卡片 {card.id} 對應不存在的怪物 {card.monster_id}")
    for job in c.jobs.values():
        for sid in job.skill_ids:
            if sid not in c.skills:
                raise ContentError(f"職業 {job.id} 引用不存在的技能 {sid}")
        if job.parent_id and job.parent_id not in c.jobs:
            raise ContentError(f"職業 {job.id} 的 parent_id {job.parent_id} 不存在")
    for drop_owner in list(c.monsters.values()) + list(c.mvps.values()):
        for d in drop_owner.drops:
            if d.item_id not in c.items and d.item_id not in c.equipment and d.item_id not in c.cards:
                raise ContentError(f"{drop_owner.id} 掉落不存在的物品 {d.item_id}")
```

- [ ] **Step 4: 跑測試確認通過（`test_default_load_reads_repo_data_dir` 會因為 data/ 還沒填而失敗，這是預期的——Task 6/7 填完才會過。先確認其他 3 個過）**

Run: `uv run pytest tests/test_content_loader.py -v -k "not default_load"`
Expected: PASS（3 個）

- [ ] **Step 5: Commit**

```bash
git add server/content/__init__.py tests/test_content_loader.py
git commit -m "feat: 內容載入器含引用完整性檢查"
```

---

## Task 6: v1 地圖與怪物資料

**Files:**
- Create: `data/element_chart.json`
- Create: `data/maps.json`
- Create: `data/monsters.json`
- Create: `data/items.json`（怪物掉落會引用，先建最小集）
- Test: `tests/test_data_files_valid.py`

> **資料來源：ludens `guide.ludens.com.tw/ro-pocket/monsters/` 的名冊。** 逐筆對照下表，戰鬥數值用 `monster_stats.baseline(level, role)` 取起點微調。

**v1 地圖（8 張，`data/maps.json`）：**

| id | 名稱 | town | 等級帶 | 解鎖 Base |
|---|---|---|---|---|
| `prontera_east_gate` | 普隆德拉野外-東門村郊 | prontera | [1,12] | 1 |
| `prontera_south_field` | 普隆德拉野外-南門原野 | prontera | [9,20] | 8 |
| `mjolnir_mine` | 普隆德拉-礦洞 | prontera | [16,25] | 14 |
| `prontera_west_plain` | 普隆德拉野外-西門平原 | prontera | [1,30] | 1 |
| `prontera_south_forest` | 普隆德拉野外-南區森林 | prontera | [31,40] | 28 |
| `prontera_sewer` | 普隆德拉-王城下水道 | prontera | [39,48] | 36 |
| `prontera_north_forest` | 普隆德拉野外-北區密林 | prontera | [46,55] | 42 |
| `morroc_oasis` | 夢羅克野外-綠洲 | morroc | [42,50] | 40 |

**v1 雜怪（14 隻，`data/monsters.json`）——欄位照 ludens：**

| id | name | lv | 地圖 | race | element | size | role |
|---|---|---|---|---|---|---|---|
| `green_cotton_worm` | 綠棉蟲 | 1 | 東門村郊 | insect | earth | small | glass |
| `mad_bunny` | 瘋兔 | 2 | 東門村郊 | animal | wind | small | glass |
| `little_boar` | 小野豬 | 4 | 東門村郊 | animal | water | small | normal |
| `chick` | 小雞 | 5 | 東門村郊 | animal | fire | small | normal |
| `yoyo_monkey` | 溜溜猴 | 6 | 東門村郊 | animal | fire | small | glass |
| `raccoon` | 狸貓 | 9 | 南門原野 | animal | fire | small | normal |
| `mushroom` | 魔菇 | 9 | 南門原野 | plant | water | medium | tank |
| `grass_sprite` | 草精 | 11 | 南門原野 | plant | earth | medium | normal |
| `snail` | 蝸牛 | 12 | 南門原野 | insect | water | medium | tank |
| `poring` | 波利 | 1 | 西門平原 | angel | earth | medium | glass |
| `tree_sprite` | 樹精 | 28 | 西門平原 | plant | earth | large | tank |
| `wolf` | 狼 | 46 | 北區密林 | animal | fire | medium | normal |
| `boar` | 野豬 | 47 | 北區密林 | animal | fire | large | tank |
| `thunder_hedgehog` | 雷極刺蝟 | 42 | 綠洲 | animal | wind | small | glass |

> 每隻補：`base_exp` / `job_exp`（隨等級遞增，Lv1 給 2/1，Lv50 給約 400/200，中間插值）、`drops`（1~3 項，引用 `data/items.json` 或 Task 8 的 equipment/cards）、`lore`（ludens 有的話抄一句）。

**`data/items.json` 最小集**（掉落與商店會用，Task 8/9 補齊）：
`jellopy`(壓縮膠)、`sticky_mucus`(黏黏液)、`fluff`(絨毛)、`feather`(羽毛)、`clover`(幸運草)、`red_potion`(紅色藥水)、`blue_potion`(藍色藥水)、`elunium`(精煉礦-防具)、`oridecon`(精煉礦-武器)、`fly_wing`(蒼蠅之翼)。

**`data/element_chart.json`**：先放 Pre-Renewal 標準 10×10 倍率表（火剋地/草、水剋火、風剋水、地剋風、聖闇互剋、不死怕聖…）。查不到的組合回 1.0。完整表照 iRO wiki「Elemental Chart (Pre-Renewal)」。

- [ ] **Step 1: 寫測試 `tests/test_data_files_valid.py`**

```python
from server import content


def test_all_data_files_load_and_validate():
    c = content.load_content()
    assert len(c.monsters) >= 12
    assert len(c.maps) == 8
    assert len(c.items) >= 10


def test_every_map_has_monsters_in_its_level_range():
    c = content.load_content()
    for m in c.maps.values():
        lo, hi = m.level_range
        assert m.monster_ids, f"{m.id} 沒有怪"
        for mon in c.monsters_on_map(m.id):
            assert lo - 5 <= mon.level <= hi + 10, f"{mon.id} 等級偏離 {m.id} 的帶"


def test_element_chart_has_fire_earth_advantage():
    c = content.load_content()
    assert c.element_chart.multiplier("fire", "earth") > 1.0
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_data_files_valid.py -v`
Expected: FAIL — `ContentError`（檔案不存在）

- [ ] **Step 3: 建 `data/element_chart.json`、`data/items.json`、`data/maps.json`、`data/monsters.json`**

照上面的表逐筆建。怪物數值產生方式：

```python
# 一次性產生腳本（放 scratchpad，不進 repo）：
from server.content.monster_stats import baseline
s = baseline(level=1, role="glass")
print(s.model_dump())   # 貼進 monsters.json 再微調
```

`mvps.json` / `skills.json` / `jobs.json` / `equipment.json` / `cards.json` 先各放 `[]`（Task 7 填）。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_data_files_valid.py -v`
Expected: PASS（3 個）

- [ ] **Step 5: 跑之前擱置的載入器測試**

Run: `uv run pytest tests/test_content_loader.py::test_default_load_reads_repo_data_dir -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add data/ tests/test_data_files_valid.py
git commit -m "feat: v1 地圖與怪物資料（8 圖 14 怪）"
```

---

## Task 7: v1 MVP / 職業 / 技能 / 裝備 / 卡片資料

**Files:**
- Modify: `data/mvps.json` `data/jobs.json` `data/skills.json` `data/equipment.json` `data/cards.json` `data/items.json`
- Test: `tests/test_data_files_valid.py`（新增）

**v1 MVP（6 隻，`data/mvps.json`，結構 = MonsterDef + `cooldown_hours` + `home_map_id`）——照 ludens MVP 圖鑑：**

| id | name | lv | home_map | cooldown_h | 卡片 |
|---|---|---|---|---|---|
| `angel_poring` | 天使波利 | 16 | prontera_west_plain | 8 | `angel_poring_card` |
| `fierce_mushroom` | 兇猛魔菇 | 17 | prontera_south_field | 8 | `fierce_mushroom_card` |
| `queen_bee` | 蜂后 | 19 | prontera_south_field | 12 | `queen_bee_card` |
| `forest_guardian` | 森林守衛 | 29 | prontera_west_plain | 12 | `forest_guardian_card` |
| `choco_monkey` | 巧克猴 | 30 | prontera_east_gate | 12 | `choco_monkey_card` |
| `curly_boar_king` | 卷鬃山豬王 | 48 | prontera_north_forest | 24 | `curly_boar_king_card` |

> MVP 數值用 `baseline(level, role="boss")`。每隻掉落：自己的卡（`drop_rate` 0.02~0.05）+ 2~3 件稀有裝 + 精煉礦 + Zeny（Zeny 用 item id `zeny`，或掉落 schema 加 `zeny` 欄位——實作時決定，建議掉落 schema 加 `zeny_min`/`zeny_max`，這是對 Task 2 schema 的小修）。對應每張 MVP 卡也要進 `data/cards.json`。

**v1 職業（`data/jobs.json`）：**
- `novice`（tier novice, parent null, hp_per_level 5.0, sp_per_level 1.0, skills `[basic_attack_boost, first_aid]`）
- 6 一轉：`swordman` `mage` `archer` `acolyte` `merchant` `thief`（tier first, parent `novice`, change_job_level 10）
- 6 二轉骨架：`knight`(swordman) `wizard`(mage) `hunter`(archer) `priest`(acolyte) `blacksmith`(merchant) `assassin`(thief)（tier second, change_job_level 40）
- hp/sp 係數照 Pre-Renewal 相對關係：劍士系 hp 高 sp 低、法師系反之、其餘中間。

**v1 技能（`data/skills.json`，6 一轉 × 5 = 30 + 新手 2）——每職 5 個代表技能：**
- 劍士：`bash`(爆裂波動,physical_hit) `magnum_break`(爆裂波動範圍,aoe_fire) `provoke`(挑釁,debuff_def) `endure`(忍耐,passive) `sword_mastery`(劍術訓練,passive_atk)
- 法師：`fire_bolt` `cold_bolt` `lightning_bolt`(魔法彈,magic_hit 各屬性) `soul_strike`(靈魂攻擊,magic_hit ghost) `increase_sp`(SP回復,passive)
- 弓箭手：`double_strafe`(二連矢,physical_hit×2) `arrow_shower`(箭雨,aoe) `owls_eye`(鷹眼,passive_dex) `vultures_eye`(鷲眼,passive_hit_range) `improve_concentration`(專注,buff)
- 服事：`heal`(治癒,heal_hp matk-based) `blessing`(祝福,buff_stats) `increase_agi`(敏捷,buff_aspd) `holy_light`(聖光,magic_hit holy) `divine_protection`(神術防護,passive_resist)
- 商人：`mammonite`(金錢之擊,physical_hit 消耗zeny) `cart_revolution`(手推車攻擊,physical_hit) `enlarge_weight`(負重提升,passive) `discount`(折扣,passive_shop) `vending`(擺攤,passive placeholder)
- 盜賊：`double_attack`(二段攻擊,passive proc double) `envenom`(致命毒擊,poison_hit) `steal`(偷竊,proc_loot) `hiding`(隱藏,buff_evade) `improve_dodge`(閃躲提升,passive_flee)
- 新手：`basic_attack_boost`(基礎攻擊,passive_atk small) `first_aid`(急救,heal_hp tiny)

> `effects` 用結構化 dict，型別字串先定好（`physical_hit` / `magic_hit` / `aoe` / `heal_hp` / `buff` / `debuff` / `passive_stat` / `proc`），實際數值套用邏輯延到戰鬥引擎階段。每個技能給 `idle_default`（掛機預設優先序）。

**v1 裝備（~30 件，`data/equipment.json`）：**
- 每職一把入門武器（NPC 買得到）：小刀/短劍(劍士)、新手法杖(法師)、新手弓(弓箭手)、silvervine棒(服事)、工作斧(商人)、匕首(盜賊)
- 幾把稍好的武器（怪物/MVP 掉）
- 防具各部位 common 2~3 件 + fine/legendary 各幾件（MVP 掉）
- 用經典 RO 裝備名（皮甲、鎖子甲、涼鞋、兜帽、手套、耳環、項鍊…）

**v1 卡片（~16 張，`data/cards.json`）——經典風格獨特效果：**
- `poring_card`(armor, +HP) `green_cotton_worm_card`(garment, +FLEE) `mad_bunny_card`(accessory, +AGI/剋暴擊) `mushroom_card`(...) `snail_card`(shoes, +HP/SP) `tree_sprite_card`(armor, 地屬性抗性) `wolf_card`(weapon, +ATK/+CRIT) `thunder_hedgehog_card`(...) 等 8 張雜怪卡 + 6 張 MVP 卡（效果強：`angel_poring_card` 全屬性+1、`choco_monkey_card` 對人形傷害+、`curly_boar_king_card` MaxHP大幅+…）+ 2 張礦洞怪卡。
- 效果 dict 型別：`flat_stat` / `percent_stat` / `element_resist` / `race_damage` / `on_kill_proc` / `on_hit_proc`。

- [ ] **Step 1: 追加測試到 `tests/test_data_files_valid.py`**

```python
def test_mvps_loaded_with_cooldown_and_home_map():
    c = content.load_content()
    assert len(c.mvps) >= 6
    for mvp in c.mvps.values():
        assert mvp.cooldown_hours >= 1
        assert mvp.home_map_id in c.maps
        assert mvp.is_mvp is True


def test_all_seven_starting_jobs_plus_second_tier():
    c = content.load_content()
    assert c.get_job("novice").tier == "novice"
    for j in ["swordman", "mage", "archer", "acolyte", "merchant", "thief"]:
        assert c.get_job(j).parent_id == "novice"
    for j in ["knight", "wizard", "hunter", "priest", "blacksmith", "assassin"]:
        assert c.get_job(j).tier == "second"


def test_each_first_job_has_five_skills():
    c = content.load_content()
    for j in ["swordman", "mage", "archer", "acolyte", "merchant", "thief"]:
        assert len(c.get_job(j).skill_ids) == 5
        for sid in c.get_job(j).skill_ids:
            assert c.skills[sid].job_id == j


def test_every_mvp_card_exists():
    c = content.load_content()
    for mvp in c.mvps.values():
        card_ids = [d.item_id for d in mvp.drops if d.item_id in c.cards]
        assert card_ids, f"{mvp.id} 沒有掉自己的卡"


def test_starter_weapon_per_job_buyable():
    c = content.load_content()
    weapons = [e for e in c.equipment.values() if e.slot == "weapon"]
    assert len(weapons) >= 6
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_data_files_valid.py -v`
Expected: FAIL

- [ ] **Step 3: 填 6 個資料檔**

若 Task 2 的 `DropEntry` 需要加 `zeny_min`/`zeny_max`，一併改 `shared/content.py` 與其測試。

- [ ] **Step 4: 跑全部內容測試確認通過**

Run: `uv run pytest tests/test_data_files_valid.py tests/test_content_loader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/ shared/content.py tests/
git commit -m "feat: v1 MVP/職業/技能/裝備/卡片資料"
```

---

## Task 8: `content check` admin 子指令

**Files:**
- Modify: `server/admin.py`
- Test: `tests/test_admin_content.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_admin_content.py`**

```python
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_content_check_reports_counts():
    result = subprocess.run(
        [sys.executable, "-m", "server.admin", "content", "check"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0
    assert "monsters" in result.stdout
    assert "OK" in result.stdout or "通過" in result.stdout
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_admin_content.py -v`
Expected: FAIL

- [ ] **Step 3: 在 `server/admin.py` 加 `content` 子指令**

```python
def _cmd_content_check() -> None:
    from server import content

    c = content.load_content()
    for name in ["monsters", "mvps", "maps", "jobs", "skills", "equipment", "cards", "items"]:
        print(f"{name}: {len(getattr(c, name))}")
    print("引用完整性：OK")
```

在 `main()` 的 subparser 加：

```python
    p_content = sub.add_parser("content", help="內容資料工具")
    p_content.add_argument("action", choices=["check"])
```

並在指令分派加 `elif args.command == "content" and args.action == "check": _cmd_content_check()`。
`content check` 不需要 DB，`load_content()` 失敗會丟 `ContentError` → 非 0 退出。

- [ ] **Step 4: 跑測試確認通過**

Run: `uv run pytest tests/test_admin_content.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/admin.py tests/test_admin_content.py
git commit -m "feat: content check 子指令"
```

---

## Task 9: 文件與收尾

**Files:**
- Create: `docs/資料schema.md`
- Create: `docs/資料來源.md`
- Modify: `docs/superpowers/plans/README.md`（標記階段 2 完成）

- [ ] **Step 1: 寫 `docs/資料schema.md`**——每個 pydantic 模型的欄位表 + 每個 `effects` dict 的型別清單與範例。

- [ ] **Step 2: 寫 `docs/資料來源.md`**——本計畫「關鍵決策」那段搬進來，加：每個 `data/*.json` 的來源網址、v2 擴充步驟（新地圖 = ludens 名冊抓對應等級帶的怪 → baseline 產數值 → 加 row → `content check`）、已知偏離原版之處（口袋版屬性 vs 經典、卡片改經典風格）。

- [ ] **Step 3: 跑全套測試**

Run: `uv run pytest -q`
Expected: 全綠（地基 60 + 本階段新增約 30）。

- [ ] **Step 4: 端到端**

Run: `uv run python -m server.admin content check`
Expected: 印出各類數量 + 「引用完整性：OK」，退出碼 0。

- [ ] **Step 5: codex review**

Run: `codex review --base <階段 1 最後一個 commit>`
處理發現到 LGTM。

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "docs: 資料 schema 與來源說明；資料管線階段完成"
```

---

## Self-Review

**1. Spec coverage（對照 `docs/設計.md` §15）：**
- schema 一開始照最終還原度 → Task 1-3，欄位齊全（屬性/種族/體型/MVP 機制/卡片效果結構化/裝備孔位精煉）✓
- v1 資料量（怪 12~16 / 圖 8 / MVP 4~6 / 裝備 ~40 / 卡 16 / 技能 30）→ Task 6-7：14 怪 / 8 圖 / 6 MVP / ~30 裝備 / ~16 卡 / 32 技能 ✓（裝備比設計的 40 少，v1 夠用，v2 補）
- 可重用管線、v2 只加 row → Task 9 `docs/資料來源.md` 記錄流程 ✓
- 術語鎖 ludens/ntome → Task 6-7 名冊照抄 ✓
- 屬性相剋 v1.5 → `data/element_chart.json` 建好但戰鬥引擎 v1 不套用 ✓

**2. Placeholder scan：** Task 6/7 的資料內容用「表格 + 明確清單」而非逐行 JSON，因為資料量大且由實作者對照 ludens 逐筆填。每個資料檔都有對應的驗證測試把關（schema + 引用完整性 + 等級帶合理性），不是無把關的 TODO。

**3. Type consistency：**
- `CombatStats` 欄位（Task 2）↔ `monster_stats.baseline` 回傳（Task 4）↔ 載入器（Task 5）一致 ✓
- `MvpDef(MonsterDef)` 繼承（Task 3）↔ 載入器 `mvps` 索引（Task 5）↔ `test_mvps_loaded`（Task 7）一致 ✓
- `content.load_content()` / `get_monster` / `monsters_on_map` / `ContentError`（Task 5）↔ 各測試呼叫一致 ✓
- `DropEntry` 可能加 `zeny_min/zeny_max`（Task 7 Step 3）——若加，Task 2 測試要同步，已在 Task 7 註明 ✓

**4. 已知後續：** 技能 / 卡片 / 掉落的 `effects` dict 目前是 `list[dict]` 未型別化；戰鬥引擎階段會加 discriminated union 並回頭驗證 `data/skills.json` `data/cards.json`。本階段資料先照約定的型別字串填。

---

## Task 10: v1 資料擴充（練功路線補完）— 2026-09-06 追加

**問題：** Task 6-7 的 14 怪擠在 1~12 與 42~48，中間 13~41 級沒東西打，三張圖（礦洞/南區森林/下水道）掛的是墊檔怪。玩家練不到二轉。裝備有 21 件無取得來源。

**目標：** 雜怪補到約 36 隻、每張圖有自己真正的 5~7 隻怪 + 1 MVP，等級 1~50 連續。裝備每件至少一個來源。

### Task 10-A：`shared/content.py` 加裝備購買欄位

- `EquipmentDef` 加 `npc_buy: int | None = None`、`npc_sell: int = Field(default=0, ge=0)`。
- `tests/test_content_schema.py` 追加：入門武器 `npc_buy` 有值的斷言。

### Task 10-B：`data/monsters.json` 擴充到 ~36 隻

**保留現有 14 隻**，新增下列（名字/系/屬性/體型照 ludens 魔物出沒頁；數值 `baseline(level, role)` + 微調）：

| id | name | lv | 地圖 | race | element | size | role |
|---|---|---|---|---|---|---|---|
| bee_soldier | 蜂兵 | 14 | prontera_south_field | insect | wind | small | glass |
| poison_snail | 毒紋蝸牛 | 18 | prontera_south_field | insect | water | medium | tank |
| mole | 土撥鼠 | 16 | mjolnir_mine | animal | earth | small | normal |
| red_bat | 紅蝙蝠 | 17 | mjolnir_mine | animal | fire | small | glass |
| minion_miner | 礦工魔 | 19 | mjolnir_mine | demihuman | earth | small | normal |
| miner_foreman | 礦工工頭 | 20 | mjolnir_mine | demihuman | earth | large | tank |
| clay_doll | 泥人 | 22 | mjolnir_mine | formless | water | medium | normal |
| clay_monster | 泥怪 | 23 | mjolnir_mine | formless | water | large | tank |
| drop_poring | 水滴波利 | 24 | prontera_west_plain | angel | water | medium | glass |
| locust | 蝗蟲 | 25 | prontera_west_plain | insect | wind | medium | normal |
| heavy_locust | 重金屬蝗蟲 | 26 | prontera_west_plain | insect | wind | medium | normal |
| pobopoli | 波波利 | 27 | prontera_west_plain | angel | wind | medium | glass |
| ladybug | 瓢蟲 | 31 | prontera_south_forest | insect | wind | small | glass |
| cramy | 克瑞米 | 32 | prontera_south_forest | insect | wind | small | glass |
| forest_spirit | 森靈 | 34 | prontera_south_forest | formless | earth | medium | normal |
| bigfoot_bear | 大腳熊 | 35 | prontera_south_forest | animal | fire | large | tank |
| white_ghost | 白幽靈 | 37 | prontera_south_forest | undead | wind | small | glass |
| ghost_poring | 幽靈波利 | 38 | prontera_south_forest | undead | poison | medium | normal |
| white_rat | 白鼠 | 39 | prontera_sewer | animal | water | small | glass |
| blue_rat | 藍鼠 | 40 | prontera_sewer | animal | water | small | normal |
| familiar_thief_bug | 浮勒盜蟲 | 42 | prontera_sewer | insect | poison | medium | normal |
| poison_spore | 毒魔菇 | 43 | prontera_sewer | demon | poison | medium | normal |
| golden_bug | 黃金蟲 | 45 | prontera_sewer | insect | fire | large | tank |
| mal_thief_bug | 瑪勒盜蟲 | 45 | prontera_sewer | insect | poison | medium | normal |
| mandragora | 曼陀羅魔花 | 49 | prontera_north_forest | demon | shadow | large | normal |
| evil_sunflower | 邪惡向日葵 | 50 | prontera_north_forest | plant | holy | large | tank |
| queen_scarab | 女王甲蟲 | 44 | morroc_oasis | angel | holy | small | glass |
| dragonfly | 龍蠅 | 45 | morroc_oasis | insect | water | small | glass |

（雷極刺蝟已在；綠洲共 3 隻雜怪 + MVP。）

### Task 10-C：`data/maps.json` 校正等級帶與怪群

| id | level_range | unlock | monster_ids | mvp_id |
|---|---|---|---|---|
| prontera_east_gate | [1,10] | 1 | green_cotton_worm, mad_bunny, little_boar, chick, yoyo_monkey | angel_poring→改，見下 |
| prontera_south_field | [8,18] | 8 | raccoon, mushroom, grass_sprite, snail, bee_soldier, poison_snail | fierce_mushroom |
| prontera_west_plain | [1,30] | 1 | poring, drop_poring, locust, heavy_locust, pobopoli, tree_sprite | choco_monkey |
| mjolnir_mine | [15,25] | 14 | mole, red_bat, minion_miner, miner_foreman, clay_doll, clay_monster | angel_poring |
| prontera_south_forest | [28,40] | 26 | ladybug, cramy, forest_spirit, bigfoot_bear, white_ghost, ghost_poring | forest_guardian |
| prontera_sewer | [38,48] | 36 | white_rat, blue_rat, familiar_thief_bug, poison_spore, golden_bug, mal_thief_bug | queen_bee |
| prontera_north_forest | [45,55] | 44 | wolf, boar, mandragora, evil_sunflower | curly_boar_king |
| morroc_oasis | [42,52] | 40 | thunder_hedgehog, queen_scarab, dragonfly | raging_bigfoot |

> `mvp_id` 一圖一隻，其餘 MVP 的 `home_map_id` 可共用。angel_poring 掛礦洞（Lv16 貼齊礦洞帶）。

### Task 10-D：`data/mvps.json` 補到 8 隻

現有 6：angel_poring, fierce_mushroom, queen_bee, forest_guardian, choco_monkey, curly_boar_king。新增 2：

| id | name | lv | home_map_id | cooldown_h | element | race | size |
|---|---|---|---|---|---|---|---|
| raging_bigfoot | 狂暴大腳熊 | 36 | morroc_oasis | 12 | fire | animal | large |
| golden_bug_king | 黃金蟲王 | 45 | prontera_sewer | 24 | fire | insect | large |

（每張圖至少對得到一隻 MVP：east_gate 目前無——可接受，或把 angel_poring 掛 east_gate。實作者判斷，原則：8 張圖至少 6 張有 mvp_id。）

### Task 10-E：裝備來源補完

1. 入門武器 6 把 + 基礎防具（cotton_shirt, sandals, hood…）：填 `npc_buy`（武器 100~1500 Zeny 依 atk、防具 50~800）、`npc_sell` = npc_buy // 2。
2. 中階裝備（fine / 無 npc_buy 的）：加進新怪的 `drops`（rate 0.02~0.1），依等級帶對應——礦洞怪掉礦洞向裝備、森林怪掉森林向裝備。
3. legendary 裝備：只從 MVP drops（已有）。
4. 跑檢查：每件 `equipment` 的 id 要嘛有 `npc_buy`，要嘛出現在某個 monster/mvp 的 drops。新增測試 `test_every_equipment_obtainable`。

### Task 10-F：卡片補到 ~26 張

現有 16。為新怪補 ~8 張雜怪卡（clay_monster→armor DEF、mole→shoes、locust→weapon ASPD、bigfoot_bear→weapon ATK、ghost_poring→garment 暗抗、poison_spore→accessory 毒抗…）+ 新 2 隻 MVP 卡。全部進對應怪 drops。

### Task 10-G：驗證與 commit

- [x] `uv run pytest -q` 全綠（含新測試）— 97 passed
- [x] `uv run python -m server.admin content check` → monsters 42 / mvps 8 / cards 26
- [x] 新測試：`test_level_curve_has_no_gap`——1~50 每 5 級區間至少有 1 隻可打的怪
- [x] `test_every_equipment_obtainable`
- [x] codex review 到 LGTM
- [x] commit：`feat: v1 資料擴充——練功路線補完（~36 怪 / 8 MVP / ~26 卡）`

> 實作偏離規格處：下水道 `mvp_id` 用 `golden_bug_king`（Lv45）取代規格表的 `queen_bee`（Lv19），與該圖 [38,48] 等級帶一致；`queen_bee` 維持 `home_map_id: prontera_south_field`（與 base 相同，未被任何圖 feature，規格允許 home_map_id 共用）。
