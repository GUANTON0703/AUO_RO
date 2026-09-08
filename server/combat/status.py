from dataclasses import dataclass

from server.combat.events import StatusAppliedEvent, StatusExpiredEvent


@dataclass
class Status:
    kind: str          # dot / stat_mod / stun
    name: str
    duration: int
    magnitude: int
    stat: str = ""     # kind=stat_mod 用
    source: str = ""   # 來源技能名（顯示用）


def apply_status(target, status: Status, events: list | None = None) -> None:
    for s in target.statuses:
        if s.name == status.name:
            s.duration = status.duration
            s.magnitude = status.magnitude
            s.source = status.source
            return
    target.statuses.append(status)
    if events is not None:
        events.append(StatusAppliedEvent(actor="", target=target.name,
                                         status=status.name, duration=status.duration))


def tick_statuses(target, events: list) -> None:
    for s in list(target.statuses):
        if s.kind == "dot":
            target.take_damage(s.magnitude)
        s.duration -= 1
        if s.duration <= 0:
            target.statuses.remove(s)
            events.append(StatusExpiredEvent(target=target.name, status=s.name))
