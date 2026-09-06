import pytest

from server.auth import invites
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


def test_register_with_invite_consumes_code(db):
    code = invites.create_invite()
    acc_id = accounts.register_with_invite("carol", "h", code)
    assert acc_id > 0
    assert invites.is_available(code) is False


def test_register_with_invite_rejects_unknown_code(db):
    with pytest.raises(invites.InviteError):
        accounts.register_with_invite("dave", "h", "NOPE-NOPE-NOPE")


def test_register_with_invite_rejects_used_code(db):
    code = invites.create_invite()
    accounts.register_with_invite("erin", "h", code)
    with pytest.raises(invites.InviteError):
        accounts.register_with_invite("frank", "h", code)


def test_register_with_invite_rolls_back_on_username_collision(db):
    accounts.create_account("grace", "h")
    code = invites.create_invite()
    with pytest.raises(accounts.UsernameTakenError):
        accounts.register_with_invite("grace", "h", code)
    # 帳號建立失敗 → 邀請碼不能被消耗
    assert invites.is_available(code) is True


def test_register_with_invite_is_atomic_under_concurrency(db):
    from concurrent.futures import ThreadPoolExecutor

    code = invites.create_invite()

    def attempt(name: str):
        try:
            return accounts.register_with_invite(name, "h", code)
        except (invites.InviteError, accounts.UsernameTakenError):
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["heidi", "ivan"]))

    assert sorted(r is None for r in results) == [False, True]  # 剛好一個成功
    assert invites.is_available(code) is False
