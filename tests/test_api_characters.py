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
