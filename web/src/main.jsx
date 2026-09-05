import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api";
import "./styles.css";

const COLUMNS = [
  ["todo", "Todo"],
  ["in_progress", "In progress"],
  ["review", "Review"],
  ["blocked", "Blocked"],
  ["done", "Done"],
];

function Login({ onLogin }) {
  const [username, setUsername] = useState("doomerius");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.login(username, password);
      onLogin();
    } catch (ex) {
      setErr(String(ex.message || ex));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-wrap">
      <form className="login card" onSubmit={submit}>
        <div className="brand">MISSION CONTROL</div>
        <div className="muted">Round Table · operations surface</div>
        <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" autoComplete="username" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" autoComplete="current-password" />
        {err && <div className="error">{err}</div>}
        <button className="primary" disabled={busy}>{busy ? "…" : "Enter"}</button>
      </form>
    </div>
  );
}

function Missions({ onOpen }) {
  const [missions, setMissions] = useState([]);
  const [agents, setAgents] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [memberIds, setMemberIds] = useState([]);
  const [err, setErr] = useState(null);

  async function load() {
    try {
      setMissions(await api.missions());
    } catch {}
  }
  useEffect(() => {
    load();
    api.agents().then(setAgents).catch(() => {});
  }, []);

  async function create(e) {
    e.preventDefault();
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "mission";
    try {
      const m = await api.createMission({ name, slug, description: desc });
      for (const aid of memberIds) await api.addAgentToMission(m.id, aid);
      setShowCreate(false);
      setName("");
      setDesc("");
      setMemberIds([]);
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  }

  return (
    <div className="wrap">
      <header className="topbar">
        <div className="brand small">MISSION CONTROL</div>
        <button className="ghost" onClick={() => setShowCreate((v) => !v)}>+ New mission</button>
      </header>
      {showCreate && (
        <form className="card create" onSubmit={create}>
          <h3>New mission</h3>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <textarea placeholder="Description / goal" value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} />
          <div className="chips">
            {agents.map((a) => (
              <label key={a.id} className="chip">
                <input type="checkbox" checked={memberIds.includes(a.id)}
                  onChange={(e) =>
                    setMemberIds(e.target.checked ? [...memberIds, a.id] : memberIds.filter((x) => x !== a.id))
                  } />
                {a.handle}
              </label>
            ))}
          </div>
          {err && <div className="error">{err}</div>}
          <button className="primary">Create</button>
        </form>
      )}
      <main className="mission-grid">
        {missions.map((m) => (
          <div className="card mission-card" key={m.id} onClick={() => onOpen(m.id)} role="button">
            <div className="mission-head">
              <span className={`pill ${m.status}`}>{m.status}</span>
              <span className="slug">{m.slug}</span>
            </div>
            <h2>{m.name}</h2>
            <p>{m.description}</p>
            <div className="roster">{m.agents.map((a) => <span key={a.id} className="agent-tag">{a.handle}</span>)}</div>
          </div>
        ))}
        {!missions.length && <div className="muted empty">No missions yet — create one.</div>}
      </main>
    </div>
  );
}

function EventLine({ ev }) {
  const color = ev.actor_type === "agent" ? "agent" : ev.actor_type === "system" ? "system" : "human";
  const label = ev.payload?.text || ev.payload?.note || ev.payload?.title || ev.event_type;
  const meta = { task: ev.payload?.task_id ? `#${ev.payload.task_id}` : "", by: ev.actor };
  return (
    <div className={`event ${color}`}>
      <span className="ev-badge">{ev.actor_type}</span>
      <div>
        <div className="ev-title">
          <b>{ev.actor}</b> · {ev.event_type} {meta.task && <span className="slug">task {meta.task}</span>}
        </div>
        {label && <div className="ev-body">{typeof label === "string" ? label : JSON.stringify(label)}</div>}
        <div className="ev-time">{new Date(ev.created_at).toLocaleString()}</div>
      </div>
    </div>
  );
}

