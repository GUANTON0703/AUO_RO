def test_hunt_strategy_can_be_saved_and_read(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "策略王"}).json()
    body = {
        "include_monsters": ["poring"], "exclude_monsters": ["boss"],
        "flee_on_boss": True, "auto_potion": True,
        "potion_item_id": "red_potion", "buy_potions": True,
        "sell_items": True,
    }
    response = client.put(f"/api/hunt/strategy/{ch['id']}", headers=headers, json=body)
    assert response.status_code == 200
    assert client.get(f"/api/hunt/strategy/{ch['id']}", headers=headers).json() == body


def test_hunt_start_rejects_monster_not_in_map(client, auth, db_helpers):
    _, headers, _ = auth
    client.post("/api/characters", headers=headers, json={"name": "排除王"}).json()
    response = client.post("/api/hunt/start", headers=headers,
                           json={"map_id": "prontera_south_field",
                                 "monster_ids": ["poring"]})
    assert response.status_code == 400


def test_auto_mode_respects_exclude_list(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _strong_char(client, headers, db_helpers)
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=headers,
               json={"include_monsters": [], "exclude_monsters": ["green_cotton_worm"],
                     "flee_on_boss": True, "auto_potion": True,
                     "potion_item_id": None, "buy_potions": False, "sell_items": False})
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=20)
    seen = set()
    for _ in range(6):
        seen.add(client.get("/api/hunt/status", headers=headers).json()["monster_id"])
        db_helpers.rewind_hunt(ch["id"], seconds=20)
    assert "green_cotton_worm" not in seen


def _strong_char(client, headers, db_helpers):
    ch = client.post("/api/characters", headers=headers, json={"name": "壯漢"}).json()
    db_helpers.set_base_level(ch["id"], 20)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    return ch
