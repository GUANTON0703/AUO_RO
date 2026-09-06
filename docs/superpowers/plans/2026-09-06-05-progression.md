# 養成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。
> **審核政策**：不跑 codex。分批做完跑 `uv run pytest -q` + 掃 diff；階段收尾一次自行審核。

**Goal:** 讓角色能練等、加點、點技能、轉職，並把掛機接上 API——`build_player_combatant` 把角色數值算成戰鬥用的 Combatant，掛機端點跑結算、把經驗灌進角色升級。做完角色就能在 API 上真的掛機練到二轉。

**Architecture:** 兩層。`server/progression/` 是純數值庫（等級曲線、加點成本、衍生數值公式、`build_player_combatant`）。`server/api/` 加養成端點（加點 / 技能 / 轉職 / 掛機 start-stop-status）+ `characters` 表加掛機狀態欄位。

**Tech Stack:** 沿用。

---

## 設計決策

1. **加點/技能點不用 `characters` 表既有的 `stat_points` / `skill_points` 欄位**（那兩欄留著沒用，之後 cleanup 再處理）。改成**從等級動態算**：
   - `stat_points_available = STARTER_STAT_POINTS(48) + Σ 每級給的點 - Σ 已花在各屬性上的點`
   - `skill_points_available = job_level - 1 + 前職帶過來的 - 已點的技能等級總和`（轉職保留已學技能）
2. **Pre-Renewal 骨架的簡化衍生公式**（記進抽象清單）：
   - `max_hp = round(40 + base_level * job.hp_per_level * (1 + VIT/100))`
   - `max_sp = round(11 + base_level * job.sp_per_level * (1 + INT/100))`
   - `atk = STR + (STR//10)**2 + DEX//5 + LUK//5 + 裝備atk`
   - `matk = INT + (INT//7)**2 + 裝備matk`
   - `defense = min(95, 裝備def總和 + VIT//2)`（引擎當百分比減傷，跟怪物一致）
   - `mdef = min(95, 裝備mdef總和 + INT//2)`
   - `hit = base_level + DEX + 裝備hit`
   - `flee = base_level + AGI + 裝備flee`
   - `aspd = min(193, round(100 + AGI*0.7 + DEX*0.15 + 裝備aspd))`（武器延遲 v1 忽略）
   - `crit = round(LUK/3) + 裝備crit`
   - `is_caster = matk > atk`
3. **加點成本**（Pre-Renewal 原式）：把某屬性從 V 加到 V+1 花 `(V // 10) + 2` 點。屬性上限 v1 設 99。
4. **每級給的屬性點**：`2 + (level // 5)`（Base Level 2→ 2 點、10→4 點…）。
5. **轉職**：v1 不做任務步驟。Job Level 達門檻（一轉 10 / 二轉 40）+ 呼叫端點即完成。轉職後 `job_id` 換、`job_level=1`、`job_exp=0`、**已學技能保留**。任務內容列 v1.5。
6. **等級上限**：v1 Base 50。Job：新手 10、一轉 50、二轉 70。曲線公式照能延伸到 Base 99+ 設計。
7. **掛機 API**：
   - `POST /api/hunt/start`：body `{map_id, monster_id?}`。驗證 `character.base_level >= map.unlock_base_level`。monster_id 省略時取該圖等級最接近角色的怪。設 hunt 狀態、hunt_hp/sp = 滿。
   - `POST /api/hunt/stop`：結算到現在、套用、清 hunt 狀態。
   - `GET /api/hunt/status`：結算 `now - hunt_last_settled_at`。間隔 > `online_grace_seconds`(120) → 離線模式（打折）；否則在線。套用經驗→升級、Zeny→`character.zeny`、掉落→累進 `hunt_loot` JSON（背包是第 6 階段，先不轉真物品）、更新 hunt_hp/sp/pity/last_settled。回事件 + 現況。撤退 → 自動清 hunt 狀態。
8. **掉落先不進背包**：`hunt_loot` JSON 累積，第 6 階段做背包時 drain。

---

## 檔案結構

