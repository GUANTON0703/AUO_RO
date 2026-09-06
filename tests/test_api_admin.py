from server.config import get_settings
from server.db import connection
from server.repositories import accounts, characters
from server.settlement.config import HuntConfig


def _make_gm(name):
    gm_id = _make_account(name)
    with connection.get_connection() as conn:
        conn.execute("UPDATE accounts SET role = ? WHERE id = ?", ("GM遊戲管理者", gm_id))
    return gm_id


def _make_account(username, password="password123"):
    from server.auth import passwords
    return accounts.create_account(username, passwords.hash_password(password))


def _login(client, username, password="password123"):
    return client.post("/api/sessions", json={"username": username, "password": password})


def test_non_gm_cannot_use_admin_api(client):
    account_id = _make_account("regular")
    token = _login(client, "regular").json()["token"]
    row = characters.create_character(account_id, "受管角色", "m")

    response = client.post(
        f"/api/admin/characters/{row['id']}/money",
        json={"amount": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_gm_can_adjust_money_and_exp_and_list_online_players(client):
    gm_id = _make_account("gm")
    player_id = _make_account("player")
    with connection.get_connection() as conn:
        conn.execute("UPDATE accounts SET role = ? WHERE id = ?", ("GM遊戲管理者", gm_id))
    token = _login(client, "gm").json()["token"]
    characters.create_character(player_id, "在線角色", "m")
    row = characters.create_character(player_id, "第二角色", "m")

    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(f"/api/admin/characters/{row['id']}/money", json={"amount": 250}, headers=headers).status_code == 200
    assert client.post(f"/api/admin/characters/{row['id']}/experience", json={"base_exp": 40, "job_exp": 12}, headers=headers).status_code == 200
    got = characters.get_character(row["id"])
    assert got["zeny"] == 250 and got["base_exp"] == 40 and got["job_exp"] == 12

    online = client.get("/api/admin/online-players", headers=headers)
    assert online.status_code == 200
    assert {p["username"] for p in online.json()} == {"gm"}


def test_gm_can_set_bounded_multipliers(client):
    gm_id = _make_account("gm2")
    with connection.get_connection() as conn:
        conn.execute("UPDATE accounts SET role = ? WHERE id = ?", ("GM遊戲管理者", gm_id))
    token = _login(client, "gm2").json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/admin/settings/multipliers",
        json={"experience": 2.0, "drop": 1.5},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"experience": 2.0, "drop": 1.5}
    assert client.put("/api/admin/settings/multipliers", json={"experience": 0, "drop": 1}, headers=headers).status_code == 422


def test_me_reports_gm_flag(client):
    _make_account("plain")
    plain_token = _login(client, "plain").json()["token"]
    resp = client.get("/api/me", headers={"Authorization": f"Bearer {plain_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "plain"
    assert body["role"] == "player"
    assert body["is_gm"] is False

    _make_gm("bighand")
    gm_token = _login(client, "bighand").json()["token"]
    gm_body = client.get("/api/me", headers={"Authorization": f"Bearer {gm_token}"}).json()
    assert gm_body["is_gm"] is True
    assert gm_body["role"] == "GM遊戲管理者"


def test_me_requires_auth(client):
    assert client.get("/api/me").status_code == 401


def test_gm_can_set_hunt_settings(client):
    _make_account("plainhunt")
    plain_token = _login(client, "plainhunt").json()["token"]
    assert client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 30, "huntable_win_rate": 0.7},
        headers={"Authorization": f"Bearer {plain_token}"},
    ).status_code == 403

    _make_gm("gmhunt")
    headers = {"Authorization": f"Bearer {_login(client, 'gmhunt').json()['token']}"}
    resp = client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 30, "huntable_win_rate": 0.7},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"settle_floor_seconds": 30.0, "huntable_win_rate": 0.7}

    with connection.get_connection() as conn:
        rows = dict(
            conn.execute(
                "SELECT key, value FROM server_settings WHERE key IN ('settle_floor_seconds', 'huntable_win_rate')"
            ).fetchall()
        )
    assert rows == {"settle_floor_seconds": "30.0", "huntable_win_rate": "0.7"}

    cfg = HuntConfig.from_settings(get_settings())
    assert cfg.settle_floor_seconds == 30.0
    assert cfg.huntable_win_rate == 0.7


def test_hunt_settings_bounds(client):
    _make_gm("gmbounds")
    headers = {"Authorization": f"Bearer {_login(client, 'gmbounds').json()['token']}"}
    assert client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 30, "huntable_win_rate": 1.5},
        headers=headers,
    ).status_code == 422
    assert client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 0.5, "huntable_win_rate": 0.6},
        headers=headers,
    ).status_code == 422


def test_get_server_settings_defaults_then_updates(client):
    _make_gm("gmget")
    headers = {"Authorization": f"Bearer {_login(client, 'gmget').json()['token']}"}

    assert client.get("/api/admin/settings", headers=headers).json() == {
        "experience_multiplier": 1.0,
        "drop_multiplier": 1.0,
        "settle_floor_seconds": 15.0,
        "huntable_win_rate": 0.6,
    }

    client.put("/api/admin/settings/multipliers", json={"experience": 3.0, "drop": 2.0}, headers=headers)
    client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 45, "huntable_win_rate": 0.55},
        headers=headers,
    )
    assert client.get("/api/admin/settings", headers=headers).json() == {
        "experience_multiplier": 3.0,
        "drop_multiplier": 2.0,
        "settle_floor_seconds": 45.0,
        "huntable_win_rate": 0.55,
    }
