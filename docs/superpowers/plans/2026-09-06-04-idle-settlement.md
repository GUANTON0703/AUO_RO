# 掛機結算器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development。
>
> **審核政策**：不跑 codex。分批做完跑 `uv run pytest -q` + 掃 diff；階段收尾一次自行審核。

**Goal:** 把戰鬥引擎接上時間——給定玩家 Combatant + 目標怪 + 經過秒數 + 設定，算出這段時間打了幾隻、經驗/Zeny/掉落多少、嗑幾瓶補品、有沒有撐不住撤退，並產出結構化事件。

**Architecture:** 純函式庫（`server/settlement/`），不碰 DB、不建 Combatant、不發物品進背包——那些是第 5、6 階段。本階段輸入「已建好的 Combatant」，輸出「一份 SettlementResult」。在線／離線同一個入口，差在效率折扣、上限、以及走逐場模擬還是統計投影。

**Tech Stack:** 沿用。用到 `random.Random.binomialvariate`（Python 3.12+）做離線稀有掉落取樣。

---

## 設計決策

1. **在線 vs 離線**：`settle(..., offline: bool)`。
   - 離線：`effective_seconds = min(elapsed, offline_cap_hours*3600) * offline_efficiency`（預設 cap 8h、efficiency 0.6，都從設定檔）。
   - 在線：`effective_seconds = elapsed`，無折扣無上限。
2. **一場戰鬥花多久**：`time_per_kill = avg_rounds * round_seconds + rest_seconds`。`round_seconds` 預設 2（對齊抽象清單 #3）、`rest_seconds` 預設 3（跑去下一隻）。
3. **走逐場還是統計**：預估總擊殺數 `potential_kills`。`offline` 或 `potential_kills > 300` → 統計投影；否則逐場模擬（在線 poll 每 5 秒約 1~3 隻，逐場很便宜且能產每隻事件）。兩條路期望值要對齊。
4. **Zeny**：怪物 schema 沒有 Zeny 欄位。用公式 `zeny_per_kill = round(monster.level * 1.5 + monster.base_exp * 0.3)`，寫在 `settlement/economy.py`，之後要逐怪調再說。
5. **補品 / 安全網**（抽象：場間補血，不做場中）：
   - 每場開打前，若 `player.hp < max_hp * potion_hp_threshold` 且還有補品 → 嗑到門檻以上或用完。
   - 一場打完若 `player` 陣亡，或補品用完且血無法支撐下一場 → **撤退**：停止結算，記 `retreated=True`、`retreat_reason`、實際用掉的秒數。
6. **SP 場間回復**（抽象清單 #6 的補完）：每場之間 `player.sp = min(max_sp, sp + round(sp_regen_per_sec * time_per_kill))`。`sp_regen_per_sec` 預設 1.0。
7. **掉落擲骰**：
   - 常見掉落（`rate >= 0.02`）：統計 `round(kills * rate * avg_qty)`。
   - 稀有掉落（`rate < 0.02`，卡片這種）：離線用 `rng.binomialvariate(kills, rate)`；在線逐場 `rng.random() < rate`。
   - **保底計數器**：`pity_counters: dict[item_id, int]`（連續幾隻沒掉）。每 `pity_threshold`（預設卡片 800）隻沒掉必給一張。counter 進 result 傳回，持久化是第 6 階段的事。
8. **事件**：本階段只產結構化事件（KillBatchEvent / RareDropEvent / PotionUsedEvent / RetreatEvent，在線逐場再加戰鬥引擎的 events）。批次顯示/美化是第 10 階段。

---

## 檔案結構

```
server/settlement/
  __init__.py       # 公開 API：settle()
  config.py         # HuntConfig dataclass
  economy.py        # zeny_per_kill()
  profile.py        # FightProfile, estimate_fight_profile()
  drops.py          # roll_drops() 常見統計 + 稀有擲骰 + 保底
  events.py         # 結算事件型別
  engine.py         # settle()：統計路徑 + 逐場路徑
tests/
  test_settlement_config.py
  test_settlement_economy.py
  test_settlement_profile.py
  test_settlement_drops.py
  test_settlement_events.py
  test_settlement_engine.py
  test_settlement_integration.py
```

