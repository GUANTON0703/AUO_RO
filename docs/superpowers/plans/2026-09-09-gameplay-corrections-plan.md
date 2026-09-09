# Gameplay Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix inherited skill relearning, make random refining use the normal failure gate at ten times the Zeny cost, filter socket choices by equipment slot, and make every MVP reliably threaten high-FLEE players with visible skills.

**Architecture:** Keep the existing FastAPI, content, combat-event, and vanilla-JS boundaries. Each correction is isolated behind a small pure function or existing domain boundary so it can be proven with focused regression tests before integration. MVP abilities are generated centrally for all `is_mvp` combatants instead of duplicating identical skills in every JSON record.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, vanilla JavaScript, Node.js built-in test runner, SQLite.

---

## File map

- `server/progression/skills.py`: authoritative job-ancestry eligibility for learning skills.
- `server/api/progression.py`: uses the progression eligibility rule without changing the endpoint contract.
- `web/js/screen-build.js`: enables add buttons for novice and first-job skills inherited by a second job.
- `server/loot/refine.py`: pure two-stage random-refine roll and mode-aware Zeny pricing.
- `server/api/inventory.py`: charges the selected mode and returns the two-stage outcome.
- `web/js/screen-bag.js`: displays random-refine cost semantics and filters socket candidates.
- `server/combat/boss_skills.py`: new centralized MVP skill factory.
- `server/combat/combatant.py`: marks MVP combatants with skills, SP, and a hit floor.
- `server/combat/formulas.py`, `server/combat/engine.py`, `server/combat/skills.py`: apply an attacker-specific minimum hit chance to normal and physical-skill attacks.
- `tests/web/screen-bag.test.js`: new pure front-end tests for socket compatibility.

### Task 1: Relearn the complete job-chain skill tree

**Files:**
- Modify: `server/progression/skills.py`
- Modify: `web/js/screen-build.js`
- Test: `tests/test_progression_skills.py`
- Test: `tests/test_api_progression.py`
- Test: `tests/web/screen-build.test.js`

- [ ] **Step 1: Add failing domain and API tests for ancestor skills**

Append this test to `tests/test_progression_skills.py`:

```python
def test_second_job_can_learn_ancestor_skills_but_not_sibling_skills():
    from server.content import load_content

    content = load_content()
    for skill_id in ("basic_attack_boost", "bash", "bowling_bash"):
        ok, reason = can_learn(
            content,
            character_job="knight",
            skill_id=skill_id,
            target_level=1,
            current_learned={},
            points_available=99,
        )
        assert ok is True, (skill_id, reason)

    ok, reason = can_learn(
        content,
        character_job="knight",
        skill_id="fire_bolt",
        target_level=1,
        current_learned={},
        points_available=99,
    )
    assert ok is False
    assert reason == "非本職或前職技能"
```

Append this API regression to `tests/test_api_progression.py`:

```python
def test_second_job_reset_can_relearn_novice_and_first_job_skills(
    client, auth, db_helpers
):
    _, headers, _ = auth
    ch = _make_char(client, headers, "重修騎士")
    db_helpers.set_job(ch["id"], "knight", 20, 80)

    reset = client.post(
        f"/api/characters/{ch['id']}/resetskills", headers=headers
    )
    assert reset.status_code == 200

    for skill_id in ("basic_attack_boost", "bash", "bowling_bash"):
        learned = client.post(
            f"/api/characters/{ch['id']}/skills",
            headers=headers,
            json={"skill_id": skill_id, "level": 1},
        )
        assert learned.status_code == 200, (skill_id, learned.json())

    sibling = client.post(
        f"/api/characters/{ch['id']}/skills",
        headers=headers,
        json={"skill_id": "fire_bolt", "level": 1},
    )
    assert sibling.status_code == 400
```

- [ ] **Step 2: Run the tests and verify the current exact-job check fails**

Run:

```powershell
uv run pytest tests/test_progression_skills.py::test_second_job_can_learn_ancestor_skills_but_not_sibling_skills tests/test_api_progression.py::test_second_job_reset_can_relearn_novice_and_first_job_skills -q
```

Expected: both tests fail because `can_learn()` currently requires `skill.job_id == character_job`.

- [ ] **Step 3: Change the backend eligibility check to job ancestry**

Replace the exact-job block in `server/progression/skills.py` with:

```python
    if skill.job_id not in content.job_ancestry(character_job):
        return False, "非本職或前職技能"
```

