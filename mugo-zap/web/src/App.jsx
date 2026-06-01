import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { supabase } from "./lib/supabaseClient";

import {
  getConversations,
  getMessages,
  sendMessage,
  closeHandoff,
  updateContact,
  listTasks,
  createTask,
  doneTask,
  updateTask,
  sseUrl,
  deleteConversation,
  getDashboardSummary,
  getMe,
} from "./api";
import logoMugo from "./assets/logo-mugo.png";

const LS_STAGE_KEY = "mugozap_stages_v1";
const LS_SEEN_KEY = "mugozap_seen_v1";

const STAGES = ["Novo", "Qualificado", "Diagnóstico", "Proposta", "Negociação", "Fechado"];
const TASK_COLS = ["Atrasadas", "Hoje", "Amanhã", "Esta semana", "Futuro", "Sem data"];

function dbg(label, payload = null) {
  console.log("[MUGO_DEBUG]", label, payload);
}

function loadJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function saveJSON(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage write failures and keep the UI responsive.
  }
}

function clip(text, max = 80) {
  const s = String(text || "").trim();
  if (!s) return "";
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

function onlyDigits(v) {
  return String(v || "").replace(/\D/g, "");
}

function formatPhoneBR(v) {
  const d = onlyDigits(v);
  if (!d) return "";

  if (d.length === 13 && d.startsWith("55")) {
    return `+${d.slice(0, 2)} ${d.slice(2, 4)} ${d.slice(4, 9)}-${d.slice(9)}`;
  }

  if (d.length === 12 && d.startsWith("55")) {
    return `+${d.slice(0, 2)} ${d.slice(2, 4)} ${d.slice(4, 8)}-${d.slice(8)}`;
  }

  if (d.length === 11) {
    return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
  }

  if (d.length === 10) {
    return `(${d.slice(0, 2)}) ${d.slice(2, 6)}-${d.slice(6)}`;
  }

  return v;
}

function getDisplayName(c) {
  if (!c) return "";
  const name = String(c.name || c.contact_name || c.profile_name || "").trim();
  if (name) return name;

  const tel = String(c.telefone || c.phone || "").trim();
  if (tel) return formatPhoneBR(tel);

  const wa = String(c.wa_id || "").trim();
  if (wa) return formatPhoneBR(wa);

  return "Lead sem nome";
}

function getAvatarSeed(c) {
  const base = getDisplayName(c) || c?.wa_id || "?";
  return String(base).trim().slice(0, 1).toUpperCase();
}

function shortTime(v) {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";

  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();

  if (sameDay) {
    return d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  return d.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}

function nowLocalTime(v) {
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function parseTags(v) {
  return String(v || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .filter((tag, idx, arr) => arr.indexOf(tag) === idx);
}

function normalizeSourceLabel(source) {
  const s = String(source || "").trim();
  if (!s) return "Sem origem";

  const map = {
    meta_ads: "Meta Ads",
    google_ads: "Google Ads",
    indicacao: "Indicação",
    organico: "Orgânico",
    whatsapp: "WhatsApp",
    instagram: "Instagram",
    facebook: "Facebook",
    paid: "Pago",
    organic: "Orgânico",
    human: "Humano",
  };

  return map[s] || s;
}

function normalizeOwnerLabel(value) {
  const s = String(value || "").trim();
  return s || "Sem responsável";
}

function isArchivedConversation(conv) {
  return Boolean(conv?.closed_at) || String(conv?.lead_stage || "").trim().toLowerCase() === "arquivado";
}

function isTestConversation(conv) {
  const haystack = [
    conv?.name,
    conv?.notes,
    conv?.last_message,
    conv?.last_text,
    conv?.source,
    conv?.last_source,
    Array.isArray(conv?.tags) ? conv.tags.join(" ") : "",
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  const phone = String(conv?.wa_id || conv?.telefone || "").replace(/\D/g, "");
  return (
    haystack.includes("teste") ||
    haystack.includes("test ") ||
    haystack.includes("debug") ||
    haystack.includes("simulado") ||
    haystack.includes("fake") ||
    phone.endsWith("0000") ||
    phone === "5511999999999"
  );
}

function matchesStatusFilter(conv, statusFilter) {
  if (statusFilter === "todos") return true;
  if (statusFilter === "arquivados") return isArchivedConversation(conv);
  if (statusFilter === "ativos") return !isArchivedConversation(conv);
  return String(conv?.operation_status || "").trim() === statusFilter;
}

function taskBucket(due_at) {
  if (!due_at) return "Sem data";

  const now = new Date();
  const d = new Date(due_at);
  if (Number.isNaN(d.getTime())) return "Sem data";

  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startTomorrow = new Date(startToday);
  startTomorrow.setDate(startTomorrow.getDate() + 1);

  const startDayAfterTomorrow = new Date(startTomorrow);
  startDayAfterTomorrow.setDate(startDayAfterTomorrow.getDate() + 1);

  const startWeekLimit = new Date(startToday);
  startWeekLimit.setDate(startWeekLimit.getDate() + 7);

  if (d < startToday) return "Atrasadas";
  if (d >= startToday && d < startTomorrow) return "Hoje";
  if (d >= startTomorrow && d < startDayAfterTomorrow) return "Amanhã";
  if (d >= startDayAfterTomorrow && d < startWeekLimit) return "Esta semana";
  if (d >= startWeekLimit) return "Futuro";

  return "Sem data";
}

function toIsoLocal(dateStr, timeStr) {
  if (!dateStr) return null;
  const [y, m, d] = String(dateStr).split("-").map(Number);
  const [hh, mm] = String(timeStr || "12:00").split(":").map(Number);

  const dt = new Date(y, (m || 1) - 1, d || 1, hh || 0, mm || 0, 0);
  if (Number.isNaN(dt.getTime())) return null;

  const pad = (n) => String(n).padStart(2, "0");
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(
    dt.getMinutes()
  )}:${pad(dt.getSeconds())}`;
}

function dueForBucket(bucket) {
  const now = new Date();

  const make = (d, h, m) => {
    const t = new Date(d);
    t.setHours(h, m, 0, 0);

    const pad = (n) => String(n).padStart(2, "0");
    const yyyy = t.getFullYear();
    const MM = pad(t.getMonth() + 1);
    const dd = pad(t.getDate());
    const HH = pad(t.getHours());
    const mm2 = pad(t.getMinutes());
    const ss = pad(t.getSeconds());

    return `${yyyy}-${MM}-${dd}T${HH}:${mm2}:${ss}`;
  };

  if (bucket === "Atrasadas") return make(now, 9, 0);
  if (bucket === "Hoje") return make(now, 12, 0);

  if (bucket === "Amanhã") {
    const t = new Date(now);
    t.setDate(t.getDate() + 1);
    return make(t, 12, 0);
  }

  if (bucket === "Esta semana") {
    const t = new Date(now);
    t.setDate(t.getDate() + 3);
    return make(t, 12, 0);
  }

  if (bucket === "Futuro") {
    const t = new Date(now);
    t.setDate(t.getDate() + 10);
    return make(t, 12, 0);
  }

  return null;
}

function isTodayDate(value) {
  if (!value) return false;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return false;
  const now = new Date();
  return (
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  );
}

function getConversationLastActivityAt(conv) {
  if (!conv) return "";
  return (
    conv.last_message_at ||
    conv.last_at ||
    conv.updated_at ||
    conv.created_at ||
    ""
  );
}

function getConversationFirstActivityAt(conv) {
  if (!conv) return "";

  const primaryCandidates = [
    conv.created_at,
    conv.first_message_at,
    conv.first_activity_at,
    conv.first_in_at,
    conv.first_out_at,
    conv.first_at,
  ].filter(Boolean);

  const fallbackCandidates = [
    conv.last_message_at,
    conv.last_at,
    conv.updated_at,
  ].filter(Boolean);

  const validDates = [...primaryCandidates, ...fallbackCandidates]
    .map((value) => new Date(value))
    .filter((date) => !Number.isNaN(date.getTime()))
    .sort((a, b) => a.getTime() - b.getTime());

  return validDates[0]?.toISOString() || "";
}

function isConversationNewToday(conv) {
  return isTodayDate(getConversationFirstActivityAt(conv));
}

function getTodayLeadsCount(summary, convs) {
  const summaryCandidates = [
    summary?.new_today,
    summary?.new_leads_today,
    summary?.leads_new_today,
    summary?.conversations_new_today,
    summary?.today_new,
  ];

  for (const candidate of summaryCandidates) {
    if (Number.isFinite(candidate)) return candidate;
  }

  return (convs || []).filter((conv) => isConversationNewToday(conv)).length;
}

function cleanStrategicText(value, max = 180) {
  const text = String(value || "")
    .replace(/\b(Serviço|Objetivo|Problema|Canal|Ferramenta atual\/status|Ferramenta atual|Prazo|Orçamento|Resumo):\s*/gi, "")
    .replace(/\s+/g, " ")
    .trim();
  return clip(text, max);
}

function extractStrategicSection(raw, label) {
  const text = String(raw || "");
  if (!text || !label) return "";
  const labels = [
    "Síntese estratégica",
    "Oportunidade percebida",
    "Leitura comercial",
    "Próximo passo sugerido",
  ];
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const next = labels
    .filter((item) => item !== label)
    .map((item) => item.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  const re = new RegExp(`${escaped}:\\s*([\\s\\S]*?)(?=\\n\\n(?:${next}):|$)`, "i");
  const match = text.match(re);
  return cleanStrategicText(match?.[1] || "", 220);
}

function buildStrategicSnapshot(conv, flowData, statusMeta) {
  const raw = String(flowData?.context_summary || flowData?.briefing || conv?.notes || "").trim();
  const topic = cleanStrategicText(flowData?.topic || conv?.lead_theme || conv?.stage || "", 80);
  const source = normalizeSourceLabel(conv?.source || conv?.last_source || "");
  const status = statusMeta?.label || conv?.operation_status || "";
  const temperature = cleanStrategicText(conv?.lead_temperature || conv?.temperature || status || "Em leitura", 80);

  return {
    synthesis:
      extractStrategicSection(raw, "Síntese estratégica") ||
      cleanStrategicText(raw || conv?.last_message || conv?.last_text || "", 220) ||
      "Contato em qualificação. A leitura estratégica aparece assim que houver contexto suficiente.",
    opportunity:
      extractStrategicSection(raw, "Oportunidade percebida") ||
      (topic ? `Frente em foco: ${topic}.` : `Origem principal: ${source}. Validar a melhor frente da Mugô no atendimento.`),
    nextStep:
      extractStrategicSection(raw, "Próximo passo sugerido") ||
      (conv?.handoff_active || conv?.operation_status === "handoff_active"
        ? "Julia assumir retomando o contexto e validar prioridade antes de propor o próximo movimento."
        : "Avançar a conversa com uma pergunta consultiva e encaminhar quando houver sinal comercial claro."),
    temperature,
  };
}

function getOperationStatusMeta(status) {
  const s = String(status || "").trim();

  if (s === "handoff" || s === "handoff_active") {
    return { label: "Em atendimento humano", className: "wbBadge warn" };
  }
  if (s === "handoff_pending") {
    return { label: "Encaminhamento pendente", className: "wbBadge warn" };
  }
  if (s === "human_active") {
    return { label: "Em atendimento humano", className: "wbBadge human" };
  }
  if (s === "automation_paused" || s === "paused") {
    return { label: "Automação pausada", className: "wbBadge paused" };
  }
  if (s === "bot_active") {
    return { label: "Bot ativo", className: "wbBadge ok" };
  }
  if (s === "ai_active") {
    return { label: "IA ativa", className: "wbBadge ok" };
  }
  if (s === "resume_ready") {
    return { label: "Retomada pronta", className: "wbBadge ok" };
  }
  if (s === "followup_scheduled") {
    return { label: "Follow-up agendado", className: "wbBadge warn" };
  }
  if (s === "closed") {
    return { label: "Encerrado", className: "wbBadge" };
  }

  return { label: "Aguardando cliente", className: "wbBadge" };
}

function getAttendanceModeMeta(mode) {
  const value = String(mode || "").trim().toLowerCase();

  if (value === "human") {
    return { label: "humano", className: "wbBadge human" };
  }
  if (value === "hybrid") {
    return { label: "híbrido", className: "wbBadge warn" };
  }
  if (value === "bot") {
    return { label: "bot", className: "wbBadge ok" };
  }

  return { label: "não definido", className: "wbBadge" };
}

function sortByRecent(items) {
  return [...(items || [])].sort((a, b) => {
    const ta = getConversationLastActivityAt(a) ? new Date(getConversationLastActivityAt(a)).getTime() : 0;
    const tb = getConversationLastActivityAt(b) ? new Date(getConversationLastActivityAt(b)).getTime() : 0;
    return tb - ta;
  });
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [sourceFilter, setSourceFilter] = useState("todos");
  const [statusFilter, setStatusFilter] = useState("ativos");
  const [ownerFilter, setOwnerFilter] = useState("todos");
  const [testFilter, setTestFilter] = useState("todos");
  const [dashboardFilter, setDashboardFilter] = useState("todos");
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [refreshingTasksSummary, setRefreshingTasksSummary] = useState(false);

  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [loadingDashboard, setLoadingDashboard] = useState(false);
  const [deletingConv, setDeletingConv] = useState(false);

  const [stages, setStages] = useState(() => loadJSON(LS_STAGE_KEY, {}));
  const [seen, setSeen] = useState(() => loadJSON(LS_SEEN_KEY, {}));

  const [tasks, setTasks] = useState([]);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskSaving, setTaskSaving] = useState(false);
  const [taskTitle, setTaskTitle] = useState("Atendimento / Follow-up");
  const [taskDate, setTaskDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [taskTime, setTaskTime] = useState("12:00");

  const [editOpen, setEditOpen] = useState(false);
  const [contactSaving, setContactSaving] = useState(false);
  const [editName, setEditName] = useState("");
  const [editTel, setEditTel] = useState("");
  const [editStage, setEditStage] = useState("Novo");
  const [editTags, setEditTags] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editOwner, setEditOwner] = useState("");
  const [editAttendanceMode, setEditAttendanceMode] = useState("hybrid");
  const [editSource, setEditSource] = useState("");

  const [toast, setToast] = useState(null);

  const [dashboardSummary, setDashboardSummary] = useState({
    conversations_open: 0,
    handoffs_pending: 0,
    waiting_human: 0,
    bot_active: 0,
    paused_automation: 0,
    urgent_tasks: 0,
    leads_by_source: {},
    leads_by_entry_type: {},
    leads_by_status: {},
  });

  const esRef = useRef(null);
  const inputRef = useRef(null);
  const chatScrollRef = useRef(null);
  const selectedItemRef = useRef(null);
  const mountedRef = useRef(false);
  const selectedRef = useRef(null);
  const convsRef = useRef([]);
  const messagesRequestSeqRef = useRef(0);
  const lastMessageCountRef = useRef(0);
  const knownConvIdsRef = useRef(new Set());
  const toastTimerRef = useRef(null);

  const selectedConv = useMemo(
    () => convs.find((c) => c.wa_id === selected) || null,
    [convs, selected]
  );
  const conversationsById = useMemo(() => {
    const map = new Map();
    convs.forEach((conv) => {
      if (conv?.wa_id) {
        map.set(conv.wa_id, conv);
      }
    });
    return map;
  }, [convs]);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    convsRef.current = convs;
  }, [convs]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  function showToast(message, actionLabel = "", action = null) {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current);
    }

    setToast({
      id: Date.now(),
      message,
      actionLabel,
      action,
    });

    toastTimerRef.current = setTimeout(() => {
      setToast(null);
    }, 5000);
  }

  function scrollSelectedConversationIntoView() {
    const el = selectedItemRef.current;
    if (!el) return;

    try {
      el.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "smooth",
      });
    } catch {
      // Ignore scroll errors from detached or hidden nodes.
    }
  }

  function replaceConversationLocal(updated) {
    if (!updated?.wa_id) return;
    setConvs((prev) => {
      const idx = prev.findIndex((c) => c.wa_id === updated.wa_id);
      if (idx === -1) return prev;
      const next = [...prev];
      next[idx] = { ...next[idx], ...updated };
      return next;
    });
  }

  function prependOrReplaceConversationLocal(updated) {
    if (!updated?.wa_id) return;
    setConvs((prev) => {
      const existingIdx = prev.findIndex((c) => c.wa_id === updated.wa_id);
      if (existingIdx === -1) return [updated, ...prev];

      const current = prev[existingIdx];
      const merged = { ...current, ...updated };
      const without = prev.filter((c) => c.wa_id !== updated.wa_id);
      return [merged, ...without];
    });
  }
  async function handleLogout() {
    try {
      setErr("");
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      window.location.replace("/");
    } catch (e) {
      console.error("Erro ao sair:", e);
      setErr(String(e.message || e));
    }
  }

  async function refreshDashboard({ silent = false } = {}) {
    if (!silent) setLoadingDashboard(true);

    try {
      const summary = await getDashboardSummary();
      setDashboardSummary(
        summary || {
          conversations_open: 0,
          handoffs_pending: 0,
          waiting_human: 0,
          bot_active: 0,
          paused_automation: 0,
          urgent_tasks: 0,
          leads_by_source: {},
          leads_by_entry_type: {},
          leads_by_status: {},
        }
      );
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      if (!silent) setLoadingDashboard(false);
    }
  }

  async function refreshConversations({ keepSelected = true, silent = false } = {}) {
    if (!silent) setLoadingConvs(true);
    setErr("");

    try {
      const items = sortByRecent(await getConversations());
      console.debug(`sidebar:api total=${items?.length || 0}`);
      await applyIncomingConversations(items || [], {
        keepSelected,
        refreshSelectedMessages: true,
        source: "refresh",
      });
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      if (!silent) setLoadingConvs(false);
    }
  }

  async function applyIncomingConversations(
    items,
    { keepSelected = true, refreshSelectedMessages = false, source = "unknown" } = {}
  ) {
    const safeItems = sortByRecent(items || []);
    const previousItems = convsRef.current || [];
    const currentIds = new Set(safeItems.map((c) => c.wa_id).filter(Boolean));
    const previousIds = knownConvIdsRef.current || new Set();
    const newConversations = safeItems.filter((c) => c?.wa_id && !previousIds.has(c.wa_id));

    if (previousIds.size > 0 && newConversations.length > 0) {
      const newest = newConversations[0];
      showToast(
        `Novo lead: ${getDisplayName(newest)}`,
        "Abrir",
        () => {
          setSelected(newest.wa_id);
          setView("inbox");
        }
      );
    }

    knownConvIdsRef.current = currentIds;
    convsRef.current = safeItems;
    setConvs((prev) => {
      const prevJson = JSON.stringify(prev || []);
      const nextJson = JSON.stringify(safeItems || []);
      return prevJson === nextJson ? prev : safeItems;
    });

    if (!keepSelected && safeItems.length) {
      setSelected(safeItems[0].wa_id);
      dbg("conversations:update", { source, total: safeItems.length, selected: safeItems[0].wa_id });
      return;
    }

    if (!selectedRef.current && safeItems.length) {
      setSelected(safeItems[0].wa_id);
      dbg("conversations:update", { source, total: safeItems.length, selected: safeItems[0].wa_id });
      return;
    }

    if (selectedRef.current) {
      const stillExists = safeItems.some((c) => c.wa_id === selectedRef.current);
      if (!stillExists && safeItems.length) {
        setSelected(safeItems[0].wa_id);
        dbg("conversations:update", { source, total: safeItems.length, selected: safeItems[0].wa_id });
        return;
      }
    }

    const selectedWaId = selectedRef.current;
    const selectedUpdated = selectedWaId ? safeItems.find((c) => c.wa_id === selectedWaId) : null;
    const prevSelected = previousItems.find((c) => c.wa_id === selectedWaId);
    const selectedChanged =
      !!selectedUpdated &&
      (
        (selectedUpdated.last_message_at || selectedUpdated.last_at || "") !==
          (prevSelected?.last_message_at || prevSelected?.last_at || "") ||
        String(selectedUpdated.last_message || selectedUpdated.last_text || "") !==
          String(prevSelected?.last_message || prevSelected?.last_text || "")
      );

    dbg("conversations:update", {
      source,
      total: safeItems.length,
      selected: selectedWaId || null,
      selectedChanged,
    });

    if (selectedWaId && refreshSelectedMessages && selectedChanged) {
      await refreshMessages(selectedWaId, { preserveScroll: true, silent: true });
    }
  }

  async function refreshMessages(wa_id, { preserveScroll = true, silent = false } = {}) {
    if (!wa_id) return;
    const requestSeq = ++messagesRequestSeqRef.current;
    if (!silent) setLoadingMsgs(true);
    setErr("");
    dbg("messages:request", {
      wa_id,
      requestSeq,
      selected: selectedRef.current,
      silent,
    });

    try {
      const box = chatScrollRef.current;
      const wasNearBottom = box
        ? box.scrollHeight - box.scrollTop - box.clientHeight < 160
        : true;

      const items = await getMessages(wa_id, 40);
      const currentSelected = selectedRef.current;
      const isStaleRequest = requestSeq !== messagesRequestSeqRef.current;
      const isStaleSelection = Boolean(currentSelected && currentSelected !== wa_id);

      if (isStaleRequest || isStaleSelection) {
        dbg("messages:discard", {
          wa_id,
          requestSeq,
          currentSelected,
          currentRequestSeq: messagesRequestSeqRef.current,
        });
        return;
      }

      const prevCount = lastMessageCountRef.current;
      const nextCount = Array.isArray(items) ? items.length : 0;

      setMsgs(items || []);
      lastMessageCountRef.current = nextCount;
      dbg("messages:apply", {
        wa_id,
        requestSeq,
        count: nextCount,
        lastCreatedAt: nextCount ? items[nextCount - 1]?.created_at || null : null,
      });

      const conv = (convsRef.current || []).find((c) => c.wa_id === wa_id);
      const lastAt = conv?.last_message_at || conv?.last_at;

      if (lastAt) {
        setSeen((prev) => {
          const next = { ...(prev || {}), [wa_id]: lastAt };
          saveJSON(LS_SEEN_KEY, next);
          return next;
        });
      }

      requestAnimationFrame(() => {
        const el = chatScrollRef.current;
        if (!el) return;

        const hasNewMessages = nextCount > prevCount;

        if (!preserveScroll) {
          el.scrollTop = el.scrollHeight;
          return;
        }

        if (hasNewMessages && wasNearBottom) {
          el.scrollTop = el.scrollHeight;
        }
      });
    } catch (e) {
      if (requestSeq === messagesRequestSeqRef.current) {
        setErr(String(e.message || e));
      }
    } finally {
      if (!silent && requestSeq === messagesRequestSeqRef.current) {
        setLoadingMsgs(false);
      }
    }
  }

  async function refreshTasks({ silent = false } = {}) {
    if (!silent) setLoadingTasks(true);
    setErr("");

    try {
      const items = await listTasks({ status: "open" });
      setTasks(items || []);
      dbg("refreshTasks:success", { total: items?.length || 0 });
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      if (!silent) setLoadingTasks(false);
    }
  }

  async function refreshAll({ keepSelected = true, silent = false } = {}) {
    await Promise.all([
      refreshConversations({ keepSelected, silent }),
      refreshTasks({ silent }),
      refreshDashboard({ silent }),
    ]);
  }

  async function handleRefreshAll() {
    if (refreshingAll) return;
    setRefreshingAll(true);
    setErr("");

    try {
      await refreshAll({ keepSelected: true, silent: true });
      showToast("Painel atualizado.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setRefreshingAll(false);
    }
  }

  async function handleRefreshTasksSummary() {
    if (refreshingTasksSummary) return;
    setRefreshingTasksSummary(true);
    setErr("");

    try {
      await Promise.all([
        refreshTasks({ silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      showToast("Agenda e indicadores sincronizados.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setRefreshingTasksSummary(false);
    }
  }

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    (async () => {
      await getMe().catch(() => null);
      await refreshAll({ keepSelected: false });
    })();
  }, []);

  useEffect(() => {
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch {
        // Ignore EventSource close errors during reconnects.
      }
      esRef.current = null;
    }

    let cancelled = false;

    const loadSSE = async () => {
      try {
        const url = await sseUrl();
        if (!url || cancelled) return;

        const es = new EventSource(url);
        esRef.current = es;

        const handleIncomingConversationsEvent = async (raw, source) => {
          try {
            const payload = JSON.parse(raw || "{}");
            await applyIncomingConversations(payload?.items || [], {
              keepSelected: true,
              refreshSelectedMessages: true,
              source,
            });
          } catch (e) {
            console.warn("SSE parse fail:", e);
          }
        };

        es.addEventListener("conversations", (ev) => {
          handleIncomingConversationsEvent(ev.data, "sse:conversations");
        });

        es.onmessage = (ev) => {
          handleIncomingConversationsEvent(ev.data, "sse:message");
        };

        es.onerror = (e) => {
          console.warn("SSE error:", e);
        };
      } catch (e) {
        console.warn("SSE init error:", e);
      }
    };

    loadSSE();

    return () => {
      cancelled = true;
      if (esRef.current) {
        try {
          esRef.current.close();
        } catch {
          // Ignore EventSource close errors during teardown.
        }
        esRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    messagesRequestSeqRef.current += 1;
    lastMessageCountRef.current = 0;
    setMsgs([]);

    if (!selected) {
      setLoadingMsgs(false);
      return;
    }
    dbg("selected:change", {
      selected,
      selectedConv: selectedConv?.wa_id || null,
    });

    refreshMessages(selected, { preserveScroll: false }).catch((e) => {
      setErr(String(e.message || e));
    });
  }, [selected]);

  useEffect(() => {
    let cancelled = false;
    let inFlight = false;

    const timer = window.setInterval(async () => {
      if (cancelled || inFlight) return;
      inFlight = true;

      try {
        await refreshConversations({ keepSelected: true, silent: true });
      } catch {
        // ignora erro do polling leve de fallback
      } finally {
        inFlight = false;
      }
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (view !== "inbox" || !selected) return;

    let cancelled = false;
    let inFlight = false;
    dbg("poll:start", { wa_id: selected });

    const timer = window.setInterval(() => {
      if (cancelled || inFlight) return;

      inFlight = true;
      refreshMessages(selected, { preserveScroll: true, silent: true })
        .catch(() => null)
        .finally(() => {
          inFlight = false;
        });
    }, 5000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
      dbg("poll:stop", { wa_id: selected });
    };
  }, [selected, view]);

  useEffect(() => {
    if (!selected) return;
    requestAnimationFrame(() => {
      scrollSelectedConversationIntoView();
    });
  }, [selected, convs, view]);

  const sourceOptions = useMemo(() => {
    const set = new Set();
    convs.forEach((c) => {
      const source = c?.source || c?.last_source;
      if (source) set.add(source);
    });
    return ["todos", ...Array.from(set)];
  }, [convs]);

  const ownerOptions = useMemo(() => {
    const set = new Set();
    convs.forEach((c) => {
      const owner = c?.assigned_to || c?.human_owner || c?.owner;
      if (owner) set.add(owner);
    });
    return ["todos", ...Array.from(set)];
  }, [convs]);

  const statusOptions = useMemo(() => {
    const set = new Set(["ativos", "todos", "arquivados"]);
    convs.forEach((c) => {
      if (c?.operation_status) set.add(c.operation_status);
    });
    return Array.from(set);
  }, [convs]);

  const unreadCount = (conv) => {
    const lastAt = conv?.last_message_at || conv?.last_at;
    if (!lastAt) return 0;
    const seenAt = seen?.[conv.wa_id];
    if (!seenAt) return 1;
    return new Date(lastAt).getTime() > new Date(seenAt).getTime() ? 1 : 0;
  };

  const sidebarConvs = useMemo(() => {
    const terms = q
      .trim()
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean);

    const sourceItems = (convs || []).filter((c) => String(c?.wa_id || "").trim());
    console.debug(`sidebar:source total=${sourceItems.length}`);

    const afterSearch = sourceItems.filter((c) => {
      const source = c?.source || c?.last_source || "";
      const owner = c?.assigned_to || c?.human_owner || c?.owner || "";

      if (!terms.length) return true;

      const searchable = [
        c?.wa_id,
        c?.name,
        c?.telefone,
        c?.last_message,
        c?.last_text,
        source,
        c?.operation_status,
        c?.stage,
        c?.lead_stage,
        owner,
        c?.notes,
        Array.isArray(c?.tags) ? c.tags.join(" ") : "",
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return terms.every((term) => searchable.includes(term));
    });
    console.debug(`sidebar:afterSearch total=${afterSearch.length}`);
    const finalItems = sortByRecent(afterSearch);
    console.debug(`sidebar:visible total=${finalItems.length}`);

    return finalItems;
  }, [q, convs]);

  const visibleConvs = useMemo(() => {
    return sortByRecent(
      sidebarConvs.filter((c) => {
        return dashboardFilter === "todos"
          ? true
          : dashboardFilter === "novos"
          ? isConversationNewToday(c)
          : dashboardFilter === "handoff"
          ? Boolean(c?.handoff_active || c?.handoff_pending || c?.operation_status === "handoff")
          : dashboardFilter === "agendados"
          ? Boolean(c?.next_task)
          : dashboardFilter === "ativos"
          ? !isArchivedConversation(c)
          : true;
      })
    );
  }, [sidebarConvs, dashboardFilter]);

  const activeFilterCount = useMemo(() => {
    return [
      q.trim(),
    ].filter(Boolean).length;
  }, [q]);

  function clearSidebarFilters() {
    setQ("");
  }

  function getStageByConv(conv) {
    return conv?.stage || conv?.lead_stage || stages?.[conv?.wa_id] || "Novo";
  }

  function getStage(wa_id) {
    const conv = convs.find((c) => c.wa_id === wa_id);
    return getStageByConv(conv);
  }

  function applyDashboardCardFilter(nextFilter, nextView) {
    setDashboardFilter(nextFilter);
    setView(nextView);
  }

  function onDashboardCardKeyDown(e, nextFilter, nextView) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      applyDashboardCardFilter(nextFilter, nextView);
    }
  }

  const kpis = useMemo(() => {
    const novosHoje = getTodayLeadsCount(dashboardSummary, convs);
    return {
      total: dashboardSummary.conversations_open || convs.length,
      novos: novosHoje,
      handoff: dashboardSummary.handoffs_pending || convs.filter((c) => c.handoff_active).length,
      agendados: tasks.length,
    };
  }, [convs, seen, dashboardSummary, tasks]);

  const sourceStats = useMemo(() => {
    const raw = dashboardSummary.leads_by_source || {};
    const entries = Object.entries(raw);

    if (entries.length) {
      return entries
        .map(([key, total]) => ({
          key,
          label: key === "sem_origem" ? "Sem origem" : normalizeSourceLabel(key),
          total,
        }))
        .sort((a, b) => b.total - a.total);
    }

    const counts = {};
    convs.forEach((c) => {
      const source = c?.source || c?.last_source || "sem_origem";
      counts[source] = (counts[source] || 0) + 1;
    });

    return Object.entries(counts)
      .map(([key, total]) => ({
        key,
        label: key === "sem_origem" ? "Sem origem" : normalizeSourceLabel(key),
        total,
      }))
      .sort((a, b) => b.total - a.total);
  }, [convs, dashboardSummary]);

  const todayTasks = useMemo(() => {
    return tasks
      .filter((t) => isTodayDate(t.due_at))
      .sort((a, b) => new Date(a.due_at).getTime() - new Date(b.due_at).getTime())
      .slice(0, 6);
  }, [tasks]);

  const latestLeads = useMemo(() => {
    return sortByRecent(visibleConvs).slice(0, 6);
  }, [visibleConvs]);

  const topSource = sourceStats[0] || null;

  async function onSend() {
    const t = text.trim();
    if (!t || !selected) return;

    const optimisticMessage = {
      id: `temp-${Date.now()}`,
      direction: "out",
      text: t,
      created_at: new Date().toISOString(),
    };

    setText("");
    setErr("");
    setMsgs((prev) => [...prev, optimisticMessage]);

    prependOrReplaceConversationLocal({
      ...(selectedConv || {}),
      wa_id: selected,
      last_message: t,
      last_text: t,
      last_message_at: optimisticMessage.created_at,
      last_at: optimisticMessage.created_at,
    });

    requestAnimationFrame(() => {
      const el = chatScrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });

    try {
      await sendMessage(selected, t);
      await Promise.all([
        refreshMessages(selected, { preserveScroll: false, silent: true }),
        refreshConversations({ keepSelected: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      inputRef.current?.focus?.();
    } catch (e) {
      setErr(String(e.message || e));
      await refreshMessages(selected, { preserveScroll: false, silent: true });
    }
  }

  async function onCloseHandoff() {
    if (!selected) return;
    setErr("");

    replaceConversationLocal({
      wa_id: selected,
      handoff_active: false,
      handoff_pending: false,
      operation_status: "bot_active",
    });

    try {
      await closeHandoff(selected);
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshMessages(selected, { preserveScroll: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }

  async function onDeleteConversation() {
    console.log("[DELETE_DEBUG] clique no botão", {
      selected,
      selectedConv,
      deletingConv,
    });
  
    if (!selectedConv?.wa_id || deletingConv) {
      console.log("[DELETE_DEBUG] saiu no guard", {
        hasWaId: !!selectedConv?.wa_id,
        deletingConv,
      });
      return;
    }

  
    const confirmed = window.confirm(
      `Apagar a conversa com "${getDisplayName(selectedConv)}"?\n\nEssa ação remove mensagens, tarefas e estados vinculados a este contato.`
    );
  
    console.log("[DELETE_DEBUG] confirm result", { confirmed });
  
    if (!confirmed) return;
  
    setDeletingConv(true);
    setErr("");
  
    const removedWaId = selectedConv.wa_id;
  
    try {
      console.log("[DELETE_DEBUG] chamando deleteConversation", { removedWaId });
  
      const result = await deleteConversation(removedWaId);
  
      console.log("[DELETE_DEBUG] retorno deleteConversation", JSON.stringify(result, null, 2));
  
      setConvs((prev) => prev.filter((c) => c.wa_id !== removedWaId));
      setMsgs([]);
  
      if (selected === removedWaId) {
        const remaining = convs.filter((c) => c.wa_id !== removedWaId);
        setSelected(remaining[0]?.wa_id || null);
      }
  
      await Promise.all([
        refreshTasks({ silent: true }),
        refreshDashboard({ silent: true }),
      ]);
  
      showToast("Conversa apagada com sucesso.");
    } catch (e) {
      console.error("[DELETE_DEBUG] erro ao apagar", e);
      setErr(String(e.message || e));
      await refreshAll({ keepSelected: true, silent: true });
    } finally {
      setDeletingConv(false);
    }
  }

  async function onArchiveConversation() {
    if (!selectedConv?.wa_id) return;

    const archived = isArchivedConversation(selectedConv);
    const actionLabel = archived ? "desarquivar" : "arquivar";
    const confirmed = window.confirm(
      `${archived ? "Desarquivar" : "Arquivar"} a conversa de "${getDisplayName(selectedConv)}"?`
    );

    if (!confirmed) return;

    setErr("");

    const payload = archived
      ? {
          stage: "Novo",
          lead_stage: "novo",
          closed_at: null,
        }
      : {
          stage: "Fechado",
          lead_stage: "arquivado",
          closed_at: new Date().toISOString(),
        };

    replaceConversationLocal({
      wa_id: selectedConv.wa_id,
      ...payload,
    });

    try {
      await updateContact(selectedConv.wa_id, payload);
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      showToast(`Conversa ${actionLabel}da com sucesso.`);
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }
  function setStageLocal(wa_id, stage) {
    const next = { ...(stages || {}), [wa_id]: stage };
    setStages(next);
    saveJSON(LS_STAGE_KEY, next);
  }

  const kanbanCols = useMemo(() => {
    const cols = {};
    STAGES.forEach((s) => {
      cols[s] = [];
    });

    for (const c of visibleConvs) {
      const s = getStageByConv(c);
      (cols[s] ||= []).push(c);
    }

    for (const k of Object.keys(cols)) {
      cols[k].sort((a, b) => {
        const ta = a.last_message_at || a.last_at ? new Date(a.last_message_at || a.last_at).getTime() : 0;
        const tb = b.last_message_at || b.last_at ? new Date(b.last_message_at || b.last_at).getTime() : 0;
        return tb - ta;
      });
    }

    return cols;
  }, [visibleConvs, stages]);

  function onDragStart(ev, wa_id) {
    ev.dataTransfer.setData("text/plain", wa_id);
    ev.dataTransfer.effectAllowed = "move";
  }

  async function onDropStage(ev, stage) {
    ev.preventDefault();
    const raw = ev.dataTransfer.getData("text/plain");
    if (!raw) return;

    const wa_id = raw.startsWith("lead:")
      ? raw.replace("lead:", "").trim()
      : raw.trim();

    if (!wa_id) return;

    setStageLocal(wa_id, stage);
    replaceConversationLocal({
      wa_id,
      stage,
      lead_stage: stage,
    });

    try {
      await updateContact(wa_id, {
        stage,
        lead_stage: stage.toLowerCase(),
      });
      await refreshDashboard({ silent: true });
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }

  function openChat(wa_id, source = "ui") {
    dbg("conversation:open", {
      source,
      wa_id,
      previousSelected: selectedRef.current,
    });
    setSelected(wa_id);
    setView("inbox");

    requestAnimationFrame(() => {
      scrollSelectedConversationIntoView();
      setTimeout(() => {
        const el = chatScrollRef.current;
        if (el) el.scrollTop = el.scrollHeight;
        inputRef.current?.focus?.();
      }, 80);
    });
  }

  const taskCols = useMemo(() => {
    const cols = {};
    TASK_COLS.forEach((k) => {
      cols[k] = [];
    });

    for (const t of tasks) {
      const b = taskBucket(t.due_at);
      (cols[b] ||= []).push(t);
    }

    for (const k of Object.keys(cols)) {
      cols[k].sort((a, b) => {
        const ta = a.due_at ? new Date(a.due_at).getTime() : 0;
        const tb = b.due_at ? new Date(b.due_at).getTime() : 0;
        return ta - tb;
      });
    }

    return cols;
  }, [tasks]);

  function onCreateTaskQuick() {
    if (!selected) {
      setErr("Selecione um contato antes de agendar.");
      return;
    }
    setTaskTitle("Atendimento / Follow-up");
    setTaskDate(new Date().toISOString().slice(0, 10));
    setTaskTime("12:00");
    setTaskModalOpen(true);
  }

  async function onConfirmTask() {
    if (!selected || taskSaving) return;

    setErr("");
    setTaskSaving(true);

    const due_at = toIsoLocal(taskDate, taskTime);
    const optimisticTask = {
      id: `temp-${Date.now()}`,
      wa_id: selected,
      title: taskTitle.trim() || "Atendimento / Follow-up",
      due_at,
      status: "open",
    };

    const baseNotes = String(selectedConv?.notes || "");
    const stamp = `Agendado: ${taskTitle.trim() || "Atendimento / Follow-up"} • ${taskDate}T${taskTime}`;
    const nextNotes = baseNotes ? `${baseNotes}\n${stamp}` : stamp;

    setTasks((prev) => [optimisticTask, ...prev]);

    replaceConversationLocal({
      wa_id: selected,
      notes: nextNotes,
      next_task: optimisticTask,
      stage: "Qualificado",
      lead_stage: "qualificado",
    });

    setStageLocal(selected, "Qualificado");

    try {
      const created = await createTask({
        wa_id: selected,
        title: taskTitle.trim() || "Atendimento / Follow-up",
        due_at,
      });

      setTasks((prev) =>
        prev.map((t) => (t.id === optimisticTask.id ? { ...optimisticTask, ...(created || {}) } : t))
      );

      await updateContact(selected, {
        notes: nextNotes,
        stage: "Qualificado",
        lead_stage: "qualificado",
      });

      setTaskModalOpen(false);

      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshTasks({ silent: true }),
        refreshDashboard({ silent: true }),
      ]);
    } catch (e) {
      setErr(String(e.message || e));
      await refreshTasks({ silent: true });
      await refreshConversations({ keepSelected: true, silent: true });
    } finally {
      setTaskSaving(false);
    }
  }

  async function onDoneTask(id) {
    setErr("");
    const prevTasks = tasks;
    setTasks((prev) => prev.filter((t) => t.id !== id));

    try {
      await doneTask(id);
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
    } catch (e) {
      setErr(String(e.message || e));
      setTasks(prevTasks);
    }
  }

  const savedContacts = useMemo(() => {
    return (visibleConvs || [])
      .filter((c) => Array.isArray(c.tags) && c.tags.includes("salvo"))
      .sort((a, b) => {
        const ta = a.last_message_at || a.last_at ? new Date(a.last_message_at || a.last_at).getTime() : 0;
        const tb = b.last_message_at || b.last_at ? new Date(b.last_message_at || b.last_at).getTime() : 0;
        return tb - ta;
      });
  }, [visibleConvs]);

  function openEditContact() {
    if (!selectedConv) return;
    setEditName(selectedConv.name || "");
    setEditTel(selectedConv.telefone || "");
    setEditStage(getStage(selectedConv.wa_id));
    setEditTags(Array.isArray(selectedConv.tags) ? selectedConv.tags.join(", ") : "");
    setEditNotes(selectedConv.notes || "");
    setEditOwner(selectedConv.assigned_to || selectedConv.human_owner || "");
    setEditAttendanceMode(selectedConv.attendance_mode || "hybrid");
    setEditSource(selectedConv.source || selectedConv.last_source || "");
    setEditOpen(true);
  }

  async function saveContactEdits() {
    if (!selected || contactSaving) return;

    setErr("");
    setContactSaving(true);

    const tags = parseTags(editTags);
    if (!tags.includes("salvo")) tags.push("salvo");

    replaceConversationLocal({
      wa_id: selected,
      name: editName,
      telefone: editTel,
      stage: editStage,
      lead_stage: editStage,
      notes: editNotes,
      tags,
      assigned_to: editOwner,
      human_owner: editAttendanceMode === "human" ? editOwner : "",
      attendance_mode: editAttendanceMode,
      source: editSource,
    });

    setStageLocal(selected, editStage);

    try {
      await updateContact(selected, {
        name: editName,
        telefone: editTel,
        stage: editStage,
        lead_stage: editStage.toLowerCase(),
        notes: editNotes,
        tags,
        assigned_to: editOwner,
        human_owner: editAttendanceMode === "human" ? editOwner : "",
        attendance_mode: editAttendanceMode,
        source: editSource,
      });

      setEditOpen(false);
      await refreshDashboard({ silent: true });
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
      await refreshMessages(selected, { preserveScroll: true, silent: true });
    } finally {
      setContactSaving(false);
    }
  }

  function onDragStartTask(ev, taskId) {
    ev.dataTransfer.setData("text/plain", `task:${taskId}`);
    ev.dataTransfer.effectAllowed = "move";
  }

  async function onDropTask(ev, bucket) {
    ev.preventDefault();
    const raw = ev.dataTransfer.getData("text/plain");
    if (!raw || !raw.startsWith("task:")) return;

    const taskId = raw.replace("task:", "").trim();
    const nextDue = dueForBucket(bucket);
    if (!nextDue) return;

    const prevTasks = tasks;
    setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, due_at: nextDue } : t)));

    try {
      setErr("");
      await updateTask(taskId, { due_at: nextDue });
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
    } catch (e) {
      setErr(String(e.message || e));
      setTasks(prevTasks);
    }
  }

  function onDragStartSaved(ev, wa_id) {
    ev.dataTransfer.setData("text/plain", `lead:${wa_id}`);
    ev.dataTransfer.effectAllowed = "move";
  }

  const selectedStatusMeta = getOperationStatusMeta(selectedConv?.operation_status);
  const selectedAttendanceMeta = getAttendanceModeMeta(selectedConv?.attendance_mode);
  const selectedOwner = selectedConv?.assigned_to || selectedConv?.human_owner || "Sem responsável";
  const selectedFlowData = useMemo(() => {
    const value = selectedConv?.flow_data;
    if (!value) return {};
    if (typeof value === "object") return value;
    try {
      return JSON.parse(value);
    } catch {
      return {};
    }
  }, [selectedConv?.flow_data]);
  const selectedStrategicSnapshot = useMemo(
    () => buildStrategicSnapshot(selectedConv, selectedFlowData, selectedStatusMeta),
    [selectedConv, selectedFlowData, selectedStatusMeta]
  );

  useEffect(() => {
    if (!selectedConv?.wa_id) return;
    console.debug(`automation:status ${selectedConv.operation_status || ""}`);
    console.debug(`automation:step ${selectedFlowData.current_step || selectedConv.flow_state || ""}`);
  }, [selectedConv?.wa_id, selectedConv?.operation_status, selectedConv?.flow_state, selectedFlowData.current_step]);

  return (
    <div className="wbShell">
      <aside className="wbRail">
        <div className="wbBrand">
          <img src={logoMugo} alt="Mugô" />
        </div>

        <button className={`wbRailBtn ${view === "dashboard" ? "active" : ""}`} onClick={() => setView("dashboard")} title="Dashboard">
          ✨
        </button>
        <button className={`wbRailBtn ${view === "inbox" ? "active" : ""}`} onClick={() => setView("inbox")} title="Inbox">
          💬
        </button>
        <button className={`wbRailBtn ${view === "kanban" ? "active" : ""}`} onClick={() => setView("kanban")} title="Pipeline">
          🗂️
        </button>
        <button className={`wbRailBtn ${view === "agenda" ? "active" : ""}`} onClick={() => setView("agenda")} title="Agenda">
          🗓️
        </button>
        <button className={`wbRailBtn ${view === "contatos" ? "active" : ""}`} onClick={() => setView("contatos")} title="Contatos">
          👤
        </button>

        <button className="wbRailBtn" onClick={handleLogout} title="Sair">
          ↩
        </button>

        <div className="wbRailSpacer" />
      </aside>

      <aside className="wbSidebar">
        <div className="wbSidebarTop">
          <div className="wbSidebarBrand">
            <div className="wbSidebarLogo">
              <img src={logoMugo} alt="Mugô" />
            </div>
            <div className="wbTopRight">
              <div className="wbSidebarMeta">
                {refreshingAll ? "Atualizando..." : `${sidebarConvs.length} conversas`}
              </div>
              {activeFilterCount ? (
                <button className="wbBtnGhost wbBtnGhostCompact" onClick={clearSidebarFilters}>
                  Limpar
                </button>
              ) : null}
            </div>
          </div>
        </div>

        <div className={`wbSearch ${sidebarCollapsed ? "collapsed" : ""}`}>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar conversa por nome, telefone, mensagem ou WA ID..."
          />
        </div>

        <div className="wbList">
          {loadingConvs ? (
            <div className="wbEmpty">
              Carregando conversas...
              <div className="wbEmptyHint">Buscando leads e histórico recente.</div>
            </div>
          ) : (
            <>
              {sidebarConvs.map((c) => {
                const active = c.wa_id === selected;
                const unread = unreadCount(c);
                const source = c.source || c.last_source;
                const statusMeta = getOperationStatusMeta(c.operation_status);
                const archived = isArchivedConversation(c);
                const isTest = isTestConversation(c);

                return (
                  <button
                    key={c.wa_id}
                    ref={c.wa_id === selected ? selectedItemRef : null}
                    className={`wbItem ${active ? "active" : ""}`}
                    onClick={() => openChat(c.wa_id, "sidebar")}
                  >
                    <div className="wbAvatar">{getAvatarSeed(c)}</div>

                    <div className="wbItemMid">
                      <div className="wbItemTop">
                        <div className="wbName">{getDisplayName(c)}</div>
                        <div className="wbTime">{shortTime(c.last_message_at || c.last_at)}</div>
                      </div>

                      <div className="wbPreviewRow">
                        <div className="wbPreview">{clip(c.last_message || c.last_text || "", 90)}</div>

                        {source ? <span className="wbBadge">{normalizeSourceLabel(source)}</span> : null}
                        <span className={statusMeta.className}>{statusMeta.label}</span>
                        {c.assigned_to ? <span className="wbBadge">{normalizeOwnerLabel(c.assigned_to)}</span> : null}
                        {archived ? <span className="wbBadge">arquivado</span> : null}
                        {isTest ? <span className="wbBadge warn">demo</span> : null}
                        {c.next_task ? <span className="wbBadge ok">agendado</span> : null}
                        {unread ? <span className="wbBadge ok">novo</span> : null}
                      </div>
                    </div>
                  </button>
                );
              })}

              {!sidebarConvs.length && (
                <div className="wbEmpty">
                  Sem conversas nesse filtro.
                  <div className="wbEmptyHint">Revise busca, origem, status, responsável ou o filtro de demos.</div>
                </div>
              )}
            </>
          )}
        </div>
      </aside>

      <main className={`wbMain ${view === "inbox" ? "wbMainInbox" : ""}`}>
        <header className="wbHeader">
          <div className="wbHeaderLeft">
            {view === "dashboard" ? (
              <>
                <div className="wbHeaderTitle">Visão geral da operação</div>
                <div className="wbHeaderSub">
                  Visão operacional em tempo real dos leads, origens, tarefas e atendimento.
                </div>
              </>
            ) : view === "inbox" ? (
              <>
                <div className="wbHeaderTitle">{getDisplayName(selectedConv) || selected || "Selecione uma conversa"}</div>
                <div className="wbHeaderSub">
                  {selected ? `Contato: ${formatPhoneBR(selected)}` : "Central de conversas Mugô"}
                  {selectedConv?.telefone ? ` • Telefone: ${formatPhoneBR(selectedConv.telefone)}` : ""}
                  {selectedConv?.assigned_to ? ` • Responsável: ${selectedConv.assigned_to}` : ""}
                  {selected ? ` • Etapa: ${getStage(selected)}` : ""}
                  {selectedConv?.source || selectedConv?.last_source
                    ? ` • Origem: ${normalizeSourceLabel(selectedConv?.source || selectedConv?.last_source)}`
                    : ""}
                  {selectedConv?.operation_status ? ` • Status: ${selectedStatusMeta.label}` : ""}
                </div>
              </>
            ) : view === "kanban" ? (
              <>
                <div className="wbHeaderTitle">Funil Comercial</div>
                <div className="wbHeaderSub">Organize os leads por etapa e acompanhe a evolução de cada oportunidade.</div>
              </>
            ) : view === "agenda" ? (
              <>
                <div className="wbHeaderTitle">Agenda</div>
                <div className="wbHeaderSub">Gerencie prazos, follow-ups e prioridades da operação.</div>
              </>
            ) : (
              <>
                <div className="wbHeaderTitle">Contatos salvos</div>
                <div className="wbHeaderSub">Base de relacionamento da Mugô.</div>
              </>
            )}
          </div>

          <div className="wbHeaderRight">
            <button className="wbBtnGhost" onClick={() => setSidebarCollapsed((prev) => !prev)}>
              {sidebarCollapsed ? "Mostrar filtros" : "Ocultar filtros"}
            </button>

            {err ? <div className="wbError">Erro: {err}</div> : null}

            {view === "dashboard" ? (
              <>
                <button className="wbBtn" onClick={handleRefreshAll} disabled={refreshingAll}>
                  {refreshingAll ? "Atualizando painel..." : "Atualizar painel"}
                </button>
                <button className="wbBtnGhost" onClick={handleRefreshTasksSummary} disabled={refreshingTasksSummary}>
                  {refreshingTasksSummary ? "Sincronizando..." : "Sincronizar tarefas"}
                </button>
              </>
            ) : null}

            {view === "inbox" ? (
              <>
                <button className="wbBtn" onClick={() => inputRef.current?.focus?.()} disabled={!selected}>
                  Nova mensagem
                </button>

                <button className="wbBtnGhost" onClick={onCreateTaskQuick} disabled={!selected}>
                  Nova tarefa
                </button>

                <button className="wbBtnGhost" onClick={openEditContact} disabled={!selected}>
                  Editar contato
                </button>

                <button className="wbBtnGhost" onClick={onArchiveConversation} disabled={!selected}>
                  {isArchivedConversation(selectedConv) ? "Desarquivar" : "Arquivar"}
                </button>

                {selectedConv?.handoff_active || selectedConv?.operation_status === "handoff" ? (
                  <button className="wbBtnGhost" onClick={onCloseHandoff}>
                    Encerrar atendimento
                  </button>
                ) : null}

                <button
                  className="wbBtnGhost"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onDeleteConversation();
                  }}
                  disabled={!selected || deletingConv}
                  title="Apagar conversa"
                >
                  {deletingConv ? "Apagando..." : "Apagar conversa"}
                </button>
              </>
            ) : null}

            {view === "agenda" ? (
              <button className="wbBtnGhost" onClick={handleRefreshTasksSummary} disabled={refreshingTasksSummary}>
                {refreshingTasksSummary ? "Sincronizando agenda..." : "Sincronizar agenda"}
              </button>
            ) : null}
          </div>
        </header>

        {view === "dashboard" ? (
          <>
            <div className="wbKpis">
              <div
                className="wbKpiCard"
                onClick={() => applyDashboardCardFilter("todos", "kanban")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => onDashboardCardKeyDown(e, "todos", "kanban")}
                title="Filtrar todos os leads"
              >
                <div className="wbKpiLabel">Leads</div>
                <div className="wbKpiValue">{kpis.total}</div>
              </div>
              <div
                className="wbKpiCard"
                onClick={() => applyDashboardCardFilter("novos", "kanban")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => onDashboardCardKeyDown(e, "novos", "kanban")}
                title="Filtrar novos leads"
              >
                <div className="wbKpiLabel">Novos</div>
                <div className="wbKpiValue">{kpis.novos}</div>
              </div>
              <div
                className="wbKpiCard"
                onClick={() => applyDashboardCardFilter("handoff", "inbox")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => onDashboardCardKeyDown(e, "handoff", "inbox")}
                title="Filtrar leads em atendimento"
              >
                <div className="wbKpiLabel">Em atendimento</div>
                <div className="wbKpiValue">{dashboardSummary.handoffs_pending || kpis.handoff}</div>
              </div>
              <div
                className="wbKpiCard"
                onClick={() => applyDashboardCardFilter("agendados", "agenda")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => onDashboardCardKeyDown(e, "agendados", "agenda")}
                title="Filtrar leads agendados"
              >
                <div className="wbKpiLabel">Agendados</div>
                <div className="wbKpiValue">{kpis.agendados}</div>
              </div>
              <div
                className="wbKpiCard"
                onClick={() => applyDashboardCardFilter("ativos", "kanban")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => onDashboardCardKeyDown(e, "ativos", "kanban")}
                title="Filtrar leads ativos"
              >
                <div className="wbKpiLabel">Ativos</div>
                <div className="wbKpiValue">{convs.filter((c) => !isArchivedConversation(c)).length}</div>
              </div>
            </div>

          <section className="wbKanban">
            <div className="wbDashboardHero">
              <div className="wbHeroCard">
                <div className="wbHeroEyebrow">Operação Mugô</div>
                <div className="wbHeroTitle">
                  Leads centralizados, origem mapeada e equipe pronta para agir.
                </div>
                <div className="wbHeroText">
                  Acompanhe novos contatos, principais canais de aquisição, tarefas do dia e avance rapidamente para o atendimento.
                </div>
                <div className="wbHeroActions">
                  <button className="wbBtn" onClick={() => setView("inbox")}>Abrir conversas</button>
                  <button className="wbBtnGhost" onClick={() => setView("kanban")}>Ver pipeline</button>
                  <button className="wbBtnGhost" onClick={() => setView("agenda")}>Ver agenda</button>
                </div>
              </div>

              <div className="wbSummaryGrid">
                <div className="wbCol">
                  <div className="wbColHead">
                    <div>
                      <div className="wbSectionTitle">Origem principal</div>
                      <div className="wbSectionSub">Canal com mais volume agora</div>
                    </div>
                  </div>
                  <div className="wbColBody">
                    {topSource ? (
                      <>
                        <div className="wbStatRow">
                          <span className="wbStatLabel">{topSource.label}</span>
                          <span className="wbStatValue">{topSource.total}</span>
                        </div>
                        <div className="wbMetricBar">
                          <div
                            className="wbMetricBarFill"
                            style={{
                              width: `${Math.max(
                                10,
                                Math.round((topSource.total / Math.max(1, kpis.total || convs.length || 1)) * 100)
                              )}%`,
                            }}
                          />
                        </div>
                      </>
                    ) : (
                      <div className="wbEmpty">Sem dados de origem ainda.</div>
                    )}
                  </div>
                </div>

                <div className="wbCol">
                  <div className="wbColHead">
                    <div>
                      <div className="wbSectionTitle">Tarefas de hoje</div>
                      <div className="wbSectionSub">Acompanhamento imediato</div>
                    </div>
                  </div>
                  <div className="wbColBody">
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Hoje</span>
                      <span className="wbStatValue">{todayTasks.length}</span>
                    </div>
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Urgentes</span>
                      <span className="wbStatValue">{dashboardSummary.urgent_tasks || 0}</span>
                    </div>
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Total aberto</span>
                      <span className="wbStatValue">{tasks.length}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="wbDashboardGrid" style={{ marginTop: 16 }}>
              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Leads por origem</div>
                    <div className="wbSectionSub">Distribuição dos canais de entrada</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbStatList">
                    {sourceStats.length ? (
                      sourceStats.map((item) => (
                        <div key={item.key} className="wbStatRow">
                          <span className="wbStatLabel">{item.label}</span>
                          <span className="wbStatValue">{item.total}</span>
                        </div>
                      ))
                    ) : (
                      <div className="wbEmpty">Nenhuma origem identificada ainda.</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="wbDashboardColTall">
                <div className="wbCol">
                  <div className="wbColHead">
                    <div>
                      <div className="wbSectionTitle">Leads recentes</div>
                      <div className="wbSectionSub">Últimas conversas com atividade</div>
                    </div>
                  </div>
                  <div className="wbColBody">
                    <div className="wbMiniList">
                      {latestLeads.length ? (
                        latestLeads.map((lead) => {
                          const op = getOperationStatusMeta(lead.operation_status);
                          return (
                            <div key={lead.wa_id} className="wbMiniItem">
                              <div className="wbMiniItemMain">
                                <div className="wbMiniTitle">{getDisplayName(lead)}</div>
                        <div className="wbMiniSub">
                                  {normalizeSourceLabel(lead.source || lead.last_source)} • {clip(lead.last_message || lead.last_text || "", 48)}
                                </div>
                                <div style={{ marginTop: 6 }}>
                                  <span className={op.className}>{op.label}</span>
                                  {isConversationNewToday(lead) ? <span className="wbBadge ok">novo hoje</span> : null}
                                </div>
                              </div>
                              <button className="wbBtnGhost" onClick={() => openChat(lead.wa_id)}>
                                Abrir
                              </button>
                            </div>
                          );
                        })
                      ) : (
                        <div className="wbEmpty">Sem leads recentes.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="wbDashboardGrid" style={{ marginTop: 16 }}>
              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Agenda de hoje</div>
                    <div className="wbSectionSub">Tarefas que precisam de ação</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbMiniList">
                    {todayTasks.length ? (
                      todayTasks.map((task) => (
                        <div key={task.id} className="wbMiniItem">
                          <div className="wbMiniItemMain">
                            <div className="wbMiniTitle">{task.title}</div>
                            <div className="wbMiniSub">{formatPhoneBR(task.wa_id)}</div>
                          </div>
                          <div className="wbMiniMeta">{shortTime(task.due_at)}</div>
                        </div>
                      ))
                    ) : (
                      <div className="wbEmpty">Nenhuma tarefa marcada para hoje.</div>
                    )}
                  </div>
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Funil resumido</div>
                    <div className="wbSectionSub">Status geral das etapas</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbStatList">
                    {STAGES.map((stage) => (
                      <div key={stage} className="wbStatRow">
                        <span className="wbStatLabel">{stage}</span>
                        <span className="wbStatValue">{(kanbanCols[stage] || []).length}</span>
                      </div>
                    ))}
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Automatico</span>
                      <span className="wbStatValue">{dashboardSummary.bot_active || 0}</span>
                    </div>
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Aguardando humano</span>
                      <span className="wbStatValue">{dashboardSummary.waiting_human || 0}</span>
                    </div>
                    <div className="wbStatRow">
                      <span className="wbStatLabel">Automação pausada</span>
                      <span className="wbStatValue">{dashboardSummary.paused_automation || 0}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
          </>
        ) : view === "inbox" ? (
          <section className="wbInbox">
            {selectedConv ? (
              <section className="wbCrmBar">
                <div className="wbCrmCard wbAutomationCard">
                  <div className="wbCrmLabel">Estado da automação</div>
                  <div className="wbCrmBadges">
                    <span className={selectedStatusMeta.className}>{selectedStatusMeta.label}</span>
                    <span className={selectedAttendanceMeta.className}>{selectedAttendanceMeta.label}</span>
                  </div>
                  <div className="wbAutomationGrid">
                    <div>
                      <div className="wbCrmLabel">Etapa atual</div>
                      <div className="wbCrmValue">{selectedFlowData.current_step || selectedConv.flow_state || "sem etapa"}</div>
                    </div>
                    <div>
                      <div className="wbCrmLabel">Quem está no comando</div>
                      <div className="wbCrmValue">
                        {selectedConv?.operation_status === "human_active" || selectedConv?.operation_status === "handoff_active"
                          ? "Humano"
                          : selectedConv?.operation_status === "ai_active" || selectedConv?.operation_status === "resume_ready"
                          ? "IA"
                          : "Bot"}
                      </div>
                    </div>
                    <div>
                      <div className="wbCrmLabel">Aguardando</div>
                      <div className="wbCrmValue">{selectedFlowData.waiting_for || "cliente"}</div>
                    </div>
                    <div>
                      <div className="wbCrmLabel">Motivo do handoff</div>
                      <div className="wbCrmValue">{selectedFlowData.handoff_reason || "sem handoff"}</div>
                    </div>
                  </div>
                  <div className="wbAutomationTimeline">
                    <div><strong>Ultima do bot/IA:</strong> {clip(selectedFlowData.last_ai_text || selectedFlowData.last_bot_text || "", 120) || "sem registro"}</div>
                    <div><strong>Ultima do cliente:</strong> {clip(selectedFlowData.last_user_text || "", 120) || "sem registro"}</div>
                    <div><strong>Ultima humana:</strong> {clip(selectedFlowData.last_human_text || "", 120) || "sem registro"}</div>
                  </div>
                  <div className="wbStrategyPanel">
                    <div className="wbStrategyBlock wbStrategyBlockWide">
                      <span>Síntese estratégica</span>
                      <p>{selectedStrategicSnapshot.synthesis}</p>
                    </div>
                    <div className="wbStrategyBlock">
                      <span>Oportunidade percebida</span>
                      <p>{selectedStrategicSnapshot.opportunity}</p>
                    </div>
                    <div className="wbStrategyBlock">
                      <span>Próximo passo</span>
                      <p>{selectedStrategicSnapshot.nextStep}</p>
                    </div>
                    <div className="wbStrategyBlock wbStrategyTemperature">
                      <span>Temperatura do contato</span>
                      <p>{selectedStrategicSnapshot.temperature}</p>
                    </div>
                  </div>
                </div>
                <div className="wbCrmCard">
                  <div className="wbCrmLabel">Pipeline Mugô</div>
                  <div className="wbCrmValue">{getStage(selectedConv.wa_id)}</div>
                </div>
                <div className="wbCrmCard">
                  <div className="wbCrmLabel">Responsável</div>
                  <div className="wbCrmValue">{selectedOwner}</div>
                </div>
                <div className="wbCrmCard">
                  <div className="wbCrmLabel">Modo</div>
                  <div className="wbCrmBadges">
                    <span className={selectedAttendanceMeta.className}>{selectedAttendanceMeta.label}</span>
                  </div>
                </div>
                <div className="wbCrmCard">
                  <div className="wbCrmLabel">Origem</div>
                  <div className="wbCrmValue">
                    {normalizeSourceLabel(selectedConv?.source || selectedConv?.last_source || "Sem origem")}
                  </div>
                </div>
              </section>
            ) : null}

            <section className="wbChat" ref={chatScrollRef}>
              {!selected ? (
                <div className="wbChatEmpty">
                  <div>
                    <div className="wbChatEmptyTitle">Selecione uma conversa</div>
                    <div className="wbChatEmptySub">O histórico e as novas mensagens aparecem aqui.</div>
                  </div>
                </div>
              ) : loadingMsgs ? (
                <div className="wbChatEmpty">
                  <div>
                    <div className="wbChatEmptyTitle">Carregando conversa...</div>
                    <div className="wbChatEmptySub">Estamos preparando o histórico desta interação.</div>
                  </div>
                </div>
              ) : !msgs.length ? (
                <div className="wbChatEmpty">
                  <div>
                    <div className="wbChatEmptyTitle">Ainda não há mensagens</div>
                    <div className="wbChatEmptySub">Quando a conversa começar, o histórico ficará disponível aqui.</div>
                  </div>
                </div>
              ) : (
                <div className="wbChatInner">
                  {msgs.map((m) => {
                    const mine = m.direction === "out";
                    return (
                      <div key={m.id} className={`wbBubbleRow ${mine ? "right" : "left"}`}>
                        <div className={`wbBubble ${mine ? "out" : ""}`}>
                          <div className="wbBubbleText">{m.text}</div>
                          <div className="wbBubbleMeta">{nowLocalTime(m.created_at)}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <footer className="wbComposer">
              <div className="wbComposerInner">
                <input
                  ref={inputRef}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={selected ? "Escreva sua mensagem..." : "Selecione uma conversa para continuar o atendimento"}
                  disabled={!selected}
                  onKeyDown={(e) => (e.key === "Enter" ? onSend() : null)}
                />
                <button className="wbSend" onClick={onSend} disabled={!selected || !text.trim()}>
                  Enviar
                </button>
              </div>
            </footer>
          </section>
        ) : view === "kanban" ? (
          <section className="wbKanban">
            <div className="wbKanbanInner" style={{ gridTemplateColumns: "repeat(5, minmax(260px, 1fr))" }}>
              {STAGES.map((s) => (
                <div
                  key={s}
                  className="wbCol"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDropStage(e, s)}
                >
                  <div className="wbColHead">
                    <div className="wbColTitle">{s}</div>
                    <div className="wbColCount">{(kanbanCols[s] || []).length}</div>
                  </div>

                  <div className="wbColBody">
                    {(kanbanCols[s] || []).map((c) => {
                      const op = getOperationStatusMeta(c.operation_status);

                      return (
                        <div
                          key={c.wa_id}
                          className="wbCard"
                          draggable
                          onDragStart={(e) => onDragStart(e, c.wa_id)}
                          onClick={() => openChat(c.wa_id)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="wbCardTop">
                            <div className="wbAvatar small">{getAvatarSeed(c)}</div>
                            <div className="wbCardTitle">{getDisplayName(c)}</div>
                            <div className="wbCardTime">{shortTime(c.last_message_at || c.last_at)}</div>
                          </div>

                          <div className="wbCardSub">{formatPhoneBR(c.telefone || c.wa_id)}</div>
                          <div className="wbCardPreview">{clip(c.notes || c.last_message || c.last_text || "", 120)}</div>

                          <div className="wbCardBadges">
                            {c.assigned_to ? <span className="wbBadge">{normalizeOwnerLabel(c.assigned_to)}</span> : null}
                            {c.source || c.last_source ? (
                              <span className="wbBadge">{normalizeSourceLabel(c.source || c.last_source)}</span>
                            ) : null}
                            <span className={op.className}>{op.label}</span>
                            <span className={getAttendanceModeMeta(c.attendance_mode).className}>
                              {getAttendanceModeMeta(c.attendance_mode).label}
                            </span>
                            {Array.isArray(c.tags)
                              ? c.tags.slice(0, 2).map((tag) => (
                                  <span key={tag} className="wbBadge ok">
                                    {tag}
                                  </span>
                                ))
                              : null}
                          </div>
                        </div>
                      );
                    })}

                    {!kanbanCols[s]?.length ? <div className="wbColEmpty">Arraste um lead para cá</div> : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : view === "agenda" ? (
          <section className="wbKanban">
            <div className="wbKanbanInner">
              {TASK_COLS.map((k) => (
                <div
                  key={k}
                  className="wbCol"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => onDropTask(e, k)}
                >
                  <div className="wbColHead">
                    <div className="wbColTitle">{k}</div>
                    <div className="wbColCount">{(taskCols[k] || []).length}</div>
                  </div>

                  <div className="wbColBody">
                    {(taskCols[k] || []).map((t) => (
                      (() => {
                        const conv = conversationsById.get(t.wa_id);
                        const owner = conv?.assigned_to || conv?.human_owner || "";
                        const attendanceMeta = getAttendanceModeMeta(conv?.attendance_mode);
                        const stage = conv ? getStageByConv(conv) : "";

                        return (
                          <div
                            key={t.id}
                            className="wbCard"
                            draggable
                            onDragStart={(e) => onDragStartTask(e, t.id)}
                          >
                            <div className="wbCardTop">
                              <div className="wbAvatar small">{String(t.wa_id || "X").slice(0, 1)}</div>
                              <div className="wbCardTitle">{t.title}</div>
                              <div className="wbCardTime">{shortTime(t.due_at)}</div>
                            </div>

                            <div className="wbCardSub">{getDisplayName(conv) || formatPhoneBR(t.wa_id)}</div>
                            <div className="wbCardPreview">Vencimento: {nowLocalTime(t.due_at)}</div>

                            <div className="wbCardBadges">
                              {owner ? <span className="wbBadge">{normalizeOwnerLabel(owner)}</span> : null}
                              {stage ? <span className="wbBadge ok">{stage}</span> : null}
                              {conv?.source || conv?.last_source ? (
                                <span className="wbBadge">
                                  {normalizeSourceLabel(conv?.source || conv?.last_source)}
                                </span>
                              ) : null}
                              <span className={attendanceMeta.className}>{attendanceMeta.label}</span>
                            </div>

                            <div className="wbCardBadges">
                              <button className="wbBtnGhost" onClick={() => openChat(t.wa_id)} style={{ padding: "8px 10px" }}>
                                Abrir
                              </button>
                              <button className="wbBtn" onClick={() => onDoneTask(t.id)} style={{ padding: "8px 10px" }}>
                                Concluir
                              </button>
                            </div>
                          </div>
                        );
                      })()
                    ))}

                    {!taskCols[k]?.length ? <div className="wbColEmpty">Sem tarefas</div> : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <section className="wbKanban">
            <div className="wbKanbanInner" style={{ gridTemplateColumns: "repeat(3, minmax(260px, 1fr))" }}>
              <div className="wbCol">
                <div className="wbColHead">
                  <div className="wbColTitle">Salvos</div>
                  <div className="wbColCount">{savedContacts.length}</div>
                </div>

                <div className="wbColBody">
                  {savedContacts.map((c) => {
                    const op = getOperationStatusMeta(c.operation_status);

                    return (
                      <div
                        key={c.wa_id}
                        className="wbCard"
                        onClick={() => openChat(c.wa_id)}
                        role="button"
                        tabIndex={0}
                        draggable
                        onDragStart={(e) => onDragStartSaved(e, c.wa_id)}
                        title="Arraste para o pipeline"
                      >
                        <div className="wbCardTop">
                          <div className="wbAvatar small">{getAvatarSeed(c)}</div>
                          <div className="wbCardTitle">{getDisplayName(c)}</div>
                          <div className="wbCardTime">{shortTime(c.last_message_at || c.last_at)}</div>
                        </div>
                        <div className="wbCardSub">{formatPhoneBR(c.telefone || c.wa_id)}</div>
                        <div className="wbCardPreview">{clip(c.notes || c.last_message || c.last_text || "", 140)}</div>
                        <div className="wbCardBadges">
                          {c.source || c.last_source ? (
                            <span className="wbBadge">{normalizeSourceLabel(c.source || c.last_source)}</span>
                          ) : null}
                          <span className={op.className}>{op.label}</span>
                          {c.next_task ? <span className="wbBadge ok">agendado</span> : null}
                        </div>
                      </div>
                    );
                  })}
                  {!savedContacts.length ? <div className="wbColEmpty">Nenhum contato salvo ainda</div> : null}
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div className="wbColTitle">Como usar</div>
                  <div className="wbColCount">1</div>
                </div>
                <div className="wbColBody">
                  <div className="wbEmpty">
                    Abra uma conversa e clique em <b>Salvar contato</b>.
                    <div className="wbEmptyHint">Você pode adicionar nome, telefone, tags, notas e estágio.</div>
                  </div>
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div className="wbColTitle">Dica operacional</div>
                  <div className="wbColCount">1</div>
                </div>
                <div className="wbColBody">
                  <div className="wbEmpty">
                    Use tags como <b>crm</b>, <b>site</b>, <b>ia</b>, <b>quente</b>.
                    <div className="wbEmptyHint">Agora você também pode filtrar por origem e status operacional.</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {taskModalOpen ? (
          <div className="wbModalOverlay">
            <div className="wbModal" onClick={(e) => e.stopPropagation()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div>
                  <div className="wbModalTitle">Nova tarefa</div>
                  <div className="wbModalSub">{getDisplayName(selectedConv) || selected}</div>
                </div>

                <button
                  type="button"
                  className="wbBtnGhost wbModalClose"
                  onClick={() => setTaskModalOpen(false)}
                  disabled={taskSaving}
                  aria-label="Fechar modal"
                >
                  ×
                </button>
              </div>

              <div className="wbForm">
                <label>
                  Título
                  <input value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} />
                </label>

                <div className="wbFormRow">
                  <label>
                    Data
                    <input type="date" value={taskDate} onChange={(e) => setTaskDate(e.target.value)} />
                  </label>
                  <label>
                    Hora
                    <input type="time" value={taskTime} onChange={(e) => setTaskTime(e.target.value)} />
                  </label>
                </div>
              </div>

              <div className="wbModalActions">
                <button className="wbBtnGhost" onClick={() => setTaskModalOpen(false)} disabled={taskSaving}>
                  Cancelar
                </button>
                <button className="wbBtn" onClick={onConfirmTask} disabled={taskSaving}>
                  {taskSaving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {editOpen ? (
          <div className="wbModalOverlay">
            <div className="wbModal" onClick={(e) => e.stopPropagation()}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div>
                  <div className="wbModalTitle">Editar contato</div>
                  <div className="wbModalSub">{selectedConv?.wa_id}</div>
                </div>

                <button
                  type="button"
                  className="wbBtnGhost wbModalClose"
                  onClick={() => setEditOpen(false)}
                  disabled={contactSaving}
                  aria-label="Fechar modal"
                >
                  ×
                </button>
              </div>

              <div className="wbForm">
                <label>
                  Nome
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Ex: Maria • Loja X" />
                </label>

                <label>
                  Telefone
                  <input value={editTel} onChange={(e) => setEditTel(e.target.value)} placeholder="Ex: 55119..." />
                </label>

                <label>
                  Etapa do pipeline
                  <select value={editStage} onChange={(e) => setEditStage(e.target.value)}>
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>

                <div className="wbFormRow">
                  <label>
                    Responsável
                    <input
                      value={editOwner}
                      onChange={(e) => setEditOwner(e.target.value)}
                      placeholder="Ex: Julia"
                    />
                  </label>

                  <label>
                    Modo de atendimento
                    <select value={editAttendanceMode} onChange={(e) => setEditAttendanceMode(e.target.value)}>
                      <option value="bot">Bot</option>
                      <option value="hybrid">Hibrido</option>
                      <option value="human">Humano</option>
                    </select>
                  </label>
                </div>

                <label>
                  Origem
                  <input
                    value={editSource}
                    onChange={(e) => setEditSource(e.target.value)}
                    placeholder="Ex: Meta Ads, Indicação, Instagram..."
                  />
                </label>

                <label>
                  Tags
                  <input value={editTags} onChange={(e) => setEditTags(e.target.value)} placeholder="salvo, lead, vip..." />
                </label>

                <label>
                  Notas
                  <textarea
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    rows={4}
                    placeholder="Contexto, dores, leitura estratégica e próximos movimentos..."
                  />
                </label>
              </div>

              <div className="wbModalActions">
                <button className="wbBtnGhost" onClick={() => setEditOpen(false)} disabled={contactSaving}>
                  Cancelar
                </button>
                <button className="wbBtn" onClick={saveContactEdits} disabled={contactSaving}>
                  {contactSaving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {toast ? (
          <div className="wbToast">
            <div className="wbToastText">{toast.message}</div>
            {toast.actionLabel ? (
              <button
                className="wbToastBtn"
                onClick={() => {
                  toast.action?.();
                  setToast(null);
                }}
              >
                {toast.actionLabel}
              </button>
            ) : null}
          </div>
        ) : null}
      </main>
    </div>
  );
}
