// web/src/api.js
import { supabase } from "./lib/supabaseClient";

const __API_BASE =
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_URL_BASE ||
  "http://127.0.0.1:8000";

export const API_BASE = __API_BASE.replace(/\/$/, "");

const PANEL_KEY = import.meta.env.VITE_PANEL_KEY || "";
const DEFAULT_WORKSPACE_ID = import.meta.env.VITE_DEFAULT_WORKSPACE_ID || "workspace-mugo-default";
const WORKSPACE_STORAGE_KEY = "mugozap_workspace_id";

function dbg(label, payload = null) {
  console.log("[API_DEBUG]", label, payload);
}

async function buildHeaders(extraHeaders = {}) {
  const headers = new Headers(extraHeaders || {});

  if (PANEL_KEY) {
    headers.set("X-Panel-Key", PANEL_KEY);
  }

  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    const sessionUser = data?.session?.user || {};
    const userMetadata = sessionUser?.user_metadata || {};
    const appMetadata = sessionUser?.app_metadata || {};
    const workspaceId =
      localStorage.getItem(WORKSPACE_STORAGE_KEY) ||
      userMetadata.workspace_id ||
      appMetadata.workspace_id ||
      sessionUser.workspace_id ||
      DEFAULT_WORKSPACE_ID;

    dbg("buildHeaders:session", {
      hasSession: !!data?.session,
      hasToken: !!token,
      workspaceId,
    });

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    if (workspaceId) {
      headers.set("X-Workspace-Id", workspaceId);
    }
  } catch (e) {
    dbg("buildHeaders:session_error", { message: String(e?.message || e) });
  }

  return headers;
}

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const headers = await buildHeaders(opts.headers || {});

  dbg("apiFetch:start", {
    path,
    url,
    method: opts.method || "GET",
    hasPanelKey: !!PANEL_KEY,
  });

  let res;
  try {
    res = await fetch(url, {
      ...opts,
      headers,
    });
  } catch (e) {
    dbg("apiFetch:fetch_error", {
      url,
      message: String(e?.message || e),
    });
    throw new Error(`Erro de conexão com a API: ${String(e?.message || e)}`);
  }

  let body = null;
  const ct = res.headers.get("content-type") || "";

  if (ct.includes("application/json")) {
    body = await res.json().catch(() => null);
  } else {
    body = await res.text().catch(() => null);
  }

  dbg("apiFetch:response", {
    url,
    status: res.status,
    ok: res.ok,
    body,
  });

  if (!res.ok) {
    const detail =
      body && typeof body === "object" && body !== null && "detail" in body
        ? body.detail
        : null;
    const msg =
      (typeof detail === "string" ? detail : detail ? JSON.stringify(detail) : null) ||
      (typeof body === "string" && body) ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }

  return body;
}

export async function getConversations() {
  const r = await apiFetch("/api/conversations");
  return Array.isArray(r?.items) ? r.items : [];
}

export async function getMessages(wa_id, limit = 60) {
  const r = await apiFetch(
    `/api/messages?wa_id=${encodeURIComponent(wa_id)}&limit=${encodeURIComponent(limit)}`
  );
  return Array.isArray(r?.items) ? r.items : [];
}

export async function getConversationDetail(wa_id) {
  const r = await apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}`);
  return Array.isArray(r?.messages) ? r.messages : [];
}

export async function sendMessage(wa_id, text) {
  return apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function closeHandoff(wa_id) {
  return apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}/handoff/close`, {
    method: "POST",
  });
}

export async function deleteConversation(wa_id) {
  return apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}`, {
    method: "DELETE",
  });
}

export async function updateContact(wa_id, payload) {
  return apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function assignConversation(wa_id, payload) {
  return apiFetch(`/api/attendance/conversations/${encodeURIComponent(wa_id)}/assign`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function updateConversationStatus(wa_id, payload) {
  return apiFetch(`/api/attendance/conversations/${encodeURIComponent(wa_id)}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function listUsers() {
  const r = await apiFetch("/api/users");
  return Array.isArray(r?.items) ? r.items : [];
}

