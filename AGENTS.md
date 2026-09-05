# AGENTS.md — for AI agents contributing to RoundTable

## Ground rules

- **Small diffs, boring tech.** Prefer the simplest correct change. Python
  backend + React frontend; no new frameworks without a documented need.
- **One origin, one truth.** The backend owns state; the UI reads/writes REST +
  WebSocket only. Never duplicate state in the frontend store.
- **Secrets never in git.** `.env*` (except `.env.example`), tokens, keys:
  gitignored. Tokens are hashed at rest (sha256); plaintext is printed once.
- **English only** in code, docs, commits.
- **Smoke before push:** `./.venv/bin/python smoke_test.py` must stay green.
- **Frontend builds are verified by Docker** (`web/` needs no local node):
  `docker compose build` is the gate. Keep JSX dependency-free (no router /
  UI libraries without discussion).
- **Naming:** API entities = Mission, Task, Event, Artifact, Approval, Agent.
  Event types are `snake_case` strings like `task.state_change`.

## Where things live

- `mission_control/` — FastAPI app (`api.py` = routes, `models.py` = schema,
  `events.py` = feed bus, `dispatch.py` = Hermes webhook client)
- `web/src/` — React UI (single `main.jsx` + `styles.css` for now)
- `docs/` — design, deployment, agent contract
- `hermes/` — agent-side integration (webhook payload contract, client notes)

## Task conventions

Task states: `todo → in_progress → review (approval gate) → done`, plus
`blocked`. Adding a state means updating the backend constant, the UI board,
and `docs/agent-integration.md` in one change.

## Reviewer checklist

1. Authz: every new agent route checks `current_agent` ownership (task belongs
   to the agent). Operator routes use the session cookie.
2. Events: every state change records an Event (human/agent/system actor).
3. Secrets: nothing printed except one-time tokens.