---

## Task 1: HuntConfig 與 Zeny 公式

**Files:** Create `server/settlement/__init__.py`(空), `server/settlement/config.py`, `server/settlement/economy.py`; Test `tests/test_settlement_config.py`, `tests/test_settlement_economy.py`

- [ ] **Step 1: 寫失敗測試**

`tests/test_settlement_config.py`:
```python
from server.settlement.config import HuntConfig


def test_defaults_match_design():
    c = HuntConfig()
    assert c.offline_efficiency == 0.6
    assert c.offline_cap_hours == 8
    assert c.round_seconds == 2.0
    assert c.rest_seconds == 3.0
    assert c.sp_regen_per_sec == 1.0
    assert 0.0 < c.potion_hp_threshold < 1.0
    assert c.card_pity_threshold >= 100


def test_from_settings_reads_env(monkeypatch):
    monkeypatch.setenv("ROTXT_OFFLINE_EFFICIENCY", "0.8")
    monkeypatch.setenv("ROTXT_OFFLINE_CAP_HOURS", "12")
    from server.config import Settings
    c = HuntConfig.from_settings(Settings())
    assert c.offline_efficiency == 0.8
    assert c.offline_cap_hours == 12
```

`tests/test_settlement_economy.py`:
```python
from server.settlement.economy import zeny_per_kill
from server.content import load_content


def test_zeny_scales_with_level():
    c = load_content()
    lo = zeny_per_kill(c.get_monster("green_cotton_worm"))
    hi = zeny_per_kill(c.get_monster("wolf"))
    assert 0 < lo < hi


def test_zeny_is_int():
    c = load_content()
    assert isinstance(zeny_per_kill(c.get_monster("poring")), int)
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫實作**

`server/settlement/config.py`:
```python
from dataclasses import dataclass


@dataclass
class HuntConfig:
    offline_efficiency: float = 0.6
    offline_cap_hours: int = 8
    round_seconds: float = 2.0
    rest_seconds: float = 3.0
    sp_regen_per_sec: float = 1.0
    potion_hp_threshold: float = 0.5
    card_pity_threshold: int = 800
    rare_drop_cutoff: float = 0.02
    literal_sim_kill_cap: int = 300

    @classmethod
    def from_settings(cls, settings) -> "HuntConfig":
        return cls(
            offline_efficiency=settings.offline_efficiency,
            offline_cap_hours=settings.offline_cap_hours,
        )
```

`server/settlement/economy.py`:
```python
from shared.content import MonsterDef


def zeny_per_kill(m: MonsterDef) -> int:
    return round(m.level * 1.5 + m.base_exp * 0.3)
```

- [ ] **Step 4: 跑通過** PASS
- [ ] **Step 5: Commit** `git commit -m "feat: 掛機設定與 Zeny 公式"`

---

## Task 2: 戰鬥側寫

**Files:** Create `server/settlement/profile.py`; Test `tests/test_settlement_profile.py`

跑 N 場樣本戰鬥，估出「平均幾回合、平均受傷、勝率」。用 `Combatant` 的深拷貝跑，不動到原本的。

- [ ] **Step 1: 寫失敗測試 `tests/test_settlement_profile.py`**

```python
import random

from server.combat.combatant import Combatant
from server.settlement.profile import estimate_fight_profile
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=2000, max_sp=200, atk=200, matk=10, defense=20,
                mdef=10, hit=120, flee=90, aspd=150, crit=10)
    base.update(kw)
    return Combatant(**base)


def test_profile_of_easy_monster():
    c = load_content()
    p = estimate_fight_profile(_hero(), c.get_monster("poring"), random.Random(0), samples=20)
    assert p.win_rate == 1.0
    assert p.avg_rounds >= 1
    assert p.avg_damage_taken >= 0


def test_profile_of_unwinnable_monster():
    c = load_content()
    weak = _hero(max_hp=200, atk=10, defense=0)
    p = estimate_fight_profile(weak, c.get_monster("curly_boar_king"), random.Random(1), samples=10)
    assert p.win_rate < 1.0


