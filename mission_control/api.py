import os
import uuid as uuidlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .deps import current_agent, current_operator
from .dispatch import dispatch_task
from .events import record_event
from .models import Agent, Approval, Artifact, Event, Mission, Task
from .security import check_operator_password, make_session_token, new_agent_token, sha256
from .serializers import agent_out, approval_out, artifact_out, mission_out, task_out

router = APIRouter(prefix="/api")
TASK_STATES = {"todo", "in_progress", "review", "blocked", "done"}


def _get_mission(db: Session, mission_id: int) -> Mission:
    mission = db.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


def _get_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _touch_agent(db: Session, agent: Agent) -> None:
    agent.last_seen_at = datetime.now(timezone.utc)
    db.commit()


# ── auth ────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginBody, response=None):
    from fastapi.responses import JSONResponse

    if body.username != settings.operator_username or not check_operator_password(body.password):
        raise HTTPException(status_code=401, detail="Bad credentials")
    resp = JSONResponse({"ok": True, "user": settings.operator_username})
    resp.set_cookie(
        "session",
        make_session_token(),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return resp


@router.post("/auth/logout")
def logout(response=None):
    from fastapi.responses import JSONResponse

    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp


# ── missions ────────────────────────────────────────────────────────────────

class MissionBody(BaseModel):
    name: str
    slug: str = Field(pattern=r"^[a-z0-9-]{1,80}$")
    description: str = ""


@router.get("/missions", dependencies=[Depends(current_operator)])
def list_missions(db: Session = Depends(get_db)):
    return [mission_out(m) for m in db.query(Mission).order_by(Mission.created_at.desc()).all()]


@router.post("/missions", dependencies=[Depends(current_operator)])
def create_mission(body: MissionBody, db: Session = Depends(get_db)):
    if db.query(Mission).filter(Mission.slug == body.slug).first():
        raise HTTPException(status_code=409, detail="Slug already in use")
    m = Mission(name=body.name, slug=body.slug, description=body.description)
    db.add(m)
    db.commit()
    db.refresh(m)
    record_event(db, m.id, "human", None, "mission.created", {"name": m.name})
    return mission_out(m)


@router.get("/missions/{mission_id}", dependencies=[Depends(current_operator)])
def get_mission(mission_id: int, db: Session = Depends(get_db)):
    return mission_out(_get_mission(db, mission_id))


@router.patch("/missions/{mission_id}", dependencies=[Depends(current_operator)])
def update_mission(mission_id: int, body: dict, db: Session = Depends(get_db)):
    m = _get_mission(db, mission_id)
    for key in ("name", "description", "status"):
        if key in body:
            setattr(m, key, body[key])
    db.commit()
    db.refresh(m)
    record_event(db, m.id, "human", None, "mission.updated", {"changes": body})
    return mission_out(m)


# ── agents / membership ─────────────────────────────────────────────────────

@router.get("/agents", dependencies=[Depends(current_operator)])
def list_agents(db: Session = Depends(get_db)):
    return [agent_out(a) for a in db.query(Agent).order_by(Agent.handle).all()]


@router.patch("/agents/{agent_id}", dependencies=[Depends(current_operator)])
def update_agent(agent_id: int, body: dict, db: Session = Depends(get_db)):
    a = db.get(Agent, agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    if "webhook_url" in body:
        a.webhook_url = body["webhook_url"] or None
    if "role" in body:
        a.role = body["role"]
    db.commit()
    db.refresh(a)
    return agent_out(a)


@router.post("/missions/{mission_id}/agents/{agent_id}", dependencies=[Depends(current_operator)])
def add_agent_to_mission(mission_id: int, agent_id: int, db: Session = Depends(get_db)):
    m = _get_mission(db, mission_id)
    a = db.get(Agent, agent_id)
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    if a not in m.agents:
        m.agents.append(a)
        db.commit()
        record_event(db, m.id, "human", None, "agent.added", {"agent": a.handle})
    return mission_out(m)


@router.delete("/missions/{mission_id}/agents/{agent_id}", dependencies=[Depends(current_operator)])
def remove_agent_from_mission(mission_id: int, agent_id: int, db: Session = Depends(get_db)):
    m = _get_mission(db, mission_id)
    a = db.get(Agent, agent_id)
    if a and a in m.agents:
        m.agents.remove(a)
        db.commit()
        record_event(db, m.id, "human", None, "agent.removed", {"agent": a.handle})
    return mission_out(m)


# ── tasks ───────────────────────────────────────────────────────────────────

class TaskBody(BaseModel):
    title: str
    description: str = ""
    assignee_agent_id: int | None = None
    parent_id: int | None = None


@router.get("/missions/{mission_id}/tasks", dependencies=[Depends(current_operator)])
def list_tasks(mission_id: int, db: Session = Depends(get_db)):
    _get_mission(db, mission_id)
    tasks = (
        db.query(Task)
        .filter(Task.mission_id == mission_id)
        .order_by(Task.created_at.desc())
        .all()
    )
    return [task_out(t) for t in tasks]


@router.post("/missions/{mission_id}/tasks", dependencies=[Depends(current_operator)])
def create_task(
    mission_id: int,
    body: TaskBody,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    m = _get_mission(db, mission_id)
    if body.assignee_agent_id:
        agent = db.get(Agent, body.assignee_agent_id)
        if not agent or agent not in m.agents:
            raise HTTPException(status_code=400, detail="Assignee not in mission")
    t = Task(
        mission_id=m.id,
        title=body.title,
        description=body.description,
        assignee_agent_id=body.assignee_agent_id,
        parent_id=body.parent_id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    if body.assignee_agent_id:
        agent = db.get(Agent, body.assignee_agent_id)
        agent.status = "idle"
        db.commit()
    record_event(
        db,
        m.id,
        "human",
        None,
        "task.created",
        {"task_id": t.id, "title": t.title, "assignee": t.assignee.handle if t.assignee else None},
        task_id=t.id,
    )
    if body.assignee_agent_id:
        background.add_task(dispatch_task, db, t)
    return task_out(t)


@router.get("/tasks/{task_id}", dependencies=[Depends(current_operator)])
def get_task(task_id: int, db: Session = Depends(get_db)):
    return task_out(_get_task(db, task_id))


@router.patch("/tasks/{task_id}", dependencies=[Depends(current_operator)])
def operator_update_task(task_id: int, body: dict, db: Session = Depends(get_db)):
    t = _get_task(db, task_id)
    old = t.state
    if "state" in body:
        if body["state"] not in TASK_STATES:
            raise HTTPException(status_code=400, detail="Bad state")
        t.state = body["state"]
    if "assignee_agent_id" in body:
        t.assignee_agent_id = body["assignee_agent_id"]
    db.commit()
    db.refresh(t)
    if t.state != old:
        record_event(
            db, t.mission_id, "human", None, "task.state_change",
            {"task_id": t.id, "from": old, "to": t.state}, task_id=t.id,
        )
    return task_out(t)


@router.post("/tasks/{task_id}/comments", dependencies=[Depends(current_operator)])
def operator_comment(task_id: int, body: dict, db: Session = Depends(get_db)):
    t = _get_task(db, task_id)
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty comment")
    record_event(
        db, t.mission_id, "human", None, "comment",
        {"task_id": t.id, "text": text}, task_id=t.id,
    )
    return {"ok": True}


# ── timeline ────────────────────────────────────────────────────────────────

@router.get("/missions/{mission_id}/events", dependencies=[Depends(current_operator)])
def mission_events(mission_id: int, db: Session = Depends(get_db)):
    _get_mission(db, mission_id)
    from .serializers import event_out

    evs = (
        db.query(Event)
        .filter(Event.mission_id == mission_id)
        .order_by(Event.created_at.asc())
        .all()
    )
    return [event_out(e) for e in evs]


# ── approvals ───────────────────────────────────────────────────────────────

@router.get("/missions/{mission_id}/approvals", dependencies=[Depends(current_operator)])
def list_approvals(mission_id: int, status: str = "pending", db: Session = Depends(get_db)):
    _get_mission(db, mission_id)
    q = db.query(Approval).join(Task).filter(
        Task.mission_id == mission_id, Approval.status == status
    )
    return [approval_out(a) for a in q.order_by(Approval.created_at.desc()).all()]


class DecideBody(BaseModel):
    approve: bool
    note: str = ""


@router.post("/approvals/{approval_id}/decide", dependencies=[Depends(current_operator)])
def decide_approval(approval_id: int, body: DecideBody, db: Session = Depends(get_db)):
    ap = db.get(Approval, approval_id)
    if not ap:
        raise HTTPException(status_code=404, detail="Approval not found")
    if ap.status != "pending":
        raise HTTPException(status_code=400, detail="Already decided")
    ap.status = "approved" if body.approve else "rejected"
    ap.decision_note = body.note
    ap.decided_at = datetime.now(timezone.utc)
    db.commit()
    task = _get_task(db, ap.task_id)
    record_event(
        db, task.mission_id, "human", None, "approval.decided",
        {"approval_id": ap.id, "task_id": task.id, "approved": body.approve, "note": body.note},
        task_id=task.id,
    )
    return approval_out(ap)


# ── artifacts (operator view) ───────────────────────────────────────────────

@router.get("/missions/{mission_id}/artifacts", dependencies=[Depends(current_operator)])
def list_artifacts(mission_id: int, db: Session = Depends(get_db)):
    _get_mission(db, mission_id)
    arts = (
        db.query(Artifact)
        .filter(Artifact.mission_id == mission_id)
        .order_by(Artifact.created_at.desc())
        .all()
    )
    return [artifact_out(a) for a in arts]


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: int, db: Session = Depends(get_db)):
    a = db.get(Artifact, artifact_id)
    if not a or not a.storage_path or not Path(a.storage_path).exists():
        raise HTTPException(status_code=404, detail="Artifact file missing")
    return FileResponse(a.storage_path, filename=a.name, media_type=a.mime or "application/octet-stream")


# ── agent endpoints (bearer token) ──────────────────────────────────────────

@router.get("/agent/me")
def agent_me(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)):
    _touch_agent(db, agent)
    return agent_out(agent)


@router.get("/agent/missions")
def agent_missions(agent: Agent = Depends(current_agent), db: Session = Depends(get_db)):
    _touch_agent(db, agent)
    return [mission_out(m) for m in sorted(agent.missions, key=lambda x: x.slug)]


@router.get("/agent/missions/{mission_id}/context")
def agent_mission_context(mission_id: int, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)):
    m = _get_mission(db, mission_id)
    if agent not in m.agents:
        raise HTTPException(status_code=403, detail="Not a member")
    tasks = [task_out(t) for t in db.query(Task).filter(Task.mission_id == m.id).order_by(Task.id).all()]
    return {"mission": mission_out(m), "tasks": tasks}


@router.get("/agent/tasks")
def agent_tasks(
    state: str | None = None,
    agent: Agent = Depends(current_agent),
    db: Session = Depends(get_db),
):
    _touch_agent(db, agent)
    q = db.query(Task).filter(Task.assignee_agent_id == agent.id)
    if state:
        q = q.filter(Task.state == state)
    return [task_out(t) for t in q.order_by(Task.created_at.desc()).all()]


class AgentTaskUpdate(BaseModel):
    state: str


@router.patch("/agent/tasks/{task_id}")
def agent_update_task(
    task_id: int,
    body: AgentTaskUpdate,
    agent: Agent = Depends(current_agent),
    db: Session = Depends(get_db),
):
    t = _get_task(db, task_id)
    if t.assignee_agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Not your task")
    if body.state not in TASK_STATES:
        raise HTTPException(status_code=400, detail="Bad state")
    old = t.state
    t.state = body.state
    agent.status = {"in_progress": "working", "review": "awaiting_approval"}.get(body.state, "idle")
    db.commit()
    db.refresh(t)
    record_event(
        db, t.mission_id, "agent", agent.id, "task.state_change",
        {"task_id": t.id, "from": old, "to": t.state, "by": agent.handle}, task_id=t.id,
    )
    return task_out(t)


@router.post("/agent/tasks/{task_id}/comments")
def agent_comment(task_id: int, body: dict, agent: Agent = Depends(current_agent), db: Session = Depends(get_db)):
    t = _get_task(db, task_id)
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty comment")
    record_event(
        db, t.mission_id, "agent", agent.id, "comment",
        {"task_id": t.id, "text": text, "by": agent.handle}, task_id=t.id,
    )
    return {"ok": True}


@router.post("/agent/tasks/{task_id}/request-approval")
def agent_request_approval(
    task_id: int,
    body: dict,
    agent: Agent = Depends(current_agent),
    db: Session = Depends(get_db),
):
    t = _get_task(db, task_id)
    if t.assignee_agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Not your task")
    ap = Approval(
        task_id=t.id,
        requested_by_agent_id=agent.id,
        note=(body.get("note") or ""),
    )
    db.add(ap)
    t.state = "review"
    agent.status = "awaiting_approval"
    db.commit()
    db.refresh(ap)
    record_event(
        db, t.mission_id, "agent", agent.id, "approval.requested",
        {"approval_id": ap.id, "task_id": t.id, "note": ap.note, "by": agent.handle}, task_id=t.id,
    )
    return approval_out(ap)


@router.post("/agent/tasks/{task_id}/artifacts")
async def agent_upload_artifact(
    task_id: int,
    file: UploadFile = File(...),
    kind: str = Form("file"),
    name: str | None = Form(None),
    agent: Agent = Depends(current_agent),
    db: Session = Depends(get_db),
):
    t = _get_task(db, task_id)
    if t.assignee_agent_id != agent.id:
        raise HTTPException(status_code=403, detail="Not your task")
    content = await file.read()
    mission_dir = Path(settings.data_dir) / "missions" / str(t.mission_id)
    mission_dir.mkdir(parents=True, exist_ok=True)
    filename = name or file.filename or f"{uuidlib.uuid4().hex}"
    safe = Path(filename).name
    storage = mission_dir / f"{uuidlib.uuid4().hex[:8]}-{safe}"
    storage.write_bytes(content)
    art = Artifact(
        mission_id=t.mission_id,
        task_id=t.id,
        kind=kind,
        name=safe,
        storage_path=str(storage),
        mime=file.content_type or "application/octet-stream",
        size=len(content),
        produced_by_agent_id=agent.id,
    )
    db.add(art)
    db.commit()
    db.refresh(art)
    record_event(
        db, t.mission_id, "agent", agent.id, "artifact.added",
        {"artifact_id": art.id, "task_id": t.id, "name": art.name, "kind": art.kind, "by": agent.handle},
        task_id=t.id,
    )
    return artifact_out(art)
