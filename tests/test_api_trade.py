def _two_accounts(client):
    from server.auth import invites
    out = []
    for name in ("alice", "bob"):
        c = invites.create_invite()
        client.post("/api/accounts", json={"invite_code": c, "username": name, "password": "password123"})
        tok = client.post("/api/sessions", json={"username": name, "password": "password123"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        client.post("/api/characters", headers=h, json={"name": name.upper()})
        out.append(h)
    return out


def test_full_trade_swaps_items(client, db_helpers):
    ha, hb = _two_accounts(client)
    a_char = client.get("/api/characters", headers=ha).json()[0]
    b_char = client.get("/api/characters", headers=hb).json()[0]
    db_helpers.give_item(a_char["id"], "jellopy", 10)
    db_helpers.give_item(b_char["id"], "clover", 5)

    tid = client.post("/api/trade/offer", headers=ha, json={"to_username": "bob"}).json()["trade_id"]
    client.post(f"/api/trade/{tid}/put", headers=ha, json={"item_id": "jellopy", "qty": 6})
    client.post(f"/api/trade/{tid}/put", headers=hb, json={"item_id": "clover", "qty": 3})
    client.post(f"/api/trade/{tid}/confirm", headers=ha)
    r = client.post(f"/api/trade/{tid}/confirm", headers=hb)
    assert r.json()["status"] == "done"

    a_inv = client.get(f"/api/characters/{a_char['id']}/inventory", headers=ha).json()["items"]
    b_inv = client.get(f"/api/characters/{b_char['id']}/inventory", headers=hb).json()["items"]
    assert a_inv["jellopy"] == 4 and a_inv["clover"] == 3
    assert b_inv["clover"] == 2 and b_inv["jellopy"] == 6


def test_changing_table_voids_confirm(client, db_helpers):
    ha, hb = _two_accounts(client)
    a_char = client.get("/api/characters", headers=ha).json()[0]
    db_helpers.give_item(a_char["id"], "jellopy", 10)
    tid = client.post("/api/trade/offer", headers=ha, json={"to_username": "bob"}).json()["trade_id"]
    client.post(f"/api/trade/{tid}/put", headers=ha, json={"item_id": "jellopy", "qty": 5})
    client.post(f"/api/trade/{tid}/confirm", headers=hb)
    client.post(f"/api/trade/{tid}/put", headers=ha, json={"item_id": "jellopy", "qty": 8})
    r = client.post(f"/api/trade/{tid}/confirm", headers=ha)
    assert r.json()["status"] == "open"


def test_cannot_put_more_than_owned(client, db_helpers):
    ha, hb = _two_accounts(client)
    a_char = client.get("/api/characters", headers=ha).json()[0]
    db_helpers.give_item(a_char["id"], "jellopy", 2)
    tid = client.post("/api/trade/offer", headers=ha, json={"to_username": "bob"}).json()["trade_id"]
    r = client.post(f"/api/trade/{tid}/put", headers=ha, json={"item_id": "jellopy", "qty": 99})
    assert r.status_code == 400
