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
};
