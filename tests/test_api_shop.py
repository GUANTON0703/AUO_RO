def _char(client, h, db_helpers):
    ch = client.post("/api/characters", headers=h, json={"name": "商人"}).json()
    db_helpers.clear_inventory(ch["id"])
    db_helpers.set_zeny(ch["id"], 5000)
    return ch


def test_shop_lists_buyable(client, auth, db_helpers):
    _, h, _ = auth
    _char(client, h, db_helpers)
    r = client.get("/api/shop", headers=h)
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert "red_potion" in ids
    red_potion = next(i for i in r.json()["items"] if i["id"] == "red_potion")
    assert red_potion["sell_price"] == 25


def test_buy_deducts_zeny_and_adds_item(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    r = client.post("/api/shop/buy", headers=h, json={"item_id": "red_potion", "qty": 10})
    assert r.status_code == 200
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"]["red_potion"] == 10
    assert client.get("/api/characters", headers=h).json()[0]["zeny"] < 5000


def test_buy_rejects_insufficient_zeny(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.set_zeny(ch["id"], 10)
    r = client.post("/api/shop/buy", headers=h, json={"item_id": "blue_potion", "qty": 5})
    assert r.status_code == 400


def test_buy_equipment(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    r = client.post("/api/shop/buy", headers=h, json={"item_id": "knife", "qty": 1})
    assert r.status_code == 200
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert any(e["equipment_id"] == "knife" for e in inv["equipment"])


def test_sell_item_gives_zeny(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "jellopy", 50)
    z0 = client.get("/api/characters", headers=h).json()[0]["zeny"]
    r = client.post("/api/shop/sell", headers=h, json={"item_id": "jellopy", "qty": 50})
    assert r.status_code == 200
    assert client.get("/api/characters", headers=h).json()[0]["zeny"] > z0


def test_sell_equipped_item_rejected(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    inst = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"][0]
    client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                json={"equipment_instance_id": inst["id"]})
    r = client.post("/api/shop/sell", headers=h, json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400


def test_shop_has_varied_heal_potions(client, auth, db_helpers):
    _, h, _ = auth
    _char(client, h, db_helpers)
    items = client.get("/api/shop", headers=h).json()["items"]
    heal_ids = {i["id"] for i in items if i["id"].endswith("_potion")}
    assert {"orange_potion", "white_potion"} <= heal_ids
    # 白藥水回血比紅藥水多
    from server.content import load_content
    c = load_content()
    red = next(e["amount"] for e in c.items["red_potion"].effects if e["type"] == "heal_hp")
    white = next(e["amount"] for e in c.items["white_potion"].effects if e["type"] == "heal_hp")
    assert white > red
    assert c.items["white_potion"].required_level > 1


def test_shop_covers_level_bands_with_healing_potions(client, auth, db_helpers):
    _, h, _ = auth
    _char(client, h, db_helpers)
    from server.content import load_content

    content = load_content()
    shop_ids = {entry["id"] for entry in client.get("/api/shop", headers=h).json()["items"]}
    potions = [item for item in content.items.values()
               if item.id in shop_ids and any(e.get("type") == "heal_hp" for e in item.effects)]
    assert {1, 10, 20, 30, 40, 50} <= {item.required_level for item in potions}
    for lower, upper in ((1, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 60)):
        assert any(lower <= item.required_level <= upper for item in potions), (lower, upper)


def test_shop_has_buyable_common_equipment_for_every_slot(client, auth, db_helpers):
    _, h, _ = auth
    _char(client, h, db_helpers)
    equipment = client.get("/api/shop", headers=h).json()["equipment"]
    slots = {entry["slot"] for entry in equipment}
    assert {"weapon", "offhand", "head", "armor", "garment", "shoes", "accessory"} <= slots

    from server.content import load_content
    content = load_content()
    shop_ids = {entry["id"] for entry in equipment}
    for slot in slots:
        common = [eq for eq in content.equipment.values()
                  if eq.id in shop_ids and eq.slot == slot and eq.rarity == "common"]
        assert common
        assert max(eq.required_level for eq in common) >= 20


def test_sell_equipment_without_npc_sell_still_pays(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "guardian_greatsword")  # 掉落裝，無 npc_sell
    inst = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"][0]
    z0 = client.get("/api/characters", headers=h).json()[0]["zeny"]
    r = client.post("/api/shop/sell", headers=h, json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 200 and r.json()["gained"] > 0
    assert client.get("/api/characters", headers=h).json()[0]["zeny"] > z0


def test_sell_multiple_equipment_ids_credits_the_sum(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    for _ in range(3):
        db_helpers.give_equipment(ch["id"], "knife")
    insts = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"]
    z0 = client.get("/api/characters", headers=h).json()[0]["zeny"]
    ids = [i["id"] for i in insts[:2]]
    r = client.post("/api/shop/sell", headers=h, json={"equipment_instance_ids": ids})
    assert r.status_code == 200 and r.json()["count"] == 2
    assert client.get("/api/characters", headers=h).json()[0]["zeny"] == z0 + r.json()["gained"]
    left = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"]
    assert len(left) == 1


def test_sell_material_without_npc_sell_still_works(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "elunium", 3)   # npc_sell 未設
    r = client.post("/api/shop/sell", headers=h, json={"item_id": "elunium", "qty": 3})
    assert r.status_code == 200 and r.json()["gained"] >= 3


def test_sell_price_helpers():
    from server.content import load_content
    from server.loot.pricing import equip_sell_price, item_sell_price
    c = load_content()
    assert equip_sell_price(c.equipment["guardian_greatsword"]) > 0
    assert item_sell_price(c.items["elunium"]) >= 1
