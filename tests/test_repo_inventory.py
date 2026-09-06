import pytest

from server.db import connection
from server.repositories import accounts, characters, inventory


@pytest.fixture
def db(tmp_path):
    connection.configure(str(tmp_path / "t.db"))
    connection.init_db()


@pytest.fixture
def char(db):
    aid = accounts.create_account("o", "h")
    return characters.create_character(aid, "背包哥", location_map="m")["id"]


def test_add_and_get_stackable(char):
    inventory.add_item(char, "red_potion", 5)
    inventory.add_item(char, "red_potion", 3)
    assert inventory.item_qty(char, "red_potion") == 8


def test_consume_stackable(char):
    inventory.add_item(char, "elunium", 4)
    assert inventory.consume_item(char, "elunium", 3) is True
    assert inventory.item_qty(char, "elunium") == 1
    assert inventory.consume_item(char, "elunium", 5) is False


def test_add_equipment_creates_instance(char):
    eid = inventory.add_equipment(char, "knife")
    inst = inventory.get_equipment(eid)
    assert inst["equipment_id"] == "knife" and inst["refine"] == 0
    assert inst["equipped_slot"] is None


def test_list_inventory_scoped_to_char(char):
    other = characters.create_character(accounts.create_account("x", "h"), "別人", location_map="m")["id"]
    inventory.add_item(char, "jellopy", 10)
    inventory.add_equipment(char, "knife")
    inventory.add_item(other, "jellopy", 99)
    inv = inventory.list_inventory(char)
    assert inv["items"]["jellopy"] == 10
    assert len(inv["equipment"]) == 1


def test_apply_drops_routes_equipment_vs_items(char):
    from server.content import load_content
    load_content()
    inventory.apply_drops(char, {"jellopy": 20, "knife": 2, "poring_card": 1})
    inv = inventory.list_inventory(char)
    assert inv["items"]["jellopy"] == 20
    assert inv["items"]["poring_card"] == 1
    assert sum(1 for e in inv["equipment"] if e["equipment_id"] == "knife") == 2


def test_grant_starter_kit(char):
    inventory.grant_starter_kit(char)
    inv = inventory.list_inventory(char)
    assert inv["items"]["red_potion"] >= 5
    assert any(e["equipment_id"] == "knife" for e in inv["equipment"])