def test_profile_does_not_mutate_input():
    c = load_content()
    hero = _hero()
    estimate_fight_profile(hero, c.get_monster("wolf"), random.Random(2), samples=10)
    assert hero.hp == hero.max_hp   # 原本的 Combatant 沒被打
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/settlement/profile.py`**

```python
import copy
import random
from dataclasses import dataclass

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from shared.content import MonsterDef


@dataclass
class FightProfile:
    avg_rounds: float
    avg_damage_taken: float
    win_rate: float


def estimate_fight_profile(player: Combatant, monster: MonsterDef,
                           rng: random.Random, samples: int = 20) -> FightProfile:
    rounds = dmg = wins = 0
    for _ in range(samples):
        p = copy.deepcopy(player)
        p.hp, p.sp = p.max_hp, p.max_sp
        for s in p.skills:
            s._cd_left = 0
        foe = Combatant.from_monster(monster)
        r = simulate_fight(p, foe, rng)
        rounds += r.rounds
        dmg += max(0, p.max_hp - p.hp)
        if r.winner == p.name:
            wins += 1
    return FightProfile(rounds / samples, dmg / samples, wins / samples)
```

- [ ] **Step 4: 跑通過** PASS（3 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 戰鬥側寫估計"`

---

## Task 3: 掉落擲骰

**Files:** Create `server/settlement/drops.py`; Test `tests/test_settlement_drops.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_settlement_drops.py`**

```python
import random

from server.settlement.config import HuntConfig
from server.settlement.drops import roll_drops
from shared.content import DropEntry


def _drops():
    return [
        DropEntry(item_id="jellopy", rate=0.7, min_qty=1, max_qty=2),
        DropEntry(item_id="card_x", rate=0.001),
    ]


def test_common_drop_roughly_matches_expectation_statistical():
    cfg = HuntConfig()
    got, pity = roll_drops(_drops(), kills=1000, rng=random.Random(0),
                           offline=True, pity_in={}, cfg=cfg)
    # 0.7 機率 × 平均 1.5 個 × 1000 ≈ 1050，容差寬
    assert 800 <= got["jellopy"] <= 1300


def test_rare_drop_uses_binomial_offline():
    cfg = HuntConfig()
    totals = 0
    for seed in range(20):
        got, _ = roll_drops(_drops(), kills=2000, rng=random.Random(seed),
                            offline=True, pity_in={}, cfg=cfg)
        totals += got.get("card_x", 0)
    # 0.001 × 2000 × 20 ≈ 40
    assert 15 <= totals <= 80


def test_pity_forces_drop_after_threshold():
    cfg = HuntConfig(card_pity_threshold=500)
    got, pity = roll_drops([DropEntry(item_id="card_x", rate=0.0001)],
                           kills=500, rng=random.Random(999),
                           offline=True, pity_in={"card_x": 0}, cfg=cfg)
    assert got.get("card_x", 0) >= 1
    assert pity["card_x"] < 500  # 保底後計數器歸零再累積


def test_pity_counter_carries_when_no_drop():
    cfg = HuntConfig(card_pity_threshold=10000)
    got, pity = roll_drops([DropEntry(item_id="card_x", rate=0.0)],
                           kills=300, rng=random.Random(1),
                           offline=True, pity_in={"card_x": 50}, cfg=cfg)
    assert pity["card_x"] == 350


def test_online_mode_rolls_per_kill():
    cfg = HuntConfig()
    got, _ = roll_drops([DropEntry(item_id="jellopy", rate=1.0)], kills=5,
                        rng=random.Random(0), offline=False, pity_in={}, cfg=cfg)
    assert got["jellopy"] == 5
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/settlement/drops.py`**