```
server/progression/
  __init__.py        # build_player_combatant()
  levels.py          # base/job 經驗曲線、apply_base_exp / apply_job_exp
  stats.py           # 加點點數、成本、衍生數值公式
  skills.py          # 技能點、學技能、（v1 無 prereq）
server/api/
  progression.py     # POST /api/characters/{id}/stats、/skills、/jobchange
  hunt.py            # POST /api/hunt/start|stop、GET /api/hunt/status
server/db/
  schema.sql         # characters 加掛機欄位
server/repositories/
  characters.py      # 加掛機狀態讀寫、經驗/等級/zeny 更新
tests/
  test_progression_levels.py
  test_progression_stats.py
  test_progression_skills.py
  test_progression_combatant.py
  test_api_progression.py
  test_api_hunt.py
```

---

## Task 1: 等級曲線與經驗套用

**Files:** Create `server/progression/__init__.py`(空), `server/progression/levels.py`; Test `tests/test_progression_levels.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_progression_levels.py`**

```python
from server.progression.levels import (
    base_exp_for_next, job_exp_for_next, apply_base_exp, apply_job_exp,
    BASE_LEVEL_CAP, job_level_cap,
)


def test_exp_curve_is_increasing():
    assert base_exp_for_next(1) < base_exp_for_next(10) < base_exp_for_next(40)


def test_base_level_cap_is_50_in_v1():
    assert BASE_LEVEL_CAP == 50


def test_job_level_cap_by_tier():
    assert job_level_cap("novice") == 10
    assert job_level_cap("first") == 50
    assert job_level_cap("second") == 70


def test_apply_base_exp_single_levelup():
    # 剛好夠升一級
    need = base_exp_for_next(1)
    lv, exp, gained_stat_pts = apply_base_exp(cur_level=1, cur_exp=0, amount=need)
    assert lv == 2
    assert exp == 0
    assert gained_stat_pts == (2 + 2 // 5)


def test_apply_base_exp_multi_levelup_and_remainder():
    total = base_exp_for_next(1) + base_exp_for_next(2) + 5
    lv, exp, _ = apply_base_exp(cur_level=1, cur_exp=0, amount=total)
    assert lv == 3
    assert exp == 5


def test_apply_base_exp_stops_at_cap():
    lv, exp, _ = apply_base_exp(cur_level=49, cur_exp=0, amount=10**12)
    assert lv == 50
    assert exp == 0   # 滿級經驗歸零不溢出


def test_apply_job_exp_gives_skill_points():
    need = job_exp_for_next(1, "first")
    jl, jexp, skill_pts = apply_job_exp(cur_job_level=1, cur_job_exp=0,
                                        amount=need, tier="first")
    assert jl == 2
    assert skill_pts == 1
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/progression/levels.py`**

```python
BASE_LEVEL_CAP = 50
_JOB_CAP = {"novice": 10, "first": 50, "second": 70}


def job_level_cap(tier: str) -> int:
    return _JOB_CAP[tier]


def base_exp_for_next(level: int) -> int:
    """從 level 升到 level+1 所需經驗。曲線可延伸到 99+。"""
    return round(30 * level**2.4 + 40 * level + 30)


def job_exp_for_next(job_level: int, tier: str) -> int:
    mult = {"novice": 0.6, "first": 1.0, "second": 1.8}[tier]
    return round((20 * job_level**2.2 + 30 * job_level + 20) * mult)


def stat_points_at_level(level: int) -> int:
    return 2 + (level // 5)


def apply_base_exp(cur_level: int, cur_exp: int, amount: int):
    level, exp = cur_level, cur_exp + amount
    gained = 0
    while level < BASE_LEVEL_CAP and exp >= base_exp_for_next(level):
        exp -= base_exp_for_next(level)
        level += 1
        gained += stat_points_at_level(level)
    if level >= BASE_LEVEL_CAP:
        exp = 0
    return level, exp, gained


def apply_job_exp(cur_job_level: int, cur_job_exp: int, amount: int, tier: str):
    cap = job_level_cap(tier)
    level, exp = cur_job_level, cur_job_exp + amount
    gained = 0
    while level < cap and exp >= job_exp_for_next(level, tier):
        exp -= job_exp_for_next(level, tier)
        level += 1
        gained += 1
    if level >= cap:
        exp = 0
    return level, exp, gained
```

- [ ] **Step 4: 跑通過** PASS（7 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 等級曲線與經驗套用"`

---

## Task 2: 加點系統

