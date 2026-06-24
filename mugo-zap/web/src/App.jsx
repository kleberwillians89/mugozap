import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  assignConversation,
  updateConversationStatus,
  listUsers,
  createUser,
  updateUser,
  getDashboardSummary,
  getMe,
  getAttendanceMeta,
  submitAttendanceDiagnosis,
  createAttendanceContact,
  createAttendanceCollection,
  sendAttendanceCollectionReminder,
} from "./api";
import logoMugo from "./assets/logo-mugo.png";

const LS_STAGE_KEY = "mugozap_stages_v1";
const LS_SEEN_KEY = "mugozap_seen_v1";

const STAGES = ["Novo", "Qualificado", "Diagnóstico", "Proposta", "Negociação", "Fechado"];
const TASK_COLS = ["Atrasadas", "Hoje", "Amanhã", "Esta semana", "Futuro", "Sem data"];
const ATTENDANCE_TABS = ["inbox", "diagnostico", "contatos", "cobrancas"];
const CONTACT_STATUSES = [
  "Novo lead",
  "Diagnóstico enviado",
  "Diagnóstico concluído",
  "Orçamento enviado",
  "Cliente ativo",
  "Suporte",
  "Cobrança",
];
const COLLECTION_STATUSES = ["Em aberto", "Pago", "Atrasado"];
const TEMPERATURES = ["Frio", "Morno", "Quente"];
const USER_ROLES = ["admin", "gestor", "atendimento"];
const CONVERSATION_STATUSES = ["Novo lead", "Diagnóstico enviado", "Diagnóstico concluído", "Orçamento enviado", "Cliente ativo", "Suporte", "Cobrança", "Resolvida"];
const MUGO_INTELLIGENCE_MESSAGE =
  "Para entendermos melhor seu momento e indicarmos o melhor caminho para sua empresa, faça nosso diagnóstico gratuito:\n\n" +
  "https://intelligence.mugoagencia.com.br/\n\n" +
  "Assim que você finalizar, seguimos seu atendimento por aqui.";

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

function normalizeTemperatureLabel(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === "frio" || raw === "cold") return "Frio";
  if (raw === "quente" || raw === "hot") return "Quente";
  return raw ? "Morno" : "";
}