```python
import random

from server.settlement.config import HuntConfig
from shared.content import DropEntry


def roll_drops(entries: list[DropEntry], kills: int, rng: random.Random,
               offline: bool, pity_in: dict, cfg: HuntConfig) -> tuple[dict, dict]:
    got: dict = {}
    pity = dict(pity_in)
    for e in entries:
        avg_qty = (e.min_qty + e.max_qty) / 2
        is_rare = e.rate < cfg.rare_drop_cutoff
        if not is_rare:
            if offline:
                qty = round(kills * e.rate * avg_qty)
            else:
                qty = sum(rng.randint(e.min_qty, e.max_qty)
                          for _ in range(kills) if rng.random() < e.rate)
            if qty:
                got[e.item_id] = got.get(e.item_id, 0) + qty
            continue

        # 稀有：擲骰 + 保底
        if offline:
            hits = rng.binomialvariate(kills, e.rate) if kills > 0 else 0
        else:
            hits = sum(1 for _ in range(kills) if rng.random() < e.rate)

        counter = pity.get(e.item_id, 0)
        if e.rate > 0:
            forced = (counter + kills) // cfg.card_pity_threshold
            forced -= counter // cfg.card_pity_threshold
        else:
            forced = (counter + kills) // cfg.card_pity_threshold - counter // cfg.card_pity_threshold
        total = hits + max(0, forced)
        if total:
            got[e.item_id] = got.get(e.item_id, 0) + total
        # 保底計數器：掉了就把「距離下次保底」重算
        pity[e.item_id] = (counter + kills) % cfg.card_pity_threshold if (total and forced) else counter + kills
        if total and not forced:
            pity[e.item_id] = 0  # 靠運氣掉的也重置
    return got, pity
```

> 保底邏輯以測試為準——`test_pity_forces_drop_after_threshold` / `test_pity_counter_carries_when_no_drop` 描述了預期行為，實作對齊這兩個。若上面的算式跟測試對不上，以測試的語意重寫：counter 累加 kills，每跨過一個 threshold 邊界就強制 +1 並把 counter 取模；完全沒掉就 counter += kills。

- [ ] **Step 4: 跑通過** PASS（5 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 掉落擲骰含保底"`

---

## Task 4: 結算事件型別

**Files:** Create `server/settlement/events.py`; Test `tests/test_settlement_events.py`

- [ ] **Step 1: 寫失敗測試 `tests/test_settlement_events.py`**

```python
from server.settlement import events as ev


def test_kill_batch_event():
    e = ev.KillBatchEvent(monster_name="波利", count=42, base_exp=84, job_exp=42, zeny=210)
    assert e.count == 42 and e.kind == "kill_batch"


def test_rare_drop_event():
    e = ev.RareDropEvent(item_id="poring_card", item_name="波利卡片", qty=1)
    assert e.kind == "rare_drop"


def test_potion_used_event():
    e = ev.PotionUsedEvent(item_id="red_potion", item_name="紅色藥水", count=23, remaining=12)
    assert e.kind == "potion_used"


def test_retreat_event():
    e = ev.RetreatEvent(reason="補品用盡", seconds_survived=7200)
    assert e.kind == "retreat"
```

- [ ] **Step 2: 跑失敗** → FAIL
- [ ] **Step 3: 寫 `server/settlement/events.py`**（dataclass，同戰鬥事件的 `kind` 用 `__post_init__` 或 `field(init=False)` 手法）

```python
from dataclasses import dataclass


@dataclass
class SettlementEvent:
    def __post_init__(self):
        pass


@dataclass
class KillBatchEvent:
    monster_name: str
    count: int
    base_exp: int
    job_exp: int
    zeny: int
    kind: str = "kill_batch"


@dataclass
class RareDropEvent:
    item_id: str
    item_name: str
    qty: int
    kind: str = "rare_drop"


@dataclass
class PotionUsedEvent:
    item_id: str
    item_name: str
    count: int
    remaining: int
    kind: str = "potion_used"


@dataclass
class RetreatEvent:
    reason: str
    seconds_survived: float
    kind: str = "retreat"
```

> 這裡改用 `kind: str = "..."` 當有預設值的欄位（放最後），比 `__post_init__` 乾淨。戰鬥事件那邊已定型不動，這邊新的用這風格。

- [ ] **Step 4: 跑通過** PASS（4 個）
- [ ] **Step 5: Commit** `git commit -m "feat: 結算事件型別"`

---

## Task 5: 結算引擎（統計路徑）

**Files:** Create `server/settlement/engine.py`; Test `tests/test_settlement_engine.py`（統計部分）

- [ ] **Step 1: 寫失敗測試 `tests/test_settlement_engine.py`**

