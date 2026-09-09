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


def test_equip_allows_parent_job_gear(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.set_job(ch["id"], "knight")
    db_helpers.set_base_level(ch["id"], 30)
    db_helpers.give_equipment(ch["id"], "guardian_greatsword")
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 200
    assert _equip_list(client, ch, h)[0]["equipped_slot"] == "weapon"


def test_equip_still_rejects_unrelated_job(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.set_job(ch["id"], "mage")
    db_helpers.set_base_level(ch["id"], 30)
    db_helpers.give_equipment(ch["id"], "guardian_greatsword")
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


def test_accessory_fills_two_slots(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "clip")
    db_helpers.give_equipment(ch["id"], "clip")
    a, b = _equip_list(client, ch, h)
    for inst in (a, b):
        client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    slots = sorted(e["equipped_slot"] for e in _equip_list(client, ch, h))
    assert slots == ["accessory1", "accessory2"]


def test_third_accessory_replaces_left(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    for _ in range(3):
        db_helpers.give_equipment(ch["id"], "clip")
    a, b, c = _equip_list(client, ch, h)
    for inst in (a, b, c):
        client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    equipped = {e["id"]: e["equipped_slot"] for e in _equip_list(client, ch, h)
               if e["equipped_slot"]}
    assert set(equipped.values()) == {"accessory1", "accessory2"}
    assert equipped[c["id"]] == "accessory1"       # 第三個換掉左格
    assert a["id"] not in equipped                 # 原左格被卸下


def test_unequip_accessory_by_slot(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "clip")
    inst = _equip_list(client, ch, h)[0]
    client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                json={"equipment_instance_id": inst["id"]})
    client.post(f"/api/characters/{ch['id']}/inventory/unequip", headers=h,
                json={"slot": "accessory1"})
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
    assert r.json()["mode"] == "normal" and r.json()["increment"] == 1
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"]["oridecon"] == 9


def test_refine_random_mode_uses_increment_and_keeps_costs(client, auth, db_helpers, monkeypatch):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    db_helpers.give_item(ch["id"], "oridecon", 2)
    db_helpers.set_zeny(ch["id"], 99999)
    inst = _equip_list(client, ch, h)[0]

    class FixedRng:
        def random(self):
            return 0.99

    import server.api.inventory as inventory_api
    monkeypatch.setattr(inventory_api.random, "Random", FixedRng)
    r = client.post(f"/api/characters/{ch['id']}/inventory/refine", headers=h,
                    json={"equipment_instance_id": inst["id"], "mode": "random"})

    assert r.status_code == 200
    assert r.json()["mode"] == "random"
    assert r.json()["increment"] == 3
    assert r.json()["success"] is True and r.json()["refine"] == 3
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"]["oridecon"] == 1


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


def test_refine_missing_ore_message_uses_item_name(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_equipment(ch["id"], "knife")
    inst = _equip_list(client, ch, h)[0]
    r = client.post(f"/api/characters/{ch['id']}/inventory/refine", headers=h,
                    json={"equipment_instance_id": inst["id"]})
    assert r.status_code == 400
    assert "神之金屬" in r.json()["detail"]   # 台版官方名，不是 "oridecon"


def test_assassin_can_use_slotted_katar():
    from server.content import load_content
    c = load_content()
    anc = c.job_ancestry("assassin")
    for kid in ("jur", "jur_3", "jur_4"):
        e = c.equipment[kid]
        assert set(e.job_ids) & anc, kid
