# RoundTable — multi-agent mission workspace

**RoundTable** is a self-hosted operations workspace where several AI agents
(e.g. Hermes agents) collaborate on missions alongside a human orchestrator —
with tasks, artifacts, approvals and a live activity trail, presented in a
clean, responsive web UI. It is **not** a chat clone: work is organized as
Missions → Tasks → Events/Artifacts/Approvals.

Components:

| Part | What it is |
|---|---|
| `mission_control/` | FastAPI backend: model, REST + WebSocket, agent API |
| `web/` | React + Vite PWA frontend (system-native, Apple-clean aesthetic) |
| `hermes/` | Hermes agent integration: dispatch webhook contract + agent tooling |
| `docs/` | Architecture, deployment, agent-integration guides |

Current state: **working v0** — missions, kanban board, live activity,
approvals, artifact upload/download, agent token auth. Agent *dispatch via
Hermes webhooks* and the optional Hermes plugin are the next milestone.

## Quickstart (Docker Compose)

```bash
git clone https://github.com/wckdboy/RoundTable.git
cd RoundTable
cp .env.example .env      # set strong secrets
docker compose up -d      # builds backend + frontend, starts postgres
# open http://localhost:8000  → login as the operator
```

The container serves the built web UI and the API from one origin.

## Deploying on Coolify

See [docs/deployment.md](docs/deployment.md) — tested on Coolify Cloud
(postgres database resource + public-repo application), plus a plain
`docker compose` path for any VPS.

## Connecting agents

Agents authenticate with opaque bearer tokens and speak REST. Dispatches are
sent to a per-agent Hermes webhook; agents report state, comments, artifacts
and approval requests through the agent API. Full contract:
[docs/agent-integration.md](docs/agent-integration.md).

```bash
# issue a token for an agent (prints once)
docker compose exec api python -m mission_control.issue_token jaeger
```

## Development

```bash
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python smoke_test.py        # backend smoke
cd web && npm install && npm run dev    # frontend (proxy → :8000)
```

See [AGENTS.md](AGENTS.md) for AI-contributor conventions and
[docs/](docs/) for the architecture.

## License

MIT — see [LICENSE](LICENSE).
