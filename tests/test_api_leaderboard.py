def test_leaderboard_by_base_level(client, auth, db_helpers):
    _, h, _ = auth
    a = client.post("/api/characters", headers=h, json={"name": "高手"}).json()
    b = client.post("/api/characters", headers=h, json={"name": "菜鳥"}).json()
    db_helpers.set_base_level(a["id"], 40)
    db_helpers.set_base_level(b["id"], 5)
    r = client.get("/api/leaderboard?by=base_level", headers=h)
    assert r.status_code == 200
    rows = r.json()
    names = [x["character_name"] for x in rows]
    assert names.index("高手") < names.index("菜鳥")


def test_leaderboard_by_zeny(client, auth, db_helpers):
    _, h, _ = auth
    a = client.post("/api/characters", headers=h, json={"name": "富翁"}).json()
    db_helpers.set_zeny(a["id"], 999999)
    r = client.get("/api/leaderboard?by=zeny", headers=h)
    assert r.json()[0]["character_name"] == "富翁"


def test_leaderboard_bad_key_400(client, auth):
    _, h, _ = auth
    assert client.get("/api/leaderboard?by=nonsense", headers=h).status_code == 400