**Files:** Create `server/progression/stats.py`; Test `tests/test_progression_stats.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_progression_stats.py`**

```python
from server.progression.stats import (
    STARTER_STAT_POINTS, raise_cost, total_earned_stat_points,
    points_spent_on, stat_points_available, STAT_MAX,
)


def test_raise_cost_pre_renewal():
    assert raise_cost(1) == 2
    assert raise_cost(9) == 2
    assert raise_cost(10) == 3
    assert raise_cost(50) == 7


def test_points_spent_from_1_to_value():
    assert points_spent_on(1) == 0
    assert points_spent_on(2) == 2
    assert points_spent_on(11) == sum(raise_cost(v) for v in range(1, 11))


def test_total_earned_grows_with_level():
    assert total_earned_stat_points(1) == STARTER_STAT_POINTS
    assert total_earned_stat_points(10) > total_earned_stat_points(1)


def test_available_points_math():
    stats = {"str": 5, "agi": 1, "vit": 1, "int": 1, "dex": 1, "luk": 1}
    avail = stat_points_available(base_level=10, stats=stats)
    spent = points_spent_on(5)  # str 1→5
    assert avail == total_earned_stat_points(10) - spent


def test_stat_max_is_99():
    assert STAT_MAX == 99
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/progression/stats.py`**

```python
from server.progression.levels import stat_points_at_level

STARTER_STAT_POINTS = 48
STAT_MAX = 99
STAT_KEYS = ("str", "agi", "vit", "int", "dex", "luk")


def raise_cost(current_value: int) -> int:
    return (current_value // 10) + 2


def points_spent_on(value: int) -> int:
    return sum(raise_cost(v) for v in range(1, value))


def total_earned_stat_points(base_level: int) -> int:
    return STARTER_STAT_POINTS + sum(stat_points_at_level(l) for l in range(2, base_level + 1))


def points_spent(stats: dict) -> int:
    return sum(points_spent_on(stats[k]) for k in STAT_KEYS)


def stat_points_available(base_level: int, stats: dict) -> int:
    return total_earned_stat_points(base_level) - points_spent(stats)
```

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 加點點數與成本"`

---

## Task 3: 技能點系統

**Files:** Create `server/progression/skills.py`; Test `tests/test_progression_skills.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_progression_skills.py`**

```python
from server.progression.skills import skill_points_available, can_learn


def test_skill_points_from_job_level_minus_learned():
    learned = {"bash": 3, "provoke": 1}
    # 一轉 Job 10 → 9 點可用，已點 4 → 剩 5
    avail = skill_points_available(job_level=10, learned=learned, carried=0)
    assert avail == (10 - 1) - 4


def test_carried_points_from_previous_job():
    avail = skill_points_available(job_level=1, learned={}, carried=9)
    assert avail == 9


def test_can_learn_checks_job_and_points():
    from server.content import load_content
    c = load_content()
    # bash 屬於 swordman
    ok, reason = can_learn(c, character_job="swordman", skill_id="bash",
                           target_level=1, current_learned={}, points_available=5)
    assert ok is True
    bad, _ = can_learn(c, character_job="mage", skill_id="bash", target_level=1,
                       current_learned={}, points_available=5)
    assert bad is False


def test_cannot_exceed_skill_max_level():
    from server.content import load_content
    c = load_content()
    maxlv = c.skills["bash"].max_level
    ok, _ = can_learn(c, "swordman", "bash", target_level=maxlv + 1,
                      current_learned={}, points_available=99)
    assert ok is False


def test_not_enough_points():
    from server.content import load_content
    c = load_content()
    ok, _ = can_learn(c, "swordman", "bash", target_level=3,
                      current_learned={}, points_available=1)
    assert ok is False   # 從 0 點到 3 要 3 點
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/progression/skills.py`**

```python
def skill_points_available(job_level: int, learned: dict, carried: int = 0) -> int:
    return (job_level - 1) + carried - sum(learned.values())


def can_learn(content, character_job: str, skill_id: str, target_level: int,
              current_learned: dict, points_available: int) -> tuple[bool, str]:
    skill = content.skills.get(skill_id)
    if skill is None:
        return False, "技能不存在"
    if skill.job_id != character_job:
        return False, "非本職技能"
    if target_level < 1 or target_level > skill.max_level:
        return False, "技能等級超出範圍"
    have = current_learned.get(skill_id, 0)
    if target_level <= have:
        return False, "已達或超過該等級"
    if target_level - have > points_available:
        return False, "技能點不足"
    return True, ""
```

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 技能點系統"`

