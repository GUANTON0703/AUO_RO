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
