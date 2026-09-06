from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from server.db import connection


@pytest.fixture(autouse=True)
def _reset_hunt_memory():
    """掛機模組用 module-level dict 存每個角色的策略與事件批次。
    正式環境角色 id 全域唯一不會撞，但測試每次都是新 DB、角色 id 從 1 開始，
    會沿用上一個測試留下的狀態。每個測試前後清乾淨。"""
    from server.api import hunt

    hunt._strategies.clear()
    hunt._last_batch.clear()
    yield
    hunt._strategies.clear()
    hunt._last_batch.clear()


@pytest.fixture
def client(tmp_path):
    connection.configure(str(tmp_path / "test.db"))
    connection.init_db()
    from server.app import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def invite_code():
    from server.auth import invites

    return invites.create_invite()


@pytest.fixture
def auth(client, invite_code):
    """回傳 (token, headers, account_id)。已註冊 + 登入好一個帳號。"""
    client.post(
        "/api/accounts",
        json={"invite_code": invite_code, "username": "tester", "password": "password123"},
    )
    resp = client.post(
        "/api/sessions", json={"username": "tester", "password": "password123"}
    )
    body = resp.json()
    return body["token"], {"Authorization": f"Bearer {body['token']}"}, body["account_id"]


class _DbHelpers:
    def _exec(self, sql, params):
        with connection.get_connection() as conn:
            conn.execute(sql, params)

    def set_job_level(self, character_id, job_level):
        self._exec("UPDATE characters SET job_level = ? WHERE id = ?", (job_level, character_id))

    def set_job(self, character_id, job_id, job_level=1, job_exp=0):
        from server.repositories import characters as repo
        repo.set_job(character_id, job_id, job_level, job_exp)

    def set_base_level(self, character_id, base_level):
        self._exec("UPDATE characters SET base_level = ? WHERE id = ?", (base_level, character_id))

    def set_stats(self, character_id, stats):
        from server.repositories import characters as repo
        repo.set_stats(character_id, stats)

    def give_equipment(self, character_id, equipment_id):
        from server.repositories import inventory
        return inventory.add_equipment(character_id, equipment_id)

    def give_item(self, character_id, item_id, qty):
        from server.repositories import inventory
        inventory.add_item(character_id, item_id, qty)

    def clear_inventory(self, character_id):
        with connection.get_connection() as conn:
            conn.execute("DELETE FROM character_items WHERE character_id = ?", (character_id,))
            conn.execute("DELETE FROM character_equipment WHERE character_id = ?", (character_id,))

    def set_zeny(self, character_id, amount):
        self._exec("UPDATE characters SET zeny = ? WHERE id = ?", (amount, character_id))

    def rewind_hunt(self, character_id, seconds):
        with connection.get_connection() as conn:
            row = conn.execute(
                "SELECT hunt_last_settled_at, hunt_started_at FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()
            last = datetime.fromisoformat(row["hunt_last_settled_at"])
            new_last = (last - timedelta(seconds=seconds)).isoformat()
            conn.execute(
                "UPDATE characters SET hunt_last_settled_at = ?, hunt_started_at = ? WHERE id = ?",
                (new_last, new_last, character_id),
            )


@pytest.fixture
def db_helpers(client):
    return _DbHelpers()