---

## Task 4: build_player_combatant

**Files:** Modify `server/progression/__init__.py`; Test `tests/test_progression_combatant.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_progression_combatant.py`**

```python
from server.progression import build_player_combatant, CharacterSnapshot
from server.content import load_content


def _snap(**kw):
    base = dict(name="測試", job_id="swordman", base_level=15, job_level=8,
                stats={"str": 30, "agi": 15, "vit": 20, "int": 5, "dex": 18, "luk": 8},
                learned_skills={"bash": 3}, equipped_item_ids=[], socketed_card_ids=[],
                hp=None, sp=None)
    base.update(kw)
    return CharacterSnapshot(**base)


def test_derived_stats_from_primary():
    c = load_content()
    cb = build_player_combatant(_snap(), c)
    assert cb.name == "測試"
    assert cb.max_hp > 40
    assert cb.atk >= 30            # 至少等於 STR
    assert cb.hit == 15 + 18       # base_level + DEX
    assert cb.flee == 15 + 15
    assert 100 <= cb.aspd <= 193


def test_equipment_adds_stats():
    c = load_content()
    bare = build_player_combatant(_snap(equipped_item_ids=[]), c)
    armed = build_player_combatant(_snap(equipped_item_ids=["knife"]), c)
    assert armed.atk > bare.atk    # knife atk 17


def test_card_flat_stat_applies():
    c = load_content()
    plain = build_player_combatant(_snap(equipped_item_ids=["cotton_shirt"]), c)
    carded = build_player_combatant(
        _snap(equipped_item_ids=["cotton_shirt"], socketed_card_ids=["poring_card"]), c)
    assert carded.max_hp > plain.max_hp   # poring_card +100 HP


def test_learned_active_skills_become_resolved():
    c = load_content()
    cb = build_player_combatant(_snap(learned_skills={"bash": 3}), c)
    bash = [s for s in cb.skills if s.skill_id == "bash"]
    assert bash and bash[0].level == 3
    assert bash[0].kind == "active"


def test_passive_skill_modifies_stats_not_added_as_active():
    c = load_content()
    # sword_mastery 是 swordman 的 passive_stat atk
    with_pas = build_player_combatant(_snap(learned_skills={"bash": 1, "sword_mastery": 5}), c)
    without = build_player_combatant(_snap(learned_skills={"bash": 1}), c)
    assert with_pas.atk > without.atk
    assert not any(s.skill_id == "sword_mastery" for s in with_pas.skills)


def test_hp_sp_default_to_max_when_none():
    c = load_content()
    cb = build_player_combatant(_snap(hp=None, sp=None), c)
    assert cb.hp == cb.max_hp and cb.sp == cb.max_sp


def test_hp_sp_preserved_when_given():
    c = load_content()
    cb = build_player_combatant(_snap(hp=50, sp=10), c)
    assert cb.hp == 50 and cb.sp == 10
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/progression/__init__.py`**

