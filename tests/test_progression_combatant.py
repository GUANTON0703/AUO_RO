from server.progression import build_player_combatant, CharacterSnapshot, EquippedPiece
from server.content import load_content


def _snap(**kw):
    base = dict(name="測試", job_id="swordman", base_level=15, job_level=8,
                stats={"str": 30, "agi": 15, "vit": 20, "int": 5, "dex": 18, "luk": 8},
                learned_skills={"bash": 3}, equipped=[],
                hp=None, sp=None)
    base.update(kw)
    return CharacterSnapshot(**base)


def test_derived_stats_from_primary():
    c = load_content()
    cb = build_player_combatant(_snap(), c)
    assert cb.name == "測試"
    assert cb.max_hp > 40
    assert cb.atk >= 30
    assert cb.hit == 15 + 18 + 8 // 3  # base + DEX + LUK//3
    assert cb.flee == 15 + 15 + 8 // 5  # base + AGI + LUK//5
    assert 100 <= cb.aspd <= 250


def test_equipment_adds_stats():
    c = load_content()
    bare = build_player_combatant(_snap(equipped=[]), c)
    armed = build_player_combatant(_snap(equipped=[EquippedPiece(equipment_id="knife")]), c)
    assert armed.atk > bare.atk


def test_card_flat_stat_applies():
    c = load_content()
    plain = build_player_combatant(
        _snap(equipped=[EquippedPiece(equipment_id="cotton_shirt")]), c)
    carded = build_player_combatant(
        _snap(equipped=[EquippedPiece(equipment_id="cotton_shirt", card_ids=["poring_card"])]), c)
    assert carded.max_hp > plain.max_hp


def test_card_primary_stat_and_aspd_feed_derived():
    """str 卡要推高 atk、aspd 卡要推高攻速（曾經因為卡片在衍生數值之後才套用而失效）。"""
    c = load_content()
    plain = build_player_combatant(
        _snap(equipped=[EquippedPiece(equipment_id="knife")]), c)
    str_card = build_player_combatant(
        _snap(equipped=[EquippedPiece(equipment_id="knife", card_ids=["tarou_card"])]), c)
    aspd_card = build_player_combatant(
        _snap(equipped=[EquippedPiece(equipment_id="knife", card_ids=["locust_card"])]), c)
    assert str_card.atk > plain.atk
    assert aspd_card.aspd > plain.aspd


def test_refined_equipment_adds_more_stats():
    c = load_content()

    def snap(pieces):
        return CharacterSnapshot(name="P", job_id="swordman", base_level=20, job_level=10,
                                 stats={"str": 30, "agi": 15, "vit": 20, "int": 5, "dex": 18, "luk": 8},
                                 learned_skills={"bash": 1}, equipped=pieces)

    plain = build_player_combatant(snap([EquippedPiece(equipment_id="knife", refine=0, card_ids=[])]), c)
    r7 = build_player_combatant(snap([EquippedPiece(equipment_id="knife", refine=7, card_ids=[])]), c)
    assert r7.atk > plain.atk


def test_socketed_card_via_piece():
    c = load_content()
    snap = CharacterSnapshot(name="P", job_id="swordman", base_level=20, job_level=10,
                             stats={"str": 30, "agi": 15, "vit": 20, "int": 5, "dex": 18, "luk": 8},
                             learned_skills={"bash": 1},
                             equipped=[EquippedPiece(equipment_id="cotton_shirt", refine=0,
                                                     card_ids=["poring_card"])])
    plain_snap = CharacterSnapshot(name="P", job_id="swordman", base_level=20, job_level=10,
                                   stats={"str": 30, "agi": 15, "vit": 20, "int": 5, "dex": 18, "luk": 8},
                                   learned_skills={"bash": 1},
                                   equipped=[EquippedPiece(equipment_id="cotton_shirt", refine=0, card_ids=[])])
    assert build_player_combatant(snap, c).max_hp > build_player_combatant(plain_snap, c).max_hp


def test_learned_active_skills_become_resolved():
    c = load_content()
    cb = build_player_combatant(_snap(learned_skills={"bash": 3}), c)
    bash = [s for s in cb.skills if s.skill_id == "bash"]
    assert bash and bash[0].level == 3
    assert bash[0].kind == "active"


