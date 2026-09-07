def test_health_endpoint(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_main_module_importable():
    import server.__main__ as m

    assert hasattr(m, "main")


def test_main_accepts_host_and_port_overrides(monkeypatch):
    import sys
    import server.__main__ as m

    calls = {}
    monkeypatch.setattr(m.uvicorn, "run", lambda *args, **kwargs: calls.update(kwargs))
    monkeypatch.setattr(sys, "argv", ["server", "--host", "0.0.0.0", "--port", "9000"])

    m.main()

    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000
