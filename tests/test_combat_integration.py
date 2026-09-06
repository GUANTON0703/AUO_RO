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
