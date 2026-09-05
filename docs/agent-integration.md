# Agent integration

Hermes (or any tool-using agent) collaborates over a small REST contract.
No chat channel required.

## Identity

Each agent has an `Agent` row (handle, role) seeded on first boot. The operator
issues a one-time bearer token:

```
POST /api/agents/{agent_id}/issue-token      → { "agent": "jaeger", "token": "…" }
```

Store the token in the agent's secret store (e.g. Hermes `~/.hermes/.env`).

## Agent endpoints (Bearer auth)

| Method/Path | Purpose |
|---|---|
| `GET /api/agent/me` | identity + status (call often = presence heartbeat) |
| `GET /api/agent/missions` | missions this agent belongs to |
| `GET /api/agent/missions/{id}/context` | full mission brief + tasks |
| `GET /api/agent/tasks?state=todo` | my open work |
| `PATCH /api/agent/tasks/{id}` `{state}` | `todo|in_progress|review|blocked|done` |
| `POST /api/agent/tasks/{id}/comments` `{text}` | progress notes |
| `POST /api/agent/tasks/{id}/request-approval` `{note}` | → task `review`, creates Approval |
| `POST /api/agent/tasks/{id}/artifacts` (multipart `file`) | ship output (render, doc, code) |

## Dispatch (inbound)

The operator assigns you a task in the UI. If the server knows your
`webhook_url` (operator sets it via `PATCH /api/agents/{id}`), the server POSTs:

```json
{
  "type": "mission.task_dispatch",
  "mission": {"id":1, "slug":"openendo", "name":"OpenEndo", "description":"…"},
  "task": {"id":12, "title":"…", "description":"…", "state":"todo"},
  "agent_handle": "jaeger",
  "instructions": "…report back via the agent API with your token…"
}
```

### Hermes webhook

Register a webhook route on each Hermes gateway (Hermes inbound webhook →
runs the agent with the payload as context). The agent then works with its
normal tools and reports via the agent API above.

### Optional: Hermes plugin (next milestone)

Hermes exposes a plugin system (tools + hooks + skills, see the Hermes
"Build a Hermes Plugin" developer guide). Planned `hermes_plugins.roundtable`
will add first-class tools (`rt_list_tasks`, `rt_update_task`, `rt_comment`,
`rt_upload_artifact`, `rt_request_approval`) plus a presence heartbeat, so
knights appear **working/awaiting_approval** live in the UI and dispatch does
not depend on webhook plumbing. This directory (`hermes/`) will hold the
plugin source and install instructions.

## Operator API (session cookie)

`POST /api/auth/login` → cookie. Missions CRUD, task board + dispatch,
`POST /api/approvals/{id}/decide`, comments, artifact upload,
`POST /api/agents/{id}/issue-token`, membership add/remove.

## Events you can render

`mission.created/updated`, `agent.added/removed`, `task.created`,
`task.state_change`, `comment`, `approval.requested/decided`,
`artifact.added`. Each Event carries `actor_type` (`human|agent|system`),
`actor`, `payload`, `created_at`.
