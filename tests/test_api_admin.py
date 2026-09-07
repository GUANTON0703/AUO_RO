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
    assert response.json() == {"experience": 2.0, "drop": 1.5, "zeny": 1.0}
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

    from server.settlement.config import HuntConfig
    assert client.get("/api/admin/settings", headers=headers).json() == {
        "experience_multiplier": 1.0,
        "drop_multiplier": 1.0,
        "zeny_multiplier": 1.0,
        "settle_floor_seconds": HuntConfig().settle_floor_seconds,
        "huntable_win_rate": HuntConfig().huntable_win_rate,
    }

    client.put("/api/admin/settings/multipliers",
               json={"experience": 3.0, "drop": 2.0, "zeny": 5.0}, headers=headers)
    client.put(
        "/api/admin/settings/hunt",
        json={"settle_floor_seconds": 45, "huntable_win_rate": 0.55},
        headers=headers,
    )
    assert client.get("/api/admin/settings", headers=headers).json() == {
        "experience_multiplier": 3.0,
        "drop_multiplier": 2.0,
        "zeny_multiplier": 5.0,
        "settle_floor_seconds": 45.0,
        "huntable_win_rate": 0.55,
    }


def test_zeny_multiplier_scales_hunt_income(client, auth, db_helpers):
    _, h, _ = auth
    _make_gm("gmzeny")
    gmh = {"Authorization": f"Bearer {_login(client, 'gmzeny').json()['token']}"}
    client.put("/api/admin/settings/multipliers",
               json={"experience": 1.0, "drop": 1.0, "zeny": 10.0}, headers=gmh)
    ch = client.post("/api/characters", headers=h, json={"name": "金錢王"}).json()
    db_helpers.set_base_level(ch["id"], 20)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=600)
    body = client.get("/api/hunt/status", headers=h).json()
    assert body["kills"] > 0
    # 10x：每殺一隻 zeny 明顯高於基礎值（基礎約 level*1.5+base_exp*0.3）
    assert body["zeny"] > body["kills"] * 30


def test_announcement_set_by_gm_read_by_anyone(client):
    _make_gm("gm_announce")
    player_id = _make_account("plain_reader")
    gm_h = {"Authorization": f"Bearer {_login(client, 'gm_announce').json()['token']}"}
    pl_h = {"Authorization": f"Bearer {_login(client, 'plain_reader').json()['token']}"}

    # 一開始沒有公告
    assert client.get("/api/announcement", headers=pl_h).json()["text"] == ""

    # 一般玩家不能設定公告
    assert client.put("/api/admin/settings/announcement",
                      json={"text": "偷改"}, headers=pl_h).status_code == 403

    # GM 設定後，任何登入帳號都讀得到
    r = client.put("/api/admin/settings/announcement",
                   json={"text": "今晚 8 點雙倍經驗"}, headers=gm_h)
    assert r.status_code == 200
    got = client.get("/api/announcement", headers=pl_h).json()
    assert got["text"] == "今晚 8 點雙倍經驗"
    assert got["updated_at"]

    # 空字串 = 清掉公告
    client.put("/api/admin/settings/announcement", json={"text": ""}, headers=gm_h)
    assert client.get("/api/announcement", headers=pl_h).json()["text"] == ""
