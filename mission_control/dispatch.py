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


async def dispatch_task(db: Session, task: Task) -> bool:
    """POST the task to the assignee agent's Hermes webhook, if configured."""
    if not task.assignee_agent_id:
        return False
    agent = db.get(Agent, task.assignee_agent_id)
    if not agent or not agent.webhook_url:
        return False
    mission = db.get(Mission, task.mission_id)
    payload = {
        "type": "mission.task_dispatch",
        "mission": _mission_brief(db, mission),
        "task": _task_brief(task),
        "agent_handle": agent.handle,
        "instructions": (
            "You are assigned a task in Mission Control. Work it with your tools. "
            "Report progress and completion back to Mission Control using your agent "
            f"endpoint at {settings.public_base_url}/api/agent — authenticate with your "
            "agent token. Update task state as you work (in_progress, review, done), "
            "post artifacts and request human approval when required."
        ),
    }
    try:
        await run_in_threadpool(
            lambda: httpx.post(agent.webhook_url, json=payload, timeout=30)
        )
        return True
    except Exception:
        return False
