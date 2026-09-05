import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, openStream } from "./api";
import "./styles.css";

/* ---------- tiny helpers ---------- */
const fmt = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
};
const cls = (...xs) => xs.filter(Boolean).join(" ");

const COLUMNS = [
  ["todo", "To Do"],
  ["in_progress", "In Progress"],
  ["review", "Review"],
  ["blocked", "Blocked"],
  ["done", "Done"],
];
const STATE_NEXT = { todo: "in_progress", in_progress: "review", review: "done", blocked: "in_progress" };
const STATE_PREV = { in_progress: "todo", review: "in_progress", blocked: "todo", done: "review" };

const AGENT_COLORS = ["#0a84ff", "#bf5af2", "#ff9f0a", "#30d158", "#ff375f", "#64d2ff"];
const colorFor = (s) => AGENT_COLORS[(s.charCodeAt(0) + (s.charCodeAt(1) || 0)) % AGENT_COLORS.length];

function Avatar({ agent, size = 26 }) {
  const initials = (agent?.handle || "?").slice(0, 2).toUpperCase();
  return (
    <span
      className="avatar"
      style={{ width: size, height: size, background: agent ? colorFor(agent.handle) : "#8e8e93", fontSize: size * 0.42 }}
    >
      {initials}
    </span>
  );
}

function StatusDot({ status, pulse }) {
  return <span className={cls("sdot", status, (pulse && status === "working") && "pulse")} />;
}

function Logo() {
  return (
    <span className="logo">
      <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden>
        <path d="M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" fill="currentColor" />
      </svg>
    </span>
  );
}

/* ---------- login ---------- */
function Login({ onLogin }) {
  const [username, setUsername] = useState("doomerius");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await api.login(username.trim(), password);
      onLogin();
    } catch (ex) {
      setErr(String(ex.message || ex));
      setBusy(false);
    }
  };
  return (
    <div className="login-scrim">
      <form className="login-card" onSubmit={submit}>
        <div className="login-mark"><Logo /></div>
        <h1>Mission Control</h1>
        <p className="sub">Round Table · multi-agent operations</p>
        <div className="field">
          <label>Operator</label>
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" autoFocus />
        </div>
        {err && <div className="errline">{err}</div>}
        <button className="primary wide" disabled={busy}>{busy ? "Signing in…" : "Continue"}</button>
      </form>
    </div>
  );
}

/* ---------- app shell ---------- */
function App() {
  const [auth, setAuth] = useState(null); // null loading | true | false
  const [route, setRoute] = useState({ name: "missions" }); // {name:'missions'} | {name:'mission', id}
  useEffect(() => {
    api
      .missions()
      .then(() => setAuth(true))
      .catch(() => setAuth(false));
  }, []);
  if (auth === null) return <div className="boot"><Logo /></div>;
  if (!auth) return <Login onLogin={() => setAuth(true)} />;
  return route.name === "missions" ? (
    <Missions onOpen={(id) => setRoute({ name: "mission", id })} />
  ) : (
    <MissionRoute missionId={route.id} onBack={() => setRoute({ name: "missions" })} />
  );
}

