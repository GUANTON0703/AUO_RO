def _char(client, h, db_helpers):
    ch = client.post("/api/characters", headers=h, json={"name": "倉管"}).json()
    db_helpers.clear_inventory(ch["id"])
    return ch


def test_deposit_and_withdraw_item(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "jellopy", 30)
    assert client.post("/api/storage/deposit", headers=h,
                       json={"item_id": "jellopy", "qty": 20}).status_code == 200
    st = client.get("/api/storage", headers=h).json()
    assert st["items"]["jellopy"] == 20
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"]["jellopy"] == 10
    client.post("/api/storage/withdraw", headers=h, json={"item_id": "jellopy", "qty": 5})
    assert client.get("/api/storage", headers=h).json()["items"]["jellopy"] == 15


def test_storage_shared_across_characters(client, auth, db_helpers):
    _, h, _ = auth
    a = _char(client, h, db_helpers)
    db_helpers.give_item(a["id"], "clover", 10)
    client.post("/api/storage/deposit", headers=h, json={"item_id": "clover", "qty": 10})
    assert client.get("/api/storage", headers=h).json()["items"]["clover"] == 10


def test_deposit_equipment_instance(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    inst = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"][0]
    r = client.post("/api/storage/deposit", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 200
    assert len(client.get("/api/storage", headers=h).json()["equipment"]) == 1
    assert client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"] == []


def test_deposit_more_than_owned_rejected(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "jellopy", 3)
    r = client.post("/api/storage/deposit", headers=h, json={"item_id": "jellopy", "qty": 99})
    assert r.status_code == 400