```python
import random

from server.combat.combatant import Combatant
from server.settlement.config import HuntConfig
from server.settlement.engine import settle
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=3000, max_sp=300, atk=250, matk=10, defense=30,
                mdef=15, hit=140, flee=110, aspd=160, crit=12)
    base.update(kw)
    return Combatant(**base)


def test_offline_applies_efficiency_and_cap():
    c = load_content()
    poring = c.get_monster("poring")
    cfg = HuntConfig()
    # 掛 100 小時，cap 8h、效率 0.6 → 有效 4.8h
    r = settle(_hero(), poring, elapsed_seconds=100 * 3600, cfg=cfg,
               rng=random.Random(0), offline=True, pity_in={})
    assert r.real_elapsed_seconds == 100 * 3600
    assert abs(r.effective_seconds - 8 * 3600 * 0.6) < 1
    assert r.kills > 0
    assert r.base_exp == r.kills * poring.base_exp


def test_online_no_penalty():
    c = load_content()
    poring = c.get_monster("poring")
    r = settle(_hero(), poring, elapsed_seconds=30, cfg=HuntConfig(),
               rng=random.Random(0), offline=False, pity_in={})
    assert abs(r.effective_seconds - 30) < 0.01


def test_retreat_when_player_cannot_win():
    c = load_content()
    boss = c.get_monster("curly_boar_king")
    weak = _hero(max_hp=500, atk=40, defense=5)
    r = settle(weak, boss, elapsed_seconds=8 * 3600, cfg=HuntConfig(),
               rng=random.Random(1), offline=True, pity_in={},
               potion_item_id=None, potion_count=0)
    assert r.retreated is True
    assert r.effective_seconds < 8 * 3600 * 0.6


def test_potions_consumed_and_can_run_out():
    c = load_content()
    wolf = c.get_monster("wolf")
    squishy = _hero(max_hp=800, defense=5)
    r = settle(squishy, wolf, elapsed_seconds=4 * 3600, cfg=HuntConfig(),
               rng=random.Random(2), offline=True, pity_in={},
               potion_item_id="red_potion", potion_heal=350, potion_count=50)
    assert r.potions_used > 0
    # 補品用完會撤退
    if r.potions_used >= 50:
        assert r.retreated is True


def test_zeny_and_drops_accumulate():
    c = load_content()
    m = c.get_monster("green_cotton_worm")
    r = settle(_hero(), m, elapsed_seconds=3600, cfg=HuntConfig(),
               rng=random.Random(3), offline=True, pity_in={})
    assert r.zeny > 0
    assert sum(r.drops.values()) > 0


def test_deterministic():
    c = load_content()
    m = c.get_monster("poring")
    a = settle(_hero(), m, 3600, HuntConfig(), random.Random(7), offline=True, pity_in={})
    b = settle(_hero(), m, 3600, HuntConfig(), random.Random(7), offline=True, pity_in={})
    assert a.kills == b.kills and a.base_exp == b.base_exp and a.drops == b.drops


def test_events_include_kill_batch():
    c = load_content()
    m = c.get_monster("poring")
    r = settle(_hero(), m, 3600, HuntConfig(), random.Random(4), offline=True, pity_in={})
    assert any(e.kind == "kill_batch" for e in r.events)
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/settlement/engine.py`**

