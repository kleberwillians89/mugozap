// web/src/api.js
import { supabase } from "./lib/supabaseClient";

export const API_BASE = (
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE ||
  import.meta.env.VITE_API_URL_BASE ||
  "https://mugo-zap.onrender.com"
).replace(/\/$/, "");

const PANEL_KEY = import.meta.env.VITE_PANEL_KEY || "";

async function apiFetch(path, opts = {}) {
  const url = `${API_BASE}${path}`;
  const headers = new Headers(opts.headers || {});

  if (PANEL_KEY) headers.set("X-Panel-Key", PANEL_KEY);

  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) headers.set("Authorization", `Bearer ${token}`);
  } catch {}

  const res = await fetch(url, { ...opts, headers });

  let body = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) body = await res.json().catch(() => null);
  else body = await res.text().catch(() => null);

  if (!res.ok) {
    const msg =
      (body && body.detail) ||
      (typeof body === "string" && body) ||
      `HTTP ${res.status}`;
    throw new Error(msg);
  }

  return body;
}

export async function getConversations() {
  const r = await apiFetch("/api/conversations");
  return r.items || [];
}

export async function getMessages(wa_id) {
  const r = await apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}`);
  return r.messages || [];
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

export async function updateContact(wa_id, payload) {
  return apiFetch(`/api/conversations/${encodeURIComponent(wa_id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function listTasks(params = {}) {
  const qs = new URLSearchParams();
  if (params.status) qs.set("status", params.status);
  if (params.due_before) qs.set("due_before", params.due_before);
  if (params.wa_id) qs.set("wa_id", params.wa_id);

  const r = await apiFetch(`/api/tasks?${qs.toString()}`);
  return r.items || [];
}

export async function createTask(payload) {
  return apiFetch("/api/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function doneTask(id) {
  return apiFetch(`/api/tasks/${encodeURIComponent(id)}/done`, { method: "POST" });
}

export async function updateTask(id, payload) {
  return apiFetch(`/api/tasks/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

// SSE (EventSource não aceita header)
export async function sseUrl() {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    if (token) return `${API_BASE}/events?token=${encodeURIComponent(token)}`;
  } catch {}
  return "";
}