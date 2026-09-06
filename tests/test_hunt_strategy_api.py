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


def test_hunt_start_rejects_excluded_monster(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "排除王"}).json()
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=headers,
               json={"include_monsters": [], "exclude_monsters": ["poring"],
                     "flee_on_boss": True, "auto_potion": True,
                     "potion_item_id": None, "buy_potions": False, "sell_items": False})
    response = client.post("/api/hunt/start", headers=headers,
                           json={"map_id": "prontera_south_field", "monster_id": "poring"})
    assert response.status_code == 400
