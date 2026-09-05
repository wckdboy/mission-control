# dev smoke test — exercises core API against sqlite via TestClient
import os
import tempfile
import threading
import time

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["OPERATOR_PASSWORD"] = "test-password"
os.environ["AGENT_SEEDS"] = "jaeger=JAEGER=Data,percival=Percival=Evidence"

from fastapi.testclient import TestClient

from mission_control.main import app, seed_defaults
from mission_control.db import init_db

init_db()
seed_defaults()
client = TestClient(app)


def main() -> None:
    # login
    r = client.post("/api/auth/login", json={"username": "doomerius", "password": "test-password"})
    assert r.status_code == 200, r.text
    jar = r.cookies

    # mission
    r = client.post("/api/missions", json={"name": "OpenEndo", "slug": "openendo", "description": "mission"}, cookies=jar)
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    assert client.get("/api/missions", cookies=jar).status_code == 200

    # agents + membership
    agents = client.get("/api/agents", cookies=jar).json()
    jid = next(a["id"] for a in agents if a["handle"] == "jaeger")
    assert client.post(f"/api/missions/{mid}/agents/{jid}", cookies=jar).status_code == 200

    # operator-created task assigned to jaeger (no webhook -> no dispatch)
    r = client.post(
        f"/api/missions/{mid}/tasks",
        json={"title": "Fetch trials", "description": "Pull new trials", "assignee_agent_id": jid},
        cookies=jar,
    )
    assert r.status_code == 200, r.text
    tid = r.json()["id"]

    # agent token
    from mission_control.issue_token import main as issue
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import sys
        sys.argv = ["x", "jaeger"]
        issue()
    token = buf.getvalue().split("token=")[1].strip()
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/agent/me", headers=headers).status_code == 200
    r = client.patch(f"/api/agent/tasks/{tid}", json={"state": "in_progress"}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/agent/tasks/{tid}/request-approval", json={"note": "please check"}, headers=headers)
    assert r.status_code == 200, r.text
    r = client.post(f"/api/agent/tasks/{tid}/comments", json={"text": "done, see artifact"}, headers=headers)
    assert r.status_code == 200, r.text
    import io as _io
    r = client.post(
        f"/api/agent/tasks/{tid}/artifacts",
        headers=headers,
        files={"file": ("result.md", b"# findings\n- a", "text/markdown")},
        data={"kind": "file"},
    )
    assert r.status_code == 200, r.text
    art_id = r.json()["id"]

    # approvals list + operator decide
    approvals = client.get(f"/api/missions/{mid}/approvals", cookies=jar).json()
    assert len(approvals) == 1
    assert client.post(f"/api/approvals/{approvals[0]['id']}/decide", json={"approve": True, "note": "ok"}, cookies=jar).status_code == 200

    # timeline has events; artifact downloadable
    evs = client.get(f"/api/missions/{mid}/events", cookies=jar).json()
    types = [e["event_type"] for e in evs]
    for want in ["mission.created", "task.created", "task.state_change", "approval.requested", "comment", "artifact.added", "approval.decided"]:
        assert want in types, (want, types)
    assert client.get(f"/api/artifacts/{art_id}/download", cookies=jar).status_code == 200

    # ---- operator interjection surface (drives the board UI) ----
    # second agent, for drag-to-reassign
    pid = next(a["id"] for a in client.get("/api/agents", cookies=jar).json() if a["handle"] == "percival")
    assert client.post(f"/api/missions/{mid}/agents/{pid}", cookies=jar).status_code == 200

    # reassign (board drag -> PATCH assignee_agent_id) and confirm it stuck
    r = client.patch(f"/api/tasks/{tid}", json={"assignee_agent_id": pid}, cookies=jar)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/tasks/{tid}", cookies=jar).json()["assignee"] == "percival"

    # state edit from the detail panel
    assert client.patch(f"/api/tasks/{tid}", json={"state": "review"}, cookies=jar).status_code == 200

    # operator comment + nudge (interject mid-build)
    assert client.post(f"/api/tasks/{tid}/comments", json={"text": "tighten the citation format"}, cookies=jar).status_code == 200
    r = client.post(f"/api/tasks/{tid}/nudge", json={"text": "status?"}, cookies=jar)
    assert r.status_code == 200, r.text

    # the board's serialized task must expose what the UI binds to
    t = client.get(f"/api/tasks/{tid}", cookies=jar).json()
    for field in ["assignee", "assignee_agent_id", "state", "title"]:
        assert field in t, (field, sorted(t))

    evs2 = [e["event_type"] for e in client.get(f"/api/missions/{mid}/events", cookies=jar).json()]
    for want in ["task.reassigned", "operator.nudge"]:
        assert want in evs2, (want, sorted(set(evs2)))

    # live feed: authed websocket accepts a room connection
    # (message delivery is verified post-deploy against the real uvicorn
    #  server — TestClient's portal cannot faithfully multiplex WS + sync HTTP)
    client.cookies.update(jar)
    with client.websocket_connect(f"/ws/mission:{mid}") as ws:
        ws.send_text("ping")

    # roster cleanup: DELETE agent (removes membership, nulls references)
    r = client.delete(f"/api/agents/{pid}", cookies=jar)
    assert r.status_code == 200, r.text
    assert r.json()["removed"] == "percival"
    handles = [a["handle"] for a in client.get("/api/agents", cookies=jar).json()]
    assert "percival" not in handles, handles

    print("SMOKE OK — mission/task/agent/approval/artifact/timeline all green")
    print("INTERJECT OK — reassign/state/comment/nudge all green")


if __name__ == "__main__":
    main()
