// Dani dashboard: one page that asks the server for the state every few
// seconds and redraws. No framework. Every text from outside is put in the
// page with textContent (through h()), never as HTML.

const POLL_MS = 5000;        // how often the page asks the server
const UNDO_MS = 5000;        // the "Annulla" seconds before a tick is written
const HOUR_START = 7, HOUR_END = 23, HOUR_PX = 46;
const WEEKDAYS = ["dom", "lun", "mar", "mer", "gio", "ven", "sab"];
const MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"];

let state = null;            // the last answer of /api/state
let showAllTasks = false;
const pending = new Map();   // id -> timer: ticked, still inside the undo seconds
const sent = new Set();      // ids already written, hidden until the server drops them

const $ = (selector) => document.querySelector(selector);

function h(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (name === "class") node.className = value;
    else if (name.startsWith("on")) node.addEventListener(name.slice(2), value);
    else if (name === "style") node.style.cssText = value;
    else if (value !== false && value != null) node.setAttribute(name, value);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) node.append(kid);
  return node;
}

// --- talking to the server ---------------------------------------------------

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const pin = localStorage.getItem("dani-pin");
  if (pin) headers["X-Dani-Pin"] = pin;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    options = { ...options, body: JSON.stringify(options.json) };
  }
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) {
    const typed = prompt("PIN di Dani");
    if (typed) { localStorage.setItem("dani-pin", typed); return api(path, options); }
  }
  if (!response.ok) {
    let detail = `errore ${response.status}`;
    try { const body = await response.json(); if (typeof body.detail === "string") detail = body.detail; } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

async function poll() {
  try {
    state = await api("/api/state");
    for (const id of [...sent]) if (!isListed(id)) sent.delete(id);
    render();
  } catch (failure) {
    $("#fresh").className = "fresh bad";
    $("#fresh").textContent = `server non raggiungibile (${failure.message})`;
  }
}

function isListed(id) {
  return state.tasks.some((t) => t.id === id) || state.events.some((e) => e.key === id);
}
const gone = (id) => pending.has(id) || sent.has(id);

// --- small helpers -----------------------------------------------------------

const clock = (iso) => iso.slice(11, 16);
const dayOf = (iso) => iso.slice(0, 10);
const minutes = (iso) => Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16));
function dateIt(day) {
  const date = new Date(day + "T12:00:00");
  return `${WEEKDAYS[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]}`;
}
function calendarClass(name) {
  const key = (name || "").toLowerCase();
  if (key.includes("studio")) return "c-studio";
  if (key.includes("univ")) return "c-uni";
  if (key.includes("lavoro")) return "c-lavoro";
  return "";
}
function areaClass(area) {
  const key = (area || "").toLowerCase();
  if (key.includes("univ")) return "c-uni";
  if (key.includes("carriera") || key.includes("ict")) return "c-lavoro";
  return "";
}

function toast(text, { action, onAction, bad = false, ms = 4000 } = {}) {
  const node = h("div", { class: "toast" + (bad ? " bad" : "") }, h("span", {}, text));
  if (action) node.append(h("button", { onclick: () => { onAction(); node.remove(); } }, action));
  $("#toasts").append(node);
  setTimeout(() => node.remove(), ms);
  return node;
}

// --- ticking -----------------------------------------------------------------

function tick(kind, id, title) {
  if (gone(id)) return;
  const timer = setTimeout(async () => {
    pending.delete(id);
    sent.add(id);
    try {
      await api("/api/tick", { method: "POST", json: { kind, id } });
      poll();
    } catch (failure) {
      sent.delete(id);
      toast(`Non scritto: ${title} — ${failure.message}`, { bad: true, ms: 8000 });
      render();
    }
  }, UNDO_MS);
  pending.set(id, timer);
  const what = kind === "task" ? "Notion → Done" : "nascosto, da cancellare dal calendario";
  toast(`Fatto: ${title} (${what})`, {
    action: "Annulla", ms: UNDO_MS,
    onAction: () => { clearTimeout(timer); pending.delete(id); render(); },
  });
  render();
}

function tickButton(kind, id, title) {
  return h("button", { class: "tick", "aria-label": `Segna come fatto: ${title}`, title: "Fatto", onclick: () => tick(kind, id, title) }, "✓");
}

