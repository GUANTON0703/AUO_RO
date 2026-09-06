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
