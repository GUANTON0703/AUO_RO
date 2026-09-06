import random

from server.content import load_content
from server.mvp.challenge import ChallengeConfig, challenge_mvp
from server.progression import (
    CharacterSnapshot, EquippedPiece, build_player_combatant,
)


def _hero(lv, **kw):
    c = load_content()
    stats = {"str": lv + 20, "agi": lv // 2, "vit": lv, "int": 5, "dex": lv, "luk": lv // 3}
    stats.update(kw.get("stats", {}))
    return build_player_combatant(CharacterSnapshot(
        name="勇者", job_id="swordman", base_level=lv, job_level=min(lv, 50),
        stats=stats, learned_skills={"bash": 5},
        equipped=[EquippedPiece("blade", 5, []), EquippedPiece("cotton_shirt", 5, [])],
    ), c)


def test_geared_player_wins_and_gets_rewards():
    c = load_content()
    m = c.mvps["angel_poring"]
    r = challenge_mvp(_hero(m.level), m, ChallengeConfig(), random.Random(0), m.level)
    assert r.outcome == "win"
    assert r.base_exp > 0 and r.zeny > 0
    assert sum(r.drops.values()) >= 0
    assert len(r.events) > 5


def test_weak_player_loses_and_pays_exp():
    c = load_content()
    m = c.mvps["curly_boar_king"]
    weak = _hero(15)
    r = challenge_mvp(weak, m, ChallengeConfig(flee_hp_frac=0.0), random.Random(1), 15)
    assert r.outcome == "loss"
    assert r.exp_penalty > 0


def test_flee_no_reward_no_penalty():
    c = load_content()
    m = c.mvps["curly_boar_king"]
    weak = _hero(20)
    r = challenge_mvp(weak, m, ChallengeConfig(flee_hp_frac=0.2), random.Random(2), 20)
    assert r.outcome == "fled"
    assert r.exp_penalty == 0 and r.base_exp == 0