def test_passive_skill_modifies_stats_not_added_as_active():
    c = load_content()
    with_pas = build_player_combatant(_snap(learned_skills={"bash": 1, "sword_mastery": 5}), c)
    without = build_player_combatant(_snap(learned_skills={"bash": 1}), c)
    assert with_pas.atk > without.atk
    assert not any(s.skill_id == "sword_mastery" for s in with_pas.skills)


def test_monk_spirit_recovery_grants_regen_bonus():
    """武僧補的 Classic 技能：回氣（passive）要折進 regen_bonus_pct，跟藥水的 buff 走同一個池子。"""
    c = load_content()
    cb = build_player_combatant(_snap(job_id="monk", learned_skills={"spirit_recovery": 3}), c)
    assert cb.regen_bonus_pct == 30


def test_hp_sp_default_to_max_when_none():
    c = load_content()
    cb = build_player_combatant(_snap(hp=None, sp=None), c)
    assert cb.hp == cb.max_hp and cb.sp == cb.max_sp


def test_hp_sp_preserved_when_given():
    c = load_content()
    cb = build_player_combatant(_snap(hp=50, sp=10), c)
    assert cb.hp == 50 and cb.sp == 10


def test_skill_toggle_off_removes_skill():
    c = load_content()
    on = build_player_combatant(_snap(learned_skills={"bash": 3, "magnum_break": 3}), c)
    off = build_player_combatant(_snap(learned_skills={"bash": 3, "magnum_break": 3},
                                       skill_toggles={"magnum_break": False}), c)
    assert {s.skill_id for s in on.skills} == {"bash", "magnum_break"}
    assert {s.skill_id for s in off.skills} == {"bash"}


def test_primary_skill_gets_top_priority():
    c = load_content()
    cb = build_player_combatant(_snap(learned_skills={"bash": 3, "magnum_break": 3},
                                      primary_skill_id="magnum_break"), c)
    prio = {s.skill_id: s.priority for s in cb.skills}
    assert prio["magnum_break"] > prio["bash"]
    assert prio["magnum_break"] == 99


def test_primary_skill_ignores_its_own_default_trigger():
    """治癒術預設要血量低於 50% 才放，但指定成主攻後要能一直放，
    不然服事系設了也打不了不死怪（治癒術對不死系是傷害）。"""
    c = load_content()
    cb = build_player_combatant(_snap(job_id="acolyte", learned_skills={"heal": 5},
                                      primary_skill_id="heal"), c)
    heal = next(s for s in cb.skills if s.skill_id == "heal")
    assert heal.trigger == "every_turn"
    assert heal.priority == 99


def test_default_disabled_skill_excluded_unless_toggled_on():
    c = load_content()
    # provoke 的 idle_default.enabled = false
    base = build_player_combatant(_snap(learned_skills={"bash": 3, "provoke": 3}), c)
    forced = build_player_combatant(_snap(learned_skills={"bash": 3, "provoke": 3},
                                          skill_toggles={"provoke": True}), c)
    assert "provoke" not in {s.skill_id for s in base.skills}
    assert "provoke" in {s.skill_id for s in forced.skills}


def test_equipment_max_hp_sp_apply():
    c = load_content()
    bare = build_player_combatant(_snap(equipped=[]), c)
    # curly_horn_helm = +200 HP, circlet = +10 SP（經典小數值尺度）
    hp_gear = build_player_combatant(_snap(equipped=[EquippedPiece("curly_horn_helm")]), c)
    sp_gear = build_player_combatant(_snap(equipped=[EquippedPiece("circlet")]), c)
    assert hp_gear.max_hp >= bare.max_hp + 190
    assert sp_gear.max_sp >= bare.max_sp + 8


def test_stale_hp_clamped_to_new_max():
    c = load_content()
    # 帶著舊的高 hp，但沒穿加 HP 裝 → 應被夾到新 max_hp
    cb = build_player_combatant(_snap(equipped=[], hp=999999, sp=999999), c)
    assert cb.hp == cb.max_hp
    assert cb.sp == cb.max_sp


