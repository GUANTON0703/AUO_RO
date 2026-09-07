from dataclasses import dataclass, field

from server.combat.combatant import Combatant, ResolvedSkill
from server.loot import refine as refine_mod


@dataclass
class EquippedPiece:
    equipment_id: str
    refine: int = 0
    card_ids: list = field(default_factory=list)


@dataclass
class CharacterSnapshot:
    name: str
    job_id: str
    base_level: int
    job_level: int
    stats: dict
    learned_skills: dict = field(default_factory=dict)
    equipped: list = field(default_factory=list)
    hp: int | None = None
    sp: int | None = None


def _sum_equipment_stats(content, pieces: list) -> dict:
    acc: dict = {}
    for piece in pieces:
        eq = content.equipment.get(piece.equipment_id)
        if not eq:
            continue
        bonus = refine_mod.refine_stat_bonus(eq.stats, piece.refine)
        for k, v in eq.stats.items():
            acc[k] = acc.get(k, 0) + v + bonus.get(k, 0)
    return acc


def _apply_card_effects(content, pieces: list, derived: dict) -> dict:
    """把卡片效果套進 derived（數值），並回傳戰鬥用的 {resist, race, atk_element}。
    附魔卡（weapon_element）只有鑲在武器上才算。"""
    combat = {"resist": {}, "race": {}, "atk_element": None}
    for piece in pieces:
        eq = content.equipment.get(piece.equipment_id)
        slot = eq.slot if eq else None
        for cid in piece.card_ids:
            card = content.cards.get(cid)
            if not card:
                continue
            for eff in card.effects:
                t = eff.get("type")
                if t == "flat_stat":
                    derived[eff["stat"]] = derived.get(eff["stat"], 0) + eff["amount"]
                elif t == "percent_stat":
                    base = derived.get(eff["stat"], 0)
                    derived[eff["stat"]] = round(base * (1 + eff["pct"] / 100))
                elif t == "element_resist":
                    combat["resist"][eff["element"]] = (
                        combat["resist"].get(eff["element"], 0) + eff["pct"])
                elif t == "race_damage":
                    combat["race"][eff["race"]] = (
                        combat["race"].get(eff["race"], 0) + eff["pct"])
                elif t == "weapon_element" and slot == "weapon":
                    combat["atk_element"] = eff["element"]
                # on_hit_proc：走技能路線的 proc，卡片 proc 暫不支援
    return combat


def _passive_procs(content, learned: dict) -> dict:
    """被動技能的觸發機率 {effect: 機率%}（例：double_attack → {extra_hit: 25}）。"""
    out: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "passive":
            continue
        for eff in sk.effects:
            if eff.get("type") != "proc":
                continue
            seq = eff.get("chance_pct", [0])
            val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
            key = eff.get("effect", "")
            out[key] = max(out.get(key, 0), val)
    return out


def _passive_stat_bonus(content, learned: dict) -> dict:
    bonus: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "passive":
            continue
        for eff in sk.effects:
            if eff.get("type") == "passive_stat":
                seq = eff.get("amount", [0])
                val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
                bonus[eff["stat"]] = bonus.get(eff["stat"], 0) + val
    return bonus


def build_player_combatant(snap: CharacterSnapshot, content) -> Combatant:
    job = content.get_job(snap.job_id)
    s = snap.stats
    STR, AGI, VIT, INT, DEX, LUK = (s["str"], s["agi"], s["vit"], s["int"], s["dex"], s["luk"])

    eq = _sum_equipment_stats(content, snap.equipped)
    passives = _passive_stat_bonus(content, snap.learned_skills)

    # HP/SP 隨等級加速成長（配合怪物 HP 公式的 level² 項），玩家才打得動同級怪
    lv = snap.base_level
    max_hp = round((40 + lv * job.hp_per_level * (1.5 + lv / 12)) * (1 + VIT / 60))
    max_sp = round((11 + lv * job.sp_per_level * (1.2 + lv / 25)) * (1 + INT / 80))
    atk = round((STR + (STR // 10) ** 2 + DEX // 5 + LUK // 5 + eq.get("atk", 0)
                 + passives.get("atk", 0)) * (1 + lv / 50))
    matk = round((INT + (INT // 7) ** 2 + eq.get("matk", 0)
                  + passives.get("matk", 0)) * (1 + lv / 50))
    defense = min(95, eq.get("def", 0) + VIT // 2 + passives.get("defense", 0))
    mdef = min(95, eq.get("mdef", 0) + INT // 2)
    hit = snap.base_level + DEX + eq.get("hit", 0)
    flee = snap.base_level + AGI + eq.get("flee", 0)
    aspd = min(193, round(100 + AGI * 0.7 + DEX * 0.15 + eq.get("aspd", 0)))
    crit = round(LUK / 3) + eq.get("crit", 0)

    derived = {"max_hp": max_hp, "max_sp": max_sp, "atk": atk, "matk": matk,
               "defense": defense, "mdef": mdef, "hit": hit, "flee": flee,
               "crit": crit}
    combat_mods = _apply_card_effects(content, snap.equipped, derived)

    # 攻擊屬性：武器本身屬性 → 附魔卡覆蓋
    weapon = next((content.equipment.get(p.equipment_id) for p in snap.equipped
                   if content.equipment.get(p.equipment_id)
                   and content.equipment[p.equipment_id].slot == "weapon"), None)
    attack_element = combat_mods["atk_element"] or (
        weapon.element if weapon else "neutral")

    resolved = []
    for sid, lvl in snap.learned_skills.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        sp_cost = sk.sp_cost[min(lvl, len(sk.sp_cost)) - 1] if sk.sp_cost else 0
        resolved.append(ResolvedSkill(
            skill_id=sid, name=sk.name, level=lvl, kind="active",
            sp_cost=sp_cost, cooldown_rounds=round(sk.cooldown_s / 2),
            effects=sk.effects, trigger=idle.get("trigger", "every_turn"),
            priority=idle.get("priority", 1),
        ))

    return Combatant(
        name=snap.name, max_hp=derived["max_hp"], max_sp=derived["max_sp"],
        atk=max(0, derived["atk"]), matk=max(0, derived["matk"]),
        defense=max(0, min(95, derived["defense"])), mdef=max(0, min(95, derived["mdef"])),
        hit=max(0, derived["hit"]), flee=max(0, derived["flee"]),
        aspd=max(1, min(193, aspd)), crit=max(0, derived["crit"]),
        is_caster=(derived["matk"] > derived["atk"]),
        soft_def=VIT // 3, soft_mdef=INT // 4,
        skills=resolved,
        attack_element=attack_element,
        element_resist=combat_mods["resist"],
        race_bonus=combat_mods["race"],
        procs=_passive_procs(content, snap.learned_skills),
        hp=snap.hp if snap.hp is not None else 0,
        sp=snap.sp if snap.sp is not None else 0,
    )
