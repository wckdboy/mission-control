import datetime as dt

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|paused|archived
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    agents: Mapped[list["Agent"]] = relationship(secondary="mission_agents", overlaps="missions")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    handle: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(20), default="offline")  # idle|working|awaiting_approval|offline
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    missions: Mapped[list["Mission"]] = relationship(secondary="mission_agents", overlaps="agents")


class MissionAgent(Base):
    __tablename__ = "mission_agents"

    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    assignee_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    state: Mapped[str] = mapped_column(String(20), default="todo", index=True)  # todo|in_progress|review|blocked|done
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    mission: Mapped["Mission"] = relationship(back_populates="tasks")
    assignee: Mapped["Agent | None"] = relationship()
    approvals: Mapped[list["Approval"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", foreign_keys="Approval.task_id"
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    actor_type: Mapped[str] = mapped_column(String(10))  # human|agent|system
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # agent id or None (operator/system)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="file")  # file|render|code_ref|link
    name: Mapped[str] = mapped_column(String(300))
    storage_path: Mapped[str] = mapped_column(String(600), default="")
    mime: Mapped[str] = mapped_column(String(120), default="")
    size: Mapped[int] = mapped_column(Integer, default=0)
    preview_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    produced_by_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    requested_by_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    note: Mapped[str] = mapped_column(Text, default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship(back_populates="approvals", foreign_keys=[task_id])