```python
import copy
import random
from dataclasses import dataclass, field

from server.combat.combatant import Combatant
from server.combat.engine import simulate_fight
from server.settlement.config import HuntConfig
from server.settlement.drops import roll_drops
from server.settlement.economy import zeny_per_kill
from server.settlement.events import (
    KillBatchEvent, PotionUsedEvent, RareDropEvent, RetreatEvent,
)
from server.settlement.profile import estimate_fight_profile
from shared.content import MonsterDef


@dataclass
class SettlementResult:
    kills: int
    base_exp: int
    job_exp: int
    zeny: int
    drops: dict = field(default_factory=dict)
    potions_used: int = 0
    retreated: bool = False
    retreat_reason: str = ""
    real_elapsed_seconds: float = 0.0
    effective_seconds: float = 0.0
    pity_out: dict = field(default_factory=dict)
    events: list = field(default_factory=list)


def settle(player: Combatant, monster: MonsterDef, elapsed_seconds: float,
           cfg: HuntConfig, rng: random.Random, *, offline: bool, pity_in: dict,
           potion_item_id: str | None = None, potion_heal: int = 0,
           potion_count: int = 0) -> SettlementResult:

    if offline:
        capped = min(elapsed_seconds, cfg.offline_cap_hours * 3600)
        effective = capped * cfg.offline_efficiency
    else:
        effective = elapsed_seconds

    prof = estimate_fight_profile(player, monster, rng, samples=20)
    time_per_kill = prof.avg_rounds * cfg.round_seconds + cfg.rest_seconds
    potential = int(effective / time_per_kill) if time_per_kill > 0 else 0

    retreated = False
    reason = ""
    # 打不贏 → 立刻撤退
    if prof.win_rate <= 0.0:
        retreated, reason = True, "打不過這裡的怪"
        kills = 0
        used_seconds = 0.0
    else:
        # 每場平均要幾瓶補品（場間補血模型）
        need_potion_per_fight = 0
        if prof.avg_damage_taken > 0 and potion_heal > 0:
            need_potion_per_fight = prof.avg_damage_taken / potion_heal

        max_kills_by_potion = potential
        potions_used = 0
        if need_potion_per_fight > 0:
            # 沒補品但每場會掉血 → 撐不了幾場（用血量粗估）
            if potion_count <= 0:
                sustainable = int(player.max_hp / max(1, prof.avg_damage_taken))
                if sustainable < potential:
                    max_kills_by_potion = sustainable
                    retreated, reason = True, "沒有補品，血量見底"
            else:
                affordable = int(potion_count / need_potion_per_fight)
                if affordable < potential:
                    max_kills_by_potion = affordable
                    retreated, reason = True, "補品用盡"

        kills = round(prof.win_rate * max_kills_by_potion)
        if need_potion_per_fight > 0:
            potions_used = min(potion_count, round(kills * need_potion_per_fight))
        used_seconds = kills * time_per_kill

    base_exp = kills * monster.base_exp
    job_exp = kills * monster.job_exp
    zeny = kills * zeny_per_kill(monster)
    drops, pity_out = roll_drops(monster.drops, kills, rng, offline=offline,
                                 pity_in=pity_in, cfg=cfg)

    events: list = []
    if kills > 0:
        events.append(KillBatchEvent(monster.name, kills, base_exp, job_exp, zeny))
    for item_id, qty in drops.items():
        entry = next((d for d in monster.drops if d.item_id == item_id), None)
        if entry and entry.rate < cfg.rare_drop_cutoff:
            events.append(RareDropEvent(item_id, item_id, qty))
    if 'potions_used' in dir() and locals().get('potions_used'):
        events.append(PotionUsedEvent(potion_item_id or "", potion_item_id or "",
                                      potions_used, max(0, potion_count - potions_used)))
    if retreated:
        events.append(RetreatEvent(reason, used_seconds))

    return SettlementResult(
        kills=kills, base_exp=base_exp, job_exp=job_exp, zeny=zeny, drops=drops,
        potions_used=locals().get('potions_used', 0),
        retreated=retreated, retreat_reason=reason,
        real_elapsed_seconds=elapsed_seconds,
        effective_seconds=used_seconds if retreated else effective,
        pity_out=pity_out, events=events,
    )
```

> 上面的 `locals()` 用法很醜——實作時把 `potions_used` 在函式開頭初始化為 0，別靠 `locals()`。這段是給實作者看邏輯用的骨架，清理成正常變數。

- [ ] **Step 4: 跑通過** PASS（7 個）。retreat 的 `effective_seconds` 語意：撤退時 = 實際撐住的秒數；沒撤退 = 全部有效秒數。
- [ ] **Step 5: Commit** `git commit -m "feat: 結算引擎統計路徑"`

---

## Task 6: 逐場路徑（在線）

**Files:** Modify `server/settlement/engine.py`; Test `tests/test_settlement_engine.py`（新增在線逐場）

在線且 `potential <= cfg.literal_sim_kill_cap` 時，實際跑 `simulate_fight` 迴圈，逐場：場間 SP 回、場間補血、產每隻的擊殺（可合併成 KillBatch 但保留稀有掉落單獨事件）。

