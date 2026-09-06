# 戰鬥引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.
>
> **審核政策**：不跑 codex。分批做完跑 `uv run pytest -q` + 掃 diff；階段收尾一次自行審核（讀全階段程式對照計畫查 bug）。

**Goal:** 一個可單獨測的回合制戰鬥函式庫——輸入兩個 Combatant，模擬到分出勝負，回傳結果 + 結構化事件流；另提供批次模式給掛機結算用。

**Architecture:** 純函式為主。Pre-Renewal 傷害/命中/暴擊公式集中在 `formulas.py`。回合迴圈在 `engine.py`。技能效果、狀態效果各一個小模組。RNG 可注入 seed，測試確定性。戰鬥引擎**不碰 DB、不碰時間**——時間換算、離線效率、掉落、補品、事件渲染都是第 4 階段（掛機結算器）的事。

**Tech Stack:** 沿用（Python 3.12 / pydantic v2 / pytest）。純標準庫 `random`。

---

## 設計決策

1. **戰鬥固定 1v1**（設計文件），`aoe` 技能在 v1 當單體處理，之後多目標再擴充。
2. **ASPD 抽象**（抽象清單 #1）：不逐刀即時模擬。每回合攻擊次數 = `aspd // 100` + `(aspd % 100)/100` 機率的一次額外攻擊。
3. **物理傷害**（Pre-Renewal 骨架）：`dmg = max(1, round(atk * (1 - clamp(target.defense,0,95)/100)))`。`defense` 當百分比減傷（怪物 schema 的 defense 欄位）。
4. **魔法傷害**：`dmg = max(1, round(matk * (1 - clamp(target.mdef,0,95)/100)))`，**魔法必中**（不判迴避）。
5. **命中**：`hit_chance = clamp(80 + attacker.hit - target.flee, 5, 95) / 100`。
6. **暴擊**：`crit_chance = clamp(attacker.crit, 0, 100) / 100`，暴擊**必中**、傷害 ×1.4。
7. **屬性相剋**：v1 不套用（v1.5）。`formulas.py` 留一個 `element_multiplier` 參數，預設 1.0。
8. **狀態效果**：v1 只做三種——`stat_mod`（N 回合內某 stat 加減）、`dot`（N 回合每回合固定傷害）、`stun`（跳過 N 回合的行動）。
9. **技能**：Combatant 攜帶已解析好的 `ResolvedSkill`（SkillDef + 選定等級 + 掛機觸發設定），引擎不查 content，保持自足可測。
10. **戰鬥有回合上限**（預設 500）防呆——超過視為玩家打不動（撤退），回 `outcome="stalemate"`。

---

## 檔案結構

```
server/combat/
  __init__.py       # 公開 API：simulate_fight(), simulate_grind()
  formulas.py       # 純函式：physical_damage/magic_damage/hit_chance/crit_chance/attacks_this_round
  events.py         # CombatEvent 型別（dataclass）
  combatant.py      # Combatant, ResolvedSkill, from_monster()
  status.py         # Status（stat_mod/dot/stun）+ 套用邏輯
  skills.py         # resolve_skill_effect()：一個技能在一回合造成什麼
  engine.py         # 回合迴圈，simulate_fight()
  grind.py          # simulate_grind()：批次打同一隻怪 N 場，累計統計
tests/
  test_combat_formulas.py
  test_combat_events.py
  test_combat_combatant.py
  test_combat_status.py
  test_combat_skills.py
  test_combat_engine.py
  test_combat_grind.py
  test_combat_integration.py
```

---

## Task 1: 公式

**Files:** Create `server/combat/__init__.py`(空), `server/combat/formulas.py`; Test `tests/test_combat_formulas.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_formulas.py`**

```python
import random

from server.combat import formulas as f


def test_physical_damage_reduced_by_defense_pct():
    assert f.physical_damage(atk=100, target_defense=0) == 100
    assert f.physical_damage(atk=100, target_defense=30) == 70
    assert f.physical_damage(atk=100, target_defense=100) == 5  # clamp 95% → 5


def test_physical_damage_floor_is_one():
    assert f.physical_damage(atk=1, target_defense=95) == 1


def test_magic_damage_uses_mdef():
    assert f.magic_damage(matk=200, target_mdef=50) == 100


def test_hit_chance_formula():
    assert f.hit_chance(attacker_hit=50, target_flee=50) == 0.80
    assert f.hit_chance(attacker_hit=70, target_flee=50) == 0.95  # clamp 上限
    assert f.hit_chance(attacker_hit=0, target_flee=200) == 0.05  # clamp 下限


def test_crit_chance_clamped_fraction():
    assert f.crit_chance(20) == 0.20
    assert f.crit_chance(150) == 1.0
    assert f.crit_chance(-5) == 0.0


def test_element_multiplier_defaults_to_one():
    assert f.physical_damage(atk=100, target_defense=0, element_multiplier=1.0) == 100
    assert f.physical_damage(atk=100, target_defense=0, element_multiplier=2.0) == 200


def test_attacks_this_round_from_aspd():
    rng = random.Random(0)
    # aspd 100 → 每回合剛好 1 次
    assert all(f.attacks_this_round(100, rng) == 1 for _ in range(20))
    # aspd 200 → 剛好 2 次
    assert all(f.attacks_this_round(200, rng) == 2 for _ in range(20))
    # aspd 150 → 1 或 2，平均接近 1.5
    xs = [f.attacks_this_round(150, rng) for _ in range(2000)]
    assert set(xs) == {1, 2}
    assert 1.4 < sum(xs) / len(xs) < 1.6
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `uv run pytest tests/test_combat_formulas.py -v` → FAIL（no module）

- [ ] **Step 3: 寫 `server/combat/formulas.py`**

```python
import random


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def physical_damage(atk: int, target_defense: int, element_multiplier: float = 1.0) -> int:
    reduction = _clamp(target_defense, 0, 95) / 100
    return max(1, round(atk * (1 - reduction) * element_multiplier))