def test_bow_atk_scales_with_dex_not_str():
    c = load_content()

    def archer(dex, str_):
        return build_player_combatant(CharacterSnapshot(
            name="弓", job_id="archer", base_level=40, job_level=40,
            stats={"str": str_, "agi": 20, "vit": 20, "int": 5, "dex": dex, "luk": 8},
            learned_skills={}, equipped=[EquippedPiece("hunter_bow", 0, [])]), c)

    assert archer(dex=60, str_=10).atk > archer(dex=10, str_=60).atk


def test_card_special_effects_wire_into_combatant():
    c = load_content()

    def sin(cards):
        return build_player_combatant(CharacterSnapshot(
            name="P", job_id="assassin", base_level=60, job_level=50,
            stats={"str": 50, "agi": 60, "vit": 30, "int": 5, "dex": 40, "luk": 30},
            learned_skills={},
            equipped=[EquippedPiece("jur_3", 5, cards.get("w", [])),
                      EquippedPiece("full_plate_1", 5, cards.get("a", [])),
                      EquippedPiece("bee_wing_mantle", 5, cards.get("g", []))]), c)

    assert sin({"a": ["ghostring_card"]}).element == "ghost"
    assert "freeze" in sin({"a": ["marc_card"]}).immunities
    assert sin({"g": ["hunter_fly_card"]}).procs.get("life_leech") == 3
    assert sin({"w": ["zenorc_card"]}).procs.get("poison") == 10
    assert sin({"g": ["whisper_card"]}).perfect_dodge == 3


def test_mvp_gear_builtin_effects_wire_into_combatant():
    """MVP 神裝自帶的 effects（不是鑲卡）也要生效。"""
    c = load_content()

    def hero(weapon):
        return build_player_combatant(CharacterSnapshot(
            name="P", job_id="knight", base_level=80, job_level=50,
            stats={"str": 70, "agi": 30, "vit": 60, "int": 5, "dex": 50, "luk": 10},
            learned_skills={}, equipped=[EquippedPiece(weapon, 0, [])]), c)

    assert hero("sword_of_the_sun").attack_element == "fire"
    assert hero("sword_of_the_sun").race_bonus.get("undead") == 30
    assert hero("baphomet_trident").procs.get("extra_hit") == 10


def test_active_potion_buffs_fold_into_stats():
    c = load_content()

    def hero(active_item_buffs):
        return build_player_combatant(CharacterSnapshot(
            name="P", job_id="knight", base_level=50, job_level=40,
            stats={"str": 40, "agi": 20, "vit": 30, "int": 5, "dex": 20, "luk": 10},
            learned_skills={}, equipped=[],
            active_item_buffs=active_item_buffs), c)

    bare = hero({})
    boosted = hero({"concentration_potion": {"hit": 10, "crit": 5}})
    assert boosted.hit == bare.hit + 10
    assert boosted.crit == bare.crit + 5

    # 狂暴藥：防禦歸零（用大負數表達，靠既有的 max(0,...) 夾住）、爆擊傷害倍率額外加成
    berserked = hero({"berserk_potion": {"atk": 90, "defense": -999}})
    assert berserked.defense == 0
    assert berserked.atk == bare.atk + 90

    sweet = hero({"sweet_spot_potion": {"crit_mult_bonus": 0.2}})
    assert round(sweet.crit_mult - bare.crit_mult, 2) == 0.2

    healboost = hero({"heal_boost_potion": {"potion_heal_pct": 25}})
    assert healboost.potion_heal_pct == 25
    vitality = hero({"vitality_potion": {"regen_bonus_pct": 100}})
    assert vitality.regen_bonus_pct == 100


def test_on_hit_poison_card_applies_dot():
    import random
    from server.combat import simulate_fight
    from server.combat.combatant import Combatant
    c = load_content()
    p = build_player_combatant(CharacterSnapshot(
        name="P", job_id="assassin", base_level=60, job_level=50,
        stats={"str": 50, "agi": 60, "vit": 30, "int": 5, "dex": 40, "luk": 20},
        learned_skills={}, equipped=[EquippedPiece("jur_3", 5, ["zenorc_card"])]), c)
    r = simulate_fight(p, Combatant.from_monster(c.get_monster("raydric")),
                       random.Random(1), max_rounds=100)
    assert any(e.kind == "dot" for e in r.events)