/* ---------- missions home ---------- */
function Missions({ onOpen }) {
  const [missions, setMissions] = useState(null);
  const [agents, setAgents] = useState([]);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState(null);
  const [f, setF] = useState({ name: "", desc: "", agents: [] });

  const load = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([api.missions(), api.agents()]);
      setMissions(m);
      setAgents(a);
    } catch {}
  }, []);
  useEffect(() => {
    load();
    const iv = setInterval(load, 8000);
    return () => clearInterval(iv);
  }, [load]);

  const create = async (e) => {
    e.preventDefault();
    try {
      const slug = (f.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "mission") + "-" + Date.now().toString(36);
      const m = await api.createMission({ name: f.name, slug, description: f.desc });
      for (const id of f.agents) await api.addAgentToMission(m.id, id);
      setCreating(false);
      setF({ name: "", desc: "", agents: [] });
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  };

  return (
    <Shell agents={agents}>
      <header className="page-head">
        <div>
          <h1>Missions</h1>
          <p className="sub">Pick a mission to see its board, agents and live activity.</p>
        </div>
        <button className="primary" onClick={() => setCreating((v) => !v)}>{creating ? "Cancel" : "+ New Mission"}</button>
      </header>

      {creating && (
        <form className="mission-compose" onSubmit={create}>
          <input placeholder="Mission name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required autoFocus />
          <textarea placeholder="What are we trying to achieve? (optional)" value={f.desc} onChange={(e) => setF({ ...f, desc: e.target.value })} rows={2} />
          <div className="agent-picker">
            <span className="lbl">Agents</span>
            {agents.map((a) => (
              <label key={a.id} className={cls("pick", f.agents.includes(a.id) && "on")}>
                <input type="checkbox" checked={f.agents.includes(a.id)}
                  onChange={(e) => setF({ ...f, agents: e.target.checked ? [...f.agents, a.id] : f.agents.filter((x) => x !== a.id) })} />
                <Avatar agent={a} size={18} /> {a.handle}
              </label>
            ))}
          </div>
          {err && <div className="errline">{err}</div>}
          <button className="primary">Create mission</button>
        </form>
      )}

      {!missions ? null : missions.length === 0 ? (
        <div className="empty">No missions yet — create the first one.</div>
      ) : (
        <div className="tile-grid">
          {missions.map((m) => (
            <button key={m.id} className="tile" onClick={() => onOpen(m.id)}>
                <div className="tile-top">
                  <span className={cls("pill", m.status)}>{m.status}</span>
                  <span className="tile-count">{m.agents.length} agents</span>
                </div>
                <div className="tile-name">{m.name}</div>
                <div className="tile-desc">{m.description || "—"}</div>
                <div className="avatars">{m.agents.slice(0, 5).map((a) => <Avatar key={a.id} agent={a} size={22} />)}</div>
              </button>
          ))}
        </div>
      )}
    </Shell>
  );
}

/* ---------- sidebar shell ---------- */
function Shell({ agents, children }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="side-brand"><Logo /> Mission Control</div>
        <nav className="side-nav">
          <span className="side-lbl">Workspace</span>
          <a className="side-item active" href="#/"><svg viewBox="0 0 16 16" width="15" height="15"><rect x="1.5" y="1.5" width="13" height="13" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.4"/></svg>Missions</a>
        </nav>
        <div className="side-agents">
          <span className="side-lbl">Agents</span>
          {agents.map((a) => (
            <div key={a.id} className="agent-row" title={a.role}>
              <Avatar agent={a} size={24} />
              <span className="agent-name">{a.handle}</span>
              <StatusDot status={a.status} pulse />
            </div>
          ))}
        </div>
      </aside>
      <div className="content">{children}</div>
    </div>
  );
}