// --- Home --------------------------------------------------------------------

function renderHome() {
  $("#home-date").textContent = dateIt(state.today);

  const today = state.today;
  const rows = [];
  for (const event of state.events) {
    if (dayOf(event.start) !== today || gone(event.key)) continue;
    rows.push({ sort: event.all_day ? -1 : minutes(event.start), node: h("div", { class: "item" },
      h("div", { class: "when" }, event.all_day ? "tutto il giorno" : `${clock(event.start)}–${clock(event.end)}`),
      h("div", { class: "body" }, h("div", { class: "title" }, event.title),
        h("div", { class: "meta" }, h("span", { class: "chip " + calendarClass(event.calendar) }, event.calendar))),
      event.tickable ? tickButton("event", event.key, event.title) : h("span", { class: "notick" })) });
  }
  for (const block of state.blocks) {
    if (dayOf(block.start) !== today || gone(block.task_id)) continue;
    rows.push({ sort: minutes(block.start), node: h("div", { class: "item block" },
      h("div", { class: "when" }, `${clock(block.start)}–${clock(block.end)}`),
      h("div", { class: "body" }, h("div", { class: "title" }, block.title), h("div", { class: "meta" }, "blocco proposto dal planner")),
      tickButton("task", block.task_id, block.title)) });
  }
  rows.sort((a, b) => a.sort - b.sort);
  $("#home-events").replaceChildren(...(rows.length ? rows.map((r) => r.node) : [h("div", { class: "empty" }, "Niente in calendario oggi.")]));

  $("#priority-note").textContent = state.priority.ok ? "ordine verificato dall'AI" : `ordine per scadenza (${state.priority.reason})`;
  const tasks = state.tasks.filter((t) => !gone(t.id));
  const shown = showAllTasks ? tasks : tasks.slice(0, 8);
  const taskNodes = shown.map((task) => h("div", { class: "item" },
    tickButton("task", task.id, task.title),
    h("div", { class: "body" },
      h("div", { class: "title" }, task.title),
      h("div", { class: "meta" },
        task.area && h("span", { class: "chip " + areaClass(task.area) }, task.area), " ",
        [task.deadline && `scade ${dateIt(task.deadline)}`, task.priority, task.next_action && "next action"].filter(Boolean).join(" · ")),
      task.reason && h("div", { class: "meta" }, task.reason))));
  if (tasks.length > 8) taskNodes.push(h("button", { class: "btn ghost small more", onclick: () => { showAllTasks = !showAllTasks; render(); } },
    showAllTasks ? "Mostra meno" : `Mostra tutti (${tasks.length})`));
  $("#home-tasks").replaceChildren(...(taskNodes.length ? taskNodes : [h("div", { class: "empty" }, "Nessun task aperto.")]));

  const cycle = state.cycle;
  if (!cycle) {
    $("#home-cycle").replaceChildren(h("p", { class: "muted" }, "Imposta la data del ciclo in Impostazioni per vedere la fase."));
  } else {
    const detail = cycle.day ? `giorno ${cycle.day}` : (cycle.late_days ? `${cycle.late_days} giorni di ritardo` : "atteso oggi");
    $("#home-cycle").replaceChildren(
      h("div", { class: "phase" }, cycle.phase, h("small", {}, detail + (cycle.estimated ? " · stima" : ""))),
      h("p", { class: "muted", style: "margin-top:10px" }, cycle.hint),
      h("p", { class: "muted" }, `Prossimo inizio previsto: ${dateIt(cycle.next_start)}. Google Health non collegato.`),
      cycle.phase === "in arrivo" && h("button", { class: "btn ghost small", onclick: cycleStarted }, "È iniziato oggi"));
  }
}

// --- Calendar ------------------------------------------------------------------

// Events that overlap share the column width: each gets a lane.
function withLanes(items) {
  items.sort((a, b) => a.from - b.from || b.to - a.to);
  let group = [], groupEnd = -1;
  const close = () => { const lanes = Math.max(...group.map((i) => i.lane)) + 1; group.forEach((i) => (i.lanes = lanes)); };
  for (const item of items) {
    if (group.length && item.from >= groupEnd) { close(); group = []; }
    const used = new Set(group.filter((g) => g.to > item.from).map((g) => g.lane));
    item.lane = 0;
    while (used.has(item.lane)) item.lane++;
    group.push(item);
    groupEnd = Math.max(groupEnd, item.to);
  }
  if (group.length) close();
  return items;
}

