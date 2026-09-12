def test_player_can_query_monster_drops_and_item_details(client, auth):
    _token, h, _account = auth
    ch = client.post("/api/characters", headers=h, json={"name": "查詢者"}).json()
    monster = client.get("/api/content/monsters/poring", headers=h)
    assert monster.status_code == 200
    body = monster.json()
    assert body["name"] == "波利"
    assert body["drops"][0]["item_name"] == "壓縮膠"
    assert body["drops"][0]["rate"] == 0.7
    item = client.get("/api/content/items/red_potion", headers=h)
    assert item.status_code == 200 and item.json()["kind"] == "consumable"


def test_equipment_details_include_player_requirement_state(client, auth, db_helpers):
    _token, h, _account = auth
    ch = client.post("/api/characters", headers=h, json={"name": "查詢者"}).json()
    db_helpers.set_base_level(ch["id"], 1)
    result = client.get("/api/content/equipment/queen_staff", headers=h)
    assert result.status_code == 200
    req = result.json()["requirements"]
    assert req["met"] is False
    assert req["reasons"]


def test_catalog_returns_full_content_pack(client, auth):
    _token, h, _account = auth
    r = client.get("/api/content/catalog", headers=h)
    assert r.status_code == 200
    body = r.json()
    for key in ("maps", "monsters", "items", "equipment", "cards", "jobs", "skills"):
        assert key in body and body[key]
    assert body["maps"]["prontera_east_gate"]["name"]
    assert body["monsters"]["poring"]["name"] == "波利"
    # 屬性表也要跟著出去，前端才能算「這隻怪怕什麼屬性」
    assert body["element_chart"]["fire"]["earth"] == 1.5
