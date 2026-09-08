def test_hunt_strategy_can_be_saved_and_read(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "策略王"}).json()
    body = {
        "include_monsters": ["poring"], "exclude_monsters": ["boss"],
        "flee_on_boss": True, "auto_potion": True,
        "potion_item_id": "red_potion", "potion_hp_pct": 0.4,
        "auto_buy_potion": True, "buy_potion_id": "red_potion",
        "buy_potion_upto": 30, "sell_item_ids": ["jellopy"],
        "skill_min_sp_pct": 0.3,
    }
    response = client.put(f"/api/hunt/strategy/{ch['id']}", headers=headers, json=body)
    assert response.status_code == 200
    assert client.get(f"/api/hunt/strategy/{ch['id']}", headers=headers).json() == body


def test_hunt_strategy_survives_restart(client, auth, db_helpers):
    from server.repositories import characters as characters_repo

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "重啟王"}).json()
    body = {
        "include_monsters": ["poring", "lunatic"], "exclude_monsters": ["boss"],
        "flee_on_boss": False, "auto_potion": True,
        "potion_item_id": "red_potion", "potion_hp_pct": 0.35,
        "auto_buy_potion": True, "buy_potion_id": "red_potion",
        "buy_potion_upto": 50, "sell_item_ids": ["jellopy"],
        "skill_min_sp_pct": 0.2,
    }
    assert client.put(f"/api/hunt/strategy/{ch['id']}", headers=headers, json=body).status_code == 200
    # 策略進了 DB（模擬重啟：記憶體沒有任何暫存，直接查資料表）
    assert characters_repo.get_hunt_strategy(ch["id"]) == body
    assert client.get(f"/api/hunt/strategy/{ch['id']}", headers=headers).json() == body


def test_hunt_strategy_load_ignores_unknown_keys(client, auth, db_helpers):
    from server.repositories import characters as characters_repo
    from server.api.hunt import _load_strategy

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "未知欄"}).json()
    characters_repo.set_hunt_strategy(ch["id"], {"flee_on_boss": False, "legacy_field": 123})
    strategy = _load_strategy(ch["id"])
    assert strategy.flee_on_boss is False
    assert not hasattr(strategy, "legacy_field")


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
                     "flee_on_boss": True, "auto_potion": True, "potion_item_id": None})
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


def test_auto_sell_converts_drops_to_zeny(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "自動賣"}).json()
    db_helpers.set_base_level(ch["id"], 20)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=h,
               json={"sell_item_ids": ["jellopy", "sticky_mucus", "fluff",
                                       "feather", "clover"]})
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_east_gate"})
    z0 = client.get("/api/characters", headers=h).json()[0]["zeny"]
    db_helpers.rewind_hunt(ch["id"], seconds=600)
    body = client.get("/api/hunt/status", headers=h).json()
    z1 = client.get("/api/characters", headers=h).json()[0]["zeny"]
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert body["kills"] > 0
    assert body.get("sold", 0) > 0          # 有賣出
    assert z1 - z0 > body["zeny"] - body.get("sold", 0)  # 總 zeny 含賣出所得
    # 被列入自動賣的道具背包不會留
    for iid in ("jellopy", "fluff"):
        assert inv["items"].get(iid, 0) == 0


def test_potion_hp_pct_and_auto_buy(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "自動買水"}).json()
    db_helpers.set_base_level(ch["id"], 12)
    db_helpers.set_stats(ch["id"], {"str": 20, "agi": 8, "vit": 16, "int": 1,
                                    "dex": 12, "luk": 1})
    db_helpers.set_zeny(ch["id"], 100000)
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=h,
               json={"auto_potion": True, "potion_hp_pct": 0.6,
                     "auto_buy_potion": True, "buy_potion_id": "red_potion",
                     "buy_potion_upto": 200})
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=1800)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    # 自動買水補過貨（起始 10 瓶，掛機途中會補到接近 200）
    assert inv["items"].get("red_potion", 0) > 50
