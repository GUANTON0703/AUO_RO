import pytest

from server.db import connection
from server.repositories import accounts, characters, mvp


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()


@pytest.fixture
def char(db):
    aid = accounts.create_account("o", "h")
    return characters.create_character(aid, "王殺", location_map="m")["id"]


def test_cooldown_set_and_check(char):
    assert mvp.is_available(char, "angel_poring") is True
    mvp.set_cooldown(char, "angel_poring", hours=8)
    assert mvp.is_available(char, "angel_poring") is False
    remain = mvp.seconds_remaining(char, "angel_poring")
    assert 0 < remain <= 8 * 3600


def test_seconds_remaining_zero_when_available(char):
    assert mvp.seconds_remaining(char, "queen_bee") == 0


def test_all_cooldowns_lists_only_active(char):
    mvp.set_cooldown(char, "angel_poring", hours=8)
    mvp.set_cooldown(char, "queen_bee", hours=-1)   # 已過期
    cds = mvp.all_cooldowns(char)
    assert "angel_poring" in cds and "queen_bee" not in cds


def test_set_cooldown_overwrites(char):
    mvp.set_cooldown(char, "angel_poring", hours=8)
    mvp.set_cooldown(char, "angel_poring", hours=1)
    assert mvp.seconds_remaining(char, "angel_poring") <= 3600
