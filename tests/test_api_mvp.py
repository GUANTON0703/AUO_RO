def test_list_mvp_shows_availability(client, auth, db_helpers):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "王殺"}).json()
    r = client.get("/api/mvp", headers=h)
    assert r.status_code == 200
    assert all("available" in m for m in r.json())


def test_list_mvp_includes_mid_late_roster(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "王名冊"})
    rows = client.get("/api/mvp", headers=h).json()
    ids = {row["id"] for row in rows}
    assert {
        "drake", "moonlight_flower", "doppelganger", "orc_lord",
        "stormy_knight", "pharaoh", "dark_lord",
    } <= ids


def test_challenge_sets_cooldown(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "王殺2"}).json()
    db_helpers.set_base_level(ch["id"], 45)
    db_helpers.set_stats(ch["id"], {"str": 60, "agi": 25, "vit": 40, "int": 5, "dex": 40, "luk": 15})
    db_helpers.give_equipment(ch["id"], "bastard_sword_3")
    db_helpers.give_equipment(ch["id"], "full_plate_1")
    for _inst in client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"]:
        client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": _inst["id"]})
    r = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "angel_poring"})
    assert r.status_code == 200
    assert r.json()["outcome"] in ("win", "loss", "fled")
    r2 = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "angel_poring"})
    assert r2.status_code == 400


def test_challenge_unknown_mvp_404(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "x"})
    r = client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "no_such_mvp"})
    assert r.status_code in (400, 404)


def test_mvp_challenge_ignores_hunt_skill_toggles(client, auth, db_helpers):
    """掛機關掉的技能不該影響 MVP 挑戰（那是手動戰鬥，要全套技能）。"""
    import json
    from server.repositories import characters as characters_repo
    from server.api.hunt import _snapshot

    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "MVP哥"}).json()
    characters_repo.set_learned_skills(ch["id"], {"bash": 3, "magnum_break": 3})
    characters_repo.set_hunt_strategy(ch["id"], {"skill_toggles": {"magnum_break": False}})
    row = characters_repo.get_character(ch["id"])
    hunt_snap = _snapshot(row)
    mvp_snap = _snapshot(row, apply_prefs=False)
    assert hunt_snap.skill_toggles == {"magnum_break": False}
    assert mvp_snap.skill_toggles == {}


def test_challenge_cooldown_is_20_minutes(client, auth, db_helpers):
    _, h, _ = auth
    ch = client.post("/api/characters", headers=h, json={"name": "王殺CD"}).json()
    db_helpers.set_base_level(ch["id"], 45)
    db_helpers.set_stats(ch["id"], {"str": 60, "agi": 25, "vit": 40, "int": 5, "dex": 40, "luk": 15})
    db_helpers.give_equipment(ch["id"], "bastard_sword_3")
    db_helpers.give_equipment(ch["id"], "full_plate_1")
    for _inst in client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()["equipment"]:
        client.post(f"/api/characters/{ch['id']}/inventory/equip", headers=h,
                    json={"equipment_instance_id": _inst["id"]})
    client.post("/api/mvp/challenge", headers=h, json={"mvp_id": "angel_poring"})
    row = next(m for m in client.get("/api/mvp", headers=h).json() if m["id"] == "angel_poring")
    assert row["cooldown_minutes"] == 20
    assert 1000 < row["seconds_remaining"] <= 1200   # ~20 分鐘內