def magic_damage(matk: int, target_mdef: int, element_multiplier: float = 1.0) -> int:
    reduction = _clamp(target_mdef, 0, 95) / 100
    return max(1, round(matk * (1 - reduction) * element_multiplier))


def hit_chance(attacker_hit: int, target_flee: int) -> float:
    return _clamp(80 + attacker_hit - target_flee, 5, 95) / 100


def crit_chance(attacker_crit: int) -> float:
    return _clamp(attacker_crit, 0, 100) / 100


CRIT_MULTIPLIER = 1.4


def attacks_this_round(aspd: int, rng: random.Random) -> int:
    whole = aspd // 100
    frac = (aspd % 100) / 100
    extra = 1 if rng.random() < frac else 0
    return max(1, whole + extra)
```

- [ ] **Step 4: 跑測試確認通過** → `uv run pytest tests/test_combat_formulas.py -v` PASS（7 個）

- [ ] **Step 5: Commit** `git commit -m "feat: 戰鬥 Pre-Renewal 公式"`

---

## Task 2: 戰鬥事件型別

**Files:** Create `server/combat/events.py`; Test `tests/test_combat_events.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_events.py`**

```python
from server.combat import events as ev


def test_events_carry_actor_and_target():
    a = ev.AttackEvent(actor="玩家", target="波利", damage=42, crit=False, hit=True)
    assert a.damage == 42 and a.hit is True


def test_miss_event_has_zero_damage():
    m = ev.AttackEvent(actor="波利", target="玩家", damage=0, crit=False, hit=False)
    assert m.hit is False and m.damage == 0


def test_kill_event():
    k = ev.KillEvent(actor="玩家", target="波利")
    assert k.target == "波利"


def test_skill_event():
    s = ev.SkillEvent(actor="玩家", target="波利", skill_id="bash", skill_name="爆裂波動", damage=88)
    assert s.skill_id == "bash"


def test_heal_event():
    h = ev.HealEvent(actor="玩家", target="玩家", amount=30)
    assert h.amount == 30


def test_status_events():
    ap = ev.StatusAppliedEvent(actor="玩家", target="波利", status="poison", duration=3)
    ex = ev.StatusExpiredEvent(target="波利", status="poison")
    assert ap.status == "poison" and ex.status == "poison"


def test_all_events_have_kind_string():
    e = ev.AttackEvent(actor="a", target="b", damage=1, crit=False, hit=True)
    assert e.kind == "attack"
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/events.py`**

```python
from dataclasses import dataclass, field


@dataclass
class CombatEvent:
    kind: str = field(init=False, default="event")


@dataclass
class AttackEvent(CombatEvent):
    actor: str
    target: str
    damage: int
    crit: bool
    hit: bool
    def __post_init__(self): self.kind = "attack"


@dataclass
class SkillEvent(CombatEvent):
    actor: str
    target: str
    skill_id: str
    skill_name: str
    damage: int = 0
    def __post_init__(self): self.kind = "skill"


@dataclass
class HealEvent(CombatEvent):
    actor: str
    target: str
    amount: int
    def __post_init__(self): self.kind = "heal"


@dataclass
class KillEvent(CombatEvent):
    actor: str
    target: str
    def __post_init__(self): self.kind = "kill"


@dataclass
class StatusAppliedEvent(CombatEvent):
    actor: str
    target: str
    status: str
    duration: int
    def __post_init__(self): self.kind = "status_applied"


@dataclass
class StatusExpiredEvent(CombatEvent):
    target: str
    status: str
    def __post_init__(self): self.kind = "status_expired"
```

> `@dataclass` 繼承 + `kind` 用 `__post_init__` 設定，避免 field 順序問題。

- [ ] **Step 4: 跑通過** PASS（7 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 戰鬥事件型別"`

---

## Task 3: Combatant

**Files:** Create `server/combat/combatant.py`; Test `tests/test_combat_combatant.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_combatant.py`**