/* ---------- mission workspace ---------- */
function MissionRoute({ missionId, onBack }) {
  const [mission, setMission] = useState(null);
  const [agents, setAgents] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const [approvals, setApprovals] = useState([]);
  const [artifacts, setArtifacts] = useState([]);
  const [sheet, setSheet] = useState(null);
  const [notice, setNotice] = useState(null);
  const [err, setErr] = useState(null);
  const [link, setLink] = useState("connecting");
  const [view, setView] = useState("board"); // board | lanes
  const [drag, setDrag] = useState(null); // {id, from}
  const [over, setOver] = useState(null);
  const [draft, setDraft] = useState({ title: "", desc: "", assignee: "" });
  const toastTimer = useRef(null);
  const feedRef = useRef(null);

  const notify = (msg) => {
    setNotice(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setNotice(null), 3500);
  };

  const load = useCallback(async () => {
    try {
      const [m, a, t, e, ap, ar] = await Promise.all([
        api.mission(missionId), api.agents(), api.tasks(missionId), api.events(missionId),
        api.approvals(missionId), api.artifacts(missionId),
      ]);
      setMission(m); setAgents(a); setTasks(t); setEvents(e); setApprovals(ap); setArtifacts(ar);
      setErr(null);
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  }, [missionId]);

  // One fetch for the snapshot, then the socket keeps us honest — no 5s polling.
  useEffect(() => {
    load();
    const close = openStream(`mission:${missionId}`, {
      onStatus: setLink,
      onMessage: (msg) => {
        if (msg.kind === "event" && msg.event) {
          setEvents((prev) => (prev.some((e) => e.id === msg.event.id) ? prev : [...prev, msg.event]));
          // Board/approval shape changed — refetch just the affected slices.
          const t = msg.event.event_type || "";
          if (t.startsWith("task.") || t.startsWith("approval.") || t.startsWith("artifact.")) load();
        }
      },
    });
    return close;
  }, [missionId, load]);

  // Keep the feed pinned to the newest line unless the operator scrolled up.
  useEffect(() => {
    const el = feedRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) el.scrollTop = el.scrollHeight;
  }, [events]);

  const dispatch = async (e) => {
    e.preventDefault();
    if (!draft.title.trim()) return;
    try {
      const t = await api.createTask(missionId, {
        title: draft.title,
        description: draft.desc,
        assignee_agent_id: draft.assignee ? Number(draft.assignee) : null,
      });
      setDraft({ title: "", desc: "", assignee: "" });
      notify(`Dispatched “${t.title}”${t.assignee ? " → @" + t.assignee : ""}`);
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  };

  const decide = async (ap, ok) => {
    try {
      await api.decideApproval(ap.id, ok, ok ? "" : "rejected by operator");
      notify(ok ? "Approved — agent unblocked" : "Rejected — agent notified");
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
    }
  };

  const moveTask = async (id, state) => {
    setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, state } : t))); // optimistic
    try {
      await api.setTaskState(id, state);
    } catch (ex) {
      setErr(String(ex.message || ex));
      load();
    }
  };

  const reassign = async (id, agentId) => {
    try {
      await api.updateTask(id, { assignee_agent_id: agentId });
      notify(agentId ? "Reassigned — new owner dispatched" : "Unassigned");
      load();
    } catch (ex) {
      setErr(String(ex.message || ex));
      load();
    }
  };

  if (!mission) return <div className="boot"><Logo /></div>;
  const roster = mission.agents;
  const byState = (s) => tasks.filter((t) => t.state === s);
  const activeCount = byState("in_progress").length;

  return (
    <div className="ws">
      <aside className="ws-back" onClick={onBack} aria-label="Back to missions" role="button" tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && onBack()}>
        <svg viewBox="0 0 16 16" width="14" height="14"><path d="M10 3 5 8l5 5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </aside>

      <main className="ws-main">
        <header className="ws-head">
          <div className="ws-title">
            <div className="ws-crumb">
              <span className={cls("pill", mission.status)}>{mission.status}</span>
              <span className={cls("link-dot", link)} title={`Stream ${link}`} />
              <span className="link-lbl">{link === "live" ? "live" : link}</span>
            </div>
            <h1>{mission.name}</h1>
            {mission.description && <p className="sub">{mission.description}</p>}
          </div>
          <div className="ws-headright">
            <div className="ws-stats">
              <span><b>{activeCount}</b> active</span>
              <span><b>{byState("done").length}</b>/{tasks.length} done</span>
            </div>
            <div className="segmented" role="tablist">
              <button role="tab" aria-selected={view === "board"} className={cls(view === "board" && "on")} onClick={() => setView("board")}>Board</button>
              <button role="tab" aria-selected={view === "lanes"} className={cls(view === "lanes" && "on")} onClick={() => setView("lanes")}>Agents</button>
            </div>
          </div>
        </header>

        <div className="ws-progress" aria-hidden>
          {COLUMNS.map(([s]) => {
            const n = byState(s).length;
            return n ? <span key={s} className={cls("seg", s)} style={{ flexGrow: n }} /> : null;
          })}
        </div>

        {approvals.length > 0 && (
          <div className="approval-strip" role="alert">
            <span className="strip-ico">!</span>
            <div className="strip-body">
              {approvals.map((ap) => {
                const t = tasks.find((x) => x.id === ap.task_id);
                return (
                  <div key={ap.id} className="strip-item">
                    <div className="strip-text">
                      <b>{t?.assignee ? "@" + t.assignee : "An agent"}</b> needs approval on “{t?.title || `#${ap.task_id}`}”
                      {ap.note && <em> — {ap.note}</em>}
                    </div>
                    <div className="row">
                      <button className="mini ok" onClick={() => decide(ap, true)}>Approve</button>
                      <button className="mini bad" onClick={() => decide(ap, false)}>Reject</button>
                      <button className="mini" onClick={() => setSheet(ap.task_id)}>Open</button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <form className="composer" onSubmit={dispatch}>
          <input placeholder="What should be done?" value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} aria-label="Task title" />
          <input className="desc" placeholder="Context / brief (optional)" value={draft.desc} onChange={(e) => setDraft({ ...draft, desc: e.target.value })} aria-label="Task brief" />
          <select value={draft.assignee} onChange={(e) => setDraft({ ...draft, assignee: e.target.value })} aria-label="Assignee">
            <option value="">Assign…</option>
            {roster.map((a) => <option key={a.id} value={a.id}>{a.handle}</option>)}
          </select>
          <button className="primary" disabled={!draft.title.trim()}>Dispatch</button>
        </form>

        {view === "board" ? (
          <div className="board-scroll">
            <div className="board">
              {COLUMNS.map(([state, label]) => {
                const col = byState(state);
                return (
                  <section
                    className={cls("bcol", over === state && "over")}
                    key={state}
                    onDragOver={(e) => { e.preventDefault(); setOver(state); }}
                    onDragLeave={() => setOver((s) => (s === state ? null : s))}
                    onDrop={(e) => {
                      e.preventDefault();
                      setOver(null);
                      if (drag && drag.from !== state) moveTask(drag.id, state);
                      setDrag(null);
                    }}
                  >
                    <header className="bcol-head">
                      <span className={cls("bcol-dot", state)} />
                      <span>{label}</span>
                      <span className="bcount">{col.length}</span>
                    </header>
                    <div className="bcol-body">
                      {col.map((t) => (
                        <TaskCard
                          key={t.id}
                          task={t}
                          dragging={drag?.id === t.id}
                          onOpen={() => setSheet(t.id)}
                          onDragStart={() => setDrag({ id: t.id, from: state })}
                          onDragEnd={() => { setDrag(null); setOver(null); }}
                          onMove={moveTask}
                        />
                      ))}
                      {!col.length && <div className="bempty">{over === state ? "Drop here" : ""}</div>}
                    </div>
                  </section>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="lanes">
            {roster.map((a) => {
              const mine = tasks.filter((t) => t.assignee === a.handle && t.state !== "done");
              const now = mine.find((t) => t.state === "in_progress");
              return (
                <section key={a.id}
                  onDragOver={(e) => { e.preventDefault(); setOver("lane" + a.id); }}
                  onDragLeave={() => setOver((s) => (s === "lane" + a.id ? null : s))}
                  onDrop={(e) => { e.preventDefault(); setOver(null); if (drag) reassign(drag.id, a.id); setDrag(null); }}
                  className={cls("lane", over === "lane" + a.id && "over")}
                >
                  <header className="lane-head">
                    <Avatar agent={a} size={30} />
                    <div className="lane-id">
                      <b>{a.handle}</b>
                      <span className="sub">{a.role || "agent"}</span>
                    </div>
                    <StatusDot status={a.status} pulse />
                  </header>
                  <div className="lane-now">
                    {now ? (
                      <button className="now-card" onClick={() => setSheet(now.id)}>
                        <span className="now-lbl">working on</span>
                        <span className="now-title">{now.title}</span>
                      </button>
                    ) : (
                      <div className="now-idle">{a.status === "awaiting_approval" ? "waiting on you" : "idle"}</div>
                    )}
                  </div>
                  <div className="lane-body">
                    {mine.filter((t) => t.id !== now?.id).map((t) => (
                      <TaskCard key={t.id} task={t} compact
                        dragging={drag?.id === t.id}
                        onOpen={() => setSheet(t.id)}
                        onDragStart={() => setDrag({ id: t.id, from: t.state })}
                        onDragEnd={() => { setDrag(null); setOver(null); }}
                        onMove={moveTask} />
                    ))}
                    {!mine.length && <div className="empty small">Nothing queued</div>}
                  </div>
                </section>
              );
            })}
            <section className={cls("lane unassigned", over === "laneNull" && "over")}
              onDragOver={(e) => { e.preventDefault(); setOver("laneNull"); }}
              onDragLeave={() => setOver((s) => (s === "laneNull" ? null : s))}
              onDrop={(e) => { e.preventDefault(); setOver(null); if (drag) reassign(drag.id, null); setDrag(null); }}>
              <header className="lane-head"><div className="lane-id"><b>Unassigned</b><span className="sub">drop to park</span></div></header>
              <div className="lane-body">
                {tasks.filter((t) => !t.assignee && t.state !== "done").map((t) => (
                  <TaskCard key={t.id} task={t} compact
                    dragging={drag?.id === t.id}
                    onOpen={() => setSheet(t.id)}
                    onDragStart={() => setDrag({ id: t.id, from: t.state })}
                    onDragEnd={() => { setDrag(null); setOver(null); }}
                    onMove={moveTask} />
                ))}
              </div>
            </section>
          </div>
        )}
      </main>

      <aside className="ws-rail">
        <div className="rail-block grow">
          <span className="rail-lbl">
            Live activity
            <span className={cls("link-dot", link)} />
          </span>
          <div className="feed" ref={feedRef}>
            {events.map((ev) => (
              <div className={cls("feed-item", ev.actor_type)} key={ev.id}>
                <Avatar agent={{ handle: ev.actor || "system" }} size={20} />
                <div className="feed-body">
                  <div className="feed-line"><b>{ev.actor || "system"}</b> {actionLabel(ev)}</div>
                  {ev.payload?.text && <div className="feed-text">{ev.payload.text}</div>}
                  {ev.payload?.title && !ev.payload?.text && <div className="feed-text">“{ev.payload.title}”</div>}
                  <div className="feed-time">{fmt(ev.created_at)}</div>
                </div>
              </div>
            ))}
            {!events.length && <div className="empty small">No activity yet</div>}
          </div>
        </div>
        <div className="rail-block">
          <span className="rail-lbl">Artifacts</span>
          {artifacts.map((a) => (
            <a className="art" key={a.id} href={a.download_url} download>
              <span className="art-ico">⤓</span>
              <span className="art-meta"><span className="art-name">{a.name}</span><span className="sub">{a.kind}</span></span>
            </a>
          ))}
          {!artifacts.length && <div className="empty small">Nothing shipped yet</div>}
        </div>
        {err && <div className="errline">{err}</div>}
      </aside>

      {notice && <div className="toast">{notice}</div>}
      {sheet !== null && (
        <TaskSheet taskId={sheet} tasks={tasks} events={events} artifacts={artifacts} agents={agents}
          roster={roster}
          onClose={() => setSheet(null)}
          onChanged={load}
          onReassign={reassign}
          onNotify={notify}
          onError={setErr} />
      )}
    </div>
  );
}

/* ---------- task card ---------- */
function TaskCard({ task, onOpen, onDragStart, onDragEnd, onMove, dragging, compact }) {
  const next = STATE_NEXT[task.state];
  const prev = STATE_PREV[task.state];
  return (
    <div
      className={cls("tcard", dragging && "dragging", compact && "compact")}
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onClick={onOpen}
      role="button"
      tabIndex={0}
      aria-label={`${task.title}, ${task.state}`}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen();
        // Keyboard parity for drag-and-drop.
        if (e.key === "ArrowRight" && next) { e.preventDefault(); onMove(task.id, next); }
        if (e.key === "ArrowLeft" && prev) { e.preventDefault(); onMove(task.id, prev); }
      }}
    >
      <div className="tcard-top">
        <span className="tag" style={{ color: task.assignee ? colorFor(task.assignee) : undefined }}>
          {task.assignee ? "@" + task.assignee : "unassigned"}
        </span>
        <span className="tid">#{task.id}</span>
      </div>
      <div className="tcard-title">{task.title}</div>
      {!compact && task.description && <div className="tcard-desc">{task.description}</div>}
      <div className="tcard-foot">
        <span>{fmt(task.updated_at)}</span>
        <span className="tcard-move">
          {prev && <button className="chev" title={`Move to ${prev}`} onClick={(e) => { e.stopPropagation(); onMove(task.id, prev); }}>‹</button>}
          {next && <button className="chev" title={`Move to ${next}`} onClick={(e) => { e.stopPropagation(); onMove(task.id, next); }}>›</button>}
        </span>
      </div>
    </div>
  );
}

function actionLabel(ev) {
  const map = {
    "task.created": "created task",
    "task.state_change": `moved task ${ev.payload?.task_id != null ? "#" + ev.payload.task_id : ""} ${ev.payload?.from ? ev.payload.from + " \u2192 " : ""}${ev.payload?.to || ""}`,
    "task.reassigned": `reassigned to ${ev.payload?.to ? "@" + ev.payload.to : "nobody"}`,
    "task.nudged": "steered the agent",
    "comment": "commented",
    "approval.requested": "requested approval",
    "approval.decided": "approval " + (ev.payload?.approved ? "approved" : "rejected"),
    "artifact.added": "shipped artifact",
    "mission.created": "created the mission",
    "mission.updated": "updated the mission",
    "agent.added": "joined the mission",
    "agent.removed": "left the mission",
  };
  return map[ev.event_type] || String(ev.event_type || "").replaceAll("_", " ").replaceAll(".", " ");
}

/* ---------- task detail sheet ---------- */
function TaskSheet({ taskId, tasks, events, artifacts, agents, roster, onClose, onChanged, onReassign, onNotify, onError }) {
  const task = tasks.find((t) => t.id === taskId);
  const [text, setText] = useState("");
  const [mode, setMode] = useState("nudge"); // nudge = steer the agent | note = record only
  const [busy, setBusy] = useState(false);
  const feedRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const related = events.filter((e) => e.task_id === taskId);
  useEffect(() => {
    const el = feedRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [related.length]);

  if (!task) return null;
  const agent = agents.find((a) => a.handle === task.assignee);
  const arts = artifacts.filter((a) => a.task_id === task.id);

  const setState = async (s) => {
    try {
      await api.setTaskState(task.id, s);
      onChanged();
    } catch (ex) {
      onError(String(ex.message || ex));
    }
  };

  const send = async (e) => {
    e.preventDefault();
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      if (mode === "nudge") {
        const r = await api.nudgeTask(task.id, body);
        onNotify?.(r?.delivered ? `Sent to @${task.assignee}` : "Recorded — agent not reachable");
      } else {
        await api.commentTask(task.id, body);
        onNotify?.("Note added");
      }
      setText("");
      onChanged();
    } catch (ex) {
      onError(String(ex.message || ex));
    } finally {
      setBusy(false);
    }
  };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(`/api/tasks/${task.id}/artifacts`, { method: "POST", body: fd, credentials: "same-origin" });
      if (!res.ok) throw new Error(`upload failed (${res.status})`);
      e.target.value = "";
      onChanged();
    } catch (ex) {
      onError(String(ex.message || ex));
    }
  };

  return (
    <div className="scrim" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={task.title}>
        <div className="sheet-head">
          <div className="sheet-title">
            <span className={cls("pill", task.state)}>{task.state.replace("_", " ")}</span>
            <h2>{task.title}</h2>
            {task.description && <p className="sub">{task.description}</p>}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Close">✕</button>
        </div>

        <div className="sheet-assignee">
          {agent ? <><Avatar agent={agent} size={22} /> <b>{agent.handle}</b><span className="sub"> · {agent.role}</span></> : <span className="sub">Unassigned</span>}
          <select
            className="reassign"
            value={task.assignee_agent_id || ""}
            onChange={(e) => onReassign?.(task.id, e.target.value ? Number(e.target.value) : null)}
            aria-label="Reassign task"
          >
            <option value="">Unassigned</option>
            {(roster || []).map((a) => <option key={a.id} value={a.id}>{a.handle}</option>)}
          </select>
        </div>

        <div className="sheet-controls">
          <span className="lbl">Move</span>
          {task.state !== "todo" && <button className="mini" onClick={() => setState("todo")}>← To Do</button>}
          {task.state !== "in_progress" && <button className="mini" onClick={() => setState("in_progress")}>In Progress</button>}
          {task.state !== "review" && <button className="mini" onClick={() => setState("review")}>Review</button>}
          {task.state !== "blocked" && <button className="mini bad" onClick={() => setState("blocked")}>Blocked</button>}
          {task.state !== "done" && <button className="mini ok" onClick={() => setState("done")}>Done ✓</button>}
        </div>

        {arts.length > 0 && (
          <div className="sheet-arts">
            <span className="lbl">Artifacts</span>
            {arts.map((a) => (
              <a key={a.id} href={a.download_url} download className="art">
                <span className="art-ico">⤓</span>
                <span className="art-meta"><span className="art-name">{a.name}</span><span className="sub">{(a.size / 1024).toFixed(1)} KB</span></span>
              </a>
            ))}
          </div>
        )}

        <div className="sheet-feed" ref={feedRef}>
          <span className="lbl">Activity</span>
          {related.map((ev) => (
            <div className={cls("feed-item", ev.actor_type)} key={ev.id}>
              <Avatar agent={{ handle: ev.actor || "system" }} size={20} />
              <div className="feed-body">
                <div className="feed-line"><b>{ev.actor || "system"}</b> {actionLabel(ev)}</div>
                {ev.payload?.text && <div className="feed-text">{ev.payload.text}</div>}
                <div className="feed-time">{fmt(ev.created_at)}</div>
              </div>
            </div>
          ))}
          {!related.length && <div className="empty small">No activity on this task yet</div>}
        </div>

        <form className="sheet-comment" onSubmit={send}>
          <div className="segmented tiny" role="tablist">
            <button type="button" role="tab" aria-selected={mode === "nudge"} className={cls(mode === "nudge" && "on")} onClick={() => setMode("nudge")}>Steer agent</button>
            <button type="button" role="tab" aria-selected={mode === "note"} className={cls(mode === "note" && "on")} onClick={() => setMode("note")}>Note only</button>
          </div>
          <div className="row">
            <input
              placeholder={mode === "nudge"
                ? (task.assignee ? `Tell @${task.assignee} what to change…` : "Assign someone to steer them…")
                : "Record a note on the timeline…"}
              value={text}
              onChange={(e) => setText(e.target.value)}
              aria-label={mode === "nudge" ? "Steer the agent" : "Add a note"}
            />
            <button className="primary" disabled={!text.trim() || busy}>{busy ? "…" : mode === "nudge" ? "Send" : "Post"}</button>
          </div>
          {mode === "nudge" && !task.assignee && <div className="hint">Nobody owns this task — the message will only be recorded.</div>}
        </form>
        <label className="attach"><input type="file" onChange={upload} />Attach file</label>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