function renderWeek() {
  const names = state.calendars.length ? state.calendars : [];
  $("#legend").replaceChildren(...names.map((n) => h("span", { class: "chip " + calendarClass(n) }, n)),
    h("span", { class: "chip", style: "background:rgba(255,255,255,.7);border:1px dashed var(--peony)" }, "blocco proposto"));

  const top = HOUR_START * 60, bottom = HOUR_END * 60;
  const height = (HOUR_END - HOUR_START) * HOUR_PX;
  const week = $("#week");
  const cells = [h("div")];
  for (const day of state.days) {
    const date = new Date(day + "T12:00:00");
    cells.push(h("div", { class: "dayhead" + (day === state.today ? " today" : "") }, WEEKDAYS[date.getDay()], h("b", {}, String(date.getDate()))));
  }
  cells.push(h("div"));
  for (const day of state.days) {
    const all = state.events.filter((e) => e.all_day && dayOf(e.start) === day && !gone(e.key));
    cells.push(h("div", { class: "allday" }, all.map((e) => h("div", { class: "ev static " + calendarClass(e.calendar) }, h("b", {}, e.title)))));
  }
  const hours = h("div", { class: "hours", style: `height:${height}px` });
  for (let hour = HOUR_START; hour <= HOUR_END; hour++) hours.append(h("span", { style: `top:${(hour - HOUR_START) * HOUR_PX}px` }, String(hour).padStart(2, "0")));
  cells.push(hours);

  for (const day of state.days) {
    const items = [];
    for (const e of state.events) {
      if (e.all_day || dayOf(e.start) !== day || gone(e.key)) continue;
      const to = dayOf(e.end) === day ? minutes(e.end) : 24 * 60;
      items.push({ from: minutes(e.start), to, title: e.title, cls: calendarClass(e.calendar), label: `${clock(e.start)}–${clock(e.end)}`,
        tick: e.tickable ? ["event", e.key] : null });
    }
    for (const b of state.blocks) {
      if (dayOf(b.start) !== day || gone(b.task_id)) continue;
      items.push({ from: minutes(b.start), to: minutes(b.end), title: b.title, cls: "block", label: `${clock(b.start)}–${clock(b.end)}`, tick: ["task", b.task_id] });
    }
    const column = h("div", { class: "col" + (new Date(day + "T12:00:00").getDay() === 0 ? " sunday" : ""), style: `height:${height}px` });
    for (const item of withLanes(items)) {
      const from = Math.max(item.from, top), to = Math.min(item.to, bottom);
      if (to <= from) continue;
      const width = 100 / item.lanes;
      column.append(h("div", { class: "ev " + item.cls, title: `${item.label} ${item.title}`,
        style: `top:${(from - top) / 60 * HOUR_PX}px;height:${Math.max((to - from) / 60 * HOUR_PX - 2, 20)}px;left:calc(${item.lane * width}% + 2px);width:calc(${width}% - 4px)` },
        h("b", {}, item.title), h("span", { class: "t" }, item.label),
        item.tick && tickButton(item.tick[0], item.tick[1], item.title)));
    }
    if (day === state.today) {
      const now = minutes(state.now);
      if (now > top && now < bottom) column.append(h("div", { class: "nowline", style: `top:${(now - top) / 60 * HOUR_PX}px` }));
    }
    cells.push(column);
  }
  week.replaceChildren(...cells);
}

// --- Settings ------------------------------------------------------------------

const SOURCE_NAMES = { notion: "Notion", calendar: "Google Calendar", gmail: "Gmail" };