```python
from dataclasses import dataclass, field

from server.combat.combatant import Combatant, ResolvedSkill


@dataclass
class CharacterSnapshot:
    name: str
    job_id: str
    base_level: int
    job_level: int
    stats: dict                       # str/agi/vit/int/dex/luk
    learned_skills: dict = field(default_factory=dict)   # skill_id -> level
    equipped_item_ids: list = field(default_factory=list)
    socketed_card_ids: list = field(default_factory=list)
    hp: int | None = None
    sp: int | None = None


def _sum_equipment_stats(content, item_ids: list) -> dict:
    acc: dict = {}
    for iid in item_ids:
        eq = content.equipment.get(iid)
        if not eq:
            continue
        for k, v in eq.stats.items():
            acc[k] = acc.get(k, 0) + v
    return acc


def _apply_card_effects(content, card_ids: list, out: dict) -> None:
    for cid in card_ids:
        card = content.cards.get(cid)
        if not card:
            continue
        for eff in card.effects:
            t = eff.get("type")
            if t == "flat_stat":
                out[eff["stat"]] = out.get(eff["stat"], 0) + eff["amount"]
            elif t == "percent_stat":
                out[eff["stat"]] = round(out.get(eff["stat"], 0) * (1 + eff["pct"] / 100)) \
                    if out.get(eff["stat"]) else out.get(eff["stat"], 0)
            # element_resist / race_damage / proc：戰鬥引擎 v1 尚未支援，略過


def _passive_stat_bonus(content, learned: dict) -> dict:
    bonus: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "passive":
            continue
        for eff in sk.effects:
            if eff.get("type") == "passive_stat":
                seq = eff.get("amount", [0])
                val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
                bonus[eff["stat"]] = bonus.get(eff["stat"], 0) + val
    return bonus


def build_player_combatant(snap: CharacterSnapshot, content) -> Combatant:
    job = content.get_job(snap.job_id)
    s = snap.stats
    STR, AGI, VIT, INT, DEX, LUK = (s["str"], s["agi"], s["vit"], s["int"], s["dex"], s["luk"])

    eq = _sum_equipment_stats(content, snap.equipped_item_ids)
    passives = _passive_stat_bonus(content, snap.learned_skills)

    max_hp = round(40 + snap.base_level * job.hp_per_level * (1 + VIT / 100))
    max_sp = round(11 + snap.base_level * job.sp_per_level * (1 + INT / 100))
    atk = STR + (STR // 10) ** 2 + DEX // 5 + LUK // 5 + eq.get("atk", 0) + passives.get("atk", 0)
    matk = INT + (INT // 7) ** 2 + eq.get("matk", 0) + passives.get("matk", 0)
    defense = min(95, eq.get("def", 0) + VIT // 2 + passives.get("defense", 0))
    mdef = min(95, eq.get("mdef", 0) + INT // 2)
    hit = snap.base_level + DEX + eq.get("hit", 0)
    flee = snap.base_level + AGI + eq.get("flee", 0)
    aspd = min(193, round(100 + AGI * 0.7 + DEX * 0.15 + eq.get("aspd", 0)))
    crit = round(LUK / 3) + eq.get("crit", 0)

    derived = {"max_hp": max_hp, "max_sp": max_sp, "atk": atk, "matk": matk,
               "defense": defense, "mdef": mdef, "hit": hit, "flee": flee,
               "crit": crit}
    _apply_card_effects(content, snap.socketed_card_ids, derived)

    resolved = []
    for sid, lvl in snap.learned_skills.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        sp_cost = sk.sp_cost[min(lvl, len(sk.sp_cost)) - 1] if sk.sp_cost else 0
        resolved.append(ResolvedSkill(
            skill_id=sid, name=sk.name, level=lvl, kind="active",
            sp_cost=sp_cost, cooldown_rounds=round(sk.cooldown_s / 2),
            effects=sk.effects, trigger=idle.get("trigger", "every_turn"),
            priority=idle.get("priority", 1),
        ))

    return Combatant(
        name=snap.name, max_hp=derived["max_hp"], max_sp=derived["max_sp"],
        atk=max(0, derived["atk"]), matk=max(0, derived["matk"]),
        defense=max(0, min(95, derived["defense"])), mdef=max(0, min(95, derived["mdef"])),
        hit=max(0, derived["hit"]), flee=max(0, derived["flee"]),
        aspd=max(1, min(193, aspd)), crit=max(0, derived["crit"]),
        is_caster=(derived["matk"] > derived["atk"]),
        skills=resolved,
        hp=snap.hp if snap.hp is not None else 0,
        sp=snap.sp if snap.sp is not None else 0,
    )
```

> `_apply_card_effects` 的 percent_stat 實作有點繞（要先有 base 值才乘）——以測試為準，`test_card_flat_stat_applies` 只驗 flat。percent 的細節實作對齊「對該 derived 值做 ×(1+pct/100)」即可。

- [ ] **Step 4: 跑通過** PASS（7 個）
- [ ] **Step 5: Commit** `git commit -m "feat: build_player_combatant"`

---

## Task 5: characters 表加掛機欄位 + repository

**Files:** Modify `server/db/schema.sql`, `server/repositories/characters.py`; Test `tests/test_repo_characters.py`（新增）

