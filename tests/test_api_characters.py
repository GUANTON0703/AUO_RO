def test_list_empty(client, auth):
    _, headers, _ = auth
    resp = client.get("/api/characters", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_character(client, auth):
    _, headers, _ = auth
    resp = client.post("/api/characters", headers=headers, json={"name": "小勇者"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "小勇者"
    assert body["job_id"] == "novice"
    assert body["base_level"] == 1
    assert body["location_map"] == "prontera_east_gate"


def test_create_requires_auth(client):
    resp = client.post("/api/characters", json={"name": "無權"})
    assert resp.status_code == 401


def test_three_character_limit(client, auth):
    _, headers, _ = auth
    for n in ["一", "二", "三"]:
        assert client.post("/api/characters", headers=headers, json={"name": n}).status_code == 201
    resp = client.post("/api/characters", headers=headers, json={"name": "四"})
    assert resp.status_code == 409
    assert "上限" in resp.json()["detail"]


def test_duplicate_name_across_accounts(client, auth, invite_code):
    _, headers, _ = auth
    client.post("/api/characters", headers=headers, json={"name": "撞名"})

    from server.auth import invites

    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "second", "password": "password123"})
    tok = client.post("/api/sessions", json={"username": "second", "password": "password123"}).json()["token"]
    resp = client.post(
        "/api/characters", headers={"Authorization": f"Bearer {tok}"}, json={"name": "撞名"}
    )
    assert resp.status_code == 409


def test_delete_own_character(client, auth):
    _, headers, _ = auth
    cid = client.post("/api/characters", headers=headers, json={"name": "刪除對象"}).json()["id"]
    assert client.delete(f"/api/characters/{cid}", headers=headers).status_code == 204
    assert client.get("/api/characters", headers=headers).json() == []


def test_cannot_delete_others_character(client, auth):
    _, headers, _ = auth
    cid = client.post("/api/characters", headers=headers, json={"name": "受害者"}).json()["id"]

    from server.auth import invites

    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "attacker", "password": "password123"})
    tok = client.post("/api/sessions", json={"username": "attacker", "password": "password123"}).json()["token"]
    resp = client.delete(f"/api/characters/{cid}", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 404


def test_logout_then_use_token_fails(client, auth):
    token, headers, _ = auth
    client.delete("/api/sessions", headers=headers)
    assert client.get("/api/characters", headers=headers).status_code == 401


def test_new_character_has_starter_kit(client, auth):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "新兵"}).json()
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=headers).json()
    assert inv["items"].get("red_potion", 0) > 0
    assert len(inv["equipment"]) >= 1


def test_new_character_has_zero_skill_points(client, auth):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "菜鳥"}).json()
    assert ch["skill_points"] == 0
    listed = client.get("/api/characters", headers=headers).json()[0]
    assert listed["skill_points"] == 0


def test_skill_points_track_job_level(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "練功"}).json()
    db_helpers.set_job_level(ch["id"], 8)
    listed = client.get("/api/characters", headers=headers).json()[0]
    assert listed["skill_points"] == 7


def test_skill_points_drop_after_learning(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "劍士"}).json()
    db_helpers.set_job(ch["id"], "swordman", 10, 0)
    before = client.get("/api/characters", headers=headers).json()[0]["skill_points"]
    client.post(f"/api/characters/{ch['id']}/skills", headers=headers,
                json={"skill_id": "bash", "level": 3})
    after = client.get("/api/characters", headers=headers).json()[0]["skill_points"]
    assert after == before - 3


def test_stat_points_reflect_earned_minus_spent(client, auth, db_helpers):
    from server.progression.stats import points_spent, total_earned_stat_points

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "壯漢"}).json()
    db_helpers.set_base_level(ch["id"], 20)
    listed = client.get("/api/characters", headers=headers).json()[0]
    starting = {k: 1 for k in ("str", "agi", "vit", "int", "dex", "luk")}
    assert listed["stat_points"] == total_earned_stat_points(20) - points_spent(starting)


def test_list_characters_works_for_second_job(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "刺客大人"}).json()
    db_helpers.set_job(ch["id"], "assassin", 20, 0)
    r = client.get("/api/characters", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()[0]["job_id"] == "assassin"


def test_sheet_reflects_active_potion_buffs(client, auth, db_helpers):
    """喝下去的 buff 藥/NPC 代喝，數值面板（/sheet）要能看到差異，不能只有掛機結算內部折算。"""
    from server.repositories import characters as characters_repo

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "數值面板王"}).json()
    baseline = client.get(f"/api/characters/{ch['id']}/sheet", headers=headers).json()

    from datetime import datetime, timedelta, timezone
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=180)
    characters_repo.set_active_potion_buffs(ch["id"], {
        "concentration_potion": {"expires_at": expires_at.isoformat(), "stats": {"hit": 10, "crit": 5}},
    })

    buffed = client.get(f"/api/characters/{ch['id']}/sheet", headers=headers).json()
    assert buffed["hit"] == baseline["hit"] + 10
    assert buffed["crit"] == baseline["crit"] + 5