function temperatureBadgeClass(value) {
  const temp = normalizeTemperatureLabel(value);
  if (temp === "Quente") return "hot";
  if (temp === "Frio") return "cold";
  return temp ? "warm" : "";
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

function normalizeContactStatus(value) {
  const s = String(value || "").trim();
  return CONTACT_STATUSES.includes(s) ? s : "Novo lead";
}

function normalizeCollectionStatus(value) {
  const s = String(value || "").trim();
  return COLLECTION_STATUSES.includes(s) ? s : "Em aberto";
}

function normalizeRole(value) {
  const role = String(value || "").trim().toLowerCase();
  if (role === "admin") return "admin";
  if (role === "gestor") return "gestor";
  return "atendimento";
}

function canManageUsers(role) {
  return normalizeRole(role) === "admin";
}

function canManageAllConversations(role) {
  return ["admin", "gestor"].includes(normalizeRole(role));
}

function canAccessBilling(role) {
  return ["admin", "gestor"].includes(normalizeRole(role));
}

function getConversationOwner(conv) {
  return String(conv?.assigned_to || conv?.human_owner || conv?.owner || "").trim();
}

function userDisplayName(user) {
  return String(user?.name || user?.email || "").trim();
}

function formatMoneyBR(value) {
  const s = String(value || "").trim();
  if (!s) return "";
  if (s.startsWith("R$")) return s;
  const n = Number(s.replace(/\./g, "").replace(",", "."));
  if (Number.isFinite(n)) {
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }
  return s;
}

function formatDateBR(value) {
  if (!value) return "";
  const d = new Date(`${value}`.includes("T") ? value : `${value}T12:00:00`);
  if (Number.isNaN(d.getTime())) return String(value || "");
  return d.toLocaleDateString("pt-BR");
}

function getDiagnosisFromConv(conv, flowData = null) {
  const data =
    flowData ||
    (typeof conv?.flow_data === "object"
      ? conv.flow_data
      : (() => {
          try {
            return conv?.flow_data ? JSON.parse(conv.flow_data) : {};
          } catch {
            return {};
          }
        })());
  const diagnosis = data?.diagnosis_summary || data?.attendance_summary?.diagnosis || conv?.diagnosis || {};

  return {
    name: diagnosis.name || conv?.name || conv?.contact_name || "",
    company: diagnosis.company || conv?.company || "",
    phone: diagnosis.phone || conv?.telefone || conv?.phone || conv?.wa_id || "",
    email: diagnosis.email || conv?.email || "",
    segment: diagnosis.segment || conv?.segment || "",
    score_overall: diagnosis.score_overall || conv?.score_overall || "",
    score_marketing: diagnosis.score_marketing || "",
    score_sales: diagnosis.score_sales || "",
    score_automation: diagnosis.score_automation || "",
    score_data: diagnosis.score_data || "",
    score_relationship: diagnosis.score_relationship || "",
    opportunity: diagnosis.opportunity || conv?.lead_theme || "",
    recommended_service: diagnosis.recommended_service || conv?.service || "",
    summary: diagnosis.summary || diagnosis.resumo_gerado || conv?.notes || "",
    temperature: normalizeTemperatureLabel(diagnosis.temperature || conv?.lead_temperature || conv?.temperature || ""),
  };
}

function hasDiagnosis(diagnosis) {
  return Boolean(
    diagnosis &&
      [
        diagnosis.name,
        diagnosis.company,
        diagnosis.email,
        diagnosis.segment,
        diagnosis.score_overall,
        diagnosis.opportunity,
        diagnosis.recommended_service,
        diagnosis.summary,
      ].some((item) => String(item || "").trim())
  );
}

function buildContactPayloadFromConv(conv = {}) {
  return {
    name: conv.name || conv.contact_name || "",
    company: conv.company || "",
    telefone: conv.telefone || conv.phone || conv.wa_id || "",
    wa_id: conv.wa_id || conv.telefone || "",
    email: conv.email || "",
    instagram: conv.instagram || "",
    site: conv.site || conv.website || "",
    service_interest: conv.service_interest || conv.lead_theme || "",
    service_contracted: conv.service_contracted || conv.service || "",
    owner: conv.assigned_to || conv.human_owner || conv.owner || "",
    status: normalizeContactStatus(conv.status || conv.stage || conv.lead_stage || ""),
    notes: conv.notes || "",
  };
}

function buildCollectionReminderMessage(collection = {}) {
  const amount = formatMoneyBR(collection.amount || collection.valor);
  const due = formatDateBR(collection.due_date || collection.vencimento);
  if (amount && due) {
    return `Olá! Este é um lembrete de cobrança da Mugô no valor de ${amount}, com vencimento em ${due}. Favor confirmar o pagamento ou entrar em contato conosco.`;
  }
  if (amount) {
    return `Olá! Este é um lembrete de cobrança da Mugô no valor de ${amount}. Favor confirmar o pagamento ou entrar em contato conosco.`;
  }
  return "Olá! Este é um lembrete de cobrança da Mugô. Favor confirmar o pagamento ou entrar em contato conosco.";
}

function sortByRecent(items) {
  return [...(items || [])].sort((a, b) => {
    const ta = getConversationLastActivityAt(a) ? new Date(getConversationLastActivityAt(a)).getTime() : 0;
    const tb = getConversationLastActivityAt(b) ? new Date(getConversationLastActivityAt(b)).getTime() : 0;
    return tb - ta;
  });
}

function AgendaTaskCard({ task, conv, owner, attendanceMeta, stage, onOpen, onDone, onDragStart }) {
  return (
    <div
      className="wbCard"
      draggable
      onDragStart={(e) => onDragStart(e, task.id)}
    >
      <div className="wbCardTop">
        <div className="wbAvatar small">{String(task.wa_id || "X").slice(0, 1)}</div>
        <div className="wbCardTitle">{task.title}</div>
        <div className="wbCardTime">{shortTime(task.due_at)}</div>
      </div>

      <div className="wbCardSub">{getDisplayName(conv) || formatPhoneBR(task.wa_id)}</div>
      <div className="wbCardPreview">Vencimento: {nowLocalTime(task.due_at)}</div>

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
        <button className="wbBtnGhost" onClick={() => onOpen(task.wa_id)} style={{ padding: "8px 10px" }}>
          Abrir
        </button>
        <button className="wbBtn" onClick={() => onDone(task.id)} style={{ padding: "8px 10px" }}>
          Concluir
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("dashboard");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [leadPanelOpen, setLeadPanelOpen] = useState(() => {
    if (typeof window === "undefined") return true;
    return window.innerWidth >= 1280;
  });
  const [mobileChatOpen, setMobileChatOpen] = useState(false);
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [dashboardFilter, setDashboardFilter] = useState("todos");
  const [inboxFilter, setInboxFilter] = useState("todas");
  const [responsibleFilter, setResponsibleFilter] = useState("todos");
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [refreshingTasksSummary, setRefreshingTasksSummary] = useState(false);

  const [loadingConvs, setLoadingConvs] = useState(true);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [, setLoadingTasks] = useState(false);
  const [, setLoadingDashboard] = useState(false);
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

  const [currentUser, setCurrentUser] = useState(null);
  const currentRole = normalizeRole(currentUser?.role);
  const [users, setUsers] = useState([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userSaving, setUserSaving] = useState(false);
  const [newUser, setNewUser] = useState({ name: "", email: "", role: "atendimento", password: "" });
  const [transferOwner, setTransferOwner] = useState("");
  const [statusDraft, setStatusDraft] = useState("Novo lead");

  const [attendanceContact, setAttendanceContact] = useState(() => buildContactPayloadFromConv({}));
  const [attendanceContactSaving, setAttendanceContactSaving] = useState(false);
  const [diagnosisForm, setDiagnosisForm] = useState({
    name: "",
    company: "",
    phone: "",
    email: "",
    segment: "",
    score_overall: "",
    score_marketing: "",
    score_sales: "",
    score_automation: "",
    score_data: "",
    score_relationship: "",
    opportunity: "",
    recommended_service: "",
    summary: "",
    temperature: "Morno",
  });
  const [diagnosisSaving, setDiagnosisSaving] = useState(false);
  const [collections, setCollections] = useState([]);
  const [collectionForm, setCollectionForm] = useState({
    cliente: "",
    empresa: "",
    wa_id: "",
    telefone: "",
    amount: "",
    due_date: "",
    status: "Em aberto",
    notes: "",
  });
  const [collectionSaving, setCollectionSaving] = useState(false);
  const [reminderSending, setReminderSending] = useState(false);

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
  const [attendanceMeta, setAttendanceMeta] = useState({ queues: [], statuses: [], welcome_message: "" });

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
  const clientIdSeqRef = useRef(0);

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
    let active = true;

    async function loadAttendanceMeta() {
      try {
        const meta = await getAttendanceMeta();
        if (active) {
          setAttendanceMeta(meta || { queues: [], statuses: [], welcome_message: "" });
        }
      } catch (e) {
        if (active) {
          console.warn("attendance meta unavailable", e);
        }
      }
    }

    loadAttendanceMeta();
    return () => {
      active = false;
    };
  }, []);

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
      id: `toast-${++clientIdSeqRef.current}`,
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

  async function refreshUsers({ silent = false } = {}) {
    if (!canManageAllConversations(currentRole)) return;
    if (!silent) setUsersLoading(true);
    setErr("");

    try {
      const items = await listUsers();
      setUsers(items || []);
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      if (!silent) setUsersLoading(false);
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
      const me = await getMe().catch(() => null);
      if (me?.user) {
        setCurrentUser(me.user);
      }
      await refreshAll({ keepSelected: false });
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesRequestSeqRef.current += 1;
    lastMessageCountRef.current = 0;
    const frame = window.requestAnimationFrame(() => {
      setMsgs([]);
      if (!selected) {
        setLoadingMsgs(false);
      }
    });

    if (!selected) {
      return () => window.cancelAnimationFrame(frame);
    }
    dbg("selected:change", {
      selected,
      selectedConv: selectedConv?.wa_id || null,
    });

    refreshMessages(selected, { preserveScroll: false }).catch((e) => {
      setErr(String(e.message || e));
    });

    return () => window.cancelAnimationFrame(frame);
  }, [selected, selectedConv?.wa_id]);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    if (!canManageAllConversations(currentRole)) {
      const frame = window.requestAnimationFrame(() => setUsers([]));
      return () => window.cancelAnimationFrame(frame);
    }
    const frame = window.requestAnimationFrame(() => {
      refreshUsers({ silent: true }).catch(() => null);
    });
    return () => window.cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentRole]);

  useEffect(() => {
    if (!selected) return;
    requestAnimationFrame(() => {
      scrollSelectedConversationIntoView();
    });
  }, [selected, convs, view]);

  const unreadCount = (conv) => {
    const lastAt = conv?.last_message_at || conv?.last_at;
    if (!lastAt) return 0;
    const seenAt = seen?.[conv.wa_id];
    if (!seenAt) return 1;
    return new Date(lastAt).getTime() > new Date(seenAt).getTime() ? 1 : 0;
  };

  const responsibleOptions = useMemo(() => {
    const names = new Set();
    convs.forEach((conv) => {
      const owner = getConversationOwner(conv);
      if (owner) names.add(owner);
    });
    users.forEach((user) => {
      const name = userDisplayName(user);
      if (name) names.add(name);
    });
    return Array.from(names).sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [convs, users]);

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
    const currentName = userDisplayName(currentUser).toLowerCase();
    const currentEmail = String(currentUser?.email || "").toLowerCase();
    const afterInboxFilter = afterSearch.filter((c) => {
      const owner = getConversationOwner(c);
      const ownerLower = owner.toLowerCase();
      const resolved = isArchivedConversation(c) || ["resolvida", "resolvido", "resolved"].includes(String(c?.status || c?.stage || "").toLowerCase());

      if (inboxFilter === "minhas") {
        return ownerLower && (ownerLower === currentName || ownerLower === currentEmail);
      }
      if (inboxFilter === "nao_atribuidas") {
        return !owner;
      }
      if (inboxFilter === "resolvidas") {
        return resolved;
      }
      if (inboxFilter === "responsavel") {
        return responsibleFilter === "todos" ? Boolean(owner) : owner === responsibleFilter;
      }
      return true;
    });

    const finalItems = sortByRecent(afterInboxFilter);
    console.debug(`sidebar:visible total=${finalItems.length}`);

    return finalItems;
  }, [q, convs, inboxFilter, responsibleFilter, currentUser]);

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
      inboxFilter !== "todas" ? inboxFilter : "",
      inboxFilter === "responsavel" && responsibleFilter !== "todos" ? responsibleFilter : "",
    ].filter(Boolean).length;
  }, [q, inboxFilter, responsibleFilter]);

  function clearSidebarFilters() {
    setQ("");
    setInboxFilter("todas");
    setResponsibleFilter("todos");
  }

  const getStageByConv = useCallback((conv) => {
    return conv?.stage || conv?.lead_stage || stages?.[conv?.wa_id] || "Novo";
  }, [stages]);

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
  }, [convs, dashboardSummary, tasks]);

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
      id: `temp-message-${++clientIdSeqRef.current}`,
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
  }, [visibleConvs, getStageByConv]);

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
    setMobileChatOpen(true);

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
      id: `temp-task-${++clientIdSeqRef.current}`,
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

  async function onAssumeConversation() {
    if (!selected || !currentUser) return;
    const owner = userDisplayName(currentUser);
    setErr("");
    replaceConversationLocal({
      wa_id: selected,
      assigned_to: owner,
      human_owner: owner,
      owner,
      attendance_mode: "human",
      automation_paused: true,
      bot_enabled: false,
    });
    try {
      await assignConversation(selected, { assigned_to: owner });
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshMessages(selected, { preserveScroll: true, silent: true }),
      ]);
      showToast("Atendimento assumido.");
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }

  async function onTransferConversation() {
    if (!selected || !transferOwner || !canManageAllConversations(currentRole)) return;
    setErr("");
    replaceConversationLocal({
      wa_id: selected,
      assigned_to: transferOwner,
      human_owner: transferOwner,
      owner: transferOwner,
      attendance_mode: "human",
    });
    try {
      await assignConversation(selected, { assigned_to: transferOwner });
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshMessages(selected, { preserveScroll: true, silent: true }),
      ]);
      showToast("Atendimento transferido.");
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }

  async function onChangeConversationStatus() {
    if (!selected || !statusDraft) return;
    setErr("");
    replaceConversationLocal({
      wa_id: selected,
      status: statusDraft,
      stage: statusDraft,
      lead_stage: statusDraft.toLowerCase(),
      closed_at: statusDraft === "Resolvida" ? new Date().toISOString() : selectedConv?.closed_at,
    });
    try {
      await updateConversationStatus(selected, { status: statusDraft });
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshMessages(selected, { preserveScroll: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      showToast("Status atualizado.");
    } catch (e) {
      setErr(String(e.message || e));
      await refreshConversations({ keepSelected: true, silent: true });
    }
  }

  async function onCreateUser() {
    if (!canManageUsers(currentRole) || userSaving) return;
    setUserSaving(true);
    setErr("");
    try {
      await createUser(newUser);
      setNewUser({ name: "", email: "", role: "atendimento", password: "" });
      await refreshUsers({ silent: true });
      showToast("Usuário criado.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setUserSaving(false);
    }
  }

  async function onUpdateUser(userId, patch) {
    if (!canManageUsers(currentRole) || !userId) return;
    setErr("");
    setUsers((prev) => prev.map((user) => (user.id === userId ? { ...user, ...patch } : user)));
    try {
      await updateUser(userId, patch);
      await refreshUsers({ silent: true });
    } catch (e) {
      setErr(String(e.message || e));
      await refreshUsers({ silent: true });
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
  const selectedDiagnosis = useMemo(
    () => getDiagnosisFromConv(selectedConv, selectedFlowData),
    [selectedConv, selectedFlowData]
  );
  const selectedHasDiagnosis = hasDiagnosis(selectedDiagnosis);
  const selectedOpenCollections = useMemo(() => {
    const selectedWaId = selectedConv?.wa_id || selected;
    if (!selectedWaId) return [];
    return collections.filter(
      (item) =>
        String(item.wa_id || item.telefone || "") === String(selectedWaId) &&
        normalizeCollectionStatus(item.status) !== "Pago"
    );
  }, [collections, selectedConv?.wa_id, selected]);

  useEffect(() => {
    if (!selectedConv) return;

    const contact = buildContactPayloadFromConv(selectedConv);
    const diagnosis = getDiagnosisFromConv(selectedConv, selectedFlowData);
    const frame = window.requestAnimationFrame(() => {
      setAttendanceContact(contact);
      setDiagnosisForm((prev) => ({
        ...prev,
        ...diagnosis,
        name: diagnosis.name || contact.name,
        company: diagnosis.company || contact.company,
        phone: diagnosis.phone || contact.telefone,
        temperature: diagnosis.temperature || prev.temperature || "Morno",
      }));
      setCollectionForm((prev) => ({
        ...prev,
        cliente: contact.name,
        empresa: contact.company,
        telefone: contact.telefone,
        wa_id: contact.wa_id,
      }));
    });

    return () => window.cancelAnimationFrame(frame);
  }, [selectedConv, selectedFlowData]);

  function updateAttendanceContactField(field, value) {
    setAttendanceContact((prev) => ({ ...prev, [field]: value }));
  }

  function updateDiagnosisField(field, value) {
    setDiagnosisForm((prev) => ({ ...prev, [field]: value }));
  }

  function updateCollectionField(field, value) {
    setCollectionForm((prev) => ({ ...prev, [field]: value }));
  }

  function suggestMugoIntelligenceMessage() {
    setText(MUGO_INTELLIGENCE_MESSAGE);
    setView("inbox");
    showToast("Mensagem do Mugô Intelligence pronta para aprovação.");
    requestAnimationFrame(() => inputRef.current?.focus?.());
  }

  function suggestContinueAttendanceMessage() {
    const opportunity = selectedDiagnosis.opportunity || "uma oportunidade estratégica de crescimento";
    const service = selectedDiagnosis.recommended_service || "uma solução personalizada da Mugô";
    setText(
      "Obrigado por concluir seu diagnóstico.\n\n" +
      `Analisamos suas respostas e vimos que a principal oportunidade da sua empresa está em: ${opportunity}.\n\n` +
      `O caminho recomendado pela Mugô é: ${service}.\n\n` +
      "Podemos seguir por aqui e te mostrar como isso funcionaria na prática?"
    );
    setView("inbox");
    showToast("Mensagem de continuidade pronta para aprovação.");
    requestAnimationFrame(() => inputRef.current?.focus?.());
  }

  async function saveAttendanceContact() {
    if (attendanceContactSaving) return;

    const waId = onlyDigits(attendanceContact.wa_id || attendanceContact.telefone);
    if (!waId) {
      setErr("Informe telefone ou wa_id para vincular o contato.");
      return;
    }

    setErr("");
    setAttendanceContactSaving(true);

    const payload = {
      ...attendanceContact,
      wa_id: waId,
      telefone: onlyDigits(attendanceContact.telefone || waId),
      phone: onlyDigits(attendanceContact.telefone || waId),
      service: attendanceContact.service_contracted || attendanceContact.service_interest,
      service_contratado: attendanceContact.service_contracted,
      responsible: attendanceContact.owner,
      notes: attendanceContact.notes || `Status: ${attendanceContact.status || "Novo lead"}`,
    };

    try {
      const result = await createAttendanceContact(payload);
      prependOrReplaceConversationLocal({
        ...(selectedConv || {}),
        wa_id: waId,
        name: payload.name,
        telefone: payload.telefone,
        company: payload.company,
        email: payload.email,
        instagram: payload.instagram,
        site: payload.site,
        service_interest: payload.service_interest,
        service_contracted: payload.service_contracted,
        assigned_to: payload.owner,
        status: payload.status,
        notes: payload.notes,
        tags: Array.from(new Set([...(Array.isArray(selectedConv?.tags) ? selectedConv.tags : []), "salvo"])),
      });
      setSelected(waId);
      await refreshConversations({ keepSelected: true, silent: true });
      showToast(result?.ok ? "Contato salvo e vinculado à conversa." : "Contato salvo.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setAttendanceContactSaving(false);
    }
  }

  async function saveDiagnosis() {
    if (diagnosisSaving) return;
    const waId = onlyDigits(selected || diagnosisForm.phone || attendanceContact.wa_id || attendanceContact.telefone);
    if (!waId) {
      setErr("Selecione uma conversa ou informe telefone para salvar o diagnóstico.");
      return;
    }

    setErr("");
    setDiagnosisSaving(true);

    try {
      await submitAttendanceDiagnosis(waId, {
        fields: diagnosisForm,
        status: "Diagnóstico concluído",
        queue: "Novos leads",
        owner: attendanceContact.owner || selectedConv?.assigned_to || "",
      });
      replaceConversationLocal({
        wa_id: waId,
        name: diagnosisForm.name || selectedConv?.name,
        telefone: onlyDigits(diagnosisForm.phone || selectedConv?.telefone || waId),
        company: diagnosisForm.company,
        email: diagnosisForm.email,
        segment: diagnosisForm.segment,
        lead_temperature: diagnosisForm.temperature,
        lead_theme: diagnosisForm.opportunity || diagnosisForm.recommended_service,
        stage: "Diagnóstico",
        lead_stage: "diagnostico",
        flow_data: {
          ...(selectedFlowData || {}),
          diagnosis_summary: diagnosisForm,
        },
      });
      await Promise.all([
        refreshConversations({ keepSelected: true, silent: true }),
        refreshMessages(waId, { preserveScroll: true, silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      showToast("Diagnóstico salvo no atendimento.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setDiagnosisSaving(false);
    }
  }

  async function saveCollection() {
    if (collectionSaving) return;
    const waId = onlyDigits(collectionForm.wa_id || collectionForm.telefone);
    if (!waId) {
      setErr("Informe telefone ou wa_id para vincular a cobrança.");
      return;
    }

    setErr("");
    setCollectionSaving(true);

    const item = {
      ...collectionForm,
      wa_id: waId,
      telefone: onlyDigits(collectionForm.telefone || waId),
      amount: collectionForm.amount,
      due_date: collectionForm.due_date,
      status: normalizeCollectionStatus(collectionForm.status),
      id: `collection-${waId}-${collectionForm.due_date || "sem-data"}-${collections.length + 1}`,
      created_at: new Date().toISOString(),
    };

    try {
      const result = await createAttendanceCollection(item);
      const saved = { ...item, ...(result?.collection || {}) };
      setCollections((prev) => [saved, ...prev.filter((existing) => existing.id !== saved.id)]);
      await Promise.all([
        refreshTasks({ silent: true }),
        refreshDashboard({ silent: true }),
      ]);
      showToast("Cobrança criada. O lembrete ficou disponível para aprovação.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setCollectionSaving(false);
    }
  }

  function markCollectionPaid(collectionId) {
    setCollections((prev) =>
      prev.map((item) => (item.id === collectionId ? { ...item, status: "Pago", paid_at: new Date().toISOString() } : item))
    );
    showToast("Cobrança marcada como paga.");
  }

  function prepareCollectionReminder(collection) {
    setSelected(collection.wa_id || collection.telefone || selected);
    setText(collection.message_suggestion || buildCollectionReminderMessage(collection));
    setView("inbox");
    showToast("Lembrete de cobrança pronto para aprovação.");
    requestAnimationFrame(() => inputRef.current?.focus?.());
  }

  async function sendApprovedCollectionReminder(collection) {
    if (reminderSending) return;
    const waId = onlyDigits(collection.wa_id || collection.telefone || selected);
    const message = text.trim() || collection.message_suggestion || buildCollectionReminderMessage(collection);
    if (!waId || !message) return;

    setReminderSending(true);
    setErr("");

    try {
      await sendAttendanceCollectionReminder(waId, {
        amount: collection.amount,
        due_date: collection.due_date,
        message,
      });
      setText("");
      await refreshMessages(waId, { preserveScroll: false, silent: true });
      showToast("Lembrete aprovado e enviado para a conversa.");
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setReminderSending(false);
    }
  }

  useEffect(() => {
    if (!selectedConv?.wa_id) return;
    console.debug(`automation:status ${selectedConv.operation_status || ""}`);
    console.debug(`automation:step ${selectedFlowData.current_step || selectedConv.flow_state || ""}`);
  }, [selectedConv?.wa_id, selectedConv?.operation_status, selectedConv?.flow_state, selectedFlowData.current_step]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setTransferOwner(getConversationOwner(selectedConv));
      setStatusDraft(selectedConv?.status || selectedConv?.stage || "Novo lead");
    });
    return () => window.cancelAnimationFrame(frame);
  }, [selectedConv]);

  const shellClassName = [
    "wbShell",
    view === "inbox" ? "isInbox" : "",
    leadPanelOpen ? "leadPanelOpen" : "leadPanelClosed",
    mobileChatOpen ? "mobileChatOpen" : "mobileListOpen",
  ].filter(Boolean).join(" ");

  return (
    <div className={shellClassName}>
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
        <button className={`wbRailBtn ${view === "diagnostico" ? "active" : ""}`} onClick={() => setView("diagnostico")} title="Diagnóstico">
          📊
        </button>
        <button className={`wbRailBtn ${view === "contatos" ? "active" : ""}`} onClick={() => setView("contatos")} title="Contatos">
          👤
        </button>
        {canAccessBilling(currentRole) ? (
          <button className={`wbRailBtn ${view === "cobrancas" ? "active" : ""}`} onClick={() => setView("cobrancas")} title="Cobranças">
            💳
          </button>
        ) : null}
        {canManageUsers(currentRole) ? (
          <button className={`wbRailBtn ${view === "usuarios" ? "active" : ""}`} onClick={() => setView("usuarios")} title="Configurações">
            ⚙
          </button>
        ) : null}
        <button className={`wbRailBtn ${view === "kanban" ? "active" : ""}`} onClick={() => setView("kanban")} title="Pipeline">
          🗂️
        </button>
        <button className={`wbRailBtn ${view === "agenda" ? "active" : ""}`} onClick={() => setView("agenda")} title="Agenda">
          🗓️
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

        <div className="wbSidebarFilters">
          <select className="wbMobileFilterSelect" value={inboxFilter} onChange={(e) => setInboxFilter(e.target.value)}>
            <option value="todas">Todas</option>
            <option value="minhas">Minhas</option>
            <option value="nao_atribuidas">Não atribuídas</option>
            <option value="resolvidas">Resolvidas</option>
            <option value="responsavel">Por responsável</option>
          </select>
          {[
            ["todas", "Todas"],
            ["minhas", "Minhas"],
            ["nao_atribuidas", "Não atribuídas"],
            ["resolvidas", "Resolvidas"],
            ["responsavel", "Por responsável"],
          ].map(([value, label]) => (
            <button
              key={value}
              className={inboxFilter === value ? "active" : ""}
              onClick={() => setInboxFilter(value)}
              type="button"
            >
              {label}
            </button>
          ))}
          {inboxFilter === "responsavel" ? (
            <select value={responsibleFilter} onChange={(e) => setResponsibleFilter(e.target.value)}>
              <option value="todos">Todos os responsáveis</option>
              {responsibleOptions.map((owner) => (
                <option key={owner} value={owner}>{owner}</option>
              ))}
            </select>
          ) : null}
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
            ) : view === "diagnostico" ? (
              <>
                <div className="wbHeaderTitle">Diagnóstico</div>
                <div className="wbHeaderSub">Leitura do Mugô Intelligence vinculada ao atendimento selecionado.</div>
              </>
            ) : view === "cobrancas" ? (
              <>
                <div className="wbHeaderTitle">Cobranças</div>
                <div className="wbHeaderSub">Controle inicial de vencimentos, status e lembretes aprovados pelo operador.</div>
              </>
            ) : view === "usuarios" ? (
              <>
                <div className="wbHeaderTitle">Configurações</div>
                <div className="wbHeaderSub">Usuários, perfis e acesso da equipe Mugô.</div>
              </>
            ) : (
              <>
                <div className="wbHeaderTitle">Contatos</div>
                <div className="wbHeaderSub">Cadastro, edição e vínculo de clientes por telefone ou wa_id.</div>
              </>
            )}
          </div>

          <div className="wbHeaderRight">
            <div className="wbPrimaryTabs" aria-label="Navegação da central de atendimento">
              {ATTENDANCE_TABS.filter((tab) => tab !== "cobrancas" || canAccessBilling(currentRole)).map((tab) => (
                <button
                  key={tab}
                  className={view === tab ? "active" : ""}
                  onClick={() => setView(tab)}
                  type="button"
                >
                  {tab === "inbox" ? "Inbox" : tab === "diagnostico" ? "Diagnóstico" : tab === "contatos" ? "Contatos" : "Cobranças"}
                </button>
              ))}
            </div>

            {currentUser ? (
              <div className="wbUserBadge">
                <strong>{userDisplayName(currentUser)}</strong>
                <span>{currentRole}</span>
              </div>
            ) : null}

            {view === "inbox" ? (
              <>
                <button className="wbBtnGhost wbMobileBackBtn" onClick={() => setMobileChatOpen(false)}>
                  Voltar para conversas
                </button>
                <button className="wbBtnGhost" onClick={() => setLeadPanelOpen((prev) => !prev)} disabled={!selected}>
                  {leadPanelOpen ? "Ocultar painel" : "Abrir painel"}
                </button>
              </>
            ) : null}

            <button className="wbBtnGhost wbHeaderFilterToggle" onClick={() => setSidebarCollapsed((prev) => !prev)}>
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
                <button className="wbBtn wbDesktopAction" onClick={onAssumeConversation} disabled={!selected}>
                  Assumir atendimento
                </button>

                {canManageAllConversations(currentRole) ? (
                  <>
                    <select className="wbHeaderSelect wbDesktopAction" value={transferOwner} onChange={(e) => setTransferOwner(e.target.value)} disabled={!selected}>
                      <option value="">Sem responsável</option>
                      {responsibleOptions.map((owner) => (
                        <option key={owner} value={owner}>{owner}</option>
                      ))}
                    </select>
                    <button className="wbBtnGhost wbDesktopAction" onClick={onTransferConversation} disabled={!selected || !transferOwner}>
                      Transferir
                    </button>
                  </>
                ) : null}

                <select className="wbHeaderSelect wbDesktopAction" value={statusDraft} onChange={(e) => setStatusDraft(e.target.value)} disabled={!selected}>
                  {CONVERSATION_STATUSES.map((status) => (
                    <option key={status} value={status}>{status}</option>
                  ))}
                </select>
                <button className="wbBtnGhost wbDesktopAction" onClick={onChangeConversationStatus} disabled={!selected || !statusDraft}>
                  Alterar status
                </button>

                <button className="wbBtn wbDesktopAction" onClick={() => inputRef.current?.focus?.()} disabled={!selected}>
                  Nova mensagem
                </button>

                <button className="wbBtnGhost wbDesktopAction" onClick={onCreateTaskQuick} disabled={!selected}>
                  Nova tarefa
                </button>

                <button className="wbBtnGhost wbDesktopAction" onClick={openEditContact} disabled={!selected}>
                  Editar contato
                </button>

                {currentRole === "admin" ? (
                  <button className="wbBtnGhost wbDesktopAction" onClick={onArchiveConversation} disabled={!selected}>
                    {isArchivedConversation(selectedConv) ? "Desarquivar" : "Arquivar"}
                  </button>
                ) : null}

                {selectedConv?.handoff_active || selectedConv?.operation_status === "handoff" ? (
                  <button className="wbBtnGhost wbDesktopAction" onClick={onCloseHandoff}>
                    Encerrar atendimento
                  </button>
                ) : null}

                {currentRole === "admin" ? (
                  <button
                    className="wbBtnGhost wbDesktopAction"
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
                ) : null}
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
                {attendanceMeta.welcome_message ? (
                  <div className="wbHeroText" style={{ marginTop: 8, whiteSpace: "pre-wrap" }}>
                    {attendanceMeta.welcome_message}
                  </div>
                ) : null}
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

            <div className="wbInboxWorkspace">
              <div className="wbConversationPane">
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
                  <div className="wbComposerTools">
                    {selectedHasDiagnosis ? (
                      <button className="wbBtnGhost wbBtnGhostCompact" onClick={suggestContinueAttendanceMessage} disabled={!selected}>
                        Usar diagnóstico
                      </button>
                    ) : (
                      <button className="wbBtnGhost wbBtnGhostCompact" onClick={suggestMugoIntelligenceMessage} disabled={!selected}>
                        Enviar Intelligence
                      </button>
                    )}
                    <button className="wbBtnGhost wbBtnGhostCompact" onClick={onAssumeConversation} disabled={!selected}>
                      Assumir
                    </button>
                  </div>
                  <div className="wbComposerInner">
                    <textarea
                      ref={inputRef}
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder={selected ? "Escreva sua mensagem..." : "Selecione uma conversa para continuar o atendimento"}
                      disabled={!selected}
                      rows={2}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          onSend();
                        }
                      }}
                    />
                    <button className="wbSend" onClick={onSend} disabled={!selected || !text.trim()}>
                      Enviar
                    </button>
                  </div>
                </footer>
              </div>

              {leadPanelOpen ? (
              <aside className="wbRightPanel">
                <button className="wbBtnGhost wbPanelClose" onClick={() => setLeadPanelOpen(false)}>
                  Ocultar painel
                </button>
                <div className="wbSideBlock">
                  <div className="wbSideTitle">Dados do contato</div>
                  <div className="wbInfoGrid">
                    <span>Nome</span><strong>{getDisplayName(selectedConv) || "Sem nome"}</strong>
                    <span>Empresa</span><strong>{selectedConv?.company || attendanceContact.company || "Sem empresa"}</strong>
                    <span>Telefone</span><strong>{formatPhoneBR(selectedConv?.telefone || selectedConv?.wa_id || selected)}</strong>
                    <span>Email</span><strong>{selectedConv?.email || attendanceContact.email || "Sem email"}</strong>
                    <span>Status</span><strong>{attendanceContact.status || getStage(selectedConv?.wa_id)}</strong>
                  </div>
                  <button className="wbBtnGhost wbSideAction" onClick={() => setView("contatos")} disabled={!selected}>
                    Editar contato
                  </button>
                </div>

                <div className="wbSideBlock">
                  <div className="wbSideTitle">Diagnóstico Intelligence</div>
                  {selectedHasDiagnosis ? (
                    <>
                      <div className="wbDiagnosisSideHero">
                        <div>
                          <span>Score geral</span>
                          <strong>{selectedDiagnosis.score_overall || "sem score"}</strong>
                        </div>
                        <span className={`wbBadge temp ${temperatureBadgeClass(selectedDiagnosis.temperature)}`}>
                          {selectedDiagnosis.temperature || "sem temperatura"}
                        </span>
                      </div>
                      <div className="wbInfoGrid">
                        <span>Oportunidade</span><strong>{selectedDiagnosis.opportunity || "sem leitura"}</strong>
                        <span>Serviço</span><strong>{selectedDiagnosis.recommended_service || "sem recomendação"}</strong>
                        <span>Resumo</span><strong>{selectedDiagnosis.summary || "sem resumo"}</strong>
                      </div>
                      <button className="wbBtn wbSideAction" onClick={suggestContinueAttendanceMessage} disabled={!selected}>
                        Continuar atendimento
                      </button>
                    </>
                  ) : (
                    <>
                      <div className="wbEmptyHint">Ainda não há diagnóstico vinculado a este contato.</div>
                      <button className="wbBtn wbSideAction" onClick={suggestMugoIntelligenceMessage} disabled={!selected}>
                        Enviar Mugô Intelligence
                      </button>
                    </>
                  )}
                </div>

                <div className="wbSideBlock">
                  <div className="wbSideTitle">Cobranças em aberto</div>
                  {selectedOpenCollections.length ? (
                    <div className="wbMiniList">
                      {selectedOpenCollections.map((collection) => (
                        <div key={collection.id} className="wbMiniItem wbMiniItemStack">
                          <div className="wbMiniTitle">{formatMoneyBR(collection.amount)}</div>
                          <div className="wbMiniSub">
                            Vence em {formatDateBR(collection.due_date)} • {collection.status}
                          </div>
                          <div className="wbSideActionsRow">
                            <button className="wbBtnGhost" onClick={() => prepareCollectionReminder(collection)}>
                              Gerar lembrete
                            </button>
                            <button className="wbBtn" onClick={() => sendApprovedCollectionReminder(collection)} disabled={reminderSending}>
                              Enviar aprovado
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="wbEmptyHint">Nenhuma cobrança aberta vinculada.</div>
                  )}
                  <button className="wbBtnGhost wbSideAction" onClick={() => setView("cobrancas")} disabled={!selected}>
                    Nova cobrança
                  </button>
                </div>

                <div className="wbSideBlock">
                  <div className="wbSideTitle">Observações internas</div>
                  <p className="wbSideNote">{selectedConv?.notes || selectedStrategicSnapshot.nextStep || "Sem observações internas ainda."}</p>
                </div>
              </aside>
              ) : null}
            </div>
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
                    {(taskCols[k] || []).map((t) => {
                      const conv = conversationsById.get(t.wa_id);
                      return (
                        <AgendaTaskCard
                          key={t.id}
                          task={t}
                          conv={conv}
                          owner={conv?.assigned_to || conv?.human_owner || ""}
                          attendanceMeta={getAttendanceModeMeta(conv?.attendance_mode)}
                          stage={conv ? getStageByConv(conv) : ""}
                          onOpen={openChat}
                          onDone={onDoneTask}
                          onDragStart={onDragStartTask}
                        />
                      );
                    })}

                    {!taskCols[k]?.length ? <div className="wbColEmpty">Sem tarefas</div> : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : view === "diagnostico" ? (
          <section className="wbKanban">
            <div className="wbAttendanceLayout">
              <div className="wbCol wbAttendanceMain">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Diagnóstico do lead</div>
                    <div className="wbSectionSub">{selected ? formatPhoneBR(selected) : "Selecione uma conversa para vincular o diagnóstico"}</div>
                  </div>
                  {selectedHasDiagnosis ? (
                    <button className="wbBtn" onClick={suggestContinueAttendanceMessage} disabled={!selected}>
                      Continuar atendimento
                    </button>
                  ) : (
                    <button className="wbBtn" onClick={suggestMugoIntelligenceMessage} disabled={!selected}>
                      Enviar Mugô Intelligence
                    </button>
                  )}
                </div>

                <div className="wbColBody">
                  {selectedHasDiagnosis ? (
                    <>
                      <div className="wbDiagnosisHero">
                        <div>
                          <span>Score geral</span>
                          <strong>{selectedDiagnosis.score_overall || "Não informado"}</strong>
                        </div>
                        <span className={`wbBadge temp ${temperatureBadgeClass(selectedDiagnosis.temperature)}`}>
                          {selectedDiagnosis.temperature || "Sem temperatura"}
                        </span>
                      </div>
                      <div className="wbDiagnosisGrid">
                        {[
                          ["Nome", selectedDiagnosis.name],
                          ["Empresa", selectedDiagnosis.company],
                          ["Telefone", formatPhoneBR(selectedDiagnosis.phone)],
                          ["Email", selectedDiagnosis.email],
                          ["Segmento", selectedDiagnosis.segment],
                          ["Score marketing", selectedDiagnosis.score_marketing],
                          ["Score vendas", selectedDiagnosis.score_sales],
                          ["Score automação", selectedDiagnosis.score_automation],
                          ["Score dados", selectedDiagnosis.score_data],
                          ["Score relacionamento", selectedDiagnosis.score_relationship],
                          ["Principal oportunidade", selectedDiagnosis.opportunity],
                          ["Serviço recomendado", selectedDiagnosis.recommended_service],
                          ["Resumo gerado", selectedDiagnosis.summary],
                        ].map(([label, value]) => (
                          <div key={label} className={label === "Resumo gerado" ? "wbDiagnosisItem wide" : "wbDiagnosisItem"}>
                            <span>{label}</span>
                            <strong>{value || "Não informado"}</strong>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <div className="wbEmpty">
                      Nenhum diagnóstico encontrado para esta conversa.
                      <div className="wbEmptyHint">Use o botão “Enviar Mugô Intelligence” para preparar a mensagem no atendimento.</div>
                    </div>
                  )}
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Cadastro manual do diagnóstico</div>
                    <div className="wbSectionSub">Preencha quando o resultado chegar por fora da integração automática</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbForm wbFormTight">
                    <div className="wbFormRow">
                      <label>Nome<input value={diagnosisForm.name} onChange={(e) => updateDiagnosisField("name", e.target.value)} /></label>
                      <label>Empresa<input value={diagnosisForm.company} onChange={(e) => updateDiagnosisField("company", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Telefone<input value={diagnosisForm.phone} onChange={(e) => updateDiagnosisField("phone", e.target.value)} /></label>
                      <label>Email<input value={diagnosisForm.email} onChange={(e) => updateDiagnosisField("email", e.target.value)} /></label>
                    </div>
                    <label>Segmento<input value={diagnosisForm.segment} onChange={(e) => updateDiagnosisField("segment", e.target.value)} /></label>
                    <div className="wbScoreGrid">
                      <label>Score geral<input value={diagnosisForm.score_overall} onChange={(e) => updateDiagnosisField("score_overall", e.target.value)} /></label>
                      <label>Marketing<input value={diagnosisForm.score_marketing} onChange={(e) => updateDiagnosisField("score_marketing", e.target.value)} /></label>
                      <label>Vendas<input value={diagnosisForm.score_sales} onChange={(e) => updateDiagnosisField("score_sales", e.target.value)} /></label>
                      <label>Automação<input value={diagnosisForm.score_automation} onChange={(e) => updateDiagnosisField("score_automation", e.target.value)} /></label>
                      <label>Dados<input value={diagnosisForm.score_data} onChange={(e) => updateDiagnosisField("score_data", e.target.value)} /></label>
                      <label>Relacionamento<input value={diagnosisForm.score_relationship} onChange={(e) => updateDiagnosisField("score_relationship", e.target.value)} /></label>
                    </div>
                    <label>Principal oportunidade<textarea value={diagnosisForm.opportunity} onChange={(e) => updateDiagnosisField("opportunity", e.target.value)} /></label>
                    <label>Serviço recomendado<input value={diagnosisForm.recommended_service} onChange={(e) => updateDiagnosisField("recommended_service", e.target.value)} /></label>
                    <label>
                      Temperatura
                      <select value={diagnosisForm.temperature} onChange={(e) => updateDiagnosisField("temperature", e.target.value)}>
                        {TEMPERATURES.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </label>
                    <label>Resumo gerado<textarea value={diagnosisForm.summary} onChange={(e) => updateDiagnosisField("summary", e.target.value)} /></label>
                    <button className="wbBtn" onClick={saveDiagnosis} disabled={diagnosisSaving || !selected}>
                      {diagnosisSaving ? "Salvando..." : "Salvar diagnóstico"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </section>
        ) : view === "contatos" ? (
          <section className="wbKanban">
            <div className="wbAttendanceLayout">
              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Cadastro e edição de contatos</div>
                    <div className="wbSectionSub">Vincule cada cliente a uma conversa pelo telefone ou wa_id</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbForm wbFormTight">
                    <div className="wbFormRow">
                      <label>Nome<input value={attendanceContact.name} onChange={(e) => updateAttendanceContactField("name", e.target.value)} /></label>
                      <label>Empresa<input value={attendanceContact.company} onChange={(e) => updateAttendanceContactField("company", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Telefone<input value={attendanceContact.telefone} onChange={(e) => updateAttendanceContactField("telefone", e.target.value)} /></label>
                      <label>wa_id<input value={attendanceContact.wa_id} onChange={(e) => updateAttendanceContactField("wa_id", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Email<input value={attendanceContact.email} onChange={(e) => updateAttendanceContactField("email", e.target.value)} /></label>
                      <label>Instagram<input value={attendanceContact.instagram} onChange={(e) => updateAttendanceContactField("instagram", e.target.value)} /></label>
                    </div>
                    <label>Site<input value={attendanceContact.site} onChange={(e) => updateAttendanceContactField("site", e.target.value)} /></label>
                    <div className="wbFormRow">
                      <label>Serviço de interesse<input value={attendanceContact.service_interest} onChange={(e) => updateAttendanceContactField("service_interest", e.target.value)} /></label>
                      <label>Serviço contratado<input value={attendanceContact.service_contracted} onChange={(e) => updateAttendanceContactField("service_contracted", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Responsável Mugô<input value={attendanceContact.owner} onChange={(e) => updateAttendanceContactField("owner", e.target.value)} /></label>
                      <label>
                        Status
                        <select value={attendanceContact.status} onChange={(e) => updateAttendanceContactField("status", e.target.value)}>
                          {CONTACT_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
                        </select>
                      </label>
                    </div>
                    <label>Observações internas<textarea value={attendanceContact.notes} onChange={(e) => updateAttendanceContactField("notes", e.target.value)} /></label>
                    <button className="wbBtn" onClick={saveAttendanceContact} disabled={attendanceContactSaving}>
                      {attendanceContactSaving ? "Salvando..." : "Salvar contato"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Contatos da central</div>
                    <div className="wbSectionSub">Conversas recentes e clientes salvos</div>
                  </div>
                  <div className="wbColCount">{visibleConvs.length}</div>
                </div>
                <div className="wbColBody">
                  <div className="wbMiniList">
                    {visibleConvs.slice(0, 18).map((contact) => (
                      <div key={contact.wa_id} className="wbMiniItem">
                        <div className="wbMiniItemMain">
                          <div className="wbMiniTitle">{getDisplayName(contact)}</div>
                          <div className="wbMiniSub">{formatPhoneBR(contact.telefone || contact.wa_id)} • {contact.status || getStageByConv(contact)}</div>
                        </div>
                        <button className="wbBtnGhost" onClick={() => {
                          setSelected(contact.wa_id);
                          setAttendanceContact(buildContactPayloadFromConv(contact));
                        }}>
                          Editar
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </section>
        ) : view === "cobrancas" ? (
          <section className="wbKanban">
            <div className="wbAttendanceLayout">
              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Nova cobrança</div>
                    <div className="wbSectionSub">Crie o controle e gere o lembrete para aprovação</div>
                  </div>
                </div>
                <div className="wbColBody">
                  <div className="wbForm wbFormTight">
                    <div className="wbFormRow">
                      <label>Cliente<input value={collectionForm.cliente} onChange={(e) => updateCollectionField("cliente", e.target.value)} /></label>
                      <label>Empresa<input value={collectionForm.empresa} onChange={(e) => updateCollectionField("empresa", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Telefone<input value={collectionForm.telefone} onChange={(e) => updateCollectionField("telefone", e.target.value)} /></label>
                      <label>wa_id<input value={collectionForm.wa_id} onChange={(e) => updateCollectionField("wa_id", e.target.value)} /></label>
                    </div>
                    <div className="wbFormRow">
                      <label>Valor<input value={collectionForm.amount} onChange={(e) => updateCollectionField("amount", e.target.value)} placeholder="R$ 0,00" /></label>
                      <label>Data de vencimento<input type="date" value={collectionForm.due_date} onChange={(e) => updateCollectionField("due_date", e.target.value)} /></label>
                    </div>
                    <label>
                      Status
                      <select value={collectionForm.status} onChange={(e) => updateCollectionField("status", e.target.value)}>
                        {COLLECTION_STATUSES.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                    </label>
                    <label>Observações<textarea value={collectionForm.notes} onChange={(e) => updateCollectionField("notes", e.target.value)} /></label>
                    <button className="wbBtn" onClick={saveCollection} disabled={collectionSaving}>
                      {collectionSaving ? "Criando..." : "Criar cobrança"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Controle de cobranças</div>
                    <div className="wbSectionSub">Lembretes só são enviados depois da aprovação</div>
                  </div>
                  <div className="wbColCount">{collections.length}</div>
                </div>
                <div className="wbColBody">
                  {collections.length ? collections.map((collection) => (
                    <div key={collection.id} className="wbCard">
                      <div className="wbCardTop">
                        <div className="wbAvatar small">{String(collection.cliente || collection.wa_id || "C").slice(0, 1)}</div>
                        <div className="wbCardTitle">{collection.cliente || getDisplayName(conversationsById.get(collection.wa_id)) || "Cliente"}</div>
                        <div className="wbCardTime">{formatDateBR(collection.due_date)}</div>
                      </div>
                      <div className="wbCardSub">{collection.empresa || "Sem empresa"} • {formatPhoneBR(collection.telefone || collection.wa_id)}</div>
                      <div className="wbCardPreview">{formatMoneyBR(collection.amount)} • {collection.status} {collection.notes ? `• ${collection.notes}` : ""}</div>
                      <div className="wbCardBadges">
                        <button className="wbBtnGhost" onClick={() => setCollectionForm(collection)}>Editar</button>
                        <button className="wbBtnGhost" onClick={() => markCollectionPaid(collection.id)} disabled={collection.status === "Pago"}>Marcar como paga</button>
                        <button className="wbBtnGhost" onClick={() => prepareCollectionReminder(collection)}>Gerar lembrete</button>
                        <button className="wbBtn" onClick={() => sendApprovedCollectionReminder(collection)} disabled={reminderSending}>Enviar lembrete aprovado</button>
                      </div>
                    </div>
                  )) : (
                    <div className="wbEmpty">
                      Nenhuma cobrança criada nesta sessão.
                      <div className="wbEmptyHint">Ao criar uma cobrança, ela também gera uma tarefa de acompanhamento.</div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </section>
        ) : view === "usuarios" ? (
          <section className="wbKanban">
            <div className="wbAttendanceLayout">
              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Usuários</div>
                    <div className="wbSectionSub">Crie e mantenha acessos da equipe Mugô</div>
                  </div>
                  <button className="wbBtnGhost" onClick={() => refreshUsers()} disabled={usersLoading}>
                    {usersLoading ? "Atualizando..." : "Atualizar"}
                  </button>
                </div>
                <div className="wbColBody">
                  {canManageUsers(currentRole) ? (
                    <div className="wbForm wbFormTight">
                      <div className="wbFormRow">
                        <label>Nome<input value={newUser.name} onChange={(e) => setNewUser((prev) => ({ ...prev, name: e.target.value }))} /></label>
                        <label>Email<input value={newUser.email} onChange={(e) => setNewUser((prev) => ({ ...prev, email: e.target.value }))} /></label>
                      </div>
                      <div className="wbFormRow">
                        <label>
                          Perfil
                          <select value={newUser.role} onChange={(e) => setNewUser((prev) => ({ ...prev, role: e.target.value }))}>
                            {USER_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                          </select>
                        </label>
                        <label>Senha inicial opcional<input type="password" value={newUser.password} onChange={(e) => setNewUser((prev) => ({ ...prev, password: e.target.value }))} /></label>
                      </div>
                      <button className="wbBtn" onClick={onCreateUser} disabled={userSaving || !newUser.email.trim()}>
                        {userSaving ? "Criando..." : "Criar usuário"}
                      </button>
                    </div>
                  ) : (
                    <div className="wbEmpty">Apenas Admin pode gerenciar usuários.</div>
                  )}
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div>
                    <div className="wbSectionTitle">Equipe cadastrada</div>
                    <div className="wbSectionSub">Perfis ativos e permissões</div>
                  </div>
                  <div className="wbColCount">{users.length}</div>
                </div>
                <div className="wbColBody">
                  {users.length ? users.map((user) => (
                    <div key={user.id} className="wbCard">
                      <div className="wbCardTop">
                        <div className="wbAvatar small">{String(user.name || user.email || "U").slice(0, 1).toUpperCase()}</div>
                        <input
                          className="wbInlineInput"
                          value={user.name || ""}
                          onChange={(e) => setUsers((prev) => prev.map((item) => item.id === user.id ? { ...item, name: e.target.value } : item))}
                          onBlur={(e) => onUpdateUser(user.id, { name: e.target.value })}
                          disabled={!canManageUsers(currentRole)}
                        />
                        <span className={`wbBadge ${user.active ? "ok" : "paused"}`}>{user.active ? "ativo" : "inativo"}</span>
                      </div>
                      <div className="wbCardSub">{user.email}</div>
                      <div className="wbCardBadges">
                        <select
                          className="wbHeaderSelect"
                          value={normalizeRole(user.role)}
                          onChange={(e) => onUpdateUser(user.id, { role: e.target.value })}
                          disabled={!canManageUsers(currentRole)}
                        >
                          {USER_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                        </select>
                        <button
                          className="wbBtnGhost"
                          onClick={() => onUpdateUser(user.id, { active: !user.active })}
                          disabled={!canManageUsers(currentRole)}
                        >
                          {user.active ? "Desativar" : "Ativar"}
                        </button>
                      </div>
                    </div>
                  )) : (
                    <div className="wbEmpty">
                      Nenhum usuário retornado.
                      <div className="wbEmptyHint">Aplique a migration de profiles se a tabela ainda não existir.</div>
                    </div>
                  )}
                </div>
              </div>
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
