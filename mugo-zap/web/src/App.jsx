// web/src/App.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import {
  closeHandoff,
  createTask,
  doneTask,
  getConversations,
  getMessages,
  listTasks,
  sendMessage,
  sseUrl,
  updateContact,
  updateTask, // ✅ novo (api.js)
} from "./api";
import "./styles.css";

const STAGES = ["Novo", "Em contato", "Proposta", "Ganhou", "Perdeu"];
const LS_STAGE_KEY = "mugozap_stage_v2";
const LS_SEEN_KEY = "mugozap_seen_v2";

function nowLocalTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return "";
  }
}
function shortTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}
function clip(s = "", n = 72) {
  const t = String(s || "").replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n - 1) + "…" : t;
}
function getAvatarSeed(conv) {
  return (conv?.name || conv?.wa_id || "X").toString().slice(0, 1).toUpperCase();
}
function loadJSON(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback));
  } catch {
    return fallback;
  }
}
function saveJSON(key, obj) {
  localStorage.setItem(key, JSON.stringify(obj || {}));
}
function startOfDay(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}
function endOfDay(d) {
  const x = new Date(d);
  x.setHours(23, 59, 59, 999);
  return x;
}
function sameDay(a, b) {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
function parseTags(str) {
  return String(str || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

// ✅ FIX DEFINITIVO: NÃO converter para UTC (toISOString) — isso quebrava “Hoje”
function toIsoLocal(dateStr, timeStr) {
  const [y, m, d] = dateStr.split("-").map((x) => parseInt(x, 10));
  const [hh, mm] = timeStr.split(":").map((x) => parseInt(x, 10));
  const dt = new Date(y, (m || 1) - 1, d || 1, hh || 0, mm || 0, 0, 0);

  const pad = (n) => String(n).padStart(2, "0");
  const yyyy = dt.getFullYear();
  const MM = pad(dt.getMonth() + 1);
  const dd = pad(dt.getDate());
  const HH = pad(dt.getHours());
  const mm2 = pad(dt.getMinutes());
  const ss = pad(dt.getSeconds());

  // ISO “local” sem timezone (backend aceita string ISO)
  return `${yyyy}-${MM}-${dd}T${HH}:${mm2}:${ss}`;
}

function taskBucket(dueAtIso) {
  if (!dueAtIso) return "Sem data";
  const due = new Date(dueAtIso);
  const now = new Date();
  const todayStart = startOfDay(now);
  const todayEnd = endOfDay(now);

  if (due < todayStart) return "Atrasadas";
  if (due >= todayStart && due <= todayEnd) return "Hoje";

  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (sameDay(due, tomorrow)) return "Amanhã";

  const weekEnd = new Date(now);
  weekEnd.setDate(weekEnd.getDate() + 7);
  return due <= endOfDay(weekEnd) ? "Esta semana" : "Futuro";
}

const TASK_COLS = ["Atrasadas", "Hoje", "Amanhã", "Esta semana", "Futuro", "Sem data"];

// ✅ Helpers para drag de tasks (Agenda)
function dueForBucket(bucket) {
  const now = new Date();
  const make = (baseDate, hh = 12, mm = 0) => {
    const d = new Date(baseDate);
    d.setHours(hh, mm, 0, 0);
    const pad = (n) => String(n).padStart(2, "0");
    const yyyy = d.getFullYear();
    const MM = pad(d.getMonth() + 1);
    const dd = pad(d.getDate());
    const HH = pad(d.getHours());
    const mm2 = pad(d.getMinutes());
    const ss = pad(d.getSeconds());
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

  // Sem data => não mexe (precisaria endpoint para limpar due_at)
  return null;
}

export default function App() {
  const [view, setView] = useState("inbox"); // inbox | kanban | agenda | contatos
  const [convs, setConvs] = useState([]);
  const [selected, setSelected] = useState(null); // wa_id
  const [msgs, setMsgs] = useState([]);
  const [q, setQ] = useState("");
  const [text, setText] = useState("");
  const [err, setErr] = useState("");

  const [stages, setStages] = useState(() => loadJSON(LS_STAGE_KEY, {}));
  const [seen, setSeen] = useState(() => loadJSON(LS_SEEN_KEY, {}));

  // Agenda
  const [tasks, setTasks] = useState([]);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskTitle, setTaskTitle] = useState("Atendimento / Follow-up");
  const [taskDate, setTaskDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [taskTime, setTaskTime] = useState("12:00");

  // Contato editor (salvar contato)
  const [editOpen, setEditOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editTel, setEditTel] = useState("");
  const [editStage, setEditStage] = useState("Novo");
  const [editTags, setEditTags] = useState("");
  const [editNotes, setEditNotes] = useState("");

  const esRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  const selectedConv = useMemo(
    () => convs.find((c) => c.wa_id === selected) || null,
    [convs, selected]
  );

  async function refreshConversations({ keepSelected = true } = {}) {
    setErr("");
    const items = await getConversations();
    setConvs(items);

    if (!keepSelected && items.length) setSelected(items[0].wa_id);
    if (!selected && items.length) setSelected(items[0].wa_id);
  }

  async function refreshMessages(wa_id) {
    if (!wa_id) return;
    setErr("");
    const m = await getMessages(wa_id);
    setMsgs(m);

    const lastAt = convs.find((c) => c.wa_id === wa_id)?.last_at;
    if (lastAt) {
      const next = { ...seen, [wa_id]: lastAt };
      setSeen(next);
      saveJSON(LS_SEEN_KEY, next);
    }
  }

  async function refreshTasks() {
    setErr("");
    const items = await listTasks({ status: "open" });
    setTasks(items);
  }

  // init
  useEffect(() => {
    (async () => {
      try {
        await refreshConversations({ keepSelected: false });
        await refreshTasks();
      } catch (e) {
        setErr(String(e.message || e));
      }
    })();
    // eslint-disable-next-line
  }, []);

  // SSE
  useEffect(() => {
    if (esRef.current) {
      try {
        esRef.current.close();
      } catch {}
      esRef.current = null;
    }

    const loadSSE = async () => {
      try {
        const url = await sseUrl();
        if (!url) return;

        const es = new EventSource(url);
        esRef.current = es;

        es.addEventListener("ping", () => {});
        es.addEventListener("update", async (ev) => {
          try {
            const payload = JSON.parse(ev.data || "{}");
            const type = payload?.type;
            const wa = payload?.wa_id;

            await refreshConversations({ keepSelected: true });
            if (wa && wa === selected) await refreshMessages(selected);
            if (String(type || "").startsWith("task_")) await refreshTasks();
          } catch (e) {
            console.warn("SSE parse fail:", e);
          }
        });

        es.onerror = (e) => console.warn("SSE error:", e);
      } catch (e) {
        console.warn("SSE init error:", e);
      }
    };

    loadSSE();

    return () => {
      if (esRef.current) {
        try {
          esRef.current.close();
        } catch {}
        esRef.current = null;
      }
    };
    // eslint-disable-next-line
  }, [selected]);

  // troca de chat
  useEffect(() => {
    (async () => {
      try {
        if (selected) await refreshMessages(selected);
      } catch (e) {
        setErr(String(e.message || e));
      }
    })();
    // eslint-disable-next-line
  }, [selected]);

  // auto scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [msgs.length]);

  const filteredConvs = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return convs;
    return convs.filter((c) => {
      const a = (c.wa_id || "").toLowerCase();
      const b = (c.name || "").toLowerCase();
      const d = (c.telefone || "").toLowerCase();
      const e = (c.last_text || "").toLowerCase();
      return a.includes(s) || b.includes(s) || d.includes(s) || e.includes(s);
    });
  }, [q, convs]);

  const unreadCount = (conv) => {
    const lastAt = conv?.last_at;
    if (!lastAt) return 0;
    const seenAt = seen?.[conv.wa_id];
    if (!seenAt) return 1;
    return new Date(lastAt).getTime() > new Date(seenAt).getTime() ? 1 : 0;
  };

  async function onSend() {
    const t = text.trim();
    if (!t || !selected) return;

    setText("");
    setErr("");

    try {
      await sendMessage(selected, t);
      await refreshMessages(selected);
      await refreshConversations({ keepSelected: true });
      inputRef.current?.focus?.();
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  async function onCloseHandoff() {
    if (!selected) return;
    setErr("");
    try {
      await closeHandoff(selected);
      await refreshConversations({ keepSelected: true });
      await refreshMessages(selected);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  // Kanban local (stages)
  function getStage(wa_id) {
    return stages?.[wa_id] || "Novo";
  }
  function setStageLocal(wa_id, stage) {
    const next = { ...(stages || {}), [wa_id]: stage };
    setStages(next);
    saveJSON(LS_STAGE_KEY, next);
  }

  const kanbanCols = useMemo(() => {
    const cols = {};
    STAGES.forEach((s) => (cols[s] = []));
    for (const c of convs) {
      const s = getStage(c.wa_id);
      (cols[s] ||= []).push(c);
    }
    for (const k of Object.keys(cols)) {
      cols[k].sort((a, b) => {
        const ta = a.last_at ? new Date(a.last_at).getTime() : 0;
        const tb = b.last_at ? new Date(b.last_at).getTime() : 0;
        return tb - ta;
      });
    }
    return cols;
    // eslint-disable-next-line
  }, [convs, stages]);

  function onDragStart(ev, wa_id) {
    ev.dataTransfer.setData("text/plain", wa_id);
    ev.dataTransfer.effectAllowed = "move";
  }
  function onDrop(ev, stage) {
    ev.preventDefault();
    const wa_id = ev.dataTransfer.getData("text/plain");
    if (!wa_id) return;
    setStageLocal(wa_id, stage);
  }

  function openChat(wa_id) {
    setSelected(wa_id);
    setView("inbox");
    setTimeout(() => inputRef.current?.focus?.(), 80);
  }

  // Agenda cols
  const taskCols = useMemo(() => {
    const cols = {};
    TASK_COLS.forEach((k) => (cols[k] = []));
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

  async function onCreateTaskQuick() {
    if (!selected) {
      setErr("Selecione um contato antes de agendar.");
      return;
    }
    setTaskTitle("Atendimento / Follow-up");
    setTaskModalOpen(true);
  }

  async function onConfirmTask() {
    if (!selected) return;
    setErr("");
    try {
      const due_at = toIsoLocal(taskDate, taskTime);
      await createTask({ wa_id: selected, title: taskTitle.trim() || "Atendimento / Follow-up", due_at });

      // nota visual no contato
      const baseNotes = String(selectedConv?.notes || "");
      const stamp = `Agendado: ${taskTitle.trim() || "Atendimento / Follow-up"} • ${taskDate}T${taskTime}`;
      const nextNotes = baseNotes ? `${baseNotes}\n${stamp}` : stamp;

      await updateContact(selected, { notes: nextNotes });

      setTaskModalOpen(false);

      // ✅ garante atualizar agenda e listas
      await refreshTasks();
      await refreshConversations({ keepSelected: true });
      await refreshMessages(selected);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  async function onDoneTask(id) {
    setErr("");
    try {
      await doneTask(id);
      await refreshTasks();
      await refreshConversations({ keepSelected: true });
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  // Contatos salvos (tag salvo)
  const savedContacts = useMemo(() => {
    return (convs || [])
      .filter((c) => Array.isArray(c.tags) && c.tags.includes("salvo"))
      .sort((a, b) => {
        const ta = a.last_at ? new Date(a.last_at).getTime() : 0;
        const tb = b.last_at ? new Date(b.last_at).getTime() : 0;
        return tb - ta;
      });
  }, [convs]);

  function openEditContact() {
    if (!selectedConv) return;
    setEditName(selectedConv.name || "");
    setEditTel(selectedConv.telefone || "");
    setEditStage(getStage(selectedConv.wa_id));
    setEditTags((selectedConv.tags || []).join(", "));
    setEditNotes(selectedConv.notes || "");
    setEditOpen(true);
  }

  async function saveContactEdits() {
    if (!selected) return;
    setErr("");
    try {
      const tags = parseTags(editTags);
      if (!tags.includes("salvo")) tags.push("salvo");

      // ✅ FIX: salva name/telefone de verdade no Supabase (via PATCH)
      await updateContact(selected, {
        name: editName,
        telefone: editTel,
        stage: editStage,
        notes: editNotes,
        tags,
      });

      setStageLocal(selected, editStage);
      setEditOpen(false);

      // ✅ refresh completo pra UI trocar número por nome
      await refreshConversations({ keepSelected: true });
      await refreshMessages(selected);
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  // ✅ Drag: tarefas (Agenda)
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

    if (!nextDue) return; // Sem data = não mexe por enquanto

    try {
      setErr("");
      await updateTask(taskId, { due_at: nextDue });
      await refreshTasks();
      await refreshConversations({ keepSelected: true });
    } catch (e) {
      setErr(String(e.message || e));
    }
  }

  // ✅ Drag: contatos salvos -> colunas do Kanban
  function onDragStartSaved(ev, wa_id) {
    ev.dataTransfer.setData("text/plain", `lead:${wa_id}`);
    ev.dataTransfer.effectAllowed = "move";
  }
  function onDropLeadToStage(ev, stage) {
    ev.preventDefault();
    const raw = ev.dataTransfer.getData("text/plain");
    if (!raw || !raw.startsWith("lead:")) return;
    const wa_id = raw.replace("lead:", "").trim();
    if (!wa_id) return;
    setStageLocal(wa_id, stage);
    setView("kanban");
  }

  return (
    <div className="wbShell">
      {/* Rail */}
      <aside className="wbRail">
        <div className="wbBrand">M</div>

        <button className={`wbRailBtn ${view === "inbox" ? "active" : ""}`} onClick={() => setView("inbox")} title="Inbox">
          💬
        </button>

        <button className={`wbRailBtn ${view === "kanban" ? "active" : ""}`} onClick={() => setView("kanban")} title="Kanban">
          🗂️
        </button>

        <button className={`wbRailBtn ${view === "agenda" ? "active" : ""}`} onClick={() => setView("agenda")} title="Agenda">
          🗓️
        </button>

        <button className={`wbRailBtn ${view === "contatos" ? "active" : ""}`} onClick={() => setView("contatos")} title="Contatos salvos">
          👤
        </button>

        <div className="wbRailSpacer" />
      </aside>

      {/* Sidebar */}
      <aside className="wbSidebar">
        <div className="wbSidebarTop">
          <div>
            <div className="wbTitle">MUGÔZAP</div>
            <div className="wbSub">
              {view === "inbox" ? "Inbox" : view === "kanban" ? "Kanban" : view === "agenda" ? "Agenda" : "Contatos"}
            </div>
          </div>

          <div className="wbTopRight">
            <button className="wbBtnGhost" onClick={() => refreshConversations({ keepSelected: true })}>
              Atualizar
            </button>
          </div>
        </div>

        <div className="wbSearch">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nome, wa_id, telefone..." />
        </div>

        <div className="wbList">
          {filteredConvs.map((c) => {
            const active = c.wa_id === selected;
            const unread = unreadCount(c);
            return (
              <button key={c.wa_id} className={`wbItem ${active ? "active" : ""}`} onClick={() => setSelected(c.wa_id)}>
                <div className="wbAvatar">{getAvatarSeed(c)}</div>

                <div className="wbItemMid">
                  <div className="wbItemTop">
                    <div className="wbName">{c.name || c.wa_id}</div>
                    <div className="wbTime">{shortTime(c.last_at)}</div>
                  </div>

                  <div className="wbPreviewRow">
                    <div className="wbPreview">{clip(c.last_text || "", 90)}</div>

                    {c.handoff_active ? <span className="wbBadge warn">handoff</span> : null}
                    {c.next_task ? <span className="wbBadge ok">agendado</span> : null}
                    {unread ? <span className="wbBadge ok">novo</span> : null}
                  </div>
                </div>
              </button>
            );
          })}

          {!filteredConvs.length && (
            <div className="wbEmpty">
              Sem conversas ainda.
              <div className="wbEmptyHint">Dica: o webhook precisa estar recebendo eventos do WhatsApp.</div>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="wbMain">
        <header className="wbHeader">
          <div className="wbHeaderLeft">
            {view === "inbox" ? (
              <>
                <div className="wbHeaderTitle">{selectedConv?.name || selected || "Selecione uma conversa"}</div>
                <div className="wbHeaderSub">
                  {selected ? `wa_id: ${selected}` : "Painel estilo WhatsApp Business"}
                  {selectedConv?.telefone ? ` • tel: ${selectedConv.telefone}` : ""}
                  {selectedConv?.next_task?.due_at ? ` • próximo: ${nowLocalTime(selectedConv.next_task.due_at)}` : ""}
                </div>
              </>
            ) : view === "kanban" ? (
              <>
                <div className="wbHeaderTitle">Kanban</div>
                <div className="wbHeaderSub">Arraste cards entre colunas (local)</div>
              </>
            ) : view === "agenda" ? (
              <>
                <div className="wbHeaderTitle">Agenda</div>
                <div className="wbHeaderSub">Arraste tarefas entre colunas (atualiza due_at)</div>
              </>
            ) : (
              <>
                <div className="wbHeaderTitle">Contatos salvos</div>
                <div className="wbHeaderSub">Arraste um contato para o Kanban</div>
              </>
            )}
          </div>

          <div className="wbHeaderRight">
            {err ? <div className="wbError">Erro: {err}</div> : null}

            {view === "inbox" ? (
              <>
                <button className="wbBtn" onClick={() => inputRef.current?.focus?.()} disabled={!selected}>
                  Responder
                </button>

                <button className="wbBtn" onClick={onCreateTaskQuick} disabled={!selected}>
                  Agendar
                </button>

                <button className="wbBtnGhost" onClick={openEditContact} disabled={!selected} title="Salvar/editar contato (CRM)">
                  Salvar contato
                </button>
              </>
            ) : null}

            {view === "agenda" ? (
              <button className="wbBtnGhost" onClick={refreshTasks}>
                Atualizar agenda
              </button>
            ) : null}
          </div>
        </header>

        {/* Views */}
        {view === "inbox" ? (
          <>
            <section className="wbChat">
              {!selected ? (
                <div className="wbChatEmpty">
                  <div className="wbChatEmptyTitle">Selecione uma conversa.</div>
                  <div className="wbChatEmptySub">As mensagens aparecem aqui com visual de WhatsApp Business.</div>
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
                  <div ref={chatEndRef} />
                </div>
              )}
            </section>

            <footer className="wbComposer">
              <div className="wbComposerInner">
                <input
                  ref={inputRef}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder={selected ? "Digite uma mensagem..." : "Selecione uma conversa para responder"}
                  disabled={!selected}
                  onKeyDown={(e) => (e.key === "Enter" ? onSend() : null)}
                />
                <button className="wbSend" onClick={onSend} disabled={!selected || !text.trim()}>
                  Enviar
                </button>
              </div>
            </footer>
          </>
        ) : view === "kanban" ? (
          <section className="wbKanban">
            <div className="wbKanbanInner">
              {STAGES.map((s) => (
                <div
                  key={s}
                  className="wbCol"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    onDrop(e, s); // cards do kanban
                    onDropLeadToStage(e, s); // ✅ contatos salvos
                  }}
                >
                  <div className="wbColHead">
                    <div className="wbColTitle">{s}</div>
                    <div className="wbColCount">{(kanbanCols[s] || []).length}</div>
                  </div>

                  <div className="wbColBody">
                    {(kanbanCols[s] || []).map((c) => (
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
                          <div className="wbCardTitle">{c.name || c.wa_id}</div>
                          <div className="wbCardTime">{shortTime(c.last_at)}</div>
                        </div>

                        <div className="wbCardSub">{c.telefone ? c.telefone : c.wa_id}</div>
                        <div className="wbCardPreview">{clip(c.last_text || "", 120)}</div>

                        <div className="wbCardBadges">
                          {c.handoff_active ? <span className="wbBadge warn">handoff</span> : null}
                          {c.next_task ? <span className="wbBadge ok">agendado</span> : null}
                          {unreadCount(c) ? <span className="wbBadge ok">novo</span> : null}
                        </div>
                      </div>
                    ))}

                    {!kanbanCols[s]?.length ? <div className="wbColEmpty">Arraste um card pra cá</div> : null}
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
                      <div
                        key={t.id}
                        className="wbCard"
                        role="button"
                        tabIndex={0}
                        draggable
                        onDragStart={(e) => onDragStartTask(e, t.id)}
                      >
                        <div className="wbCardTop">
                          <div className="wbAvatar small">{String(t.wa_id || "X").slice(0, 1)}</div>
                          <div className="wbCardTitle">{t.title}</div>
                          <div className="wbCardTime">{shortTime(t.due_at)}</div>
                        </div>

                        <div className="wbCardSub">{t.wa_id}</div>
                        <div className="wbCardPreview">Vencimento: {nowLocalTime(t.due_at)}</div>

                        <div className="wbCardBadges">
                          <button className="wbBtnGhost" onClick={() => openChat(t.wa_id)} style={{ padding: "8px 10px" }}>
                            Abrir conversa
                          </button>
                          <button className="wbBtn" onClick={() => onDoneTask(t.id)} style={{ padding: "8px 10px" }}>
                            Concluir
                          </button>
                        </div>
                      </div>
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
                  {savedContacts.map((c) => (
                    <div
                      key={c.wa_id}
                      className="wbCard"
                      onClick={() => openChat(c.wa_id)}
                      role="button"
                      tabIndex={0}
                      draggable
                      onDragStart={(e) => onDragStartSaved(e, c.wa_id)}
                      title="Arraste para o Kanban"
                    >
                      <div className="wbCardTop">
                        <div className="wbAvatar small">{getAvatarSeed(c)}</div>
                        <div className="wbCardTitle">{c.name || c.wa_id}</div>
                        <div className="wbCardTime">{shortTime(c.last_at)}</div>
                      </div>
                      <div className="wbCardSub">{c.telefone || c.wa_id}</div>
                      <div className="wbCardPreview">{clip(c.notes || c.last_text || "", 140)}</div>
                      <div className="wbCardBadges">
                        {c.next_task ? <span className="wbBadge ok">agendado</span> : null}
                        {c.handoff_active ? <span className="wbBadge warn">handoff</span> : null}
                      </div>
                    </div>
                  ))}
                  {!savedContacts.length ? <div className="wbColEmpty">Nenhum contato salvo ainda</div> : null}
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div className="wbColTitle">Como salvar</div>
                  <div className="wbColCount">1</div>
                </div>
                <div className="wbColBody">
                  <div className="wbEmpty">
                    Abra uma conversa → clique em <b>Salvar contato</b>.
                    <div className="wbEmptyHint">Ele aplica tag “salvo” + stage/tags/notes.</div>
                  </div>
                </div>
              </div>

              <div className="wbCol">
                <div className="wbColHead">
                  <div className="wbColTitle">Dica</div>
                  <div className="wbColCount">1</div>
                </div>
                <div className="wbColBody">
                  <div className="wbEmpty">
                    Use tags: <b>cliente</b>, <b>lead</b>, <b>vip</b>, <b>quente</b>.
                    <div className="wbEmptyHint">Separadas por vírgula.</div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Modal: Agendar */}
        {taskModalOpen ? (
          <div className="wbModalOverlay" onClick={() => setTaskModalOpen(false)}>
            <div className="wbModal" onClick={(e) => e.stopPropagation()}>
              <div className="wbModalTitle">Agendar atendimento</div>
              <div className="wbModalSub">{selectedConv?.name || selected}</div>

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
                <button className="wbBtnGhost" onClick={() => setTaskModalOpen(false)}>
                  Cancelar
                </button>
                <button className="wbBtn" onClick={onConfirmTask}>
                  Salvar
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {/* Modal: Salvar contato (CRM) */}
        {editOpen ? (
          <div className="wbModalOverlay" onClick={() => setEditOpen(false)}>
            <div className="wbModal" onClick={(e) => e.stopPropagation()}>
              <div className="wbModalTitle">Salvar contato</div>
              <div className="wbModalSub">{selectedConv?.wa_id}</div>

              <div className="wbForm">
                <label>
                  Nome
                  <input value={editName} onChange={(e) => setEditName(e.target.value)} placeholder="Ex: Maria (Loja X)" />
                </label>

                <label>
                  Telefone
                  <input value={editTel} onChange={(e) => setEditTel(e.target.value)} placeholder="Ex: 55119..." />
                </label>

                <label>
                  Stage (Kanban)
                  <select value={editStage} onChange={(e) => setEditStage(e.target.value)}>
                    {STAGES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  Tags (vírgula)
                  <input value={editTags} onChange={(e) => setEditTags(e.target.value)} placeholder="salvo, lead, vip..." />
                </label>

                <label>
                  Notas
                  <textarea value={editNotes} onChange={(e) => setEditNotes(e.target.value)} rows={4} placeholder="Contexto, dores, próximos passos..." />
                </label>

                <div className="wbEmptyHint">Nome/Telefone agora salvam no Supabase também ✅</div>
              </div>

              <div className="wbModalActions">
                <button className="wbBtnGhost" onClick={() => setEditOpen(false)}>
                  Cancelar
                </button>
                <button className="wbBtn" onClick={saveContactEdits}>
                  Salvar
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}