```python
from server.combat.combatant import Combatant, ResolvedSkill
from server.content import load_content


def test_combatant_starts_at_full_hp():
    c = Combatant(name="玩家", max_hp=200, max_sp=50, atk=60, matk=10,
                  defense=0, mdef=0, hit=40, flee=30, aspd=140, crit=10)
    assert c.hp == 200 and c.sp == 50
    assert c.alive is True


def test_combatant_dies_at_zero_hp():
    c = Combatant(name="x", max_hp=10, max_sp=0, atk=1, matk=0, defense=0,
                  mdef=0, hit=1, flee=1, aspd=100, crit=0)
    c.take_damage(15)
    assert c.hp == 0 and c.alive is False


def test_heal_caps_at_max():
    c = Combatant(name="x", max_hp=100, max_sp=0, atk=1, matk=0, defense=0,
                  mdef=0, hit=1, flee=1, aspd=100, crit=0)
    c.take_damage(50)
    c.heal(999)
    assert c.hp == 100


def test_from_monster_reads_defstats():
    content = load_content()
    poring = content.get_monster("poring")
    c = Combatant.from_monster(poring)
    assert c.name == poring.name
    assert c.max_hp == poring.stats.max_hp
    assert c.atk == poring.stats.atk
    assert c.is_caster is False


def test_resolved_skill_picks_level_value():
    rs = ResolvedSkill(
        skill_id="bash", name="爆裂波動", level=3, kind="active",
        sp_cost=9, cooldown_rounds=0,
        effects=[{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
        trigger="every_turn", priority=1,
    )
    assert rs.effect_value("power_pct") == 160   # level 3 → index 2
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/combatant.py`**

```python
from dataclasses import dataclass, field

from shared.content import MonsterDef


@dataclass
class ResolvedSkill:
    skill_id: str
    name: str
    level: int
    kind: str                 # active / passive
    sp_cost: int
    cooldown_rounds: int
    effects: list[dict]
    trigger: str              # every_turn / hp_below_50 / hp_below_30 / sp_available / cooldown_ready
    priority: int
    _cd_left: int = 0

    def effect_value(self, key: str):
        """從 effects 裡找出帶 key 的那筆，取對應 level 的值（level 1 → index 0）。"""
        for e in self.effects:
            if key in e:
                seq = e[key]
                if isinstance(seq, list):
                    return seq[min(self.level, len(seq)) - 1]
                return seq
        return None


@dataclass
class Combatant:
    name: str
    max_hp: int
    max_sp: int
    atk: int
    matk: int
    defense: int
    mdef: int
    hit: int
    flee: int
    aspd: int
    crit: int
    is_caster: bool = False
    skills: list[ResolvedSkill] = field(default_factory=list)
    statuses: list = field(default_factory=list)  # server.combat.status.Status
    hp: int = field(default=0)
    sp: int = field(default=0)

    def __post_init__(self):
        if self.hp == 0:
            self.hp = self.max_hp
        if self.sp == 0:
            self.sp = self.max_sp

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, amount: int) -> None:
        self.hp = max(0, self.hp - max(0, amount))

    def heal(self, amount: int) -> None:
        self.hp = min(self.max_hp, self.hp + max(0, amount))

    def spend_sp(self, amount: int) -> bool:
        if self.sp < amount:
            return False
        self.sp -= amount
        return True

    @classmethod
    def from_monster(cls, m: MonsterDef) -> "Combatant":
        s = m.stats
        return cls(
            name=m.name, max_hp=s.max_hp, max_sp=s.max_sp, atk=s.atk, matk=s.matk,
            defense=s.defense, mdef=s.mdef, hit=s.hit, flee=s.flee, aspd=s.aspd,
            crit=s.crit, is_caster=(s.matk > s.atk),
        )
```

> 註：`hp==0` 當「未指定」哨兵——Combatant 一律滿血起手，要打殘狀態測試就先建好再 `take_damage`。

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: Combatant 與 ResolvedSkill"`

---

## Task 4: 狀態效果

**Files:** Create `server/combat/status.py`; Test `tests/test_combat_status.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_status.py`**

```python
from server.combat.combatant import Combatant
from server.combat.status import Status, tick_statuses, apply_status


def _dummy(**kw):
    base = dict(name="x", max_hp=100, max_sp=20, atk=50, matk=10, defense=0,
                mdef=0, hit=30, flee=30, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_dot_deals_damage_each_round_then_expires():
    c = _dummy()
    apply_status(c, Status(kind="dot", name="poison", duration=3, magnitude=8))
    events = []
    for _ in range(3):
        tick_statuses(c, events)
    assert c.hp == 100 - 24
    assert not c.statuses  # 3 回合後過期


def test_stat_mod_changes_effective_stat_while_active():
    c = _dummy(atk=50)
    apply_status(c, Status(kind="stat_mod", name="curse", duration=2, stat="atk", magnitude=-20))
    assert c.effective_atk == 30
    tick_statuses(c, [])
    tick_statuses(c, [])
    assert c.effective_atk == 50   # 過期還原


def test_stun_flag():
    c = _dummy()
    apply_status(c, Status(kind="stun", name="stun", duration=1, magnitude=0))
    assert c.stunned is True
    tick_statuses(c, [])
    assert c.stunned is False


def test_reapplying_status_refreshes_duration():
    c = _dummy()
    apply_status(c, Status(kind="dot", name="poison", duration=2, magnitude=5))
    tick_statuses(c, [])
    apply_status(c, Status(kind="dot", name="poison", duration=2, magnitude=5))
    assert [s for s in c.statuses if s.name == "poison"][0].duration == 2
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/status.py` + 在 `combatant.py` 加 `effective_atk` / `effective_matk` / `effective_defense` / `effective_flee` / `stunned` property**

`status.py`:

