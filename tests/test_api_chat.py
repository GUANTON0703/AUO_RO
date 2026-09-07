def test_send_and_read_world_chat(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "話癆"})
    assert client.post("/api/chat", headers=h,
                       json={"channel": "world", "text": "安安"}).status_code == 200
    msgs = client.get("/api/chat?channel=world&after=0", headers=h).json()
    assert any(m["text"] == "安安" and m["character_name"] == "話癆" for m in msgs)


def test_chat_after_filters(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "n"})
    client.post("/api/chat", headers=h, json={"channel": "world", "text": "一"})
    first = client.get("/api/chat?channel=world&after=0", headers=h).json()
    last_id = first[-1]["id"]
    client.post("/api/chat", headers=h, json={"channel": "world", "text": "二"})
    newer = client.get(f"/api/chat?channel=world&after={last_id}", headers=h).json()
    assert [m["text"] for m in newer] == ["二"]


def test_chat_rejects_too_long(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "n"})
    r = client.post("/api/chat", headers=h, json={"channel": "world", "text": "x" * 500})
    assert r.status_code == 422

def test_chat_recent_returns_tail_in_order(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "刷頻"})
    for i in range(8):
        client.post("/api/chat", headers=h, json={"channel": "world", "text": str(i)})
    recent = client.get("/api/chat?channel=world&recent=3", headers=h).json()
    assert [m["text"] for m in recent] == ["5", "6", "7"]


def _second_account(client):
    from server.auth import invites
    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": "bob", "password": "password123"})
    body = client.post("/api/sessions", json={"username": "bob", "password": "password123"}).json()
    return {"Authorization": f"Bearer {body['token']}"}, body["account_id"]


def test_whisper_delivers_to_both_and_lists_thread(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "愛麗絲"})
    bh, _ = _second_account(client)
    client.post("/api/characters", headers=bh, json={"name": "鮑伯"})

    r = client.post("/api/chat/whisper", headers=h, json={"to_name": "鮑伯", "text": "在嗎"})
    assert r.status_code == 200
    channel = r.json()["channel"]
    assert channel.startswith("dm:")

    # 收件人讀得到
    got = client.get(f"/api/chat?channel={channel}&after=0", headers=bh).json()
    assert [m["text"] for m in got] == ["在嗎"]
    # 回覆
    client.post("/api/chat/whisper", headers=bh, json={"to_name": "愛麗絲", "text": "在"})

    # 雙方的 threads 都看得到這條對話
    a_threads = client.get("/api/chat/threads", headers=h).json()
    assert a_threads and a_threads[0]["other_name"] == "鮑伯"
    assert a_threads[0]["last_text"] == "在"
    b_threads = client.get("/api/chat/threads", headers=bh).json()
    assert b_threads[0]["other_name"] == "愛麗絲"


def test_non_canonical_dm_channel_rejected(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "阿甲"})
    bh, _ = _second_account(client)
    client.post("/api/characters", headers=bh, json={"name": "阿乙"})
    ch = client.post("/api/chat/whisper", headers=h, json={"to_name": "阿乙", "text": "hi"}).json()["channel"]
    lo, hi = ch.split(":")[1:]
    swapped = f"dm:{hi}:{lo}"
    assert client.get(f"/api/chat?channel={swapped}&after=0", headers=h).status_code == 400
    # 指向不存在帳號
    assert client.get("/api/chat?channel=dm:1:999999&after=0", headers=h).status_code in (403, 404)


def test_whisper_unknown_target_404(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "找無人"})
    assert client.post("/api/chat/whisper", headers=h,
                       json={"to_name": "查無此人", "text": "hi"}).status_code == 404


def test_cannot_read_others_dm_channel(client, auth):
    _, h, _ = auth
    client.post("/api/characters", headers=h, json={"name": "甲"})
    bh, _ = _second_account(client)
    client.post("/api/characters", headers=bh, json={"name": "乙"})
    ch = client.post("/api/chat/whisper", headers=h, json={"to_name": "乙", "text": "秘密"}).json()["channel"]

    ch_h, _ = _second_account_named(client, "carol")
    r = client.get(f"/api/chat?channel={ch}&after=0", headers=ch_h)
    assert r.status_code == 403


def _second_account_named(client, username):
    from server.auth import invites
    code = invites.create_invite()
    client.post("/api/accounts", json={"invite_code": code, "username": username, "password": "password123"})
    body = client.post("/api/sessions", json={"username": username, "password": "password123"}).json()
    client.post("/api/characters", headers={"Authorization": f"Bearer {body['token']}"}, json={"name": username + "角"})
    return {"Authorization": f"Bearer {body['token']}"}, body["account_id"]
