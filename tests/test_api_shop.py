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
