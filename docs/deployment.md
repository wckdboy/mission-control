# Deployment

## Option A — plain Docker Compose (any VPS)

```bash
git clone https://github.com/wckdboy/RoundTable.git
cd RoundTable
cp .env.example .env        # set MC_DB_PASSWORD, MC_OPERATOR_PASSWORD, MC_SESSION_SECRET
docker compose up -d --build
# http://<host>:8000
```

Reverse proxy (Caddy/nginx) in front for TLS; set `MC_PUBLIC_BASE_URL`,
`MC_COOKIE_SECURE=true`, `MC_CORS_ORIGINS=https://your.domain` then redeploy.

## Option B — Coolify Cloud (as run for the Round Table fleet, 2026-09)

1. **Postgres**: New → Database → PostgreSQL on the target server. Note the
   `internal_db_url` from the resource detail (host is the resource uuid).
2. **App**: New → Application → Public Repository:
   - Repo `https://github.com/wckdboy/RoundTable`, branch `main`
   - Build pack **Dockerfile** (`/Dockerfile`), ports `8000`
   - Domain e.g. `missions.example.com`
   - Enable **connect to Docker network** (so it reaches the database by uuid)
3. **Env** (app): as in `.env.example`, plus:
   - `DATABASE_URL=postgresql+psycopg2://<user>:<pw>@<db-uuid>:5432/<db>` from step 1
   - `FRONTEND_DIST=/srv/web-dist` (baked; only needed if you override the image)
4. **Storage**: add a persistent volume mounted at `/srv/data` (artifacts).
5. Deploy. First boot seeds the operator from env and the four agents from
   `MC_AGENT_SEEDS`.

### Issue agent tokens

After first boot (operator login via UI):

```bash
curl -X POST -H "Content-Type: application/json" \
  -b <session-cookie> https://<domain>/api/agents/<id>/issue-token
```

or inside the container: `python -m mission_control.issue_token <handle>`.

## Updating

- Compose: `git pull && docker compose up -d --build`
- Coolify: push to `main` → redeploy (volume + postgres persist).
