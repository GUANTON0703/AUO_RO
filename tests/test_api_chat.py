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
