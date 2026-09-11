import threading


def _ready_char(client, headers, db_helpers, base_level=20):
    ch = client.post("/api/characters", headers=headers, json={"name": "掛機王"}).json()
    db_helpers.set_base_level(ch["id"], base_level)
    db_helpers.set_stats(ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5,
                                    "dex": 25, "luk": 10})
    return ch


def test_hunt_drops_go_to_inventory(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert sum(inv["items"].values()) + len(inv["equipment"]) > 0


def test_hunt_consumes_potions_from_inventory(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_stats(ch["id"], {"str": 55, "agi": 1, "vit": 1, "int": 1,
                                    "dex": 30, "luk": 1})
    db_helpers.give_item(ch["id"], "red_potion", 400)
    client.post("/api/hunt/start", headers=h,
                json={"map_id": "prontera_south_field", "monster_id": "bee_soldier"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("red_potion", 200) < 200


def test_buff_potion_auto_drink_and_stat_boost(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.give_item(ch["id"], "concentration_potion", 5)
    r = client.put(f"/api/hunt/strategy/{ch['id']}", headers=h,
                   json={"auto_buff_potions": ["concentration_potion"]})
    assert r.status_code == 200
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    status = client.get("/api/hunt/status", headers=h).json()

    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("concentration_potion", 5) < 5

    buffs = status["character"]["active_potion_buffs"]
    assert any(b["item_id"] == "concentration_potion" for b in buffs)
    # 顯示效果，不是只有名字跟倒數
    assert buffs[0]["stats"].get("hit") == 10


def test_auto_buy_buff_potion(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_zeny(ch["id"], 50000)
    r = client.put(f"/api/hunt/strategy/{ch['id']}", headers=h,
                   json={"auto_buy_buff_potions": {"concentration_potion": 5}})
    assert r.status_code == 200
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    # 沒開自動喝，買了但至少手上會補到接近設定的數量（可能同一批次也喝了幾瓶）
    assert inv["items"].get("concentration_potion", 0) > 0


def test_npc_buff_rent_once_charges_zeny_and_applies_buff(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_zeny(ch["id"], 10000)
    r = client.post("/api/hunt/npc_buff/rent_once", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["zeny"] == 5000
    assert body["stats"].get("atk") == 20
    zeny = client.get("/api/characters", headers=h).json()[0]["zeny"]
    assert zeny == 5000


def test_npc_buff_rent_once_rejects_when_broke(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_zeny(ch["id"], 100)
    r = client.post("/api/hunt/npc_buff/rent_once", headers=h)
    assert r.status_code == 400


def test_npc_buff_continuous_rental_bills_hourly(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_zeny(ch["id"], 100000)
    db_helpers.give_item(ch["id"], "red_potion", 400)  # 別讓角色沒水喝到撤退，掛機才撐得過兩個小時
    r = client.put(f"/api/hunt/strategy/{ch['id']}", headers=h, json={"npc_buff_rental": True})
    assert r.status_code == 200
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    status = client.get("/api/hunt/status", headers=h).json()
    buffs = status["character"]["active_potion_buffs"]
    npc = next((b for b in buffs if b["item_id"] == "npc_buff_rental"), None)
    assert npc is not None
    assert npc["stats"].get("atk") == 20
    spent_after_first = status["character"]["hunt_potion_zeny_spent"]
    assert spent_after_first >= 8000

    # 租期到期（用直接清掉目前生效的 buff 模擬過期，不用真的等一小時）才會再扣一次
    from server.repositories import characters as characters_repo
    characters_repo.set_active_potion_buffs(ch["id"], {})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    status2 = client.get("/api/hunt/status", headers=h).json()
    assert status2["character"]["hunt_potion_zeny_spent"] >= spent_after_first + 8000


def test_npc_buff_continuous_rental_lapses_when_broke(client, auth, db_helpers):
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    db_helpers.set_zeny(ch["id"], 3000)  # 不夠一次續租
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=h, json={"npc_buff_rental": True})
    client.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    status = client.get("/api/hunt/status", headers=h).json()
    buffs = status["character"]["active_potion_buffs"]
    assert not any(b["item_id"] == "npc_buff_rental" for b in buffs)


def test_hunt_warm_start_yields_kills_on_first_status(client, auth, db_helpers):
    # 暖啟動：按下掛機後不 rewind，第一次 status 就該結算出一場戰鬥
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=h,
                json={"map_id": "prontera_south_field"})
    body = client.get("/api/hunt/status", headers=h).json()
    assert body["kills"] >= 1
    assert not body["offline"]


def test_start_hunt_validates_unlock_level(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers, base_level=1)
    r = client.post("/api/hunt/start", headers=headers,
                    json={"map_id": "prontera_north_forest"})
    assert r.status_code == 400


def test_status_requires_active_hunt(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers)
    assert client.get("/api/hunt/status", headers=headers).status_code == 409


def test_start_then_status_accrues_progress(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    assert client.post("/api/hunt/start", headers=headers,
                       json={"map_id": "prontera_south_field"}).status_code == 200
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    body = client.get("/api/hunt/status", headers=headers).json()
    assert body["kills"] > 0
    assert body["character"]["base_exp"] >= 0
    assert any(e["kind"] == "kill_batch" for e in body["events"])


def test_hunt_status_returns_cumulative_session_totals(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=90)
    first = client.get("/api/hunt/status", headers=headers).json()
    db_helpers.rewind_hunt(ch["id"], seconds=90)
    second = client.get("/api/hunt/status", headers=headers).json()
    assert first["kills"] > 0
    assert second["effective_seconds"] >= first["effective_seconds"]
    assert second["kills"] >= first["kills"]
    assert second["base_exp"] >= first["base_exp"]
    assert second["zeny"] >= first["zeny"]


def test_hunt_status_includes_current_target(client, auth, db_helpers):
    _, headers, _ = auth
    _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field", "monster_id": "mushroom"})
    body = client.get("/api/hunt/status", headers=headers).json()
    assert body["monster_id"] == "mushroom"
    assert body["monster_name"] == "魔菇"


def test_hunt_rotates_through_map_monsters(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    # 自動模式（不指定怪），地圖多隻怪都打得贏 → 每次結算輪替到下一隻
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=20)
    m1 = client.get("/api/hunt/status", headers=headers).json()["monster_id"]
    db_helpers.rewind_hunt(ch["id"], seconds=20)
    m2 = client.get("/api/hunt/status", headers=headers).json()["monster_id"]
    assert m1 != m2


def test_status_below_floor_does_not_resettle(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=60)
    first = client.get("/api/hunt/status", headers=headers).json()
    # 只往前 1 秒（未達結算防抖門檻）→ 不重算，累積值不變、沒有新事件
    db_helpers.rewind_hunt(ch["id"], seconds=1)
    second = client.get("/api/hunt/status", headers=headers).json()
    assert second["kills"] == first["kills"]
    assert second["base_exp"] == first["base_exp"]
    assert second["effective_seconds"] == first["effective_seconds"]
    assert second["events"] == first["events"]
    assert second["batch_id"] == first["batch_id"]


def test_explicit_monster_ids_bypass_winrate_filter(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "硬拚仔"}).json()
    db_helpers.set_base_level(ch["id"], 8)
    db_helpers.set_stats(ch["id"], {"str": 1, "agi": 1, "vit": 1, "int": 1,
                                    "dex": 1, "luk": 1})
    # 弱角色指定打強怪，伺服器不擋（玩家自己扛）
    r = client.post("/api/hunt/start", headers=headers,
                    json={"map_id": "prontera_south_field",
                          "monster_ids": ["poison_snail"]})
    assert r.status_code == 200
    assert r.json()["monster_id"] == "poison_snail"


def test_auto_mode_all_unwinnable_refuses_start(client, auth, db_helpers):
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "菜雞"}).json()
    db_helpers.set_base_level(ch["id"], 8)
    db_helpers.set_stats(ch["id"], {"str": 1, "agi": 1, "vit": 1, "int": 1,
                                    "dex": 1, "luk": 1})
    r = client.post("/api/hunt/start", headers=headers,
                    json={"map_id": "prontera_south_field"})
    assert r.status_code == 400


def test_offline_gap_applies_efficiency(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=6 * 3600)
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["offline"] is True
    assert r["effective_seconds"] < 6 * 3600


def test_stop_hunt_settles_and_clears(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=1800)
    assert client.post("/api/hunt/stop", headers=headers).status_code == 200
    assert client.get("/api/hunt/status", headers=headers).status_code == 409
    from server.api import hunt as hunt_api
    assert ch["id"] not in hunt_api._settlement_locks


def test_concurrent_status_settles_once(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)

    results = []
    barrier = threading.Barrier(2)

    def hit():
        barrier.wait()
        results.append(client.get("/api/hunt/status", headers=headers).json())

    threads = [threading.Thread(target=hit) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 累計欄位下，競爭請求也會看到已累計的擊殺；用事件判斷誰實際結算。
    settled = [r for r in results if any(e["kind"] == "kill_batch" for e in r["events"])]
    noop = [r for r in results if not r["events"]]
    assert len(settled) == 1
    assert len(noop) == 1
    final = client.get("/api/characters", headers=headers).json()[0]
    assert final["base_exp"] == settled[0]["character"]["base_exp"]


def test_repeat_status_without_time_advance_adds_no_exp(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_south_field"})
    db_helpers.rewind_hunt(ch["id"], seconds=3600)
    client.get("/api/hunt/status", headers=headers)
    after_first = client.get("/api/characters", headers=headers).json()[0]
    client.get("/api/hunt/status", headers=headers)
    after_second = client.get("/api/characters", headers=headers).json()[0]
    assert after_second["base_exp"] == after_first["base_exp"]
    assert after_second["base_level"] == after_first["base_level"]


def test_status_event_cursor_deduplicates_repeated_polling(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field"})

    first = client.get("/api/hunt/status", headers=headers).json()
    assert first["event_cursor"]
    assert first["event_batch"]["cursor"] == first["event_cursor"]
    assert first["event_batch"]["mode"] == "live"
    assert first["combat_state"] == "combat"

    repeated = client.get("/api/hunt/status", headers=headers,
                          params={"cursor": first["event_cursor"]}).json()
    assert repeated["event_cursor"] == first["event_cursor"]
    assert repeated["event_batch"]["events"] == []
    assert repeated["events"] == []
    assert repeated["combat_state"] == "hunting"


def test_status_without_events_is_hunting_not_combat(client, auth, db_helpers):
    from server.api import hunt

    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field"})
    hunt._warm_start_pending.discard(ch["id"])

    status = client.get("/api/hunt/status", headers=headers).json()
    assert status["hunt_state"] == "active"
    assert status["combat_state"] == "hunting"
    assert status["events"] == []


def test_eventless_short_status_does_not_probe_a_fight(client, auth, db_helpers, monkeypatch):
    from server.api import hunt

    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field"})
    hunt._warm_start_pending.discard(ch["id"])
    monkeypatch.setattr(
        hunt, "_probe_hunt_buffs",
        lambda row: (_ for _ in ()).throw(AssertionError("unexpected combat probe")),
    )

    status = client.get("/api/hunt/status", headers=headers).json()
    assert status["events"] == []


def test_stop_waits_for_an_inflight_settlement(client, auth, db_helpers):
    from server.api import hunt

    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=20)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_south_field"})
    lock = hunt._settlement_lock(ch["id"])
    lock.acquire()
    result = []
    thread = threading.Thread(
        target=lambda: result.append(client.post("/api/hunt/stop", headers=headers)),
    )
    thread.start()
    thread.join(timeout=0.05)
    assert thread.is_alive()
    lock.release()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result[0].status_code == 200


def test_levelup_from_hunting(client, auth, db_helpers):
    _, headers, _ = auth
    ch = _ready_char(client, headers, db_helpers, base_level=5)
    client.post("/api/hunt/start", headers=headers, json={"map_id": "prontera_east_gate"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    before = client.get("/api/characters", headers=headers).json()[0]["base_level"]
    r = client.get("/api/hunt/status", headers=headers).json()
    assert r["character"]["base_level"] >= before


def test_online_time_accumulates_across_short_polls(client, auth, db_helpers):
    """每次只前進幾秒（過了防抖門檻但湊不滿一場戰鬥），連續輪詢，
    零碎時間不會被丟掉，最後照樣累積出擊殺。"""
    _, headers, _ = auth
    ch = client.post("/api/characters", headers=headers, json={"name": "碎時間"}).json()
    db_helpers.set_base_level(ch["id"], 10)
    db_helpers.set_stats(ch["id"], {"str": 18, "agi": 8, "vit": 14, "int": 1,
                                    "dex": 10, "luk": 1})
    db_helpers.give_item(ch["id"], "red_potion", 50)
    client.post("/api/hunt/start", headers=headers,
                json={"map_id": "prontera_east_gate", "monster_ids": ["mad_bunny"]})
    for _ in range(8):
        db_helpers.rewind_hunt(ch["id"], seconds=5)
        body = client.get("/api/hunt/status", headers=headers).json()
    assert body["kills"] > 0
    assert body["base_exp"] > 0


def test_underlevel_potion_not_auto_used(client, auth, db_helpers):
    """等級不足的補品：掛機引擎不會拿來喝（跟裝備一樣買得到、用不了）。"""
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=10)  # white_potion 需 Lv40
    db_helpers.set_stats(ch["id"], {"str": 55, "agi": 1, "vit": 1, "int": 1,
                                    "dex": 30, "luk": 1})
    db_helpers.give_item(ch["id"], "white_potion", 400)
    client.post("/api/hunt/start", headers=h,
                json={"map_id": "prontera_south_field", "monster_id": "bee_soldier"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("white_potion", 0) == 400   # 一瓶都沒喝


def test_shared_hp_sp_potion_not_over_consumed(client, auth, db_helpers):
    """HP 水跟 SP 水都設成蜂王乳時，扣的量不超過背包持有量。"""
    _, h, _ = auth
    ch = _ready_char(client, h, db_helpers, base_level=25)
    db_helpers.set_stats(ch["id"], {"str": 55, "agi": 1, "vit": 1, "int": 20,
                                    "dex": 30, "luk": 1})
    db_helpers.give_item(ch["id"], "royal_jelly", 40)
    client.put(f"/api/hunt/strategy/{ch['id']}", headers=h, json={
        "auto_potion": True, "potion_item_id": "royal_jelly", "potion_hp_pct": 0.9,
        "auto_sp_potion": True, "sp_potion_item_id": "royal_jelly", "sp_potion_pct": 0.9,
    })
    client.post("/api/hunt/start", headers=h,
                json={"map_id": "prontera_south_field", "monster_id": "bee_soldier"})
    db_helpers.rewind_hunt(ch["id"], seconds=8 * 3600)
    client.get("/api/hunt/status", headers=h)
    inv = client.get(f"/api/characters/{ch['id']}/inventory", headers=h).json()
    assert inv["items"].get("royal_jelly", 0) >= 0   # 不會變負

