import asyncio
import json
from typing import Any

from fastapi import WebSocket
from sqlalchemy.orm import Session

from .models import Agent, Event


class RoomHub:
    """Tiny in-process WS hub: rooms are strings; clients get JSON blobs."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        # Endpoints are sync (`def`), so they run in a threadpool with no running
        # loop. The loop is captured at startup so those handlers can still publish.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish_soon(self, room: str, message: dict[str, Any]) -> None:
        """Schedule a publish from any thread. No-op if the loop isn't up yet."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.publish(room, message), loop)

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
    # fire-and-forget publish (safe from threadpool threads: loop bound at startup)
    hub.publish_soon(f"mission:{mission_id}", {"kind": "event", "event": out})
    hub.publish_soon("board", {"kind": "mission.update", "mission_id": mission_id})
    return ev
