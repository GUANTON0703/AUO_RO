import json
from dataclasses import dataclass, field
from pathlib import Path

from shared.content import (
    CardDef, ElementChart, EquipmentDef, ItemDef, JobDef, MapDef,
    MonsterDef, MvpDef, RecipeDef, SkillDef,
)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class ContentError(Exception):
    pass


def _read(path: Path) -> list | dict:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class Content:
    monsters: dict[str, MonsterDef] = field(default_factory=dict)
    mvps: dict[str, MvpDef] = field(default_factory=dict)
    maps: dict[str, MapDef] = field(default_factory=dict)
    jobs: dict[str, JobDef] = field(default_factory=dict)
    skills: dict[str, SkillDef] = field(default_factory=dict)
    equipment: dict[str, EquipmentDef] = field(default_factory=dict)
    cards: dict[str, CardDef] = field(default_factory=dict)
    items: dict[str, ItemDef] = field(default_factory=dict)
    recipes: dict[str, RecipeDef] = field(default_factory=dict)
    element_chart: ElementChart = field(default_factory=ElementChart)

    def get_monster(self, mid: str) -> MonsterDef:
        if mid in self.monsters:
            return self.monsters[mid]
        return self.mvps[mid]

    def get_map(self, map_id: str) -> MapDef:
        return self.maps[map_id]

    def get_job(self, job_id: str) -> JobDef:
        return self.jobs[job_id]

    def monsters_on_map(self, map_id: str) -> list[MonsterDef]:
        return [self.get_monster(m) for m in self.maps[map_id].monster_ids]

    def job_ancestry(self, job_id: str) -> set[str]:
        """回傳這個職業自己 + 所有前職的 id 集合（防環）。"""
        seen: set[str] = set()
        j = self.jobs.get(job_id)
        while j and j.id not in seen:
            seen.add(j.id)
            j = self.jobs.get(j.parent_id) if j.parent_id else None
        return seen


def _index(models, kind: str, key="id") -> dict:
    out: dict = {}
    for m in models:
        k = getattr(m, key)
        if k in out:
            raise ContentError(f"{kind} 有重複 id：{k}")
        out[k] = m
    return out


def load_content(data_dir: Path | None = None) -> Content:
    d = Path(data_dir) if data_dir else _DATA_DIR
    try:
        c = Content(
            monsters=_index((MonsterDef(**x) for x in _read(d / "monsters.json")), "monsters"),
            mvps=_index((MvpDef(**x) for x in _read(d / "mvps.json")), "mvps"),
            maps=_index((MapDef(**x) for x in _read(d / "maps.json")), "maps"),
            jobs=_index((JobDef(**x) for x in _read(d / "jobs.json")), "jobs"),
            skills=_index((SkillDef(**x) for x in _read(d / "skills.json")), "skills"),
            equipment=_index((EquipmentDef(**x) for x in _read(d / "equipment.json")), "equipment"),
            cards=_index((CardDef(**x) for x in _read(d / "cards.json")), "cards"),
            items=_index((ItemDef(**x) for x in _read(d / "items.json")), "items"),
            recipes=_index((RecipeDef(**x) for x in _read(d / "recipes.json")), "recipes"),
            element_chart=ElementChart(**_read(d / "element_chart.json")),
        )
    except ContentError:
        raise
    except Exception as exc:
        raise ContentError(f"資料載入失敗：{exc}") from exc

    _check_integrity(c)
    return c


def _check_integrity(c: Content) -> None:
    overlap = set(c.monsters) & set(c.mvps)
    if overlap:
        raise ContentError(f"怪物與 MVP 共用 id：{sorted(overlap)}")
    all_monsters = set(c.monsters) | set(c.mvps)
    for m in c.maps.values():
        for mid in m.monster_ids:
            if mid not in all_monsters:
                raise ContentError(f"地圖 {m.id} 引用不存在的怪物 {mid}")
        if m.mvp_id and m.mvp_id not in c.mvps:
            raise ContentError(f"地圖 {m.id} 引用不存在的 MVP {m.mvp_id}")
    for mvp in c.mvps.values():
        if mvp.home_map_id not in c.maps:
            raise ContentError(f"MVP {mvp.id} 的 home_map_id {mvp.home_map_id} 不存在")
    for card in c.cards.values():
        if card.monster_id not in all_monsters:
            raise ContentError(f"卡片 {card.id} 對應不存在的怪物 {card.monster_id}")
    for job in c.jobs.values():
        for sid in job.skill_ids:
            if sid not in c.skills:
                raise ContentError(f"職業 {job.id} 引用不存在的技能 {sid}")
        if job.parent_id and job.parent_id not in c.jobs:
            raise ContentError(f"職業 {job.id} 的 parent_id {job.parent_id} 不存在")
    for recipe in c.recipes.values():
        if recipe.result_item not in c.items:
            raise ContentError(f"配方 {recipe.id} 的產出 {recipe.result_item} 不存在")
        for mat_id in recipe.materials:
            if mat_id not in c.items:
                raise ContentError(f"配方 {recipe.id} 的材料 {mat_id} 不存在")
    _ELEMENTS = {"neutral", "water", "earth", "fire", "wind", "poison",
                 "holy", "shadow", "ghost", "undead"}
    for skill in c.skills.values():
        if skill.job_id not in c.jobs:
            raise ContentError(f"技能 {skill.id} 屬於不存在的職業 {skill.job_id}")
        for req_id in skill.requires:
            if req_id not in c.skills:
                raise ContentError(f"技能 {skill.id} 的前置 {req_id} 不存在")
            # 前置必須是同職業或前職鏈上的技能
            chain = {skill.job_id}
            j = c.jobs.get(skill.job_id)
            while j and j.parent_id:
                chain.add(j.parent_id)
                j = c.jobs.get(j.parent_id)
            if c.skills[req_id].job_id not in chain:
                raise ContentError(
                    f"技能 {skill.id} 的前置 {req_id} 不在本職或前職鏈上"
                )
    for eq in c.equipment.values():
        if eq.element not in _ELEMENTS:
            raise ContentError(f"裝備 {eq.id} 的 element {eq.element} 不合法")
        for jid in eq.job_ids:
            if jid not in c.jobs:
                raise ContentError(f"裝備 {eq.id} 限定不存在的職業 {jid}")
    for drop_owner in list(c.monsters.values()) + list(c.mvps.values()):
        for d in drop_owner.drops:
            if d.item_id not in c.items and d.item_id not in c.equipment and d.item_id not in c.cards:
                raise ContentError(f"{drop_owner.id} 掉落不存在的物品 {d.item_id}")
