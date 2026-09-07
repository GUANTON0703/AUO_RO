import pytest

from server.db import connection
from server.auth import invites


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (id, username, password_hash, created_at) "
            "VALUES (1, 'u', 'h', 't'), (2, 'u2', 'h', 't')"
        )


def test_generate_code_format():
    code = invites.generate_code()
    parts = code.split("-")
    assert len(parts) == 3
    assert all(len(p) == 4 for p in parts)
    assert set(code.replace("-", "")) <= set(invites._ALPHABET)


def test_create_and_consume(db):
    code = invites.create_invite()
    assert invites.is_available(code) is True
    invites.consume_invite(code, account_id=1)
    assert invites.is_available(code) is False


def test_consume_unknown_code_raises(db):
    with pytest.raises(invites.InviteError):
        invites.consume_invite("NOPE-NOPE-NOPE", account_id=1)


def test_consume_twice_raises(db):
    code = invites.create_invite()
    invites.consume_invite(code, account_id=1)
    with pytest.raises(invites.InviteError):
        invites.consume_invite(code, account_id=2)


def test_open_invite_code_registers_without_consuming(client):
    # 預設 open_invite_code = "99auo99"，多人可重複用
    for name in ("openone", "opentwo"):
        r = client.post("/api/accounts", json={
            "invite_code": "99auo99", "username": name, "password": "password123"})
        assert r.status_code == 201, r.text