def test_sheet_ignores_expired_buffs(client, auth, db_helpers):
    from server.repositories import characters as characters_repo

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "過期不算"}).json()
    baseline = client.get(f"/api/characters/{ch['id']}/sheet", headers=headers).json()

    from datetime import datetime, timedelta, timezone
    expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    characters_repo.set_active_potion_buffs(ch["id"], {
        "concentration_potion": {"expires_at": expired_at.isoformat(), "stats": {"hit": 10}},
    })

    sheet = client.get(f"/api/characters/{ch['id']}/sheet", headers=headers).json()
    assert sheet["hit"] == baseline["hit"]


def test_new_character_becomes_active_and_shop_uses_it(client, auth, db_helpers):
    """建立多個角色時，最新建立的那個要變成「目前在玩」，掛機/商店等端點才會作用在它身上。"""
    _, headers, _ = auth
    first = client.post("/api/characters", headers=headers, json={"name": "老大"}).json()
    second = client.post("/api/characters", headers=headers, json={"name": "小弟"}).json()

    chars = client.get("/api/characters", headers=headers).json()
    active = next(c for c in chars if c["is_active"])
    assert active["id"] == second["id"]
    assert not next(c for c in chars if c["id"] == first["id"])["is_active"]

    db_helpers.set_zeny(second["id"], 500)
    r = client.get("/api/shop", headers=headers)
    assert r.status_code == 200
    # 商店端點作用在目前的角色（小弟），不是最早建立的那個
    buy = client.post("/api/shop/buy", headers=headers, json={"item_id": "red_potion", "qty": 1})
    assert buy.status_code == 200
    inv = client.get(f"/api/characters/{second['id']}/inventory", headers=headers).json()
    assert inv["items"].get("red_potion", 0) > 0


def test_activate_switches_current_character(client, auth, db_helpers):
    _, headers, _ = auth
    first = client.post("/api/characters", headers=headers, json={"name": "阿一"}).json()
    second = client.post("/api/characters", headers=headers, json={"name": "阿二"}).json()

    r = client.post(f"/api/characters/{first['id']}/activate", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is True

    chars = {c["id"]: c for c in client.get("/api/characters", headers=headers).json()}
    assert chars[first["id"]]["is_active"] is True
    assert chars[second["id"]]["is_active"] is False


def test_activate_rejects_character_not_owned(client, auth, invite_code):
    _, headers, _ = auth
    client.post("/api/characters", headers=headers, json={"name": "我方"})

    from server.auth import invites
    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "stranger", "password": "password123"})
    login = client.post("/api/sessions", json={"username": "stranger", "password": "password123"}).json()
    other_headers = {"Authorization": "Bearer " + login["token"]}
    other = client.post("/api/characters", headers=other_headers, json={"name": "別人的"}).json()

    r = client.post(f"/api/characters/{other['id']}/activate", headers=headers)
    assert r.status_code == 404


def test_transfer_zeny_between_own_characters(client, auth, db_helpers):
    _, headers, _ = auth
    first = client.post("/api/characters", headers=headers, json={"name": "轉出方"}).json()
    second = client.post("/api/characters", headers=headers, json={"name": "轉入方"}).json()
    db_helpers.set_zeny(first["id"], 10000)
    db_helpers.set_zeny(second["id"], 0)

    # 目前活躍角色是 second（最後建立的），先切回 first 才能從 first 轉出
    client.post(f"/api/characters/{first['id']}/activate", headers=headers)
    r = client.post("/api/characters/transfer-zeny", headers=headers,
                    json={"to_character_id": second["id"], "amount": 3000})
    assert r.status_code == 200

    chars = {c["id"]: c for c in client.get("/api/characters", headers=headers).json()}
    assert chars[first["id"]]["zeny"] == 7000
    assert chars[second["id"]]["zeny"] == 3000


def test_transfer_zeny_rejects_insufficient_and_other_accounts(client, auth, db_helpers, invite_code):
    _, headers, _ = auth
    mine = client.post("/api/characters", headers=headers, json={"name": "自己人"}).json()
    db_helpers.set_zeny(mine["id"], 100)

    from server.auth import invites
    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "stranger2", "password": "password123"})
    login = client.post("/api/sessions", json={"username": "stranger2", "password": "password123"}).json()
    other_headers = {"Authorization": "Bearer " + login["token"]}
    other = client.post("/api/characters", headers=other_headers, json={"name": "陌生人"}).json()

    # 錢不夠
    r = client.post("/api/characters/transfer-zeny", headers=headers,
                    json={"to_character_id": mine["id"], "amount": 99999})
    assert r.status_code == 400

    # 不能轉給別的帳號的角色（防呆）
    r2 = client.post("/api/characters/transfer-zeny", headers=headers,
                     json={"to_character_id": other["id"], "amount": 10})
    assert r2.status_code == 400
