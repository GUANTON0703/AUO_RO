def test_web_index_served_at_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ROtxt" in r.text


def test_web_static_assets_served(client):
    assert client.get("/style.css").status_code == 200
    assert client.get("/js/app.js").status_code == 200


def test_health_still_reachable(client):
    assert client.get("/health").json() == {"status": "ok"}
