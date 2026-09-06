import threading


def _ready_char(client, headers, db_helpers, base_level=20):
    ch = client.post("/api/characters", headers=headers, json={"name": "掛機王"}).json()
    db_helpers.set_base_level(ch["id"], base_level)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    return ch


def test_hunt_drops_go_to_inventory(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert sum(inv["items"].values()) + len(inv["equipment"]) > 0


def test_hunt_consumes_potions_from_inventory(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_stats(ch["id"], {"str": 55, "agi": 1, "vit": 1, "int": 1,
                                    "dex": 30, "luk": 1})
    db_helpers.give_item(ch["id"], "red_potion", 400)
    client.post("/api/hunt/start", headers=h,
                json={"map_id": "prontera_south_field", "monster_id": "bee_soldier"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("red_potion", 200) < 200


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


def test_hunt_status_includes_current_target(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field", "monster_id": "mushroom"})
    body = client.get("/api/hunt/status", headers=headers).json()
    assert body["monster_id"] == "mushroom"
    assert body["monster_name"] == "魔菇"


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


def test_concurrent_status_settles_once(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)

    results = []
    barrier = threading.Barrier(2)

    def hit():
        barrier.wait()
        results.append(client.get("/api/hunt/status", headers=headers).json())

    threads = [threading.Thread(target=hit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    settled = [r for r in results if r["kills"] > 0]
    noop = [r for r in results if r["kills"] == 0]
    assert len(settled) == 1
    assert len(noop) == 1
    final = client.get("/api/characters", headers=headers).json()[0]
    assert final["base_exp"] == settled[0]["character"]["base_exp"]


def test_repeat_status_without_time_advance_adds_no_exp(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    client.get("/api/hunt/status", headers=headers)
    after_first = client.get("/api/characters", headers=headers).json()[0]
    client.get("/api/hunt/status", headers=headers)
    after_second = client.get("/api/characters", headers=headers).json()[0]
    assert after_second["base_exp"] == after_first["base_exp"]
    assert after_second["base_level"] == after_first["base_level"]


def test_levelup_from_hunting(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=5)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    before = client.get("/api/characters", headers=headers).json()[0]["base_level"]
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["character"]["base_level"] >= before
