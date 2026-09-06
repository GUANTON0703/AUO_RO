"""打寶示範：建角色 → 給 +7 knife → 穿上 → 掛機 2 小時 → 印背包與角色數值。

跑法：uv run python scripts/loot_demo.py
"""

import io
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

from server.db import connection  # noqa: E402


def _rewind(character_id: int, seconds: int) -> None:
    with connection.get_connection() as conn:
        row = conn.execute(
            "SELECT hunt_last_settled_at FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        new = (datetime.fromisoformat(row["hunt_last_settled_at"])
               - timedelta(seconds=seconds)).isoformat()
        conn.execute(
            "UPDATE characters SET hunt_last_settled_at = ?, hunt_started_at = ? WHERE id = ?",
            (new, new, character_id),
        )


def main() -> None:
    connection.configure(str(Path(tempfile.mkdtemp()) / "loot_demo.db"))
    connection.init_db()

    from server.app import create_app
    from server.auth import invites
    from server.repositories import inventory

    code = invites.create_invite()
    with TestClient(create_app()) as c:
        c.post("/api/accounts", json={"invite_code": code, "username": "lootdemo",
                                      "password": "password123"})
        tok = c.post("/api/sessions", json={"username": "lootdemo",
                                            "password": "password123"}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}

        ch = c.post("/api/characters", headers=h, json={"name": "打寶哥"}).json()
        cid = ch["id"]
        with connection.get_connection() as conn:
            conn.execute(
                "UPDATE characters SET base_level = 20, job_level = 15, "
                "stat_str = 45, stat_agi = 20, stat_vit = 25, stat_int = 5, "
                "stat_dex = 25, stat_luk = 10 WHERE id = ?", (cid,))

        eid = inventory.add_equipment(cid, "knife", refine=7)
        c.post(f"/api/characters/{cid}/inventory/equip", headers=h,
               json={"equipment_instance_id": eid})

        c.post("/api/hunt/start", headers=h, json={"map_id": "prontera_south_field"})
        _rewind(cid, 2 * 3600)
        settle = c.get("/api/hunt/status", headers=h).json()

        inv = c.get(f"/api/characters/{cid}/inventory", headers=h).json()
        fresh = c.get("/api/characters", headers=h).json()[0]

    print("=" * 60)
    print("角色：Lv20 劍士，武器 knife +7（已裝備）")
    print("掛機：南門原野 2 小時")
    print("=" * 60)
    print(f"擊殺 {settle['kills']}   base_exp {settle['base_exp']}   "
          f"job_exp {settle['job_exp']}   zeny {settle['zeny']}")
    print(f"本次掉落：{settle['drops'] or '（無）'}")
    print("-" * 60)
    print(f"背包素材/消耗品：{inv['items'] or '（空）'}")
    print("背包裝備：")
    for e in inv["equipment"]:
        print(f"  #{e['id']} {e['equipment_id']} +{e['refine']} "
              f"slot={e['equipped_slot']} cards={e['card_ids']}")
    print("-" * 60)
    print(f"角色現況：Base Lv {fresh['base_level']}  Job Lv {fresh['job_level']}  "
          f"zeny {fresh['zeny']}")


if __name__ == "__main__":
    main()