- [ ] **Step 1: 追加測試**

```python
def test_online_literal_path_matches_kills_roughly():
    c = load_content()
    poring = c.get_monster("poring")
    r = settle(_hero(), poring, elapsed_seconds=60, cfg=HuntConfig(),
               rng=random.Random(0), offline=False, pity_in={})
    # 60 秒，每隻約 (avg_rounds*2 + 3) 秒 → 個位數擊殺
    assert 1 <= r.kills <= 30
    assert r.base_exp == r.kills * poring.base_exp


def test_online_sp_regen_between_fights():
    c = load_content()
    # 一個會耗 SP 的英雄，長時間在線應該不會因 SP 歸零就一直平砍
    ...  # 視實作補；重點是場間有回 SP


def test_online_and_offline_expected_values_align():
    c = load_content()
    m = c.get_monster("green_cotton_worm")
    hero = _hero()
    on = settle(hero, m, 3600, HuntConfig(), random.Random(1), offline=False, pity_in={})
    off = settle(hero, m, 3600, HuntConfig(), random.Random(1), offline=True, pity_in={})
    # 在線無折扣、離線 0.6 折扣 → 離線擊殺約為在線的 60%（容差 ±25%）
    ratio = off.kills / max(1, on.kills)
    assert 0.4 < ratio < 0.85
```

- [ ] **Step 2: 跑失敗（新測試）** → FAIL

- [ ] **Step 3: 在 `settle()` 加逐場分支**——`offline=False and potential <= cap` 時走 `_settle_literal()`：deepcopy player，迴圈 `simulate_fight`，場間 `player.hp` heal（若有補品）、`player.sp` regen，累計 kills/exp/dmg，撐不住 break 設 retreat。掉落用 `roll_drops(..., offline=False)`（逐場擲）。統計路徑保持不變。

- [ ] **Step 4: 跑通過**
- [ ] **Step 5: Commit** `git commit -m "feat: 結算引擎在線逐場路徑"`

---

## Task 7: 公開 API 與整合

**Files:** Modify `server/settlement/__init__.py`; Create `tests/test_settlement_integration.py`; Modify `scripts/combat_demo.py` 或新增 `scripts/settlement_demo.py`

- [ ] **Step 1: 寫 `tests/test_settlement_integration.py`**

```python
import random

from server import settlement
from server.combat.combatant import Combatant
from server.content import load_content


def _hero(**kw):
    base = dict(name="英雄", max_hp=3000, max_sp=300, atk=250, matk=10, defense=30,
                mdef=15, hit=140, flee=110, aspd=160, crit=12)
    base.update(kw); return Combatant(**base)


def test_public_api():
    assert hasattr(settlement, "settle")
    assert hasattr(settlement, "HuntConfig")
    assert hasattr(settlement, "SettlementResult")


def test_full_offline_session_on_real_map_monster():
    c = load_content()
    # 在南門原野掛狸貓 6 小時
    r = settlement.settle(_hero(), c.get_monster("raccoon"),
                          elapsed_seconds=6 * 3600, cfg=settlement.HuntConfig(),
                          rng=random.Random(0), offline=True, pity_in={},
                          potion_item_id="red_potion", potion_heal=45, potion_count=500)
    assert r.kills > 100
    assert r.base_exp > 0 and r.zeny > 0
    assert not r.retreated   # 英雄輾壓狸貓

def test_card_can_drop_over_long_session():
    c = load_content()
    # 波利卡 drop_rate 很低，掛超久 + 保底應該至少一張
    total_cards = 0
    for seed in range(5):
        r = settlement.settle(_hero(), c.get_monster("poring"),
                              elapsed_seconds=8 * 3600, cfg=settlement.HuntConfig(),
                              rng=random.Random(seed), offline=True, pity_in={})
        total_cards += r.drops.get("poring_card", 0)
    assert total_cards >= 1
```

- [ ] **Step 2: 跑失敗** → FAIL

- [ ] **Step 3: 寫 `server/settlement/__init__.py`**（export `settle`, `HuntConfig`, `SettlementResult`）

