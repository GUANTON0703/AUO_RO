import pytest

from server.db import connection
from server.auth import tokens


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()
    with connection.get_connection() as conn:
        conn.execute(
            "INSERT INTO accounts (id, username, password_hash, created_at) VALUES (1, 'u', 'h', 't')"
        )


def test_issue_then_resolve(db):
    token = tokens.issue_token(account_id=1, ttl_hours=1)
    assert tokens.resolve_token(token) == 1


def test_resolve_unknown_returns_none(db):
    assert tokens.resolve_token("garbage") is None


def test_expired_token_returns_none(db):
    token = tokens.issue_token(account_id=1, ttl_hours=-1)
    assert tokens.resolve_token(token) is None


def test_revoke(db):
    token = tokens.issue_token(account_id=1, ttl_hours=1)
    tokens.revoke_token(token)
    assert tokens.resolve_token(token) is None
