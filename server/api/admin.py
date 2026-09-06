from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import GMAccount
from server.db import connection

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MoneyRequest(BaseModel):
    amount: int = Field(ge=-10_000_000, le=10_000_000)


class ExperienceRequest(BaseModel):
    base_exp: int = Field(ge=0, le=2_147_483_647)
    job_exp: int = Field(ge=0, le=2_147_483_647)


class MultipliersRequest(BaseModel):
    experience: float = Field(gt=0, le=100)
    drop: float = Field(gt=0, le=100)


def _character(character_id: int):
    with connection.get_connection() as conn:
        row = conn.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="找不到角色")
    return row


@router.post("/characters/{character_id}/money")
def adjust_money(character_id: int, body: MoneyRequest, _: GMAccount):
    _character(character_id)
    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET zeny = zeny + ? WHERE id = ?", (body.amount, character_id))
        return dict(conn.execute("SELECT id, zeny FROM characters WHERE id = ?", (character_id,)).fetchone())


@router.post("/characters/{character_id}/experience")
def set_experience(character_id: int, body: ExperienceRequest, _: GMAccount):
    _character(character_id)
    with connection.get_connection() as conn:
        conn.execute("UPDATE characters SET base_exp = ?, job_exp = ? WHERE id = ?", (body.base_exp, body.job_exp, character_id))
        return dict(conn.execute("SELECT id, base_exp, job_exp FROM characters WHERE id = ?", (character_id,)).fetchone())


@router.put("/settings/multipliers")
def set_multipliers(body: MultipliersRequest, _: GMAccount):
    with connection.transaction() as conn:
        conn.executemany("INSERT INTO server_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [("experience_multiplier", str(body.experience)), ("drop_multiplier", str(body.drop))])
    return {"experience": body.experience, "drop": body.drop}


@router.get("/online-players")
def online_players(_: GMAccount):
    with connection.get_connection() as conn:
        rows = conn.execute("""
            SELECT a.id AS account_id, a.username, a.role, c.id AS character_id, c.name,
                   c.base_level, c.job_level, c.zeny
            FROM accounts a JOIN sessions s ON s.account_id = a.id
            LEFT JOIN characters c ON c.account_id = a.id
            WHERE s.expires_at > datetime('now') ORDER BY a.id, c.id
        """).fetchall()
    return [dict(row) for row in rows]
