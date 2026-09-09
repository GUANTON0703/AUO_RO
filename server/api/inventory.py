import json
import random
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.db import connection
from server.loot import refine as refine_mod
from server.repositories import characters as characters_repo
from server.repositories import inventory

router = APIRouter(prefix="/api/characters", tags=["inventory"])

_content = load_content()


def _owned(character_id: int, account_id: int):
    row = characters_repo.get_character(character_id)
    if row is None or row["account_id"] != account_id:
        raise HTTPException(status_code=404, detail="找不到角色")
    return row


def _instance(character_id: int, instance_id: int) -> dict:
    inst = inventory.get_equipment(instance_id)
    if inst is None or inst["character_id"] != character_id:
        raise HTTPException(status_code=404, detail="找不到裝備")
    return inst


class EquipRequest(BaseModel):
    equipment_instance_id: int


class UnequipRequest(BaseModel):
    slot: str


class SocketRequest(BaseModel):
    equipment_instance_id: int
    card_item_id: str


class RefineRequest(BaseModel):
    equipment_instance_id: int
    mode: Literal["normal", "random"] = "normal"


@router.get("/{character_id}/inventory")
def get_inventory(character_id: int, account_id: CurrentAccount):
    _owned(character_id, account_id)
    return inventory.list_inventory(character_id)


@router.post("/{character_id}/inventory/equip")
def equip(character_id: int, body: EquipRequest, account_id: CurrentAccount):
    row = _owned(character_id, account_id)
    inst = _instance(character_id, body.equipment_instance_id)
    eq = _content.equipment.get(inst["equipment_id"])
    if eq is None:
        raise HTTPException(status_code=400, detail="裝備定義不存在")
    if eq.job_ids and not (set(eq.job_ids) & _content.job_ancestry(row["job_id"])):
        raise HTTPException(status_code=400, detail="此職業無法裝備")
    if row["base_level"] < eq.required_level:
        raise HTTPException(
            status_code=400, detail=f"Base Level 未達裝備需求（{eq.required_level}）"
        )
    with connection.transaction() as conn:
        # 雙手武器與副手（盾）互斥
        worn = {
            r["equipped_slot"]: r["equipment_id"]
            for r in conn.execute(
                "SELECT equipped_slot, equipment_id FROM character_equipment "
                "WHERE character_id = ? AND equipped_slot IS NOT NULL",
                (character_id,),
            ).fetchall()
        }
        if eq.slot == "offhand":
            w = _content.equipment.get(worn.get("weapon"))
            if w and w.two_handed:
                raise HTTPException(status_code=400,
                                    detail="裝備雙手武器時無法再裝副手")
        if eq.slot == "weapon" and eq.two_handed and "offhand" in worn:
            conn.execute(
                "UPDATE character_equipment SET equipped_slot = NULL "
                "WHERE character_id = ? AND equipped_slot = 'offhand'",
                (character_id,),
            )
        if eq.slot == "accessory":
            # 飾品有左右兩格：先塞空的那格，兩格都滿就換掉左格（accessory1）
            if inst["equipped_slot"] in ("accessory1", "accessory2"):
                return inventory.list_inventory(character_id)
            used = {
                r["equipped_slot"]
                for r in conn.execute(
                    "SELECT equipped_slot FROM character_equipment "
                    "WHERE character_id = ? AND equipped_slot IN "
                    "('accessory1', 'accessory2')",
                    (character_id,),
                ).fetchall()
            }
            target = "accessory1" if "accessory1" not in used else (
                "accessory2" if "accessory2" not in used else "accessory1"
            )
        else:
            target = eq.slot
        conn.execute(
            "UPDATE character_equipment SET equipped_slot = NULL "
            "WHERE character_id = ? AND equipped_slot = ?",
            (character_id, target),
        )
        conn.execute(
            "UPDATE character_equipment SET equipped_slot = ? WHERE id = ?",
            (target, inst["id"]),
        )
    return inventory.list_inventory(character_id)


@router.post("/{character_id}/inventory/unequip")
def unequip(character_id: int, body: UnequipRequest, account_id: CurrentAccount):
    _owned(character_id, account_id)
    with connection.get_connection() as conn:
        conn.execute(
            "UPDATE character_equipment SET equipped_slot = NULL "
            "WHERE character_id = ? AND equipped_slot = ?",
            (character_id, body.slot),
        )
    return inventory.list_inventory(character_id)