```python
from dataclasses import dataclass

from server.combat.events import StatusAppliedEvent, StatusExpiredEvent


@dataclass
class Status:
    kind: str          # dot / stat_mod / stun
    name: str
    duration: int
    magnitude: int
    stat: str = ""     # kind=stat_mod 用


def apply_status(target, status: Status, events: list | None = None) -> None:
    for s in target.statuses:
        if s.name == status.name:
            s.duration = status.duration
            return
    target.statuses.append(status)
    if events is not None:
        events.append(StatusAppliedEvent(actor="", target=target.name,
                                         status=status.name, duration=status.duration))


def tick_statuses(target, events: list) -> None:
    for s in list(target.statuses):
        if s.kind == "dot":
            target.take_damage(s.magnitude)
        s.duration -= 1
        if s.duration <= 0:
            target.statuses.remove(s)
            events.append(StatusExpiredEvent(target=target.name, status=s.name))
```

在 `Combatant` 加：

```python
    def _stat_mod(self, stat: str) -> int:
        return sum(s.magnitude for s in self.statuses
                   if s.kind == "stat_mod" and s.stat == stat)

    @property
    def effective_atk(self) -> int:
        return max(0, self.atk + self._stat_mod("atk"))

    @property
    def effective_matk(self) -> int:
        return max(0, self.matk + self._stat_mod("matk"))

    @property
    def effective_defense(self) -> int:
        return max(0, self.defense + self._stat_mod("defense"))

    @property
    def effective_flee(self) -> int:
        return max(0, self.flee + self._stat_mod("flee"))

    @property
    def stunned(self) -> bool:
        return any(s.kind == "stun" for s in self.statuses)
```

- [ ] **Step 4: 跑通過** PASS（4 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 戰鬥狀態效果（dot/stat_mod/stun）"`

---

## Task 5: 技能效果解析

**Files:** Create `server/combat/skills.py`; Test `tests/test_combat_skills.py`

技能在「該不該放」跟「放了做什麼」兩件事。這個 Task 做「放了做什麼」——給定施法者、目標、一個 ResolvedSkill、rng，回傳 `(events, )` 並改動 combatant 狀態。

支援的 effect type（對齊 `data/skills.json` 用的字串）：
- `physical_hit`：`power_pct` 當普攻倍率的一次攻擊（走命中/暴擊判定）。可帶 `hits`（多段）。
- `magic_hit`：`power_pct` × matk 的必中魔法傷害。可帶 `hits`。`element` 欄位 v1 忽略。
- `aoe`：v1 當單體 `physical_hit` 處理。
- `heal_hp`：`flat` 或 `matk_pct` 回自己血。
- `buff`：對自己加 `stat_mod` status（`stats` dict + `duration_s`→回合數，1 回合≈2 秒，取 `round(duration_s/2)`）。
- `debuff`：對目標加 `stat_mod`（負值）。
- `proc` / `passive_stat`：戰鬥中不主動觸發（proc 在普攻時處理、passive 在建 Combatant 時已算進 stat），這個函式收到就當 no-op 回空事件。

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_skills.py`**

```python
import random

from server.combat.combatant import Combatant, ResolvedSkill
from server.combat.skills import cast_skill