function renderSources() {
  $("#sources").replaceChildren(...Object.entries(SOURCE_NAMES).map(([key, name]) => {
    const source = state.sources[key];
    const dot = source.ok === true ? "" : source.ok === false ? " bad" : " off";
    const text = source.ok === true ? `ok · aggiornato alle ${clock(source.at)}:${source.at.slice(17, 19)}`
      : source.ok === false ? `errore alle ${clock(source.at)}: ${source.error}` : (source.error || "mai aggiornato");
    return h("div", { class: "item" },
      h("div", { class: "body" }, h("div", { class: "title" }, h("span", { class: "dot" + dot }), name), h("div", { class: "meta" }, text)),
      h("button", { class: "btn ghost small", disabled: key === "gmail", onclick: () => refresh(key) }, "Aggiorna"));
  }));
  $("#hidden").replaceChildren(...(state.hidden_events.length ? state.hidden_events.map((entry) => h("div", { class: "item" },
    h("div", { class: "body" }, h("div", { class: "title" }, entry.title),
      h("div", { class: "meta" }, `${dateIt(dayOf(entry.start))} ${clock(entry.start)} · ${entry.calendar}`)),
    h("button", { class: "btn ghost small", onclick: async () => { await api("/api/unhide", { method: "POST", json: { key: entry.key } }); poll(); } }, "Ripristina")))
    : [h("div", { class: "empty" }, "Nessun evento nascosto.")]));
}

async function refresh(source) {
  try { state = await api("/api/refresh", { method: "POST", json: { source } }); render(); toast("Aggiornato."); }
  catch (failure) { toast(failure.message, { bad: true }); }
}

// The form is filled once (and after a save), not at every poll, so the
// polling never overwrites what is being typed.
async function loadSettings() {
  const settings = await api("/api/settings");
  $("#context").value = settings.context;
  if (settings.cycle) {
    $("#cycle-start").value = settings.cycle.start;
    $("#cycle-length").value = settings.cycle.cycle_length;
    $("#period-length").value = settings.cycle.period_length;
    $("#cycle-confirmed").checked = settings.cycle.confirmed;
  }
  const names = [...new Set([...(state ? state.calendars : []), ...settings.tickable_calendars])].sort();
  const chosen = new Set(settings.tickable_calendars.map((n) => n.toLowerCase()));
  $("#tickable").replaceChildren(...(names.length ? names.map((name) => h("label", { class: "check" },
    h("input", { type: "checkbox", value: name, checked: chosen.has(name.toLowerCase()) ? "" : false }), name))
    : [h("div", { class: "empty" }, "Nessun calendario letto finora.")]));
}

async function saveSettings() {
  const start = $("#cycle-start").value;
  const body = {
    context: $("#context").value,
    tickable_calendars: [...document.querySelectorAll("#tickable input:checked")].map((i) => i.value),
    cycle: start ? { start, cycle_length: Number($("#cycle-length").value), period_length: Number($("#period-length").value), confirmed: $("#cycle-confirmed").checked } : null,
  };
  try {
    await api("/api/settings", { method: "PUT", json: body });
    $("#save-note").textContent = "Salvato. La priorità si ricalcola al prossimo aggiornamento.";
    await poll();
  } catch (failure) {
    $("#save-note").textContent = "";
    toast(`Non salvato: ${failure.message === "errore 422" ? "controlla le durate del ciclo (20–45 e 2–10 giorni)" : failure.message}`, { bad: true, ms: 7000 });
  }
}

async function cycleStarted() {
  try { await api("/api/cycle/started", { method: "POST" }); await poll(); await loadSettings(); toast("Segnato: iniziato oggi."); }
  catch (failure) { toast(failure.message, { bad: true }); }
}

// --- drawing everything --------------------------------------------------------

function render() {
  if (!state) return;
  const bad = Object.entries(state.sources).filter(([key, s]) => key !== "gmail" && s.ok === false).map(([key]) => SOURCE_NAMES[key]);
  const fresh = $("#fresh");
  fresh.className = "fresh" + (bad.length ? " bad" : "");
  const at = (s) => (s.at ? clock(s.at) + ":" + s.at.slice(17, 19) : "mai");
  fresh.replaceChildren(`aggiornato alle ${state.now.slice(11, 19)}`, h("br"),
    bad.length ? ` · errore: ${bad.join(", ")}` : ` · Notion ${at(state.sources.notion)} · Calendar ${at(state.sources.calendar)}`);
  renderHome();
  renderWeek();
  renderSources();
}

