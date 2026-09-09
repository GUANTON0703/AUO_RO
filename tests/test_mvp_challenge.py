import random

from server.content import load_content
from server.db import connection
from server.mvp.challenge import ChallengeConfig, challenge_mvp
from server.progression import (
    CharacterSnapshot, EquippedPiece, build_player_combatant,
)
from shared.content import DropEntry


def _hero(lv, **kw):
    c = load_content()
    stats = {"str": lv + 25, "agi": lv // 2, "vit": lv + 2,
             "int": 5, "dex": lv + 5, "luk": lv // 3}
    stats.update(kw.get("stats", {}))
    return build_player_combatant(CharacterSnapshot(
        name="勇者", job_id="swordman", base_level=lv, job_level=min(lv, 50),
        stats=stats, learned_skills={"bash": 5},
        equipped=[EquippedPiece("blade", 5, ["skeleton_card"]),
                  EquippedPiece("cotton_shirt", 5, [])],
    ), c)


def _graduated_knight(lv):
    c = load_content()
    gear = [
        EquippedPiece(
            "bastard_sword_3",
            4,
            ["skel_worker_card", "wolf_card", "skeleton_card"],
        ),
        EquippedPiece("full_plate_1", 4, []),
        EquippedPiece("boots", 4, ["matyr_card"]),
    ]
    return build_player_combatant(CharacterSnapshot(
        name="畢業騎士", job_id="knight", base_level=lv, job_level=min(lv, 50),
        stats={"str": lv + 20, "agi": lv // 2, "vit": lv,
               "int": 5, "dex": lv, "luk": lv // 3},
        learned_skills={
            "bash": 5, "sword_mastery": 5,
            "bowling_bash": 5, "twohand_quicken": 5,
        },
        equipped=gear,
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


def test_same_level_graduated_knight_fights_mid_late_mvps_in_target_band():
    c = load_content()
    target_ids = {
        "curly_boar_king", "golden_bug_king", "drake", "moonlight_flower",
        "doppelganger", "orc_lord", "stormy_knight", "pharaoh",
        "dark_lord",
    }
    for mvp_id in target_ids:
        mvp = c.mvps[mvp_id]
        result = challenge_mvp(
            _graduated_knight(mvp.level), mvp, ChallengeConfig(flee_hp_frac=0),
            random.Random(0), mvp.level,
        )
        assert result.outcome == "win", mvp_id
        assert 30 <= result.rounds <= 80, f"{mvp_id}: {result.rounds} 回合"


def test_mvp_uses_source_specific_drop_rate_override(tmp_path):
    connection.configure(str(tmp_path / "mvp-drop-rates.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO global_drop_rates(item_id, rate) VALUES (?, ?)",
            ("angel_poring_card", 0.0),
        )
        conn.execute(
            "INSERT INTO source_drop_rates(source_id, item_id, rate) VALUES (?, ?, ?)",
            ("angel_poring", "angel_poring_card", 1.0),
        )

    content = load_content()
    original = content.mvps["angel_poring"]
    mvp = original.model_copy(update={
        "drops": [DropEntry(item_id="angel_poring_card", rate=0.0)],
    })
    result = challenge_mvp(_hero(mvp.level), mvp, ChallengeConfig(),
                           random.Random(0), mvp.level)

    assert result.outcome == "win"
    assert result.drops == {"angel_poring_card": 1}