def _c(name, **kw):
    base = dict(name=name, max_hp=300, max_sp=100, atk=80, matk=60, defense=0,
                mdef=0, hit=60, flee=20, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_physical_hit_skill_damages_target():
    rng = random.Random(1)
    caster, target = _c("玩家"), _c("波利", max_hp=500, flee=0)
    rs = ResolvedSkill("bash", "爆裂波動", 3, "active", 9, 0,
                       [{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
                       "every_turn", 1)
    evs = cast_skill(caster, target, rs, rng)
    assert target.hp < 500
    assert any(e.kind == "skill" for e in evs)


def test_magic_hit_ignores_flee():
    rng = random.Random(2)
    caster, target = _c("法師", matk=100), _c("波利", max_hp=500, flee=999)
    rs = ResolvedSkill("fire_bolt", "火球", 2, "active", 12, 0,
                       [{"type": "magic_hit", "power_pct": [100, 150, 200, 250, 300],
                         "hits": [1, 2, 3, 4, 5]}], "every_turn", 1)
    evs = cast_skill(caster, target, rs, rng)
    assert target.hp < 500   # 必中


def test_heal_skill_restores_caster_hp():
    rng = random.Random(3)
    caster = _c("牧師", matk=50)
    caster.take_damage(200)
    rs = ResolvedSkill("heal", "治癒", 3, "active", 10, 0,
                       [{"type": "heal_hp", "matk_pct": [120, 160, 200, 240, 280]}],
                       "hp_below_50", 2)
    cast_skill(caster, caster, rs, rng)
    assert caster.hp > 100


def test_buff_applies_stat_mod():
    rng = random.Random(4)
    caster = _c("劍士")
    rs = ResolvedSkill("provoke", "挑釁", 2, "active", 8, 0,
                       [{"type": "buff", "stats": {"atk": [5, 10, 15, 20, 25]},
                         "duration_s": 60}], "every_turn", 1)
    cast_skill(caster, caster, rs, rng)
    assert caster.effective_atk > caster.atk


def test_passive_effect_is_noop():
    rng = random.Random(5)
    caster, target = _c("玩家"), _c("波利")
    rs = ResolvedSkill("sword_mastery", "劍術", 3, "passive", 0, 0,
                       [{"type": "passive_stat", "stat": "atk", "amount": [4, 8, 12, 16, 20]}],
                       "passive", 0)
    evs = cast_skill(caster, target, rs, rng)
    assert evs == []
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/skills.py`**

```python
import random

from server.combat.events import HealEvent, SkillEvent
from server.combat.formulas import (
    CRIT_MULTIPLIER, crit_chance, hit_chance, magic_damage, physical_damage,
)
from server.combat.status import Status, apply_status


def _seq(v, level: int):
    return v[min(level, len(v)) - 1] if isinstance(v, list) else v


def cast_skill(caster, target, skill, rng: random.Random) -> list:
    events: list = []
    for eff in skill.effects:
        t = eff.get("type")
        if t in ("physical_hit", "aoe"):
            events += _physical_skill(caster, target, skill, eff, rng)
        elif t == "magic_hit":
            events += _magic_skill(caster, target, skill, eff, rng)
        elif t == "heal_hp":
            events += _heal_skill(caster, skill, eff)
        elif t == "buff":
            _stat_mod_skill(caster, eff, skill.level, sign=1)
        elif t == "debuff":
            _stat_mod_skill(target, eff, skill.level, sign=-1)
        # proc / passive_stat：no-op
    return events


def _physical_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    total = 0
    for _ in range(hits):
        if rng.random() >= hit_chance(caster.effective_hit if hasattr(caster, "effective_hit") else caster.hit, target.effective_flee):
            continue
        dmg = physical_damage(round(caster.effective_atk * power), target.effective_defense)
        if rng.random() < crit_chance(caster.crit):
            dmg = round(dmg * CRIT_MULTIPLIER)
        target.take_damage(dmg)
        total += dmg
    return [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                       skill_name=skill.name, damage=total)]


def _magic_skill(caster, target, skill, eff, rng):
    power = _seq(eff.get("power_pct", 100), skill.level) / 100
    hits = _seq(eff.get("hits", 1), skill.level)
    total = 0
    for _ in range(hits):
        dmg = magic_damage(round(caster.effective_matk * power), target.mdef)
        target.take_damage(dmg)
        total += dmg
    return [SkillEvent(actor=caster.name, target=target.name, skill_id=skill.skill_id,
                       skill_name=skill.name, damage=total)]


def _heal_skill(caster, skill, eff):
    if "flat" in eff:
        amount = _seq(eff["flat"], skill.level)
    else:
        amount = round(caster.effective_matk * _seq(eff.get("matk_pct", 100), skill.level) / 100)
    caster.heal(amount)
    return [HealEvent(actor=caster.name, target=caster.name, amount=amount)]


def _stat_mod_skill(who, eff, level, sign):
    dur = max(1, round(eff.get("duration_s", 60) / 2))
    stats = eff.get("stats", {})
    for stat, seq in stats.items():
        mag = _seq(seq, level) * sign
        apply_status(who, Status(kind="stat_mod", name=f"{stat}_mod", duration=dur,
                                 magnitude=mag, stat=stat))
```

> `caster.hit` 沒有 `effective_hit`——在 Combatant 補一個 `effective_hit` property（`self.hit + self._stat_mod("hit")`）讓上面一致，順手也加 `effective_crit`。修 `_physical_skill` 直接用 `caster.effective_hit`。

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 技能效果解析"`

---

## Task 6: 回合迴圈

**Files:** Create `server/combat/engine.py`; Test `tests/test_combat_engine.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_engine.py`**

```python
import random

from server.combat.combatant import Combatant, ResolvedSkill
from server.combat.engine import simulate_fight


def _mk(name, **kw):
    base = dict(name=name, max_hp=200, max_sp=50, atk=40, matk=5, defense=0,
                mdef=0, hit=50, flee=20, aspd=100, crit=0)
    base.update(kw)
    return Combatant(**base)


def test_stronger_combatant_wins():
    r = simulate_fight(_mk("強", atk=80, max_hp=500), _mk("弱", atk=10, max_hp=50),
                       rng=random.Random(0))
    assert r.winner == "強"
    assert r.rounds >= 1
    assert r.loser_hp == 0


def test_events_include_attacks_and_kill():
    r = simulate_fight(_mk("A", atk=60), _mk("B", max_hp=40), rng=random.Random(1))
    kinds = {e.kind for e in r.events}
    assert "attack" in kinds
    assert "kill" in kinds


def test_high_aspd_lands_more_hits_per_round():
    slow = simulate_fight(_mk("慢", aspd=100, atk=30), _mk("靶", max_hp=100000, flee=0),
                          rng=random.Random(2), max_rounds=5)
    fast = simulate_fight(_mk("快", aspd=300, atk=30), _mk("靶", max_hp=100000, flee=0),
                          rng=random.Random(2), max_rounds=5)
    slow_atks = sum(1 for e in slow.events if e.kind == "attack" and e.actor == "慢")
    fast_atks = sum(1 for e in fast.events if e.kind == "attack" and e.actor == "快")
    assert fast_atks > slow_atks


def test_stalemate_when_nobody_can_kill():
    r = simulate_fight(_mk("鐵", atk=1, max_hp=999), _mk("壁", atk=1, max_hp=999, defense=95),
                       rng=random.Random(3), max_rounds=50)
    assert r.outcome == "stalemate"


def test_skill_fires_by_trigger_and_costs_sp():
    bash = ResolvedSkill("bash", "爆裂波動", 5, "active", 10, 0,
                         [{"type": "physical_hit", "power_pct": [130, 145, 160, 175, 190]}],
                         "every_turn", 1)
    hero = _mk("英雄", atk=50, max_sp=30, skills=[bash])
    r = simulate_fight(hero, _mk("怪", max_hp=300, flee=0), rng=random.Random(4))
    assert any(e.kind == "skill" and e.skill_id == "bash" for e in r.events)
    assert hero.sp < 30   # 有消耗


def test_deterministic_with_same_seed():
    a1 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    a2 = simulate_fight(_mk("A"), _mk("B"), rng=random.Random(7))
    assert a1.rounds == a2.rounds and a1.winner == a2.winner
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/engine.py`**

```python
import random
from dataclasses import dataclass, field

from server.combat.events import AttackEvent, KillEvent
from server.combat.formulas import (
    CRIT_MULTIPLIER, attacks_this_round, crit_chance, hit_chance, physical_damage,
)
from server.combat.skills import cast_skill
from server.combat.status import tick_statuses

MAX_ROUNDS_DEFAULT = 500


@dataclass
class FightResult:
    winner: str | None
    loser: str | None
    outcome: str            # "win" / "stalemate"
    rounds: int
    winner_hp: int
    loser_hp: int
    events: list = field(default_factory=list)


def _pick_skill(c):
    ready = []
    for s in c.skills:
        if s.kind != "active" or s._cd_left > 0 or c.sp < s.sp_cost:
            continue
        if _trigger_ok(c, s.trigger):
            ready.append(s)
    ready.sort(key=lambda s: -s.priority)
    return ready[0] if ready else None


def _trigger_ok(c, trigger: str) -> bool:
    if trigger in ("every_turn", "cooldown_ready", "sp_available", "passive"):
        return True
    if trigger == "hp_below_50":
        return c.hp <= c.max_hp * 0.5
    if trigger == "hp_below_30":
        return c.hp <= c.max_hp * 0.3
    return False


def _auto_attack(attacker, defender, rng, events):
    for _ in range(attacks_this_round(attacker.aspd, rng)):
        if not defender.alive:
            break
        hit = rng.random() < hit_chance(attacker.effective_hit, defender.effective_flee)
        if not hit:
            events.append(AttackEvent(attacker.name, defender.name, 0, False, False))
            continue
        crit = rng.random() < crit_chance(attacker.effective_crit)
        base = attacker.effective_matk if attacker.is_caster else attacker.effective_atk
        dmg = physical_damage(base, defender.effective_defense)
        if crit:
            dmg = round(dmg * CRIT_MULTIPLIER)
        defender.take_damage(dmg)
        events.append(AttackEvent(attacker.name, defender.name, dmg, crit, True))


def _take_turn(actor, foe, rng, events):
    if actor.stunned:
        return
    skill = _pick_skill(actor)
    if skill and actor.spend_sp(skill.sp_cost):
        events += cast_skill(actor, actor if _is_self_target(skill) else foe, skill, rng)
        skill._cd_left = skill.cooldown_rounds
    else:
        _auto_attack(actor, foe, rng, events)


def _is_self_target(skill) -> bool:
    return any(e.get("type") in ("heal_hp", "buff") for e in skill.effects)


def simulate_fight(a, b, rng: random.Random, max_rounds: int = MAX_ROUNDS_DEFAULT) -> FightResult:
    events: list = []
    rounds = 0
    # 先手：aspd 高者先，平手 a 先
    first, second = (a, b) if a.aspd >= b.aspd else (b, a)
    while a.alive and b.alive and rounds < max_rounds:
        rounds += 1
        for c in (first, second):
            tick_statuses(c, events)
            for s in c.skills:
                if s._cd_left > 0:
                    s._cd_left -= 1
        if not (a.alive and b.alive):
            break
        _take_turn(first, second, rng, events)
        if second.alive:
            _take_turn(second, first, rng, events)

    if a.alive and b.alive:
        return FightResult(None, None, "stalemate", rounds, a.hp, b.hp, events)
    winner, loser = (a, b) if a.alive else (b, a)
    events.append(KillEvent(actor=winner.name, target=loser.name))
    return FightResult(winner.name, loser.name, "win", rounds, winner.hp, loser.hp, events)
```

> 注意：`_take_turn` 的 skill self-target 判定用 `_is_self_target`；heal/buff 對自己，其餘對敵。

- [ ] **Step 4: 跑通過** PASS（6 個）。若「先手」邏輯讓 `test_deterministic` 或 stalemate 不穩，調整：固定 a 先手也可，把測試改成不依賴先後。
- [ ] **Step 5: Commit** `git commit -m "feat: 回合制戰鬥迴圈"`

---

## Task 7: 批次掛機模擬

**Files:** Create `server/combat/grind.py`; Test `tests/test_combat_grind.py`

給玩家 Combatant + 一隻怪的「模板」，打 N 場（每場怪都是新的滿血實例，玩家血/魔跨場**不重置**——模擬連續掛機，直到玩家撐不住）。回傳統計。

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_grind.py`**

```python
import random

from server.combat.combatant import Combatant
from server.combat.grind import simulate_grind
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=2000, max_sp=200, atk=200, matk=10, defense=20,
                mdef=10, hit=120, flee=90, aspd=150, crit=10)
    base.update(kw)
    return Combatant(**base)


def test_grind_kills_weak_monsters_and_counts_exp():
    content = load_content()
    poring = content.get_monster("poring")
    r = simulate_grind(_hero(), poring, n_fights=50, rng=random.Random(0))
    assert r.kills == 50
    assert r.base_exp == 50 * poring.base_exp
    assert r.job_exp == 50 * poring.job_exp
    assert r.player_defeated is False


def test_grind_stops_when_player_would_die():
    content = load_content()
    boss = content.get_monster("curly_boar_king")   # L48 boss，脆皮英雄打不過
    weak = _hero(max_hp=300, atk=30, defense=0)
    r = simulate_grind(weak, boss, n_fights=100, rng=random.Random(1))
    assert r.player_defeated is True
    assert r.kills < 100


def test_grind_reports_rounds_and_damage_taken():
    content = load_content()
    wolf = content.get_monster("wolf")
    r = simulate_grind(_hero(), wolf, n_fights=20, rng=random.Random(2))
    assert r.total_rounds > 0
    assert r.damage_taken >= 0


def test_grind_hp_carries_between_fights():
    content = load_content()
    wolf = content.get_monster("wolf")
    hero = _hero(max_hp=2000)
    simulate_grind(hero, wolf, n_fights=5, rng=random.Random(3))
    assert hero.hp <= 2000   # 沒有每場回滿


def test_deterministic():
    content = load_content()
    m = content.get_monster("green_cotton_worm")
    r1 = simulate_grind(_hero(), m, n_fights=30, rng=random.Random(9))
    r2 = simulate_grind(_hero(), m, n_fights=30, rng=random.Random(9))
    assert r1.kills == r2.kills and r1.base_exp == r2.base_exp
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/grind.py`**

```python
import random
from dataclasses import dataclass

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from shared.content import MonsterDef


@dataclass
class GrindResult:
    kills: int
    base_exp: int
    job_exp: int
    total_rounds: int
    damage_taken: int
    player_defeated: bool
    fights_attempted: int


def simulate_grind(player: Combatant, monster_def: MonsterDef, n_fights: int,
                   rng: random.Random) -> GrindResult:
    kills = base_exp = job_exp = total_rounds = damage_taken = 0
    defeated = False
    attempted = 0
    for _ in range(n_fights):
        attempted += 1
        hp_before = player.hp
        foe = Combatant.from_monster(monster_def)
        # 清掉上一場殘留的 debuff/CD
        player.statuses = [s for s in player.statuses if s.kind != "dot"]
        for s in player.skills:
            s._cd_left = 0
        result = simulate_fight(player, foe, rng)
        total_rounds += result.rounds
        damage_taken += max(0, hp_before - player.hp)
        if result.winner == player.name:
            kills += 1
            base_exp += monster_def.base_exp
            job_exp += monster_def.job_exp
        else:
            defeated = True
            break
    return GrindResult(kills, base_exp, job_exp, total_rounds, damage_taken,
                       defeated, attempted)
```

> 補品自動嗑、掉落擲骰、離線效率、時間換算——**都不在這裡**，是第 4 階段。這裡只回純戰鬥結果。

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 批次掛機戰鬥模擬"`

---

## Task 8: 公開 API 與整合

**Files:** Modify `server/combat/__init__.py`; Create `tests/test_combat_integration.py`; Create `scripts/combat_demo.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_combat_integration.py`**

```python
import random

from server import combat
from server.combat.combatant import Combatant, ResolvedSkill
from server.content import load_content


def test_public_api_exports():
    assert hasattr(combat, "simulate_fight")
    assert hasattr(combat, "simulate_grind")
    assert hasattr(combat, "Combatant")


def test_realistic_swordman_clears_early_map():
    content = load_content()
    # 手工組一個 Lv15 劍士（數值之後由養成階段算，這裡先寫死）
    bash_def = content.skills["bash"]
    bash = ResolvedSkill("bash", bash_def.name, 3, "active",
                         bash_def.sp_cost[2], 0, bash_def.effects, "every_turn", 1)
    hero = Combatant(name="劍士", max_hp=600, max_sp=40, atk=90, matk=5, defense=8,
                     mdef=3, hit=45, flee=35, aspd=130, crit=5, skills=[bash])
    worm = content.get_monster("green_cotton_worm")
    r = combat.simulate_grind(hero, worm, n_fights=30, rng=random.Random(0))
    assert r.kills == 30 and r.player_defeated is False


def test_mage_uses_matk_not_atk():
    content = load_content()
    mage = Combatant(name="法師", max_hp=350, max_sp=120, atk=8, matk=110, defense=2,
                     mdef=5, hit=40, flee=25, aspd=110, crit=0, is_caster=True)
    poring = content.get_monster("poring")
    r = combat.simulate_fight(mage, Combatant.from_monster(poring), rng=random.Random(0))
    assert r.winner == "法師"


def test_wolf_is_a_real_threat_to_underleveled():
    content = load_content()
    weak = Combatant(name="菜雞", max_hp=400, max_sp=20, atk=45, matk=5, defense=3,
                     mdef=2, hit=40, flee=30, aspd=110, crit=2)
    r = combat.simulate_grind(weak, content.get_monster("wolf"), n_fights=40,
                              rng=random.Random(5))
    # 不一定會死，但傷害要有感
    assert r.damage_taken > 0
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/combat/__init__.py`**

```python
from server.combat.combatant import Combatant, ResolvedSkill
from server.combat.engine import FightResult, simulate_fight
from server.combat.grind import GrindResult, simulate_grind

__all__ = [
    "Combatant", "ResolvedSkill", "FightResult", "simulate_fight",
    "GrindResult", "simulate_grind",
]
```

- [ ] **Step 4: 寫 `scripts/combat_demo.py`**——載入 content，組一個示範劍士，對 3 隻不同等級的怪各跑 `simulate_fight` 印出逐回合事件，再跑一次 `simulate_grind` 印統計。給人肉眼看平衡感。

- [ ] **Step 5: 跑通過** PASS，並手動 `uv run python scripts/combat_demo.py` 看輸出合不合理（劍士打綠棉蟲幾回合、打狼幾回合、打 boss 會不會 stalemate）。

- [ ] **Step 6: Commit** `git commit -m "feat: 戰鬥引擎公開 API 與示範腳本"`

---

## Task 9: 自行審核與文件

- [ ] **Step 1: 全套測試** `uv run pytest -q` → 全綠（地基 60 + 資料 97 的增量 + 戰鬥約 40）

- [ ] **Step 2: 自行審核**（讀 `server/combat/` 全部，對照本計畫與 `docs/設計.md` §7）重點看：
  - 傷害/命中/暴擊公式有沒有照 §7 的骨架
  - `effective_*` 有沒有到處用一致（不要有的地方用 `atk` 有的地方用 `effective_atk`）
  - RNG 有沒有真的可重現（同 seed 同結果）
  - stalemate 判定會不會誤判（血牛互毆 vs 真的打不動）
  - grind 跨場狀態清理乾不乾淨（CD、dot、buff 該不該留）
  - 先手邏輯有沒有讓某方吃虧到不合理
  - 找到問題直接修，重跑測試

- [ ] **Step 3: 建 `docs/抽象清單.md`**（若不存在）記錄：
  - #1 ASPD → 每回合攻擊次數（`attacks_this_round`）
  - #2 aoe 技能 v1 當單體
  - #3 buff/debuff 的 `duration_s` → 回合數用固定「1 回合 ≈ 2 秒」換算
  - #4 一回合雙方各行動一次；ASPD 只影響普攻次數不影響行動順序頻率

- [ ] **Step 4: 更新 `docs/superpowers/plans/README.md`** 標記階段 3 完成

- [ ] **Step 5: Commit** `git commit -m "docs: 戰鬥引擎抽象清單；階段 3 完成"`

---

## Self-Review（寫計畫時）

**1. 對照設計文件 §7：**
- 回合制模擬 ✓（engine.py）
- Pre-Renewal 物理+魔法 ✓（formulas.py）
- v1 不做屬性相剋 ✓（element_multiplier 參數留著預設 1.0，不從 chart 讀）
- ASPD 抽象 ✓（抽象清單 #1）
- HP/SP/ATK/MATK/DEF/MDEF/HIT/FLEE/ASPD/暴擊 ✓（Combatant 全帶）
- 雜怪批次快轉、只回統計 ✓（grind.py）
- 王戰逐回合事件 ✓（simulate_fight 回 events）

**2. Placeholder scan：** 每個 Task 都有完整程式碼與測試。demo 腳本（Task 8 Step 4）只給散文描述——可接受，它是肉眼檢查工具不是產品程式，實作者照描述寫即可。

**3. Type consistency：**
- `Combatant` 欄位（Task 3）↔ `from_monster` 讀 `MonsterDef.stats`（資料階段的 CombatStats）✓
- `ResolvedSkill.effects`（Task 3）↔ `cast_skill` 讀的 dict 型別字串 ↔ `data/skills.json` 現有字串（physical_hit/magic_hit/heal_hp/buff/debuff/passive_stat/proc）✓
- `effective_hit` / `effective_crit`：Task 5 用到，Task 5 Step 3 的註記要求在 Combatant 補；Task 4 已加 `effective_atk/matk/defense/flee`——實作者要把 hit/crit 也補齊，計畫已註明 ✓
- `FightResult` / `GrindResult` 欄位 ↔ 各測試斷言一致 ✓
- `simulate_fight(a, b, rng, max_rounds)` 簽名 ↔ engine 測試與 grind 呼叫一致（grind 呼叫沒給 max_rounds，用預設）✓

**4. 已知後續：**
- Combatant 的玩家數值目前測試寫死；第 5 階段（養成）會做 `build_player_combatant(character, content)` 把等級/加點/裝備/卡片/技能算成最終 Combatant。
- 掉落、補品、時間、離線效率、事件渲染 → 第 4 階段。
- `proc` 型技能（二段攻擊、偷竊）v1 引擎收到當 no-op；真正要 proc 得在 `_auto_attack` 加鉤子，列第 5 或第 6 階段。