function route() {
  const page = ["home", "calendario", "meal", "impostazioni"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  for (const section of document.querySelectorAll(".page")) section.hidden = section.id !== "page-" + page;
  for (const link of document.querySelectorAll(".nav a")) {
    link.classList.toggle("on", link.dataset.page === page);
    if (link.dataset.page === page) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  }
  if (page === "impostazioni") loadSettings().catch((failure) => toast(failure.message, { bad: true }));
  window.scrollTo(0, 0);
}

// --- chat ----------------------------------------------------------------------

const history = [];   // {role, content}: sent back to the server at every turn
let speak = localStorage.getItem("dani-speak") === "1";

function addMessage(role, text) {
  const node = h("div", { class: "msg " + role }, text);
  $("#messages").append(node);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  return node;
}

function sayAloud(text) {
  if (!speak || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "it-IT";
  speechSynthesis.speak(utterance);
}

async function send(text) {
  text = text.trim();
  if (!text) return;
  addMessage("user", text);
  const waiting = addMessage("note", "Dani sta pensando…");
  try {
    const answer = await api("/api/chat", { method: "POST", json: { message: text, history } });
    history.push({ role: "user", content: text }, { role: "assistant", content: answer.reply });
    waiting.remove();
    addMessage("assistant", answer.reply);
    sayAloud(answer.reply);
  } catch (failure) {
    waiting.remove();
    addMessage("note", `Dani non ha risposto: ${failure.message}`);
  }
}

// Voice in: Whisper through the server when it is set up, otherwise the
// browser's own dictation. Both end by sending the text like a typed message.
let recorder = null, recognition = null;

async function toggleMic() {
  const mic = $("#mic");
  if (recorder) { recorder.stop(); return; }
  if (recognition) { recognition.stop(); return; }
  if (state && state.chat.whisper && navigator.mediaDevices && window.MediaRecorder) {
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
    catch (_) { addMessage("note", "Microfono non disponibile (serve il permesso, e https fuori da questo Mac)."); return; }
    const chunks = [];
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (event) => chunks.push(event.data);
    recorder.onstop = async () => {
      const type = recorder.mimeType || "audio/webm";
      recorder = null; mic.classList.remove("rec");
      stream.getTracks().forEach((track) => track.stop());
      const note = addMessage("note", "Trascrivo…");
      try {
        const result = await api("/api/transcribe", { method: "POST", headers: { "Content-Type": type }, body: new Blob(chunks, { type }) });
        note.remove(); send(result.text);
      } catch (failure) { note.textContent = `Non ho capito l'audio: ${failure.message}`; }
    };
    recorder.start(); mic.classList.add("rec");
    return;
  }
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) { addMessage("note", "Questo browser non ha la dettatura. Usa Chrome o Safari, oppure collega Whisper."); return; }
  recognition = new Recognition();
  recognition.lang = "it-IT";
  recognition.onresult = (event) => send(event.results[0][0].transcript);
  recognition.onerror = (event) => addMessage("note", `Dettatura non riuscita (${event.error}).`);
  recognition.onend = () => { recognition = null; mic.classList.remove("rec"); };
  recognition.start(); mic.classList.add("rec");
}

function setupChat() {
  const panel = $("#chat"), open = $("#chat-open");
  open.addEventListener("click", () => {
    panel.hidden = false; open.hidden = true; $("#chat-input").focus();
    if (!$("#messages").children.length) addMessage("assistant", "Ciao Giulia! Chiedimi della tua giornata o della settimana. Da qui non modifico nulla senza il tuo sì.");
  });
  $("#chat-close").addEventListener("click", () => { panel.hidden = true; open.hidden = false; speechSynthesis && speechSynthesis.cancel(); });
  $("#chat-form").addEventListener("submit", (event) => { event.preventDefault(); const input = $("#chat-input"); send(input.value); input.value = ""; });
  $("#mic").addEventListener("click", toggleMic);
  const speakButton = $("#speak");
  speakButton.setAttribute("aria-pressed", String(speak));
  speakButton.addEventListener("click", () => {
    speak = !speak; localStorage.setItem("dani-speak", speak ? "1" : "0");
    speakButton.setAttribute("aria-pressed", String(speak));
    if (!speak && "speechSynthesis" in window) speechSynthesis.cancel();
  });
}

// --- start -----------------------------------------------------------------------

window.addEventListener("hashchange", route);
$("#save").addEventListener("click", saveSettings);
$("#refresh-all").addEventListener("click", () => refresh("all"));
$("#cycle-started").addEventListener("click", cycleStarted);
setupChat();
poll().then(route);
setInterval(poll, POLL_MS);
