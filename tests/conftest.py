import pytest
from fastapi.testclient import TestClient

from server.db import connection


@pytest.fixture
def client(tmp_path):
    connection.configure(str(tmp_path / "test.db"))
    connection.init_db()
    from server.app import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def invite_code():
    from server.auth import invites

    return invites.create_invite()


@pytest.fixture
def auth(client, invite_code):
    """回傳 (token, headers, account_id)。已註冊 + 登入好一個帳號。"""
    client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "tester", "password": "password123"},
    )
    resp = client.post(
        "/api/sessions", json={"username": "tester", "password": "password123"}
    )
    body = resp.json()
    return body["token"], {"Authorization": f"Bearer {body['token']}"}, body["account_id"]
