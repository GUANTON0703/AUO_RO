from server.db import connection
from server.repositories import accounts, characters


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
