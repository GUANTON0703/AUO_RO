def _ready_char(client, headers, db_helpers, base_level=20):
    ch = client.post("/api/characters", headers=headers, json={"name": "掛機王"}).json()
    db_helpers.set_base_level(ch["id"], base_level)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    return ch


def test_start_hunt_validates_unlock_level(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers, base_level=1)
    r = client.post("/api/hunt/start", headers=headers,
                    json={"map_id": "prontera_north_forest"})
    assert r.status_code == 400


def test_status_requires_active_hunt(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers)
    assert client.get("/api/hunt/status", headers=headers).status_code == 409


def test_start_then_status_accrues_progress(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    assert client.post("/api/hunt/start", headers=headers,
                       json={"map_id": "prontera_south_field"}).status_code == 200
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    body = client.get("/api/hunt/status", headers=headers).json()
    assert body["kills"] > 0
    assert body["character"]["base_exp"] >= 0
    assert any(e["kind"] == "kill_batch" for e in body["events"])


def test_offline_gap_applies_efficiency(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=6 * 3600)
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["offline"] is True
    assert r["effective_seconds"] < 6 * 3600


def test_stop_hunt_settles_and_clears(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=1800)
    assert client.post("/api/hunt/stop", headers=headers).status_code == 200
    assert client.get("/api/hunt/status", headers=headers).status_code == 409


def test_levelup_from_hunting(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=5)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    before = client.get("/api/characters", headers=headers).json()[0]["base_level"]
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["character"]["base_level"] >= before