- [ ] **Step 1: `schema.sql` 的 characters 加欄位**

```sql
    hunting_map_id       TEXT,
    hunting_monster_id   TEXT,
    hunt_started_at      TEXT,
    hunt_last_settled_at TEXT,
    hunt_hp              INTEGER,
    hunt_sp              INTEGER,
    hunt_pity            TEXT NOT NULL DEFAULT '{}',
    hunt_loot            TEXT NOT NULL DEFAULT '{}',
    learned_skills       TEXT NOT NULL DEFAULT '{}',
    equipped_items       TEXT NOT NULL DEFAULT '[]',
    socketed_cards       TEXT NOT NULL DEFAULT '[]'
```

> 因為是 `CREATE TABLE IF NOT EXISTS` + 開發期無正式資料，直接改 schema、砍掉本機 `rotxt.db` 重建即可。若要保留舊資料需寫 migration——v1 開發期不需要。測試用 tmp db 不受影響。

- [ ] **Step 2: 寫失敗測試（追加到 `tests/test_repo_characters.py`）**

```python
def test_hunt_state_round_trips(account_id):
    row = characters.create_character(account_id, "掛機仔", location_map="m")
    characters.set_hunt_state(row["id"], map_id="prontera_east_gate",
                              monster_id="poring", started_at="T0", last_settled_at="T0",
                              hp=100, sp=20)
    got = characters.get_character(row["id"])
    assert got["hunting_map_id"] == "prontera_east_gate"
    assert got["hunt_hp"] == 100
    characters.clear_hunt_state(row["id"])
    assert characters.get_character(row["id"])["hunting_map_id"] is None


def test_apply_progression_updates_level_exp_zeny(account_id):
    row = characters.create_character(account_id, "練功仔", location_map="m")
    characters.apply_progression(row["id"], base_level=5, base_exp=120,
                                 job_level=3, job_exp=40, zeny_delta=500)
    got = characters.get_character(row["id"])
    assert got["base_level"] == 5 and got["zeny"] == 500


def test_merge_hunt_loot_and_pity(account_id):
    row = characters.create_character(account_id, "撿寶仔", location_map="m")
    characters.merge_hunt_loot(row["id"], {"jellopy": 10}, {"poring_card": 300})
    characters.merge_hunt_loot(row["id"], {"jellopy": 5, "clover": 2}, {"poring_card": 500})
    got = characters.get_character(row["id"])
    import json
    assert json.loads(got["hunt_loot"]) == {"jellopy": 15, "clover": 2}
    assert json.loads(got["hunt_pity"]) == {"poring_card": 500}
```

- [ ] **Step 3: 實作 `characters.py` 的新函式**——`set_hunt_state` / `clear_hunt_state` / `apply_progression(id, base_level, base_exp, job_level, job_exp, zeny_delta)` / `merge_hunt_loot(id, loot_delta, pity_replace)` / `set_learned_skills` / `set_stats` / `set_job`。都走既有 `connection.get_connection()`。

- [ ] **Step 4: 跑通過**
- [ ] **Step 5: Commit** `git commit -m "feat: characters 掛機狀態欄位與 repository"`

---

## Task 6: 加點 / 技能 / 轉職 API

**Files:** Create `server/api/progression.py`; Modify `server/app.py`; Test `tests/test_api_progression.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_api_progression.py`**（用 `conftest.py` 的 `auth` fixture）

```python
def _make_char(client, headers, name="勇者"):
    return client.post("/api/characters", headers=headers, json={"name": name}).json()


def test_allocate_stats(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/stats", headers=headers,
                    json={"str": 3})
    assert r.status_code == 200
    assert r.json()["stat_str"] == 4   # 1 → 4


def test_allocate_stats_rejects_insufficient_points(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    r = client.post(f"/api/characters/{ch['id']}/stats", headers=headers,
                    json={"str": 99})
    assert r.status_code == 400


def test_learn_skill_requires_job_and_points(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    # 新手學不了劍士技能
    r = client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                    json={"skill_id": "bash", "level": 1})
    assert r.status_code == 400


def test_jobchange_gated_on_job_level(client, auth):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    # Job 1 新手轉不了
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "swordman"})
    assert r.status_code == 400


def test_jobchange_succeeds_at_job_10(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _make_char(client, headers)
    db_helpers.set_job_level(ch["id"], 10)   # conftest 提供的測試輔助
    r = client.post(f"/api/characters/{ch['id']}/jobchange", headers=headers,
                    json={"target_job_id": "swordman"})
    assert r.status_code == 200
    assert r.json()["job_id"] == "swordman"
    assert r.json()["job_level"] == 1
```

