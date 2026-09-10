from dataclasses import dataclass, field

from server.combat.combatant import Combatant, ResolvedSkill
from server.loot import refine as refine_mod

# 武器類別 → (攻擊主屬性, 基礎攻速, 爆擊率倍率)。對齊 Pre-Renewal RO 的手感：
# 短劍/拳刃最快、雙手武器最慢、弓吃 DEX、法杖走 MATK。
WEAPON_PROFILE = {
    "dagger":  ("str", 135, 1.0),
    "sword":   ("str", 125, 1.0),
    "axe":     ("str", 116, 1.0),
    "mace":    ("str", 120, 1.0),
    "twohand": ("str", 108, 1.0),
    "katar":   ("str", 130, 2.0),   # 拳刃爆擊率翻倍（刺客爆擊流核心）
    "bow":     ("dex", 122, 1.0),
    "staff":   ("str", 112, 1.0),   # 法師靠 MATK，物理攻擊本來就低
}
_DEFAULT_WEAPON = ("str", 118, 1.0)


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
    primary_skill_id: str | None = None
    skill_toggles: dict = field(default_factory=dict)
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


def _card_flat_stats(content, pieces: list) -> dict:
    """卡片的 flat_stat 貢獻，回傳跟裝備一樣的扁平 stat 池
    （str/agi/…/atk/defense/aspd/crit/max_hp…），在 STR→衍生數值計算之前併進去。"""
    acc: dict = {}
    for piece in pieces:
        for cid in piece.card_ids:
            card = content.cards.get(cid)
            if not card:
                continue
            for eff in card.effects:
                if eff.get("type") == "flat_stat":
                    acc[eff["stat"]] = acc.get(eff["stat"], 0) + eff["amount"]
    return acc


def _apply_card_effects(content, pieces: list, derived: dict) -> dict:
    """percent_stat 套進已算好的 derived，並回傳戰鬥用的 {resist, race, size, atk_element}。
    flat_stat 已在 _card_flat_stats 處理；附魔卡（weapon_element）只有鑲在武器上才算。"""
    combat = {"resist": {}, "race": {}, "size": {}, "atk_element": None,
              "def_element": None, "procs": {}, "immunities": set(),
              "perfect_dodge": 0, "on_kill": {}, "autocast": []}
    for piece in pieces:
        eq = content.equipment.get(piece.equipment_id)
        slot = eq.slot if eq else None
        for cid in piece.card_ids:
            card = content.cards.get(cid)
            if not card:
                continue
            for eff in card.effects:
                t = eff.get("type")
                if t == "percent_stat":
                    base = derived.get(eff["stat"], 0)
                    derived[eff["stat"]] = round(base * (1 + eff["pct"] / 100))
                elif t == "element_resist":
                    combat["resist"][eff["element"]] = (
                        combat["resist"].get(eff["element"], 0) + eff["pct"])
                elif t == "race_damage":
                    combat["race"][eff["race"]] = (
                        combat["race"].get(eff["race"], 0) + eff["pct"])
                elif t == "size_damage":
                    combat["size"][eff["size"]] = (
                        combat["size"].get(eff["size"], 0) + eff["pct"])
                elif t == "weapon_element" and slot == "weapon":
                    combat["atk_element"] = eff["element"]
                elif t == "armor_element":
                    combat["def_element"] = eff["element"]
                elif t == "on_hit_proc":
                    combat["procs"][eff["effect"]] = max(
                        combat["procs"].get(eff["effect"], 0), eff.get("chance_pct", 0))
                elif t in ("life_leech", "sp_leech"):
                    combat["procs"][t] = combat["procs"].get(t, 0) + eff.get("pct", 0)
                elif t == "reflect_damage":
                    combat["procs"]["reflect"] = combat["procs"].get("reflect", 0) + eff.get("pct", 0)
                elif t == "status_immune":
                    combat["immunities"].add(eff["status"])
                elif t == "perfect_dodge":
                    combat["perfect_dodge"] += eff.get("amount", eff.get("pct", 0))
                elif t == "on_kill_recover":
                    for k in ("hp_pct", "sp_pct"):
                        if eff.get(k):
                            combat["on_kill"][k] = combat["on_kill"].get(k, 0) + eff[k]
                elif t == "autocast":
                    sk = content.skills.get(eff["skill_id"])
                    if sk:
                        combat["autocast"].append({
                            "skill_id": sk.id, "name": sk.name,
                            "effects": sk.effects,
                            "chance_pct": eff.get("chance_pct", 5),
                            "level": eff.get("level", 1)})
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