- [ ] **Step 4: 寫 `scripts/settlement_demo.py`**——載入 content，示範英雄在 3 個不同地圖各掛 8 小時（離線）+ 一次 5 分鐘在線，印出 SettlementResult 摘要（擊殺/經驗/Zeny/掉落清單/有無撤退/事件），給人看數值合不合理。

- [ ] **Step 5: 跑通過 + 手動跑 demo** 看 8 小時掛機的收成合不合理（波利場 vs 狼場）。

- [ ] **Step 6: Commit** `git commit -m "feat: 結算器公開 API 與示範"`

---

## Task 8: 自行審核與文件

- [ ] **Step 1: 全套測試** `uv run pytest -q` 全綠
- [ ] **Step 2: 自行審核** 讀 `server/settlement/` 全部，重點：
  - 在線／離線期望值有沒有對齊（`test_online_and_offline_expected_values_align`）
  - 撤退時 `effective_seconds` / `used_seconds` 語意一致、事件有 RetreatEvent
  - 補品模型（場間補血）會不會低估或高估用量
  - 保底計數器 in/out 有沒有正確累加與重置
  - `estimate_fight_profile` 的 deepcopy 有沒有真的隔離
  - `settle()` 裡沒有 `locals()` 這種醜東西
  - RNG 同 seed 同結果
- [ ] **Step 3: 更新 `docs/抽象清單.md`**（結算階段的抽象）：
  - #7 補品只場間不場中
  - #8 離線走統計投影不逐場模擬
  - #9 一場戰鬥固定 `round_seconds` + `rest_seconds` 秒
  - #10 沒補品時「撐得住幾場」用 `max_hp / avg_damage_taken` 粗估
- [ ] **Step 4: 更新 `docs/superpowers/plans/README.md`** 標記階段 4 完成
- [ ] **Step 5: Commit** `git commit -m "docs: 結算器抽象清單；階段 4 完成"`

---

## Self-Review（寫計畫時）

**1. 對照設計文件 §8：**
- 在線 + 離線都做 ✓
- 離線效率 60%、上限 8h ✓（HuntConfig，從設定檔）
- 掛機安全網（打不過自動撤退不死）✓（retreat 邏輯）
- 補品自動嗑、用完撤退 ✓
- 離線混合結算（經驗金錢統計、稀有掉落擲骰+保底）✓（drops.py）
- 在線逐次擲骰逐行 ✓（Task 6 逐場路徑）
- 在線／離線期望值校準 ✓（明確有測試把關）

**2. Placeholder scan：** Task 5 Step 3 的 `locals()` 骨架已明確標註「實作時清理成正常變數」。Task 6 Step 3 用散文描述逐場分支——可接受，邏輯跟 Task 5 對稱（deepcopy player、迴圈 simulate_fight），實作者照 grind.py 的模式寫。`test_online_sp_regen_between_fights` 留了 `...` 待補——實作者補一個能驗證「長在線戰鬥不會因 SP 歸零而全程平砍」的斷言。

**3. Type consistency：**
- `HuntConfig` 欄位（Task 1）↔ `settle()` 讀取（Task 5）一致
- `FightProfile`（Task 2）↔ `settle()` 用 `prof.avg_rounds/avg_damage_taken/win_rate` 一致
- `roll_drops(entries, kills, rng, offline, pity_in, cfg) -> (dict, dict)`（Task 3）↔ `settle()` 呼叫一致
- `SettlementResult` 欄位 ↔ 各測試斷言一致
- `settle()` 簽名（含 keyword-only `offline` / `pity_in` / 補品三參數）↔ 所有測試呼叫一致
- `Combatant` / `simulate_fight` / `MonsterDef.drops(list[DropEntry])` ↔ 沿用前階段，一致

**4. 已知後續：**
- 玩家 Combatant 怎麼從 character 建 → 第 5 階段
- SettlementResult 的 exp 怎麼灌進 character 升級、drops 怎麼進背包、pity_out 怎麼存 → 第 5、6 階段
- Hunt API（`/api/hunt/start|stop|status`）+ 持久化掛機狀態 → 第 5 或 6 階段的整合步驟
- 多怪加權（一張圖多種怪）→ v1 先單怪，之後擴充 `settle` 收 `list[(MonsterDef, weight)]`