export async function createUser(payload) {
  const r = await apiFetch("/api/users", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return r?.user || r;
}

export async function updateUser(id, payload) {
  const r = await apiFetch(`/api/users/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return r?.user || r;
}

export async function listTasks(params = {}) {
  const qs = new URLSearchParams();

  if (params.status) qs.set("status", params.status);
  if (params.due_before) qs.set("due_before", params.due_before);
  if (params.wa_id) qs.set("wa_id", params.wa_id);
  if (params.limit) qs.set("limit", String(params.limit));

  const query = qs.toString();
  const r = await apiFetch(`/api/tasks${query ? `?${query}` : ""}`);
  return Array.isArray(r?.items) ? r.items : [];
}

export async function createTask(payload) {
  const r = await apiFetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });

  return r?.item || r;
}

export async function doneTask(id) {
  const r = await apiFetch(`/api/tasks/${encodeURIComponent(id)}/done`, {
    method: "POST",
  });

  return r?.item || r;
}

export async function updateTask(id, payload) {
  const r = await apiFetch(`/api/tasks/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });

  return r?.item || r;
}

export async function getDashboardSummary() {
  const r = await apiFetch("/api/dashboard/summary");
  return r?.summary || {
    conversations_open: 0,
    handoffs_pending: 0,
    waiting_human: 0,
    bot_active: 0,
    paused_automation: 0,
    urgent_tasks: 0,
    leads_by_source: {},
    leads_by_entry_type: {},
    leads_by_status: {},
  };
}

export async function getAttendanceMeta() {
  const r = await apiFetch("/api/attendance/meta");
  return r || { queues: [], statuses: [], welcome_message: "" };
}

export async function submitAttendanceDiagnosis(wa_id, payload) {
  return apiFetch(`/api/attendance/conversations/${encodeURIComponent(wa_id)}/diagnosis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function createAttendanceContact(payload) {
  return apiFetch("/api/attendance/contacts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function createAttendanceCollection(payload) {
  return apiFetch("/api/attendance/collections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function sendAttendanceCollectionReminder(wa_id, payload) {
  return apiFetch(`/api/attendance/collections/${encodeURIComponent(wa_id)}/remind`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function runFollowups() {
  return apiFetch("/api/followups/run", {
    method: "POST",
  });
}

export async function getMe() {
  const result = await apiFetch("/api/me");
  const workspaceId = result?.user?.workspace_id;

  if (workspaceId) {
    try {
      localStorage.setItem(WORKSPACE_STORAGE_KEY, workspaceId);
    } catch {
      // Ignore storage errors in private browsing or restricted environments.
    }
  }

  return result;
}

export async function getAiState(wa_id) {
  return apiFetch(`/api/debug/ai-state/${encodeURIComponent(wa_id)}`);
}

export async function simulateIncoming(wa_id, payload) {
  return apiFetch(`/api/debug/simulate-incoming/${encodeURIComponent(wa_id)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function sseUrl() {
  try {
    const headers = await buildHeaders();
    const auth = headers.get("Authorization");
    const workspaceId = headers.get("X-Workspace-Id");

    dbg("sseUrl", {
      hasAuth: !!auth,
      apiBase: API_BASE,
      hasPanelKey: !!PANEL_KEY,
      workspaceId,
    });

    if (auth?.startsWith("Bearer ")) {
      const token = auth.replace("Bearer ", "").trim();
      if (token) {
        const qs = new URLSearchParams({ token });
        if (workspaceId) {
          qs.set("workspace_id", workspaceId);
        }
        return `${API_BASE}/events?${qs.toString()}`;
      }
    }
  } catch (e) {
    dbg("sseUrl:error", { message: String(e?.message || e) });
  }

  return "";
}