@router.post("/{character_id}/inventory/socket")
def socket(character_id: int, body: SocketRequest, account_id: CurrentAccount):
    _owned(character_id, account_id)
    inst = _instance(character_id, body.equipment_instance_id)
    eq = _content.equipment.get(inst["equipment_id"])
    if eq is None:
        raise HTTPException(status_code=400, detail="裝備定義不存在")
    card = _content.cards.get(body.card_item_id)
    if card is None:
        raise HTTPException(status_code=400, detail="卡片不存在")
    if card.slot != eq.slot:
        raise HTTPException(status_code=400, detail="卡片孔位與裝備不符")

    with connection.transaction() as conn:
        r = conn.execute(
            "SELECT card_ids FROM character_equipment WHERE id = ?", (inst["id"],)
        ).fetchone()
        card_ids = json.loads(r["card_ids"])
        if len(card_ids) >= eq.card_slots:
            raise HTTPException(status_code=400, detail="沒有空的卡片孔")
        have = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (character_id, body.card_item_id),
        ).fetchone()
        if not have or have["qty"] < 1:
            raise HTTPException(status_code=400, detail="背包沒有這張卡")
        conn.execute(
            "UPDATE character_items SET qty = qty - 1 "
            "WHERE character_id = ? AND item_id = ?",
            (character_id, body.card_item_id),
        )
        card_ids.append(body.card_item_id)
        conn.execute(
            "UPDATE character_equipment SET card_ids = ? WHERE id = ?",
            (json.dumps(card_ids), inst["id"]),
        )
    return inventory.list_inventory(character_id)


@router.post("/{character_id}/inventory/refine")
def refine(character_id: int, body: RefineRequest, account_id: CurrentAccount):
    _owned(character_id, account_id)
    inst = _instance(character_id, body.equipment_instance_id)
    eq = _content.equipment.get(inst["equipment_id"])
    if eq is None:
        raise HTTPException(status_code=400, detail="裝備定義不存在")
    if not eq.refinable:
        raise HTTPException(status_code=400, detail="此裝備無法精煉")

    ore = refine_mod.refine_ore_for(eq.slot)
    ore_item = _content.items.get(ore)
    ore_name = ore_item.name if ore_item else ore
    with connection.transaction() as conn:
        r = conn.execute(
            "SELECT refine FROM character_equipment WHERE id = ?", (inst["id"],)
        ).fetchone()
        current = r["refine"]
        if current >= refine_mod.REFINE_CAP:
            raise HTTPException(status_code=400, detail="已達精煉上限")
        zeny_cost = (refine_mod.random_refine_zeny_cost(current)
                     if body.mode == "random"
                     else refine_mod.refine_zeny_cost(current))
        ore_row = conn.execute(
            "SELECT qty FROM character_items WHERE character_id = ? AND item_id = ?",
            (character_id, ore),
        ).fetchone()
        if not ore_row or ore_row["qty"] < 1:
            raise HTTPException(status_code=400,
                                detail=f"缺少精煉材料：{ore_name}（怪物掉落）")
        zeny_row = conn.execute(
            "SELECT zeny FROM characters WHERE id = ?", (character_id,)
        ).fetchone()
        if zeny_row["zeny"] < zeny_cost:
            raise HTTPException(status_code=400, detail="Zeny 不足")

        conn.execute(
            "UPDATE character_items SET qty = qty - 1 "
            "WHERE character_id = ? AND item_id = ?",
            (character_id, ore),
        )
        conn.execute(
            "UPDATE characters SET zeny = zeny - ? WHERE id = ?",
            (zeny_cost, character_id),
        )
        if body.mode == "random":
            new_refine, ok, increment = refine_mod.attempt_random_refine(
                current, random.Random()
            )
        else:
            new_refine, ok = refine_mod.attempt_refine(current, random.Random())
            increment = new_refine - current
        conn.execute(
            "UPDATE character_equipment SET refine = ? WHERE id = ?",
            (new_refine, inst["id"]),
        )
    if body.mode == "random":
        if not ok:
            message = f"隨機精煉判定失敗，{eq.name} 降至 +{new_refine}"
        elif increment == 0:
            message = f"隨機精煉判定成功，但增量 +0，{eq.name} 維持 +{new_refine}"
        else:
            message = f"隨機精煉判定成功，抽中 +{increment}，{eq.name} +{new_refine}"
    else:
        message = (
            f"精煉成功，{eq.name} +{new_refine}"
            if ok
            else f"精煉失敗，{eq.name} 降至 +{new_refine}"
        )
    return {
        "success": ok,
        "refine": new_refine,
        "message": message,
        "mode": body.mode,
        "increment": increment,
    }
