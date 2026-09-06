def test_list_mvp_shows_availability(client, auth, db_helpers):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "王殺"}).json()
    r = client.get("/api/mvp", headers=h)
    assert r.status_code == 200
    assert all("available" in m for m in r.json())


def test_challenge_sets_cooldown(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "王殺2"}).json()
    db_helpers.set_base_level(ch["id"], 16)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 12, "vit": 20, "int": 5, "dex": 18, "luk": 8})
    r = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "angel_poring"})
    assert r.status_code == 200
    assert r.json()["outcome"] in ("win", "loss", "fled")
    r2 = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "angel_poring"})
    assert r2.status_code == 400


def test_challenge_unknown_mvp_404(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "x"})
    r = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "no_such_mvp"})
    assert r.status_code in (400, 404)
