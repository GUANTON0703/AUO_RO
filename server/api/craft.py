import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.auth.dependencies import CurrentAccount
from server.content import load_content
from server.loot import crafting
from server.repositories import characters as characters_repo
from server.repositories import inventory

router = APIRouter(prefix="/api/craft", tags=["craft"])

_content = load_content()


def _current_character(account_id: int):
    row = characters_repo.get_active_character(account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="沒有角色")
    return row


@router.get("")
def list_craft(account_id: CurrentAccount):
    row = _current_character(account_id)
    craft_level = row["craft_level"]
    mastery = characters_repo.get_recipe_mastery(row["id"])
    out = []
    for r in _content.recipes.values():
        have = {m: inventory.item_qty(row["id"], m) for m in r.materials}
        attempts = mastery.get(r.id, 0)
        out.append({
            "id": r.id, "name": r.name, "result_item": r.result_item,
            "result_item_name": _content.items[r.result_item].name,
            "result_qty": r.result_qty,
            "required_craft_level": r.required_craft_level,
            "success_pct": crafting.success_rate(r, craft_level, attempts),
            "mastery_attempts": attempts,
            "mastery_bonus_pct": crafting.mastery_bonus_pct(attempts),
            "mastery_next": crafting.MASTERY_PER_ATTEMPT - (attempts % crafting.MASTERY_PER_ATTEMPT)
                if crafting.mastery_bonus_pct(attempts) < crafting.MASTERY_CAP_PCT else 0,
            "zeny_cost": r.zeny_cost,
            "materials": [
                {"item_id": m, "name": _content.items[m].name, "need": qty, "have": have[m]}
                for m, qty in r.materials.items()
            ],
        })
    return {
        "craft_level": craft_level, "craft_exp": row["craft_exp"],
        "craft_exp_next": crafting.craft_exp_for_next(craft_level)
                          if craft_level < crafting.CRAFT_LEVEL_CAP else 0,
        "recipes": out,
    }


class CraftRequest(BaseModel):
    times: int = Field(default=1, ge=1, le=10)


@router.post("/{recipe_id}")
def craft(recipe_id: str, body: CraftRequest, account_id: CurrentAccount):
    row = _current_character(account_id)
    recipe = _content.recipes.get(recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="配方不存在")

    for m, qty in recipe.materials.items():
        if inventory.item_qty(row["id"], m) < qty * body.times:
            raise HTTPException(status_code=400, detail=f"材料「{_content.items[m].name}」不夠")
    total_cost = recipe.zeny_cost * body.times
    if row["zeny"] < total_cost:
        raise HTTPException(status_code=400, detail="Zeny 不足")

    rng = random.Random()
    craft_level, craft_exp = row["craft_level"], row["craft_exp"]
    mastery = characters_repo.get_recipe_mastery(row["id"])
    attempts_before = mastery.get(recipe_id, 0)
    successes = great_successes = fails = produced = 0
    for i in range(body.times):
        for m, qty in recipe.materials.items():
            inventory.consume_item(row["id"], m, qty)
        success, great, exp_gained = crafting.attempt_craft(
            recipe, craft_level, attempts_before + i, rng)
        craft_level, craft_exp = crafting.apply_craft_exp(craft_level, craft_exp, exp_gained)
        if success:
            successes += 1
            qty = recipe.result_qty * (2 if great else 1)
            produced += qty
            inventory.add_item(row["id"], recipe.result_item, qty)
            if great:
                great_successes += 1
        else:
            fails += 1

    characters_repo.spend_zeny(row["id"], total_cost)
    characters_repo.set_craft_progress(row["id"], craft_level, craft_exp)
    mastery[recipe_id] = attempts_before + body.times
    characters_repo.set_recipe_mastery(row["id"], mastery)

    return {
        "attempts": body.times, "successes": successes, "great_successes": great_successes,
        "fails": fails, "produced": produced, "result_item": recipe.result_item,
        "craft_level": craft_level, "craft_exp": craft_exp,
        "craft_exp_next": crafting.craft_exp_for_next(craft_level)
                          if craft_level < crafting.CRAFT_LEVEL_CAP else 0,
        "mastery_attempts": mastery[recipe_id],
        "mastery_bonus_pct": crafting.mastery_bonus_pct(mastery[recipe_id]),
    }
