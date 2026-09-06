import json

import pytest

from server.db import connection
from server.repositories import accounts, characters


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()


@pytest.fixture
def account_id(db):
    return accounts.create_account("owner", "h")


def test_create_defaults_to_novice(account_id):
    row = characters.create_character(account_id, "英雄", location_map="prontera_east_gate")
    assert row["job_id"] == "novice"
    assert row["base_level"] == 1 and row["job_level"] == 1
    assert row["stat_str"] == 1 and row["stat_int"] == 1
    assert row["location_map"] == "prontera_east_gate"


def test_create_within_limit_blocks_at_cap(account_id):
    for n in ["甲", "乙"]:
        assert characters.create_within_limit(account_id, n, "m", max_count=2) is not None
    assert characters.create_within_limit(account_id, "丙", "m", max_count=2) is None
    assert characters.count_for_account(account_id) == 2


def test_create_within_limit_rejects_duplicate_name(account_id):
    characters.create_within_limit(account_id, "重複", "m", max_count=3)
    with pytest.raises(characters.NameTakenError):
        characters.create_within_limit(account_id, "重複", "m", max_count=3)


def test_create_within_limit_is_atomic_under_concurrency(account_id):
    from concurrent.futures import ThreadPoolExecutor

    characters.create_within_limit(account_id, "已有", "m", max_count=3)

    def attempt(name: str):
        return characters.create_within_limit(account_id, name, "m", max_count=3)

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(attempt, ["a", "b", "c"]))

    created = [r for r in results if r is not None]
    assert len(created) == 2  # 上限 3，已有 1，只能再進 2
    assert characters.count_for_account(account_id) == 3


def test_list_and_count_scoped_to_account(account_id):
    other = accounts.create_account("other", "h")
    characters.create_character(account_id, "甲", location_map="m")
    characters.create_character(account_id, "乙", location_map="m")
    characters.create_character(other, "丙", location_map="m")
    assert characters.count_for_account(account_id) == 2
    names = {c["name"] for c in characters.list_for_account(account_id)}
    assert names == {"甲", "乙"}


def test_duplicate_name_raises(account_id):
    characters.create_character(account_id, "重複", location_map="m")
    with pytest.raises(characters.NameTakenError):
        characters.create_character(account_id, "重複", location_map="m")


def test_get_and_delete(account_id):
    row = characters.create_character(account_id, "刪我", location_map="m")
    cid = row["id"]
    assert characters.get_character(cid)["name"] == "刪我"
    assert characters.delete_character(cid, account_id) is True
    assert characters.get_character(cid) is None


def test_delete_wrong_owner_is_noop(account_id):
    other = accounts.create_account("x", "h")
    row = characters.create_character(account_id, "別人的", location_map="m")
    assert characters.delete_character(row["id"], other) is False
    assert characters.get_character(row["id"]) is not None


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
    assert json.loads(got["hunt_loot"]) == {"jellopy": 15, "clover": 2}
    assert json.loads(got["hunt_pity"]) == {"poring_card": 500}


def test_set_stats_and_job_and_skills(account_id):
    row = characters.create_character(account_id, "轉職仔", location_map="m")
    characters.set_stats(row["id"], {"str": 9, "agi": 3, "vit": 4, "int": 1, "dex": 5, "luk": 2})
    characters.set_job(row["id"], "swordman", 1, 0)
    characters.set_learned_skills(row["id"], {"bash": 3})
    got = characters.get_character(row["id"])
    assert got["stat_str"] == 9 and got["job_id"] == "swordman" and got["job_level"] == 1
    assert json.loads(got["learned_skills"]) == {"bash": 3}
