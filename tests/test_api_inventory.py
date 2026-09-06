def _char(client, headers, db_helpers, lv=20):
    ch = client.post("/api/characters", headers=headers, json={"name": "裝備哥"}).json()
    db_helpers.set_base_level(ch["id"], lv)
    db_helpers.clear_inventory(ch["id"])
    return ch


def _equip_list(client, ch, h):
    return client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"]


def test_get_empty_inventory(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    r = client.get(f"/api/characters/{ch['id']}/inventory", headers=h)
    assert r.status_code == 200
    assert r.json()["items"] == {} and r.json()["equipment"] == []


def test_equip_weapon(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 200
    assert _equip_list(client, ch, h)[0]["equipped_slot"] == "weapon"


def test_equip_swaps_same_slot(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_equipment(ch["id"], "knife")
    a, b = _equip_list(client, ch, h)
    client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                json={"equipment_instance_id": a["id"]})
    client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                json={"equipment_instance_id": b["id"]})
    equipped = [e for e in _equip_list(client, ch, h) if e["equipped_slot"] == "weapon"]
    assert len(equipped) == 1 and equipped[0]["id"] == b["id"]


def test_equip_rejects_wrong_job(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "queen_staff")
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400


def test_equip_rejects_low_level(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers, lv=1)
    db_helpers.give_equipment(ch["id"], "blade")
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400


def test_unequip(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    inst = _equip_list(client, ch, h)[0]
    client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                json={"equipment_instance_id": inst["id"]})
    r = client.post(f"/api/characters/{ch['id']}/inventory/unequip", headers=h,
                    json={"slot": "weapon"})
    assert r.status_code == 200
    assert _equip_list(client, ch, h)[0]["equipped_slot"] is None


def test_socket_card(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "cotton_shirt")
    db_helpers.give_item(ch["id"], "poring_card", 1)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/socket", headers=h,
                    json={"equipment_instance_id": inst["id"], "card_item_id": "poring_card"})
    assert r.status_code == 200
    assert "poring_card" in _equip_list(client, ch, h)[0]["card_ids"]
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("poring_card", 0) == 0


def test_socket_rejects_wrong_slot(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "cotton_shirt")
    db_helpers.give_item(ch["id"], "wolf_card", 1)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/socket", headers=h,
                    json={"equipment_instance_id": inst["id"], "card_item_id": "wolf_card"})
    assert r.status_code == 400


def test_socket_rejects_no_slots(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "leather_gloves")  # card_slots 0
    db_helpers.give_item(ch["id"], "mad_bunny_card", 1)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/socket", headers=h,
                    json={"equipment_instance_id": inst["id"], "card_item_id": "mad_bunny_card"})
    assert r.status_code == 400


def test_refine_safe_level_succeeds(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_item(ch["id"], "oridecon", 10)
    db_helpers.set_zeny(ch["id"], 99999)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/refine", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 200
    assert r.json()["success"] is True and r.json()["refine"] == 1
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"]["oridecon"] == 9


def test_refine_rejects_no_ore(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.set_zeny(ch["id"], 99999)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/refine", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400


def test_refine_rejects_no_zeny(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_item(ch["id"], "oridecon", 10)
    db_helpers.set_zeny(ch["id"], 0)
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/refine", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400


def test_inventory_rejects_other_account(client, auth, db_helpers, invite_code):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    from server.auth import invites
    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "seconduser", "password": "password123"})
    t2 = client.post("/api/sessions", json={"username": "seconduser", "password": "password123"}).json()
    h2 = {"Authorization": f"Bearer {t2['token']}"}
    assert client.get(f"/api/characters/{ch['id']}/inventory", headers=h2).status_code == 404
