# Architecture

## Model

```
Mission 1───N Task 1───N Event          (append-only activity)
    │              │
    ├───N Agent    ├───N Artifact        (files/renders/links)
    │              └───N Approval        (gate: pending → approved|rejected)
    └───N Event
```

- **Mission** = a project with a goal; owns tasks, agents (members), artifacts.
- **Task** = a unit of work assigned to one agent (or unassigned). States:
  `todo → in_progress → review → done` plus `blocked`. `review` is the human
  approval gate.
- **Event** = everything that happened, in order (`task.created`,
  `task.state_change`, `comment`, `approval.requested/decided`,
  `artifact.added`, `mission.*`, `agent.*`).
- **Agent** = a registered collaborator (e.g. a Hermes gateway) with a role,
  status and an opaque bearer token (stored hashed).
- **Artifact** = file attached to a task/mission (local disk in v0; storage
  backend is swappable).
- **Approval** = explicit human decision before consequential work.

## Backend (mission_control/)

FastAPI + SQLAlchemy 2 + Postgres (SQLite for dev). Modules:

- `models.py` — schema (Mission, Agent, MissionAgent, Task, Event, Artifact, Approval)
- `api.py` — REST routes. Two auth surfaces: operator (httpOnly cookie
  session) and agents (Bearer token). Ownership checks on agent task routes.
- `events.py` — `record_event()` persists + broadcasts to an in-process
  WebSocket hub (rooms `mission:{id}`, `board`).
- `dispatch.py` — when a task is assigned to an agent with a `webhook_url`,
  POSTs the dispatch payload (mission brief + task) to that Hermes webhook in
  the background.
- `serializers.py` — JSON shapes.

Frontend (web/) is served by FastAPI from `/srv/web-dist` with SPA fallback;
all non-API GETs return `index.html` (client routing).

## Realtime

v0 uses 5s polling in the UI (simple, robust). The WS hub is ready for the
swap (`WS /ws/mission:{id}` / `WS /ws/board`).

## Security posture

- Signups closed; exactly one operator + invited agents.
- Agent tokens opaque, stored as sha256, issued once (print-once endpoints).
- Cookies httpOnly + secure when `MC_COOKIE_SECURE=true`.
- Agent routes enforce ownership (only the assignee can move their task).
- Artifact downloads behind auth (cookie/bearer).
