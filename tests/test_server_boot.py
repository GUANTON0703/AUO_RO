def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_main_module_importable():
    import server.__main__ as m

    assert hasattr(m, "main")