No API signature changes are required because `server/api/progression.py` already passes the loaded content and current job to `can_learn()`.

- [ ] **Step 4: Add and verify a failing front-end ancestry test**

Add this assertion to `tests/web/screen-build.test.js` before changing production JS:

```javascript
test("allows training skills from the current job ancestry only", () => {
  const jobs = {
    novice: { parent_id: null },
    swordman: { parent_id: "novice" },
    knight: { parent_id: "swordman" },
    mage: { parent_id: "novice" },
  };

  assert.equal(skillView.canTrainSkill({ job_id: "novice" }, jobs, "knight"), true);
  assert.equal(skillView.canTrainSkill({ job_id: "swordman" }, jobs, "knight"), true);
  assert.equal(skillView.canTrainSkill({ job_id: "knight" }, jobs, "knight"), true);
  assert.equal(skillView.canTrainSkill({ job_id: "mage" }, jobs, "knight"), false);
});
```

Run:

```powershell
node --test tests/web/screen-build.test.js
```

Expected: FAIL because `canTrainSkill` is not exported yet.

- [ ] **Step 5: Implement the ancestry helper and render valid inherited buttons**

Add this helper after `getSkillPrerequisiteState()` in `web/js/screen-build.js`:

```javascript
  function canTrainSkill(skill, jobs, currentJobId) {
    const seen = new Set();
    for (let jobId = currentJobId; jobId && !seen.has(jobId); jobId = jobs[jobId]?.parent_id) {
      if (skill.job_id === jobId) return true;
      seen.add(jobId);
    }
    return false;
  }

  window.ROSkillView = {
    groupSkillsByTier,
    getSkillPrerequisiteState,
    canTrainSkill,
  };
```

Inside the skill-row loop, calculate eligibility and replace the inherited-only button condition:

```javascript
        const trainableJob = canTrainSkill(sk, jobs, c.job_id);
        const noPoints = Number(c.skill_points || 0) <= 0;
        const btn = trainableJob
          ? `<button class="btn small" data-skill="${sk.id}" data-next="${lv + 1}"
              ${maxed || locked || noPoints ? "disabled" : ""}>學 +1</button>`
          : "";
```

Keep the existing `inherited` value for the `前職` badge; it must no longer control whether the button exists.

- [ ] **Step 6: Verify focused skill tests and commit**

Run:

```powershell
uv run pytest tests/test_progression_skills.py tests/test_api_progression.py -q
node --test tests/web/screen-build.test.js
```

Expected: all selected Python and Node tests pass.

Commit only the task files:

```powershell
git add -- server/progression/skills.py web/js/screen-build.js tests/test_progression_skills.py tests/test_api_progression.py tests/web/screen-build.test.js
git commit -m "fix: allow relearning inherited skills" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

### Task 2: Gate random refining through normal failure odds

**Files:**
- Modify: `server/loot/refine.py`
- Modify: `server/api/inventory.py`
- Modify: `web/js/screen-bag.js`
- Test: `tests/test_loot_refine.py`
- Test: `tests/test_api_inventory.py`

- [ ] **Step 1: Replace the old random-refine tests with two-stage failing tests**

Use this deterministic helper and tests in `tests/test_loot_refine.py`:

```python
class SequenceRng:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def random(self):
        value = self.values[self.calls]
        self.calls += 1
        return value


def test_random_refine_failure_uses_only_normal_success_roll_and_downgrades():
    rng = SequenceRng(0.99)
    assert attempt_random_refine(4, rng) == (3, False, -1)
    assert rng.calls == 1


def test_random_refine_success_then_draws_weighted_increment():
    rng = SequenceRng(0.00, 0.95)
    assert attempt_random_refine(4, rng) == (7, True, 3)
    assert rng.calls == 2


def test_random_refine_success_can_draw_zero_increment():
    assert attempt_random_refine(4, SequenceRng(0.00, 0.00)) == (4, True, 0)


def test_random_refine_caps_reported_increment_at_maximum():
    assert attempt_random_refine(9, SequenceRng(0.00, 0.99)) == (
        REFINE_CAP,
        True,
        1,
    )


def test_random_refine_zeny_cost_is_ten_times_normal():
    assert refine_zeny_cost(4, mode="random") == 10 * refine_zeny_cost(4)
