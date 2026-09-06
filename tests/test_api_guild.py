def test_create_join_leave_guild(client):
    from server.auth import invites
    hs = []
    for name in ("gld1", "gld2", "gld3"):
        c = invites.create_invite()
        client.post("/api/accounts", json={"invite_code": c, "username": name, "password": "password123"})
        tok = client.post("/api/sessions", json={"username": name, "password": "password123"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        client.post("/api/characters", headers=h, json={"name": name.upper()})
        hs.append(h)

    gid = client.post("/api/guild", headers=hs[0], json={"name": "波利獵人團"}).json()["id"]
    assert client.post(f"/api/guild/{gid}/join", headers=hs[1]).status_code == 200
    assert client.post(f"/api/guild/{gid}/join", headers=hs[2]).status_code == 200
    mine = client.get("/api/guild/mine", headers=hs[1]).json()
    assert mine["name"] == "波利獵人團" and len(mine["members"]) == 3

    client.post("/api/guild/leave", headers=hs[0])
    mine2 = client.get("/api/guild/mine", headers=hs[1]).json()
    assert any(m["role"] == "leader" for m in mine2["members"])
    assert len(mine2["members"]) == 2


def test_one_account_one_guild(client):
    from server.auth import invites
    c1, c2 = invites.create_invite(), invites.create_invite()
    client.post("/api/accounts", json={"invite_code": c1, "username": "gg1", "password": "password123"})
    tok = client.post("/api/sessions", json={"username": "gg1", "password": "password123"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    client.post("/api/characters", headers=h, json={"name": "GG1"})
    client.post("/api/guild", headers=h, json={"name": "團一"})
    r = client.post("/api/guild", headers=h, json={"name": "團二"})
    assert r.status_code == 400


def test_guild_name_unique(client):
    from server.auth import invites
    hs = []
    for n in ("unq1", "unq2"):
        c = invites.create_invite()
        client.post("/api/accounts", json={"invite_code": c, "username": n, "password": "password123"})
        tok = client.post("/api/sessions", json={"username": n, "password": "password123"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        client.post("/api/characters", headers=h, json={"name": n.upper()[:12]})
        hs.append(h)
    client.post("/api/guild", headers=hs[0], json={"name": "撞名團"})
    assert client.post("/api/guild", headers=hs[1], json={"name": "撞名團"}).status_code == 409


def test_guild_channel_requires_membership(client):
    from server.auth import invites
    hs = []
    for n in ("gc1", "gc2"):
        c = invites.create_invite()
        client.post("/api/accounts", json={"invite_code": c, "username": n, "password": "password123"})
        tok = client.post("/api/sessions", json={"username": n, "password": "password123"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        client.post("/api/characters", headers=h, json={"name": n.upper()[:12]})
        hs.append(h)
    gid = client.post("/api/guild", headers=hs[0], json={"name": "頻道團"}).json()["id"]
    assert client.post("/api/chat", headers=hs[0],
                       json={"channel": f"guild:{gid}", "text": "hi"}).status_code == 200
    assert client.post("/api/chat", headers=hs[1],
                       json={"channel": f"guild:{gid}", "text": "hi"}).status_code == 403
