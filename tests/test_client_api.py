import pytest
from fastapi.testclient import TestClient

from client.api import ApiClient, ApiError
from server.app import create_app
from server.db import connection


@pytest.fixture
def api(tmp_path):
    connection.configure(str(tmp_path / "c.db"))
    connection.init_db()
    from server.auth import invites

    code = invites.create_invite()
    http = TestClient(create_app())
    return ApiClient(http), code


def test_register_login_flow(api):
    client, code = api
    client.register(code, "player1", "password123")
    client.login("player1", "password123")
    assert client.token is not None


def test_create_and_list_character(api):
    client, code = api
    client.register(code, "player2", "password123")
    client.login("player2", "password123")
    ch = client.create_character("英雄王")
    assert ch["name"] == "英雄王"
    assert client.list_characters()[0]["name"] == "英雄王"


def test_api_error_on_bad_login(api):
    client, code = api
    with pytest.raises(ApiError):
        client.login("nobody", "nope")


def test_hunt_start_status_stop(api):
    client, code = api
    client.register(code, "player3", "password123")
    client.login("player3", "password123")
    ch = client.create_character("掛機王")
    from server.repositories import characters as characters_repo

    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET base_level = 20 WHERE id = ?", (ch["id"],))
    characters_repo.set_stats(
        ch["id"], {"str": 40, "agi": 20, "vit": 25, "int": 5, "dex": 25, "luk": 10}
    )
    client.hunt_start("prontera_east_gate")
    st = client.hunt_status()
    assert "kills" in st
    client.hunt_stop()


def test_shop_and_inventory(api):
    client, code = api
    client.register(code, "player4", "password123")
    client.login("player4", "password123")
    ch = client.create_character("購物狂")
    inv = client.inventory(ch["id"])
    assert "items" in inv and "equipment" in inv
    shop = client.shop()
    assert any(i["id"] == "red_potion" for i in shop["items"])