> `db_helpers` fixture：在 `conftest.py` 加一個小工具，直接下 SQL 改 job_level / base_level，方便測試跳過練功。

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 實作 `server/api/progression.py`**（3 個端點，用 `progression.stats` / `progression.skills` / `progression.levels` 驗證，寫回 `characters` repo）+ conftest 加 `db_helpers` + `app.py` 掛 router。

- [ ] **Step 4: 跑通過**
- [ ] **Step 5: Commit** `git commit -m "feat: 加點/技能/轉職 API"`

---

## Task 7: 掛機 API

**Files:** Create `server/api/hunt.py`; Modify `server/app.py`; Test `tests/test_api_hunt.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_api_hunt.py`**

```python
import time


def _ready_char(client, headers, db_helpers, base_level=20):
    ch = client.post("/api/characters", headers=headers, json={"name": "掛機王"}).json()
    db_helpers.set_base_level(ch["id"], base_level)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    return ch


def test_start_hunt_validates_unlock_level(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=1)
    r = client.post("/api/hunt/start", headers=headers,
                    json={"map_id": "prontera_north_forest"})   # unlock 44
    assert r.status_code == 400


def test_start_then_status_accrues_progress(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    assert client.post("/api/hunt/start", headers=headers,
                       json={"map_id": "prontera_south_field"}).status_code == 200
    # 直接改 hunt_last_settled_at 往前推 1 小時，模擬掛了一小時
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    r = client.get("/api/hunt/status", headers=headers)
    body = r.json()
    assert body["kills"] > 0
    assert body["character"]["base_exp"] >= 0
    assert any(e["kind"] == "kill_batch" for e in body["events"])


def test_offline_gap_applies_efficiency(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=6 * 3600)   # 離線 6 小時
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["offline"] is True
    assert r["effective_seconds"] < 6 * 3600


def test_stop_hunt_settles_and_clears(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=1800)
    r = client.post("/api/hunt/stop", headers=headers)
    assert r.status_code == 200
    assert client.get("/api/hunt/status", headers=headers).status_code == 409  # 沒在掛機


def test_levelup_from_hunting(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=5)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    before = client.get("/api/characters", headers=headers).json()[0]["base_level"]
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["character"]["base_level"] >= before
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 實作 `server/api/hunt.py`**
  - `start`：驗證 unlock，選怪（給 monster_id 用給的、否則挑該圖等級最接近角色 base_level 的），`set_hunt_state`，`hunt_hp/sp` = `build_player_combatant` 的 max。
  - `status`：讀 hunt 狀態 → 建 CharacterSnapshot（含 learned_skills/equipped/cards/hunt_hp/hunt_sp）→ `build_player_combatant` → `settle(elapsed = now - hunt_last_settled_at, offline = elapsed > online_grace)` → `apply_base_exp` / `apply_job_exp` → `characters.apply_progression` + `merge_hunt_loot(drops, pity_out)` + 更新 hunt_hp/sp（= result.final_hp/sp）+ `hunt_last_settled_at = now`。撤退 → `clear_hunt_state`。回 `{kills, base_exp, job_exp, zeny, drops, offline, effective_seconds, retreated, events, character:{...}}`。
  - `stop`：跑一次 status 的結算邏輯 + `clear_hunt_state`。
  - `online_grace_seconds` 加進 `server/config.py`（預設 120）。
  - conftest `db_helpers` 加 `rewind_hunt(id, seconds)`（把 hunt_last_settled_at 往前推）、`set_base_level` / `set_stats`。

- [ ] **Step 4: 跑通過**
- [ ] **Step 5: 手動 e2e**（起服務、admin 產碼、註冊登入、建角色、`db` 直接改等級、start hunt、rewind、status）——或寫成 `scripts/hunt_demo.py`
- [ ] **Step 6: Commit** `git commit -m "feat: 掛機 API（start/stop/status）"`

---

## Task 8: 自行審核與文件

- [ ] **Step 1: 全套測試** `uv run pytest -q` 全綠
- [ ] **Step 2: 自行審核** 讀 `server/progression/` + `server/api/progression.py` + `server/api/hunt.py`，重點：
  - 衍生數值公式：`build_player_combatant` 出來的 Combatant，Lv15 劍士 / Lv15 法師數值合不合理（用 `scripts/hunt_demo.py` 或臨時腳本印出來看）
  - 加點/技能點的「可用點數」算式：available >= 0 恆成立、超花會被擋
  - 掛機 status 的離線/在線判定、經驗套用、hunt_hp/sp 續存、撤退清狀態
  - 轉職後 job_level 重置、技能保留、能學新職技能
  - RNG：掛機結算每次 status 用新 seed（或從 last_settled 時間戳導）——不要每次都同 seed 導致掉落固定
  - 併發：兩個 status 請求同時打進來會不會重複結算（用 `hunt_last_settled_at` 當樂觀鎖，或 `BEGIN IMMEDIATE`）
- [ ] **Step 3: 更新 `docs/抽象清單.md`**（養成階段）：
  - #12 衍生數值用簡化 Pre-Renewal 公式（非查表）
  - #13 ASPD 不算武器延遲
  - #14 轉職無任務步驟，純 Job Level 門檻
  - #15 掛機結算的隨機性由「結算時間戳」導 seed
- [ ] **Step 4: 更新 `docs/superpowers/plans/README.md`** 標記階段 5 完成，並在依賴欄註明「打寶(6) 會 drain hunt_loot、接背包/裝備」
- [ ] **Step 5: Commit** `git commit -m "docs: 養成階段抽象清單；階段 5 完成"`

---

## Self-Review（寫計畫時）

**1. 對照設計文件 §6：**
- 雙等級 Base/Job ✓（levels.py）
- 手動加屬性點（Pre-Renewal 成本）✓（stats.py + API）
- 手動點技能樹 ✓（skills.py + API），每職 5 技能已在資料階段
- 新手 → Job 10 一轉、達門檻二轉 ✓（jobchange API，門檻 10/40）
- 洗點 v1 開發期免費：**本計畫沒做洗點**——列入 Task 8 的已知後續或第 7 階段。加點目前是單向的（沒有 reset）。可接受，v1 開發期先不需要，正式版再加。
- 掛機技能優先序：`idle_default` 從資料帶進 ResolvedSkill ✓（build_player_combatant）——玩家自訂優先序的 API 列第 7 或客戶端階段

**2. Placeholder scan：** Task 5 Step 3 / Task 6 Step 3 / Task 7 Step 3 用條列描述而非完整程式——這三個是 CRUD + 組裝邏輯，pattern 明確（照既有 repo/api 風格），可接受。`db_helpers` fixture 的細節留給實作者，測試已定義它要提供什麼方法。

**3. Type consistency：**
- `CharacterSnapshot` 欄位（Task 4）↔ Task 7 status 端點組裝時要填的欄位一致
- `build_player_combatant(snap, content) -> Combatant`（Task 4）↔ Task 7 呼叫一致
- `apply_base_exp(cur_level, cur_exp, amount) -> (level, exp, stat_pts)`（Task 1）↔ Task 7 呼叫一致
- `settle(...)` 簽名（第 4 階段）↔ Task 7 呼叫：`offline` / `pity_in` / 補品參數——Task 7 要從 character 的補品欄位帶（但背包是第 6 階段！）→ **v1 Task 7 先不帶補品**（`potion_count=0`），掛機沒補品就靠血量硬撐、撐不住撤退。補品接背包後第 6 階段補上。這條要在 Task 7 明講。
- `ResolvedSkill` 欄位 ↔ 戰鬥引擎的 ResolvedSkill 一致（沿用）

**4. 已知後續：**
- 補品：Task 7 先 `potion_count=0`；第 6 階段接背包後，掛機讀角色補品欄位帶進 `settle`
- `hunt_loot` 累積的掉落 → 第 6 階段做背包時 drain 成真物品
- 洗點、玩家自訂掛機技能優先序 → 之後
- `characters` 表的 `stat_points` / `skill_points` 欄位變成 dead（改用等級動態算）→ 之後 cleanup migration
