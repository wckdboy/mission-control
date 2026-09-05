# hermes/

Hermes integration lives here:

- `docs/agent-integration.md` — dispatch webhook contract + agent API (working now)
- Planned: `hermes_plugins.roundtable` Hermes plugin (tools + presence heartbeat)

See the Hermes "Build a Hermes Plugin" developer guide when implementing.

## MVP: poll-based dispatch (live 2026-09-05)

Push webhooks are the future; the MVP loop is **polling**, so no agent
gateway needs a public inbound port:

1. Operator issues the agent a token: `POST /api/agents/{id}/issue-token` → store
   in the agent's `~/.hermes/.env` as `RT_ROUNDTABLE_TOKEN`.
2. The agent runs a recurring Hermes cron (every 15 min) that polls
   `GET /api/agent/tasks?state=todo` with the token, works any assigned
   task, and reports via the agent API (PATCH state, comments, artifacts,
   request-approval). See GALAHAD's `rt-mission-poll-galahad` job as the
   reference prompt.
3. The operator sees live progress on the board (WebSocket timeline) with no
   extra infra. `agent.status`/`last_seen_at` update as agents call `/agent/me`
   (presence heartbeat — include it in the poll loop).

Server-side dispatch (`POST` to `agent.webhook_url` on task create/assign)
already exists and will take over when Hermes webhook endpoints are exposed.