```

- [ ] **Step 2: Run the pure tests and verify tuple/pricing failures**

Run:

```powershell
uv run pytest tests/test_loot_refine.py -q
```

Expected: the new tests fail because the current random function skips the success gate, returns a two-item tuple, and pricing has no mode.

- [ ] **Step 3: Implement mode-aware cost and the two-stage roll**

Replace the pricing and random attempt functions in `server/loot/refine.py` with:

```python
def refine_zeny_cost(current_refine: int, mode: str = "normal") -> int:
    base = (current_refine + 1) * 200
    return base * 10 if mode == "random" else base


def attempt_random_refine(
    current_refine: int, rng: random.Random
) -> tuple[int, bool, int]:
    gated_refine, ok = attempt_refine(current_refine, rng)
    if not ok:
        return gated_refine, False, gated_refine - current_refine

    roll = rng.random()
    if roll < 0.10:
        drawn = 0
    elif roll < 0.60:
        drawn = 1
    elif roll < 0.95:
        drawn = 2
    else:
        drawn = 3
    new_refine = min(REFINE_CAP, current_refine + drawn)
    return new_refine, True, new_refine - current_refine
```

The successful branch deliberately uses `current_refine`, not the `+1` returned by the gate; the gate authorizes the random draw and does not add a separate level.

- [ ] **Step 4: Add failing API tests for 10x charge and failure downgrade**

Replace the current random-mode API test in `tests/test_api_inventory.py` with two tests using a sequence RNG:

```python
def test_refine_random_mode_charges_ten_times_and_draws_after_success(
    client, auth, db_helpers, monkeypatch
):
    _, headers, _ = auth
    ch = _char(client, headers, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_item(ch["id"], "oridecon", 2)
    db_helpers.set_zeny(ch["id"], 99999)
    inst = _equip_list(client, ch, headers)[0]

    rng = SequenceRng(0.00, 0.95)
    monkeypatch.setattr("server.api.inventory.random.Random", lambda: rng)
    response = client.post(
        f"/api/characters/{ch['id']}/inventory/refine",
        headers=headers,
        json={"equipment_instance_id": inst["id"], "mode": "random"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["increment"] == 3
    with connection.get_connection() as conn:
        zeny = conn.execute(
            "SELECT zeny FROM characters WHERE id = ?", (ch["id"],)
        ).fetchone()["zeny"]
    assert zeny == 99999 - refine_zeny_cost(0, mode="random")


def test_refine_random_mode_can_fail_before_increment_draw(
    client, auth, db_helpers, monkeypatch
):
    _, headers, _ = auth
    ch = _char(client, headers, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_item(ch["id"], "oridecon", 1)
    db_helpers.set_zeny(ch["id"], 99999)
    inst = _equip_list(client, ch, headers)[0]
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE character_equipment SET refine = 4 WHERE id = ?",
            (inst["id"],),
        )

    rng = SequenceRng(0.99)
    monkeypatch.setattr("server.api.inventory.random.Random", lambda: rng)
    response = client.post(
        f"/api/characters/{ch['id']}/inventory/refine",
        headers=headers,
        json={"equipment_instance_id": inst["id"], "mode": "random"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["increment"] == -1
    assert response.json()["refine"] == 3
    assert rng.calls == 1
```

Add these imports and the deterministic helper at the top of `tests/test_api_inventory.py`:

```python
from server.db import connection
from server.loot.refine import refine_zeny_cost


class SequenceRng:
    def __init__(self, *values):
        self.values = list(values)
        self.calls = 0

    def random(self):
        value = self.values[self.calls]
        self.calls += 1
        return value
```

- [ ] **Step 5: Update the API and player-facing messages**

In `server/api/inventory.py`, calculate mode-aware cost and unpack the three-item result:

```python
        zeny_cost = refine_mod.refine_zeny_cost(current, body.mode)
```

```python
        if body.mode == "random":
            new_refine, ok, increment = refine_mod.attempt_random_refine(
                current, random.Random()
            )
        else:
            new_refine, ok = refine_mod.attempt_refine(current, random.Random())
            increment = new_refine - current
```

Use explicit random-mode messages after the transaction:

```python
    if body.mode == "random" and not ok:
        message = f"隨機精煉失敗，{eq.name} 降至 +{new_refine}"
    elif body.mode == "random" and increment == 0:
        message = f"隨機精煉判定成功，但抽中 +0，{eq.name} 維持 +{new_refine}"
    elif body.mode == "random":
        message = f"隨機精煉成功 +{increment}，{eq.name} +{new_refine}"
```

Change the prompt text in `web/js/screen-bag.js` to:

```javascript
            "選擇精煉模式：\n1. 普通（成功率／失敗降級）\n2. 隨機（普通成功率後抽 +0～+3，Zeny ×10）",
```

- [ ] **Step 6: Verify focused refining tests and commit**

Run:

```powershell
uv run pytest tests/test_loot_refine.py tests/test_api_inventory.py -q
```

Expected: all selected tests pass, including unchanged normal refining.

Commit only these files:

```powershell
git add -- server/loot/refine.py server/api/inventory.py web/js/screen-bag.js tests/test_loot_refine.py tests/test_api_inventory.py
git commit -m "fix: gate random refining and raise its cost" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

### Task 3: Filter socket choices by equipment slot

**Files:**
- Modify: `web/js/screen-bag.js`
- Create: `tests/web/screen-bag.test.js`
- Test: `tests/test_api_inventory.py`

- [ ] **Step 1: Create failing pure UI tests**

Create `tests/web/screen-bag.test.js`:

```javascript
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");

const source = fs.readFileSync(
  path.join(__dirname, "../../web/js/screen-bag.js"),
  "utf8",
);
const context = { window: {}, Screens: {} };
vm.runInNewContext(source, context);
const bagView = context.window.ROBagView;

test("returns only held cards matching the selected equipment slot", () => {
  const items = { wolf_card: 2, poring_card: 1, red_potion: 5 };
  const cards = {
    wolf_card: { slot: "weapon" },
    poring_card: { slot: "armor" },
  };
  assert.deepEqual(
    JSON.parse(JSON.stringify(bagView.compatibleCardIds(items, cards, "armor"))),
    ["poring_card"],
  );
});

test("shows socket action only while a card slot is open", () => {
  const equipment = { card_slots: 1 };
  assert.equal(bagView.hasOpenCardSlot({ card_ids: [] }, equipment), true);
  assert.equal(bagView.hasOpenCardSlot({ card_ids: ["poring_card"] }, equipment), false);
  assert.equal(bagView.hasOpenCardSlot({ card_ids: [] }, { card_slots: 0 }), false);
});
```

- [ ] **Step 2: Run the Node test and verify the helpers are absent**

Run:

```powershell
node --test tests/web/screen-bag.test.js
```

Expected: FAIL because `window.ROBagView` is not defined.

- [ ] **Step 3: Implement pure slot helpers and use them in the bag screen**

Add these helpers near the top of `web/js/screen-bag.js`:

```javascript
  function compatibleCardIds(items, cards, slot) {
    return Object.keys(items || {}).filter((id) =>
      Number(items[id] || 0) > 0 && cards?.[id]?.slot === slot
    );
  }

  function hasOpenCardSlot(instance, equipment) {
    return Number(equipment?.card_slots || 0) > (instance.card_ids || []).length;
  }

  window.ROBagView = { compatibleCardIds, hasOpenCardSlot };
```

When rendering each equipment row, obtain the equipment definition and gate the button:

```javascript
          const eq = S.catalog?.equipment?.[inst.equipment_id];
          const canSocket = hasOpenCardSlot(inst, eq);
```

```javascript
              ${canSocket ? `<button class="btn small" data-socket="${inst.id}"
                data-socket-slot="${esc(eq.slot)}">鑲卡</button>` : ""}
```

Pass the slot from the click handler:

```javascript
          const cardId = this._pickCard(inv.items || {}, b.dataset.socketSlot);
```

Replace `_pickCard()` with the slot-aware implementation:

```javascript
    _pickCard(items, slot) {
      const cards = compatibleCardIds(items, S.catalog?.cards || {}, slot);
      const slotName = SLOT_ZH[slot] || slot;
      if (!cards.length) {
        App.toast(`背包沒有可插入「${slotName}」的卡片`, true);
        return null;
      }
      const list = cards
        .map((id, i) => `${i + 1}. ${itemName(id)} ×${items[id]}（${slotName}）`)
        .join("\n");
      const pick = prompt(`要鑲哪張卡？可插部位：${slotName}\n${list}`, "1");
      if (pick == null) return null;
      const idx = Math.floor(Number(pick)) - 1;
      if (idx < 0 || idx >= cards.length) {
        App.toast("編號不對", true);
        return null;
      }
      return cards[idx];
    },
```

- [ ] **Step 4: Verify front-end filtering and backend defense, then commit**

Run:

```powershell
node --test tests/web/screen-bag.test.js
uv run pytest tests/test_api_inventory.py::test_socket_card tests/test_api_inventory.py::test_socket_rejects_wrong_slot tests/test_api_inventory.py::test_socket_rejects_no_slots -q
```

Expected: all five selected tests pass.

Commit only the socket files:

```powershell
git add -- web/js/screen-bag.js tests/web/screen-bag.test.js
git commit -m "fix: filter socket cards by equipment slot" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

### Task 4: Give every MVP skills and reliable accuracy

**Files:**
- Create: `server/combat/boss_skills.py`
- Modify: `server/combat/combatant.py`
- Modify: `server/combat/formulas.py`
- Modify: `server/combat/engine.py`
- Modify: `server/combat/skills.py`
- Test: `tests/test_combat_formulas.py`
- Test: `tests/test_combat_combatant.py`
- Test: `tests/test_mvp_challenge.py`

- [ ] **Step 1: Add failing tests for the configurable hit floor**

Append to `tests/test_combat_formulas.py`:

```python
def test_hit_chance_accepts_boss_specific_minimum():
    assert f.hit_chance(0, 999, minimum=0.35) == 0.35
    assert f.hit_chance(100, 100, minimum=0.35) == 0.80
```

Run:

```powershell
uv run pytest tests/test_combat_formulas.py::test_hit_chance_accepts_boss_specific_minimum -q
```

Expected: FAIL because `hit_chance()` does not accept `minimum`.

- [ ] **Step 2: Implement an optional minimum and route both physical attack paths through it**

Replace `hit_chance()` in `server/combat/formulas.py` with:

```python
def hit_chance(
    attacker_hit: int, target_flee: int, minimum: float = 0.05
) -> float:
    floor_pct = _clamp(round(minimum * 100), 0, 95)
    return _clamp(80 + attacker_hit - target_flee, floor_pct, 95) / 100
```

Add this field to `Combatant` in `server/combat/combatant.py`:

```python
    min_hit_chance: float = 0.05
```

Update the normal attack roll in `server/combat/engine.py`:

```python
    hit = rng.random() < hit_chance(
        attacker.effective_hit,
        defender.effective_flee,
        minimum=attacker.min_hit_chance,
    )
```

Update the physical skill roll in `server/combat/skills.py`:

```python
        chance = hit_chance(
            caster.effective_hit,
            target.effective_flee,
            minimum=caster.min_hit_chance,
        )
        if rng.random() >= chance:
            continue
```

- [ ] **Step 3: Add failing tests for MVP-only skills, SP, and hit floor**

Append to `tests/test_combat_combatant.py`:

```python
def test_mvp_combatant_gets_boss_skills_sp_and_accuracy_floor():
    from server.content import load_content

    content = load_content()
    boss = Combatant.from_monster(content.mvps["angel_poring"])
    normal = Combatant.from_monster(content.monsters["poring"])

    assert boss.min_hit_chance == 0.35
    assert boss.max_sp >= 1000
    assert {skill.skill_id for skill in boss.skills} == {
        "mvp_power_strike",
        "mvp_element_burst",
        "mvp_enrage",
    }
    assert normal.min_hit_chance == 0.05
    assert normal.skills == []
```

Append to `tests/test_mvp_challenge.py`:

```python
def test_every_mvp_emits_visible_skills_against_high_flee_target():
    from server.combat import simulate_fight
    from server.combat.combatant import Combatant

    content = load_content()
    for mvp_id, mvp in content.mvps.items():
        player = Combatant(
            name="高迴避測試者",
            max_hp=100_000,
            max_sp=0,
            atk=1,
            matk=1,
            defense=0,
            mdef=0,
            hit=1,
            flee=999,
            aspd=100,
            crit=0,
        )
        boss = Combatant.from_monster(mvp)
        result = simulate_fight(player, boss, random.Random(0), max_rounds=6)
        boss_skills = [
            event for event in result.events
            if getattr(event, "kind", "") == "skill" and event.actor == boss.name
        ]
        assert boss_skills, mvp_id
        assert player.hp < player.max_hp, mvp_id
```

Run:

```powershell
uv run pytest tests/test_combat_combatant.py::test_mvp_combatant_gets_boss_skills_sp_and_accuracy_floor tests/test_mvp_challenge.py::test_every_mvp_emits_visible_skills_against_high_flee_target -q
```

Expected: FAIL because monster combatants currently have no skills and use the global 5% floor.

- [ ] **Step 4: Create the centralized boss skill factory**

Create `server/combat/boss_skills.py`:

```python
from server.combat.combatant import ResolvedSkill


def resolve_boss_skills(mvp) -> list[ResolvedSkill]:
    element = getattr(mvp.element, "value", mvp.element)
    return [
        ResolvedSkill(
            skill_id="mvp_power_strike",
            name="王者重擊",
            level=1,
            kind="active",
            sp_cost=20,
            cooldown_rounds=2,
            effects=[{"type": "physical_hit", "power_pct": 160}],
            trigger="cooldown_ready",
            priority=90,
        ),
        ResolvedSkill(
            skill_id="mvp_element_burst",
            name="元素爆發",
            level=1,
            kind="active",
            sp_cost=25,
            cooldown_rounds=4,
            effects=[{
                "type": "magic_hit",
                "power_pct": 140,
                "element": element,
            }],
            trigger="cooldown_ready",
            priority=80,
        ),
        ResolvedSkill(
            skill_id="mvp_enrage",
            name="狂暴",
            level=1,
            kind="active",
            sp_cost=0,
            cooldown_rounds=999,
            effects=[{
                "type": "buff",
                "duration_s": 10,
                "stats": {
                    "atk": max(1, round(mvp.stats.atk * 0.25)),
                    "hit": max(1, round(mvp.stats.hit * 0.25)),
                },
            }],
            trigger="hp_below_50",
            priority=100,
        ),
    ]
```

- [ ] **Step 5: Attach boss combat settings in `Combatant.from_monster()`**

Inside `from_monster()`, prepare the MVP-only values before returning:

```python
        skills = []
        max_sp = s.max_sp
        min_hit_chance = 0.05
        if m.is_mvp:
            from server.combat.boss_skills import resolve_boss_skills

            skills = resolve_boss_skills(m)
            max_sp = max(max_sp, 1000)
            min_hit_chance = 0.35
```

Then use those values in the constructor:

```python
            name=m.name, max_hp=s.max_hp, max_sp=max_sp, atk=s.atk, matk=s.matk,
```

```python
            skills=skills, min_hit_chance=min_hit_chance,
```

- [ ] **Step 6: Run combat and balance regressions, tune only approved boss constants**

Run:

```powershell
uv run pytest tests/test_combat_formulas.py tests/test_combat_combatant.py tests/test_combat_engine.py tests/test_combat_skills.py tests/test_mvp_challenge.py tests/test_api_mvp.py -q
```

Expected: all selected tests pass. If the existing 30–80 round same-level test fails, adjust only the three approved Boss constants (`160%`, `140%`, `35%`) while preserving visible skills, real damage against FLEE 999, and the prior fight-duration band. Do not change general monster or player formulas.

- [ ] **Step 7: Commit the MVP correction**

```powershell
git add -- server/combat/boss_skills.py server/combat/combatant.py server/combat/formulas.py server/combat/engine.py server/combat/skills.py tests/test_combat_formulas.py tests/test_combat_combatant.py tests/test_mvp_challenge.py
git commit -m "fix: make MVP combat skills threatening" -m "Co-Authored-By: Codex <noreply@openai.com>"
```

### Task 5: Full verification and independent review

**Files:**
- Verify all modified files from Tasks 1–4
- Update tests only if the reviewer identifies a real uncovered defect

- [ ] **Step 1: Run all Python tests**

```powershell
uv run pytest -q
```

Expected: zero failures. Existing dependency deprecation warnings may remain but no new warnings should be introduced.

- [ ] **Step 2: Run every Node front-end test**

```powershell
node --test tests/web/*.test.js
```

Expected: zero failures.

- [ ] **Step 3: Run content validators and diff checks**

```powershell
uv run python scripts/check_content.py
uv run python scripts/check_skills.py
git diff --check
git status --short --branch
```

Expected: both validators report success, diff check is empty, and status contains no unintended files.

- [ ] **Step 4: Run the required independent Claude Code review**

From the repository root, run:

```powershell
git add -N .
git diff | claude -p "以下是待審核的 git diff,請找出 bug、邏輯錯誤、邊界條件、安全性問題,用簡短條列回報並標註嚴重度;若無問題只回 LGTM" --output-format text
```

Expected: `LGTM`, or findings categorized by severity. Fix all Critical/High findings, evaluate Medium findings, rerun affected tests, and repeat the review up to three rounds.

- [ ] **Step 5: Confirm rollback commits and report without pushing or deploying**

```powershell
git log -5 --oneline --decorate
git status --short --branch
```

Expected: the four task commits are visible and the worktree is clean. Do not push or deploy unless the user separately authorizes that external state change.
