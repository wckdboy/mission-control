# Mission Control — custom workspace (design v0, for approval)

**Decision:** full custom build (web-first PWA, Postgres + WebSocket, own auth &
agent bridge). Mattermost stays running until v0 replaces it, then retired.
Reason: chat/channel model doesn't fit mission-oriented multi-agent work.

## 1. Core model — what replaces "channels/threads"

Objects, not rooms:

| Object | Fields | Notes |
|---|---|---|
| **Mission** | name, slug, description, status (active/paused/archived), owner (human), created_at | Top-level container per project |
| **Agent** | handle (jaeger/percival/…), role, status (idle/working/awaiting_approval/offline), last_seen | Registry of Hermes knights, mission membership |
| **Task** | mission, title, description, assignee (agent or human), state: `todo → in_progress → review → done`, parent (optional subtask), linked artifacts, effort tags | The dispatch unit — an agent works ONE task at a time |
| **Event** | mission, actor (human/agent/system), type, payload, timestamp | Append-only activity: task_state_change, comment, artifact_added, approval_requested, digest |
| **Comment** | event-backed; attach to task or mission | Freeform notes/decisions around a task |
| **Artifact** | mission/task, kind (file/render/code_ref/link), storage ref, preview_url, produced_by | Renders, files, git refs — artifacts attach to tasks, not chat |
| **Approval** | task, requested_by (agent), status (pending/approved/rejected), note | Gate before consequential actions |

Relations: Mission 1—N Task/Event/Artifact; Task 1—N Event/Artifact; Agent N—M Mission.

## 2. Screens (v0, PWA)

1. **Missions** — home: mission cards (status, agent load, latest event, pending approvals badge).
2. **Mission view** — three columns:
   - **Timeline** (left): structured event feed (agent actions, approvals, artifact posts, digests).
   - **Board** (center): kanban of tasks per state, task detail on click (description, comments, artifacts, approval gate).
   - **Roster** (right): agents in this mission, their status/activity; dispatch composer (new task → assignee → task brief).
3. **Task detail** — full conversation per task (comments/events), artifacts with previews, approval approve/reject.
4. Operator auth + settings (agent tokens, webhook URLs).

## 3. Agent protocol (bridge v0 — no Hermes plugin needed)

- **Inbound dispatch:** app calls a **Hermes webhook** endpoint per knight with the task brief (mission context + instruction). Hermes runs the agent.
- **Outbound:** agent reports by `curl` to app REST API with its agent token: create artifact, change task state, request approval, add comment. (Agents already have terminal/HTTP tools; v0 uses a documented "mission client" pattern — a small helper script + skill we ship per knight.)
- GALAHAD (orchestrator) can also drive dispatch through the same API.

## 4. Stack

- Backend: Python **FastAPI** + **Postgres** + WebSocket; SQLite for dev. Runs in Coolify compose on delta.
- Frontend: **React + Vite** PWA (installable; mirrors hermes-webui design language, our own theme).
- Auth v0: single operator login (password, httpOnly cookie) + per-agent bearer tokens.
- Domain: roundtable.blxmp.dk (after Mattermost retires) or a fresh subdomain for parallel run.

## 5. v0 in / out

IN: missions, tasks + states, dispatch via webhook, event timeline, artifacts
(upload + render/image preview), approvals, operator auth, live updates (WS).
OUT (later): native desktop/mobile, multi-operator, channels/DM, notifications
push, search, integrations, Blender runner (P2).

## 6. Milestones

- M1 backend schema + API + WS (~half day)
- M2 frontend skeleton (missions → mission view → task detail) (~day)
- M3 agent bridge + first live dispatch loop (~half day)
- M4 polish + PWA + run parallel with Mattermost, migrate OpenEndo when ready
