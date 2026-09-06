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
    assert cb.hit == 15 + 18
    assert cb.flee == 15 + 15
    assert 100 <= cb.aspd <= 193


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


def test_hp_sp_default_to_max_when_none():
    c = load_content()
    cb = build_player_combatant(_snap(hp=None, sp=None), c)
    assert cb.hp == cb.max_hp and cb.sp == cb.max_sp


def test_hp_sp_preserved_when_given():
    c = load_content()
    cb = build_player_combatant(_snap(hp=50, sp=10), c)
    assert cb.hp == 50 and cb.sp == 10
