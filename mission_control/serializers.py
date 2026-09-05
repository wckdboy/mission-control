from datetime import datetime

from .models import Agent, Approval, Artifact, Event, Mission, Task


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def mission_out(m: Mission) -> dict:
    return {
        "id": m.id,
        "slug": m.slug,
        "name": m.name,
        "description": m.description,
        "status": m.status,
        "created_at": _iso(m.created_at),
        "updated_at": _iso(m.updated_at),
        "agents": [agent_out(a, light=True) for a in sorted(m.agents, key=lambda x: x.handle)],
    }


def agent_out(a: Agent, light: bool = False) -> dict:
    out = {
        "id": a.id,
        "handle": a.handle,
        "display_name": a.display_name,
        "role": a.role,
        "status": a.status,
        "last_seen_at": _iso(a.last_seen_at),
    }
    if not light:
        out["webhook_url"] = a.webhook_url
    return out


def task_out(t: Task) -> dict:
    return {
        "id": t.id,
        "mission_id": t.mission_id,
        "title": t.title,
        "description": t.description,
        "state": t.state,
        "assignee_agent_id": t.assignee_agent_id,
        "assignee": t.assignee.handle if t.assignee else None,
        "parent_id": t.parent_id,
        "due_at": _iso(t.due_at),
        "created_at": _iso(t.created_at),
        "updated_at": _iso(t.updated_at),
    }


def event_out(e: Event, actor: str | None = None) -> dict:
    """actor is the display handle; the WS payload includes it, so REST must too."""
    return {
        "id": e.id,
        "mission_id": e.mission_id,
        "task_id": e.task_id,
        "actor_type": e.actor_type,
        "actor_id": e.actor_id,
        "actor": actor
        or ("operator" if e.actor_type == "human" else "system" if e.actor_type == "system" else ""),
        "event_type": e.event_type,
        "payload": e.payload,
        "created_at": _iso(e.created_at),
    }


def artifact_out(a: Artifact, public_base: str = "") -> dict:
    return {
        "id": a.id,
        "mission_id": a.mission_id,
        "task_id": a.task_id,
        "kind": a.kind,
        "name": a.name,
        "mime": a.mime,
        "size": a.size,
        "produced_by_agent_id": a.produced_by_agent_id,
        "preview_url": a.preview_url,
        "download_url": f"/api/artifacts/{a.id}/download",
        "created_at": _iso(a.created_at),
    }


def approval_out(ap: Approval) -> dict:
    return {
        "id": ap.id,
        "task_id": ap.task_id,
        "requested_by_agent_id": ap.requested_by_agent_id,
        "status": ap.status,
        "note": ap.note,
        "decision_note": ap.decision_note,
        "created_at": _iso(ap.created_at),
        "decided_at": _iso(ap.decided_at),
    }
