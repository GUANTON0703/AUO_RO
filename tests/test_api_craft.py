def _char(client, h, db_helpers):
    ch = client.post("/api/characters", headers=h, json={"name": "煉金師"}).json()
    db_helpers.clear_inventory(ch["id"])
    db_helpers.set_zeny(ch["id"], 5000)
    return ch


def test_craft_lists_recipes_with_success_rate_and_owned_materials(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "jellopy", 3)
    r = client.get("/api/craft", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["craft_level"] == 1
    recipe = next(x for x in body["recipes"] if x["id"] == "recipe_heal_boost_potion")
    assert recipe["success_pct"] == 65  # 製作等級剛好等於門檻，基礎成功率不變
    mat = next(m for m in recipe["materials"] if m["item_id"] == "jellopy")
    assert mat["have"] == 3 and mat["need"] == 5


def test_craft_success_consumes_materials_and_grants_item(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.set_craft_level(ch["id"], 10)  # 拉滿等級 → 成功率封頂 95%，測試才不會隨機失敗
    db_helpers.give_item(ch["id"], "jellopy", 5)
    db_helpers.give_item(ch["id"], "honey", 3)
    db_helpers.give_item(ch["id"], "clover", 1)

    r = client.post("/api/craft/recipe_heal_boost_potion", headers=h, json={"times": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["successes"] == 1
    assert body["produced"] >= 1

    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("jellopy", 0) == 0
    assert inv["items"].get("heal_boost_potion", 0) >= 1
    zeny = client.get("/api/characters", headers=h).json()[0]["zeny"]
    assert zeny == 5000 - 200


def test_craft_rejects_insufficient_materials(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    r = client.post("/api/craft/recipe_heal_boost_potion", headers=h, json={"times": 1})
    assert r.status_code == 400


def test_craft_batch_gains_craft_exp_even_on_failure(client, auth, db_helpers):
    _, h, _ = auth
    ch = _char(client, h, db_helpers)
    db_helpers.give_item(ch["id"], "orc_tooth", 40)
    db_helpers.give_item(ch["id"], "rosary", 20)
    db_helpers.give_item(ch["id"], "nightmare_horn", 20)
    r = client.post("/api/craft/recipe_awakening_potion", headers=h, json={"times": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["attempts"] == 5
    assert body["successes"] + body["fails"] == 5
    assert body["craft_exp"] > 0 or body["craft_level"] > 1
