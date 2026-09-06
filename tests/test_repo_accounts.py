import pytest

from server.db import connection
from server.repositories import accounts


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()


def test_create_and_fetch(db):
    acc_id = accounts.create_account("alice", "hash1")
    assert acc_id > 0
    by_name = accounts.get_account_by_username("alice")
    assert by_name["id"] == acc_id
    assert by_name["password_hash"] == "hash1"
    assert accounts.get_account(acc_id)["username"] == "alice"


def test_get_missing_returns_none(db):
    assert accounts.get_account_by_username("nobody") is None
    assert accounts.get_account(999) is None


def test_duplicate_username_raises(db):
    accounts.create_account("bob", "h")
    with pytest.raises(accounts.UsernameTakenError):
        accounts.create_account("bob", "h2")
