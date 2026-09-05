# Mission Control

Custom mission workspace for the Round Table Hermes fleet. Missions → tasks →
events/artifacts/approvals — a structured work surface instead of chat channels.
Backend: FastAPI + Postgres + WebSocket. Frontend: React PWA (next milestone).

Design: `mission-control-design.md` (in the operator workspace).

## Run (dev)

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # edit secrets
./.venv/bin/python -c "from mission_control.main import app"   # smoke import
./.venv/bin/uvicorn mission_control.main:app --reload
```

Smoke test (sqlite, no server needed):

```bash
./.venv/bin/python smoke_test.py   # → SMOKE OK
```

## Agent tokens

Agents authenticate with opaque bearer tokens (stored hashed):

```bash
./.venv/bin/python -m mission_control.issue_token jaeger   # prints ONCE
```

## API sketch

- Operator (cookie session): `POST /api/auth/login`
  - `GET/POST /api/missions`, `POST /api/missions/{id}/tasks` (auto-dispatches to
    assignee webhook when set), `PATCH /api/tasks/{id}`, task comments,
    `GET /api/missions/{id}/events`, approvals list + `POST /api/approvals/{id}/decide`
- Agent (Bearer): `GET /api/agent/me`, `GET /api/agent/tasks`,
  `PATCH /api/agent/tasks/{id}` (state), `POST /api/agent/tasks/{id}/request-approval`,
  `POST /api/agent/tasks/{id}/artifacts` (upload), comments
- Realtime: `WS /ws/board`, `WS /ws/mission:{id}` (event feed)

## Deploy (Coolify/delta)

Compose file in repo runs db+api. Set Coolify envs:
`MC_DB_PASSWORD`, `MC_OPERATOR_PASSWORD`, `MC_SESSION_SECRET`, `MC_PUBLIC_BASE_URL`,
then issue per-knight tokens after first boot.