def _maintained_buffs(content, learned: dict, toggles: dict) -> dict:
    """掛機時「維持型」自我 buff（trigger=sp_available 的 buff 技）當成常駐，
    直接折進數值 → 不用每場重放、不耗 SP、記錄也不會洗一排施放訊息。"""
    bonus: dict = {}
    for sid, lvl in learned.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        if idle.get("trigger") != "sp_available":
            continue
        if not toggles.get(sid, idle.get("enabled", True)):
            continue
        for eff in sk.effects:
            if eff.get("type") != "buff":
                continue
            for stat, seq in eff.get("stats", {}).items():
                val = seq[min(lvl, len(seq)) - 1] if isinstance(seq, list) else seq
                bonus[stat] = bonus.get(stat, 0) + val
    return bonus


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
    eq = _sum_equipment_stats(content, snap.equipped)
    for k, v in _card_flat_stats(content, snap.equipped).items():
        eq[k] = eq.get(k, 0) + v
    mbuff = _maintained_buffs(content, snap.learned_skills, snap.skill_toggles)
    # 維持型 buff 加的基礎屬性（str/agi/…）先併進 eq，才會傳進 STR/AGI/… 的計算
    for k in ("str", "agi", "vit", "int", "dex", "luk"):
        if mbuff.get(k):
            eq[k] = eq.get(k, 0) + mbuff[k]
    STR, AGI, VIT, INT, DEX, LUK = (
        s["str"] + eq.get("str", 0), s["agi"] + eq.get("agi", 0),
        s["vit"] + eq.get("vit", 0), s["int"] + eq.get("int", 0),
        s["dex"] + eq.get("dex", 0), s["luk"] + eq.get("luk", 0))

    passives = _passive_stat_bonus(content, snap.learned_skills)
    # 維持型 buff 的衍生數值加成（atk/aspd/flee/…）併進 passives 池；
    # 基礎屬性（str/agi/…）已在上面併進 eq
    for k, v in mbuff.items():
        if k not in ("str", "agi", "vit", "int", "dex", "luk"):
            passives[k] = passives.get(k, 0) + v

    # HP/SP：Pre-Renewal 尺度（lv99 騎士約 7500，不是 10000+）
    lv = snap.base_level
    max_hp = round((40 + lv * job.hp_per_level * (0.8 + lv / 32)) * (1 + VIT / 100))
    max_sp = round((11 + lv * job.sp_per_level * (1.0 + lv / 32)) * (1 + INT / 80))
    weapon = next((content.equipment.get(p.equipment_id) for p in snap.equipped
                   if content.equipment.get(p.equipment_id)
                   and content.equipment[p.equipment_id].slot == "weapon"), None)
    wt = weapon.weapon_type if weapon else None
    atk_stat, base_aspd, crit_rate_mult = WEAPON_PROFILE.get(wt, _DEFAULT_WEAPON)
    # 攻擊主屬性照武器類型（原版 RO：近戰 STR、弓 DEX、法杖走 MATK）
    _pool = {"str": STR, "dex": DEX}
    atk_main = _pool.get(atk_stat, STR)
    atk_sub = DEX if atk_stat == "str" else STR
    # Pre-Renewal 小數值：狀態 ATK 是加法小數，武器攻擊被主屬性放大。
    # 拿掉了舊的 ×(1+lv/50) 全域倍率與 (STR//10)² 項。
    weapon_atk = weapon.stats.get("atk", 0) if weapon else 0
    scaled_weapon = weapon_atk * (1 + atk_main / 150)
    atk = round(atk_main + atk_sub // 5 + LUK // 5
                + scaled_weapon + (eq.get("atk", 0) - weapon_atk)
                + passives.get("atk", 0))
    weapon_matk = weapon.stats.get("matk", 0) if weapon else 0
    matk = round(INT + (INT // 8) ** 2 + eq.get("matk", 0)
                 + passives.get("matk", 0))
    defense = min(120, eq.get("defense", 0) + VIT // 2 + passives.get("defense", 0))
    mdef = min(120, eq.get("mdef", 0) + INT // 3 + passives.get("mdef", 0))
    hit = snap.base_level + DEX + LUK // 3 + eq.get("hit", 0) + passives.get("hit", 0)
    flee = snap.base_level + AGI + LUK // 5 + eq.get("flee", 0) + passives.get("flee", 0)
    aspd = min(193, round(base_aspd + AGI * 0.7 + DEX * 0.12 + eq.get("aspd", 0)
                          + passives.get("aspd", 0)))
    crit = round(LUK * 0.3 * crit_rate_mult) + eq.get("crit", 0) + passives.get("crit", 0)
    # 施法後延遲：DEX 高 = 可連續放招（原版高 DEX 幾乎無延遲）
    cast_delay = 0 if DEX >= 100 else (1 if DEX >= 45 else 2)
    max_hp += passives.get("max_hp", 0) + eq.get("max_hp", 0)
    max_sp += passives.get("max_sp", 0) + eq.get("max_sp", 0)

    derived = {"max_hp": max_hp, "max_sp": max_sp, "atk": atk, "matk": matk,
               "defense": defense, "mdef": mdef, "hit": hit, "flee": flee,
               "crit": crit}
    combat_mods = _apply_card_effects(content, snap.equipped, derived)

    # 攻擊屬性：武器本身屬性 → 附魔卡覆蓋
    attack_element = combat_mods["atk_element"] or (
        weapon.element if weapon else "neutral")
    crit_mult = 1.6 if (weapon and weapon.weapon_type == "katar") else 1.4

    resolved = []
    for sid, lvl in snap.learned_skills.items():
        sk = content.skills.get(sid)
        if not sk or sk.kind != "active":
            continue
        idle = sk.idle_default or {}
        if not snap.skill_toggles.get(sid, idle.get("enabled", True)):
            continue   # 玩家關掉的、或預設就不掛機放的技能
        # 純維持型 buff 已折進數值常駐 → 不進戰鬥技能清單，不會每場重放
        if (idle.get("trigger") == "sp_available"
                and all(e.get("type") == "buff" for e in sk.effects)):
            continue
        sp_cost = sk.sp_cost[min(lvl, len(sk.sp_cost)) - 1] if sk.sp_cost else 0
        priority = idle.get("priority", 1)
        if sid == snap.primary_skill_id:
            priority = 99   # 指定主攻 → 蓋過其他攻擊技
        resolved.append(ResolvedSkill(
            skill_id=sid, name=sk.name, level=lvl, kind="active",
            sp_cost=sp_cost, cooldown_rounds=round(sk.cooldown_s / 2),
            effects=sk.effects, trigger=idle.get("trigger", "every_turn"),
            priority=priority,
        ))

    return Combatant(
        name=snap.name, max_hp=derived["max_hp"], max_sp=derived["max_sp"],
        atk=max(0, derived["atk"]), matk=max(0, derived["matk"]),
        defense=max(0, min(120, derived["defense"])), mdef=max(0, min(120, derived["mdef"])),
        hit=max(0, derived["hit"]), flee=max(0, derived["flee"]),
        aspd=max(1, min(193, aspd)), crit=max(0, derived["crit"]),
        is_caster=(derived["matk"] > derived["atk"]),
        crit_mult=crit_mult,
        cast_delay=cast_delay,
        soft_def=VIT // 3, soft_mdef=INT // 4,
        skills=resolved,
        attack_element=attack_element,
        element=combat_mods["def_element"] or "neutral",
        element_resist=combat_mods["resist"],
        race_bonus=combat_mods["race"],
        size_bonus=combat_mods["size"],
        procs={**_passive_procs(content, snap.learned_skills), **combat_mods["procs"]},
        immunities=combat_mods["immunities"],
        perfect_dodge=combat_mods["perfect_dodge"],
        on_kill=combat_mods["on_kill"],
        autocast=combat_mods["autocast"],
        # 換裝後 max 可能變小，把續戰的 hp/sp 夾回上限
        hp=min(snap.hp, derived["max_hp"]) if snap.hp is not None else 0,
        sp=min(snap.sp, derived["max_sp"]) if snap.sp is not None else 0,
    )
