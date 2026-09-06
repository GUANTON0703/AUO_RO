def test_register_with_valid_invite(client, invite_code):
    resp = client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "newbie", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newbie"


def test_register_rejects_bad_invite(client):
    resp = client.post(
        "/api/accounts",
        json={"invite_code": "BAD-BAD0-BAD1", "username": "zoe", "password": "password123"},
    )
    assert resp.status_code == 400


def test_register_rejects_reused_invite(client, invite_code):
    first = {"invite_code": invite_code, "username": "ann", "password": "password123"}
    second = {"invite_code": invite_code, "username": "ben", "password": "password123"}
    assert client.post("/api/accounts", json=first).status_code == 201
    assert client.post("/api/accounts", json=second).status_code == 400


def test_register_rejects_duplicate_username(client):
    from server.auth import invites

    c1, c2 = invites.create_invite(), invites.create_invite()
    client.post("/api/accounts", json={"invite_code": c1, "username": "dup", "password": "password123"})
    resp = client.post("/api/accounts", json={"invite_code": c2, "username": "dup", "password": "password123"})
    assert resp.status_code == 409


def test_register_rejects_short_password(client, invite_code):
    resp = client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "zoe", "password": "short"},
    )
    assert resp.status_code == 422


def test_register_rejects_short_username(client, invite_code):
    resp = client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "ab", "password": "password123"},
    )
    assert resp.status_code == 422


def test_login_returns_token(client, invite_code):
    client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "loginer", "password": "password123"},
    )
    resp = client.post("/api/sessions", json={"username": "loginer", "password": "password123"})
    assert resp.status_code == 200
    assert isinstance(resp.json()["token"], str)


def test_login_rejects_wrong_password(client, invite_code):
    client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "uma", "password": "password123"},
    )
    resp = client.post("/api/sessions", json={"username": "uma", "password": "nope"})
    assert resp.status_code == 401


def test_logout_revokes_token(client, auth):
    token, headers, _ = auth
    assert client.delete("/api/sessions", headers=headers).status_code == 204
