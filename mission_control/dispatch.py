from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from .config import settings
from .models import Agent, Mission, Task

import httpx


def _mission_brief(db: Session, mission: Mission) -> dict:
    return {
        "id": mission.id,
        "slug": mission.slug,
        "name": mission.name,
        "description": mission.description,
    }


def _task_brief(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "state": task.state,
    }


def _report_hint(mission_id: int) -> str:
    return (
        f"Report back to RoundTable at {settings.public_base_url}/api/agent "
        "using your agent bearer token: PATCH /agent/tasks/{id} to change state, "
        "POST /agent/tasks/{id}/comments to narrate progress, "
        "POST /agent/tasks/{id}/request-approval before risky or irreversible steps, "
        "POST /agent/tasks/{id}/artifacts to ship results. "
        f"Mission context: GET /agent/missions/{mission_id}/context."
    )


async def _post(url: str, payload: dict) -> bool:
    """Fire a webhook. Returns True only on a 2xx response."""
    try:
        res = await run_in_threadpool(lambda: httpx.post(url, json=payload, timeout=30))
        return 200 <= res.status_code < 300
    except Exception:
        return False


async def notify_agent(webhook_url: str, payload: dict) -> bool:
    """Deliver an out-of-band message to an agent's Hermes webhook.

    Used for operator interjections, approval decisions and nudges — without
    this, agents are blind to everything the human does after dispatch.
    """
    if not webhook_url:
        return False
    return await _post(webhook_url, payload)


def build_dispatch_payload(db: Session, task: Task, agent: Agent) -> dict:
    mission = db.get(Mission, task.mission_id)
    return {
        "type": "mission.task_dispatch",
        "mission": _mission_brief(db, mission),
        "task": _task_brief(task),
        "agent_handle": agent.handle,
        "instructions": (
            "You are assigned a task in RoundTable, a shared workspace where several "
            "agents and a human orchestrator collaborate on one mission. Work the task "
            "with your tools. Narrate meaningful progress as comments so the human can "
            "follow along, and stop for approval before anything destructive or "
            "irreversible. " + _report_hint(task.mission_id)
        ),
    }


def build_interjection_payload(
    db: Session, task: Task, agent: Agent, kind: str, text: str, extra: dict | None = None
) -> dict:
    """kind: operator.comment | approval.decided | operator.nudge | task.reassigned."""
    mission = db.get(Mission, task.mission_id)
    payload = {
        "type": kind,
        "mission": _mission_brief(db, mission),
        "task": _task_brief(task),
        "agent_handle": agent.handle,
        "message": text,
        "instructions": (
            "This is an out-of-band message from the human orchestrator about a task "
            "you own in RoundTable. Take it as authoritative and adjust course. "
            + _report_hint(task.mission_id)
        ),
    }
    if extra:
        payload.update(extra)
    return payload


async def dispatch_task(db: Session, task: Task) -> bool:
    """POST the task to the assignee agent's Hermes webhook, if configured."""
    if not task.assignee_agent_id:
        return False
    agent = db.get(Agent, task.assignee_agent_id)
    if not agent or not agent.webhook_url:
        return False
    return await _post(agent.webhook_url, build_dispatch_payload(db, task, agent))
