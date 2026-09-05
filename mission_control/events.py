import json
from typing import Any

from fastapi import WebSocket
from sqlalchemy.orm import Session

from .models import Agent, Event


class RoomHub:
    """Tiny in-process WS hub: rooms are strings; clients get JSON blobs."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, room: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms.setdefault(room, set()).add(ws)

    def disconnect(self, room: str, ws: WebSocket) -> None:
        self._rooms.get(room, set()).discard(ws)

    async def publish(self, room: str, message: dict[str, Any]) -> None:
        dead = []
        blob = json.dumps(message, default=str)
        for ws in list(self._rooms.get(room, set())):
            try:
                await ws.send_text(blob)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(room, ws)


hub = RoomHub()


def agent_label(db: Session, actor_type: str, actor_id: int | None) -> str:
    if actor_type == "agent" and actor_id is not None:
        agent = db.get(Agent, actor_id)
        if agent:
            return agent.handle
    return "operator" if actor_type == "human" else "system"


def record_event(
    db: Session,
    mission_id: int,
    actor_type: str,
    actor_id: int | None,
    event_type: str,
    payload: dict[str, Any] | None = None,
    task_id: int | None = None,
) -> Event:
    ev = Event(
        mission_id=mission_id,
        task_id=task_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload or {},
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    out = {
        "id": ev.id,
        "mission_id": ev.mission_id,
        "task_id": ev.task_id,
        "actor_type": ev.actor_type,
        "actor": agent_label(db, ev.actor_type, ev.actor_id),
        "event_type": ev.event_type,
        "payload": ev.payload,
        "created_at": ev.created_at.isoformat(),
    }
    # fire-and-forget publish
    import asyncio

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(hub.publish(f"mission:{mission_id}", {"kind": "event", "event": out}))
        loop.create_task(hub.publish("board", {"kind": "mission.update", "mission_id": mission_id}))
    except RuntimeError:
        pass
    return ev
