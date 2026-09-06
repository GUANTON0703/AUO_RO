import pytest
from fastapi.testclient import TestClient

from client.api import ApiClient
from client.auth_flow import ensure_logged_in, select_or_create_character
from client.config import SessionStore
from server.app import create_app
from server.db import connection


def test_session_store_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "s.json")
    store.save(server_url="http://x", token="tok", username="u")
    loaded = SessionStore(tmp_path / "s.json").load()
    assert loaded["token"] == "tok" and loaded["username"] == "u"


def test_session_store_missing_returns_none(tmp_path):
    assert SessionStore(tmp_path / "none.json").load() is None


@pytest.fixture
def api(tmp_path):
    connection.configure(str(tmp_path / "c.db"))
    connection.init_db()
    from server.auth import invites

    code = invites.create_invite()
    return ApiClient(TestClient(create_app())), code


def test_ensure_logged_in_register_happy_path(api, tmp_path, monkeypatch):
    client, code = api
    store = SessionStore(tmp_path / "s.json")
    answers = iter([code, "brandnew", "password123", "小新"])
    monkeypatch.setattr(
        "client.auth_flow.Prompt.ask",
        lambda *a, **k: "2" if "登入" in (a[0] if a else "") else next(answers),
    )
    ensure_logged_in(client, store, "http://test")
    assert client.token is not None
    assert store.load()["username"] == "brandnew"

    ch = select_or_create_character(client)
    assert ch["name"]


def test_ensure_logged_in_reuses_saved_token(api, tmp_path, monkeypatch):
    client, code = api
    client.register(code, "returning", "password123")
    client.login("returning", "password123")
    store = SessionStore(tmp_path / "s.json")
    store.save(server_url="http://test", token=client.token, username="returning")

    fresh = ApiClient(client._http)

    def _boom(*a, **k):
        raise AssertionError("不應該再問一次")

    monkeypatch.setattr("client.auth_flow.Prompt.ask", _boom)
    ensure_logged_in(fresh, store, "http://test")
    assert fresh.token == client.token
