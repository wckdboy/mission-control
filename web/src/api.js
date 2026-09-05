async function req(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, { ...opts, credentials: "same-origin" });
  if (res.status === 401) throw new Error("unauthorized");
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = j.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  login: (username, password) => req("POST", "/api/auth/login", { username, password }),
  missions: () => req("GET", "/api/missions"),
  createMission: (m) => req("POST", "/api/missions", m),
  mission: (id) => req("GET", `/api/missions/${id}`),
  agents: () => req("GET", "/api/agents"),
  addAgentToMission: (mid, aid) => req("POST", `/api/missions/${mid}/agents/${aid}`),
  tasks: (mid) => req("GET", `/api/missions/${mid}/tasks`),
  createTask: (mid, t) => req("POST", `/api/missions/${mid}/tasks`, t),
  setTaskState: (tid, state) => req("PATCH", `/api/tasks/${tid}`, { state }),
  events: (mid) => req("GET", `/api/missions/${mid}/events`),
  commentTask: (tid, text) => req("POST", `/api/tasks/${tid}/comments`, { text }),
  approvals: (mid) => req("GET", `/api/missions/${mid}/approvals?status=pending`),
  decideApproval: (aid, approve, note) =>
    req("POST", `/api/approvals/${aid}/decide`, { approve, note: note || "" }),
  artifacts: (mid) => req("GET", `/api/missions/${mid}/artifacts`),
  nudgeTask: (tid, text) => req("POST", `/api/tasks/${tid}/nudge`, { text }),
  updateTask: (tid, patchBody) => req("PATCH", `/api/tasks/${tid}`, patchBody),
  logout: () => req("POST", "/api/auth/logout"),
};

/** Live mission stream. Falls back to caller-supplied refetch on drop. */
export function openStream(room, { onMessage, onStatus }) {
  let ws = null;
  let closed = false;
  let attempt = 0;
  let timer = null;
  let ping = null;

  const connect = () => {
    if (closed) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws/${room}`);
    ws.onopen = () => {
      attempt = 0;
      onStatus?.("live");
      ping = setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
    };
    ws.onmessage = (e) => {
      try {
        onMessage?.(JSON.parse(e.data));
      } catch {}
    };
    ws.onclose = () => {
      clearInterval(ping);
      if (closed) return;
      onStatus?.("reconnecting");
      // Exponential backoff, capped — a dead tab shouldn't hammer the server.
      const delay = Math.min(1000 * 2 ** attempt++, 15000);
      timer = setTimeout(connect, delay);
    };
    ws.onerror = () => ws?.close();
  };
  connect();

  return () => {
    closed = true;
    clearTimeout(timer);
    clearInterval(ping);
    ws?.close();
  };
}