function MissionView({ missionId, onBack }) {
  const [mission, setMission] = useState(null);
  const [agents, setAgents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [assignee, setAssignee] = useState("");

  async function load() {
    try {
      const [m, a, t, e, ap, ar] = await Promise.all([
        api.mission(missionId),
        api.agents(),
        api.tasks(missionId),
        api.events(missionId),
        api.approvals(missionId),
        api.artifacts(missionId),
      ]);
      setMission(m);
      setAgents(a);
      setTasks(t);
      setEvents(e);
      setApprovals(ap);
      setArtifacts(ar);
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  }
  useEffect(() => {
    load();
    const iv = setInterval(load, 6000);
    return () => clearInterval(iv);
  }, [missionId]);

  async function createTask(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.createTask(missionId, {
        title,
        description: desc,
        assignee_agent_id: assignee ? Number(assignee) : null,
      });
      setTitle("");
      setDesc("");
      setAssignee("");
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    } finally {
      setBusy(false);
    }
  }

  async function move(task, state) {
    await api.setTaskState(task.id, state);
    load();
  }
  async function decide(approval, approve) {
    await api.decideApproval(approval.id, approve, approve ? "" : "rejected by operator");
    load();
  }

  if (!mission) return <div className="wrap">loading…</div>;
  const roster = mission.agents;

  return (
    <div className="wrap">
      <header className="topbar">
        <button className="ghost" onClick={onBack}>← Missions</button>
        <div className="brand small">{mission.name}</div>
        <span className={`pill ${mission.status}`}>{mission.status}</span>
      </header>
      {err && <div className="error bar">{err}</div>}

      <div className="mission-layout">
        <aside className="col timeline">
          <h3>Timeline</h3>
          <div className="event-list">
            {events.slice().reverse().map((ev) => <EventLine key={ev.id} ev={ev} />)}
          </div>
          <h3>Artifacts</h3>
          <div className="artifact-list">
            {artifacts.map((a) => (
              <a key={a.id} href={a.download_url} className="artifact" download>
                <span>{a.name}</span>
                <span className="slug">{a.kind} · {(a.size / 1024).toFixed(1)} KB</span>
              </a>
            ))}
            {!artifacts.length && <div className="muted">None yet</div>}
          </div>
        </aside>

        <section className="col board">
          <h3>Board</h3>
          <form className="card dispatch" onSubmit={createTask}>
            <input placeholder="Task title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            <input placeholder="Brief (optional)" value={desc} onChange={(e) => setDesc(e.target.value)} />
            <div className="dispatch-row">
              <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
                <option value="">Unassigned</option>
                {roster.map((a) => <option key={a.id} value={a.id}>{a.handle} — {a.display_name}</option>)}
              </select>
              <button className="primary" disabled={busy}>Dispatch</button>
            </div>
          </form>

          {approvals.length > 0 && (
            <div className="approvals">
              {approvals.map((ap) => (
                <div className="card approval" key={ap.id}>
                  <div><b>Approval needed</b> — task #{ap.task_id}</div>
                  <div className="muted">{ap.note}</div>
                  <div className="row">
                    <button className="ok" onClick={() => decide(ap, true)}>Approve</button>
                    <button className="danger" onClick={() => decide(ap, false)}>Reject</button>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="columns">
            {COLUMNS.map(([state, label]) => (
              <div className="column" key={state}>
                <div className="col-label">{label} <span className="count">{tasks.filter((t) => t.state === state).length}</span></div>
                {tasks.filter((t) => t.state === state).map((t) => (
                  <div className="card task" key={t.id}>
                    <div className="task-title">{t.title}</div>
                    {t.description && <div className="muted">{t.description}</div>}
                    <div className="task-meta">
                      <span className="agent-tag">{t.assignee || "unassigned"}</span>
                    </div>
                    <div className="row">
                      {state !== "todo" && <button className="mini" onClick={() => move(t, "todo")}>← todo</button>}
                      {state !== "in_progress" && <button className="mini" onClick={() => move(t, "in_progress")}>in-prog</button>}
                      {state !== "review" && <button className="mini" onClick={() => move(t, "review")}>review</button>}
                      {state !== "done" && <button className="mini ok" onClick={() => move(t, "done")}>done</button>}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>

        <aside className="col roster">
          <h3>Agents</h3>
          {roster.map((a) => (
            <div className="card agent-card" key={a.id}>
              <div className="agent-line">
                <span className={`dot ${a.status}`} />
                <b>{a.handle}</b>
              </div>
              <div className="muted">{a.display_name}</div>
              <div className="slug">{a.role}</div>
            </div>
          ))}
          <h3>Add agent</h3>
          {agents.filter((a) => !roster.some((r) => r.id === a.id)).map((a) => (
            <button key={a.id} className="mini full" onClick={async () => { await api.addAgentToMission(missionId, a.id); load(); }}>
              + {a.handle}
            </button>
          ))}
        </aside>
      </div>
    </div>
  );
}

function App() {
  const [authed, setAuthed] = useState(null); // null=checking, false=no, true=yes
  const [openMission, setOpenMission] = useState(null);
  useEffect(() => {
    api
      .missions()
      .then(() => setAuthed(true))
      .catch(() => setAuthed(false));
  }, []);
  if (authed === null) return <div className="wrap muted">…</div>;
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  if (openMission !== null)
    return <MissionView missionId={openMission} onBack={() => setOpenMission(null)} />;
  return <Missions onOpen={setOpenMission} />;
}

createRoot(document.getElementById("root")).render(<App />);
