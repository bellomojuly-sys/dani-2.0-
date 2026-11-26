// Dani dashboard: one page that asks the server for the state every few
// seconds and redraws. No framework. Every text from outside is put in the
// page with textContent (through h()), never as HTML.

const POLL_MS = 5000;        // how often the page asks the server
const UNDO_MS = 5000;        // the "Annulla" seconds before a tick is written
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
  const what = kind === "task" ? "Notion → Done"
    : (state.calendar_write && state.calendar_write.delete ? "cancellato da Google Calendar" : "nascosto, da cancellare dal calendario");
  toast(`Fatto: ${title} (${what})`, {
    action: "Annulla", ms: UNDO_MS,
    onAction: () => { clearTimeout(timer); pending.delete(id); render(); },
  });
  render();
}

function tickButton(kind, id, title) {
  // stopPropagation: the element around the button opens the chat on click.
  return h("button", { class: "tick", "aria-label": `Segna come fatto: ${title}`, title: "Fatto",
    onclick: (event) => { event.stopPropagation(); tick(kind, id, title); } }, "✓");
}

// --- asking Dani about one event or block ------------------------------------

// Clicking an event or a planner block opens the chat with its reference
// already written, so she only adds what she wants ("riprogrammalo",
// "questo blocco mi serve libero"). Nothing is sent and nothing is written:
// a move still goes model → proposal → her Conferma (propose.py).

function whenPhrase(item) {
  return item.all_day ? dateIt(dayOf(item.start)) : `${dateIt(dayOf(item.start))} ${clock(item.start)}–${clock(item.end)}`;
}

function prefillChat(text) {
  openChat();
  const input = $("#chat-input");
  input.value = text;
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}

function askAboutEvent(event) {
  // The chat numbers the events exactly as /api/state lists them (e1, e2, …).
  const index = state.events.findIndex((e) => e.key === event.key);
  const ref = index >= 0 ? `${"e" + (index + 1)} ` : "";
  prefillChat(`Sull'evento ${ref}«${event.title}» (${whenPhrase(event)}): `);
}

function askAboutBlock(block) {
  prefillChat(`Sul blocco di studio «${block.title}» (${whenPhrase(block)}): `);
}

// --- accepting and rejecting planner blocks (D2-052) -------------------------

// Accept asks the server for a preview (nothing is written) and shows it in
// the chat with Conferma / Rifiuta. Reject hides the block and tells the
// planner not to propose it again, with 5 s of Annulla.

async function acceptBlock(block) {
  openChat();
  if (!state.calendar_write.create_block) {
    addMessage("note", "Il calendario studio non è collegato in scrittura: non posso creare il blocco.");
    return;
  }
  try {
    const answer = await api("/api/block", { method: "POST", json: { task_id: block.task_id, start: block.start, end: block.end } });
    addMessage("assistant", answer.reply);
    addBlockProposal(answer.proposal);
  } catch (failure) {
    addMessage("note", `Non posso proporre il blocco: ${failure.message}`);
  }
}

async function rejectBlock(block) {
  try {
    await api("/api/block/reject", { method: "POST", json: { task_id: block.task_id } });
    toast(`Blocco «${block.title}» rifiutato: non lo propongo più.`, {
      action: "Annulla", ms: UNDO_MS,
      onAction: async () => { await api("/api/block/restore", { method: "POST", json: { task_id: block.task_id } }).catch(() => {}); poll(); },
    });
    poll();
  } catch (failure) {
    toast(`Non rifiutato: ${failure.message}`, { bad: true });
  }
}

function blockButtons(block) {
  const stop = (fn) => (event) => { event.stopPropagation(); fn(block); };
  return h("div", { class: "row" },
    h("button", { class: "btn small", title: "Metti questo blocco nel calendario studio", onclick: stop(acceptBlock) }, "Accetta"),
    h("button", { class: "btn ghost small", title: "Non proporre più questo blocco", onclick: stop(rejectBlock) }, "Rifiuta"));
}

const ASK_HINT = "Clicca per parlarne con Dani";

// --- Home --------------------------------------------------------------------

function renderMail() {
  const mail = state.mail || { on: false, messages: [] };
  const source = state.sources.gmail || {};
  if (!mail.on) {
    $("#mail-note").textContent = "";
    $("#home-mail").replaceChildren(h("p", { class: "muted" }, h("span", { class: "dot off" }), "Gmail non collegato."));
    return;
  }
  if (source.ok === false) {
    $("#mail-note").textContent = "";
    $("#home-mail").replaceChildren(h("p", { class: "muted" }, h("span", { class: "dot bad" }), `Gmail non letto: ${source.error}`));
    return;
  }
  const people = mail.messages.filter((m) => !m.newsletter);
  const newsletters = mail.messages.length - people.length;
  $("#mail-note").textContent = `ultime 24 ore${newsletters ? ` · ${newsletters} newsletter` : ""}`;
  $("#home-mail").replaceChildren(...(people.length ? people.slice(0, 6).map((m) => h("div", { class: "item" },
    h("div", { class: "when" }, m.date ? clock(m.date) : ""),
    h("div", { class: "body" }, h("div", { class: "title" }, m.subject),
      h("div", { class: "meta" }, m.from_name, " ", h("span", { class: "chip" }, m.box === "scuola" ? "scuola" : "gmail")))))
    : [h("div", { class: "empty" }, "Nessuna mail da persone nelle ultime 24 ore.")]));
}

function renderHome() {
  $("#home-date").textContent = dateIt(state.today);
  renderMail();

  const today = state.today;
  const rows = [];
  for (const event of state.events) {
    if (dayOf(event.start) !== today || gone(event.key)) continue;
    rows.push({ sort: event.all_day ? -1 : minutes(event.start), node: h("div", { class: "item ask", title: ASK_HINT, onclick: () => askAboutEvent(event) },
      h("div", { class: "when" }, event.all_day ? "tutto il giorno" : `${clock(event.start)}–${clock(event.end)}`),
      h("div", { class: "body" }, h("div", { class: "title" }, event.title),
        h("div", { class: "meta" }, h("span", { class: "chip " + calendarClass(event.calendar) }, event.calendar))),
      event.tickable ? tickButton("event", event.key, event.title) : h("span", { class: "notick" })) });
  }
  for (const block of state.blocks) {
    if (dayOf(block.start) !== today || gone(block.task_id)) continue;
    rows.push({ sort: minutes(block.start), node: h("div", { class: "item block ask", title: ASK_HINT, onclick: () => askAboutBlock(block) },
      h("div", { class: "when" }, `${clock(block.start)}–${clock(block.end)}`),
      h("div", { class: "body" }, h("div", { class: "title" }, block.title), h("div", { class: "meta" }, "blocco proposto dal planner"), blockButtons(block)),
      tickButton("task", block.task_id, block.title)) });
  }
  rows.sort((a, b) => a.sort - b.sort);
  $("#home-events").replaceChildren(...(rows.length ? rows.map((r) => r.node) : [h("div", { class: "empty" }, "Niente in calendario oggi.")]));

  $("#priority-note").textContent = state.priority.ok ? "ordine verificato dall'AI" : `ordine per ${state.priority.reason}`;
  const reorder = $("#reorder");
  reorder.hidden = !state.chat.text;
  reorder.onclick = async () => {
    reorder.disabled = true;
    try { const r = await api("/api/priority", { method: "POST" }); toast(r.ok ? "Riordinato da Dani." : `Non riordinato: ${r.reason}`); poll(); }
    catch (failure) { toast(failure.message, { bad: true }); }
    reorder.disabled = false;
  };
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

// --- Settings ------------------------------------------------------------------

const SOURCE_NAMES = { notion: "Notion", calendar: "Google Calendar", gmail: "Gmail" };

function renderLifeStatus() {
  const life = state.life_context || { on: false };
  $("#life-status").textContent = !life.on
    ? "La pagina Notion \u201cDani \u2014 chi sono e come pianifico\u201d non \u00e8 collegata (manca NOTION_CONTEXT_PAGE_ID)."
    : life.error && !life.chars ? `La pagina Notion del contesto non si legge: ${life.error}`
    : `Il contesto principale \u00e8 la tua pagina Notion \u201cDani \u2014 chi sono e come pianifico\u201d (${life.chars} caratteri letti): correggila l\u00ec.`;
}

function renderSources() {
  renderLifeStatus();
  $("#sources").replaceChildren(...Object.entries(SOURCE_NAMES).map(([key, name]) => {
    const source = state.sources[key];
    const dot = source.ok === true ? "" : source.ok === false ? " bad" : " off";
    const text = source.ok === true ? `ok · aggiornato alle ${clock(source.at)}:${source.at.slice(17, 19)}`
      : source.ok === false ? `errore alle ${clock(source.at)}: ${source.error}` : (source.error || "mai aggiornato");
    return h("div", { class: "item" },
      h("div", { class: "body" }, h("div", { class: "title" }, h("span", { class: "dot" + dot }), name), h("div", { class: "meta" }, text)),
      h("button", { class: "btn ghost small", disabled: key === "gmail" && !(state.mail && state.mail.on), onclick: () => refresh(key) }, "Aggiorna"));
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
// --- morning briefing preview (D2-061) ------------------------------------------

async function loadBriefing() {
  const note = await api("/api/briefing");
  $("#briefing-status").textContent = note.channel
    ? "Arriva sul telefono ogni mattina (ntfy). Questa è l'anteprima di oggi."
    : "Nessun canale collegato (manca NTFY_TOPIC): per ora lo vedi solo qui.";
  $("#briefing-text").textContent = `${note.title}\n\n${note.text}`;
  const button = $("#briefing-send");
  button.hidden = !note.channel;
  button.onclick = async () => {
    button.disabled = true;
    try {
      await api("/api/briefing/send?force=true", { method: "POST" });
      toast("Briefing inviato al telefono.");
    } catch (failure) { toast(`Non inviato: ${failure.message}`, { bad: true }); }
    button.disabled = false;
  };
}

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
    const saved = await api("/api/settings", { method: "PUT", json: body });
    $("#save-note").textContent = saved.priority_recalculated
      ? "Salvato. Priorità e blocchi ricalcolati."
      : "Salvato, ma il modello non risponde: la priorità si ricalcola al prossimo aggiornamento.";
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
    bad.length ? ` · errore: ${bad.join(", ")}` : ` · Notion ${at(state.sources.notion)} · Calendar ${at(state.sources.calendar)}`,
    ` · versione ${state.version || "?"}`);
  renderHome();
  renderCalendar();  // calendar.js (D2-072)
  renderSources();
}

// --- the morning call (D2-066): a tap on the briefing opens #buongiorno ----------

async function morningCall() {
  window.history.replaceState(null, "", "#home");
  openChat();
  let note;
  try { note = await api("/api/briefing"); } catch (failure) { addMessage("note", `Briefing non disponibile: ${failure.message}`); return; }
  const text = note.text;
  addMessage("assistant", `${note.title}\n\n${text}`);
  const play = h("button", { class: "btn small", onclick: () => {
    speechSynthesis.cancel();
    const voice = new SpeechSynthesisUtterance(text.replace(/•/g, ""));
    voice.lang = "it-IT";
    speechSynthesis.speak(voice);
  } }, "\u25B6 Ascolta Dani");
  const row = h("div", { class: "msg note" }, play);
  $("#messages").append(row);
  if ("speechSynthesis" in window) {
    try { play.click(); } catch (failure) { /* the browser waits for her tap */ }
  } else { play.remove(); }
  $("#chat-input").placeholder = "Come stai, July?";
}

function route() {
  if (location.hash === "#buongiorno") { morningCall(); }
  const page = ["home", "calendario", "meal", "consumi", "impostazioni"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  for (const section of document.querySelectorAll(".page")) section.hidden = section.id !== "page-" + page;
  for (const link of document.querySelectorAll(".nav a")) {
    link.classList.toggle("on", link.dataset.page === page);
    if (link.dataset.page === page) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  }
  if (page === "impostazioni") loadSettings().catch((failure) => toast(failure.message, { bad: true }));
  if (page === "impostazioni") loadBriefing().catch(() => {});
  if (page === "home") { loadMood(); loadFocus(); loadForecast(); }
  if (page === "calendario" && cal.view) { cal.scrolled = false; requestAnimationFrame(drawCalendar); }
  if (page === "consumi") loadUsage().catch((failure) => toast(failure.message, { bad: true }));
  window.scrollTo(0, 0);
}

// --- forecasts (D2-065) --------------------------------------------------------------

async function loadForecast() {
  let data;
  try { data = await api("/api/forecast"); } catch (failure) { return; }
  const card = $("#forecast-card");
  card.hidden = !data.rows.length && !data.error;
  if (card.hidden) return;
  const tone = { "in linea": "ok", "stretta": "warn", "a rischio": "bad", "scaduta": "bad" };
  $("#home-forecast").replaceChildren(...(data.error ? [h("p", { class: "muted" }, `Previsioni non disponibili: ${data.error}`)] : []),
    ...data.lines.map((line, n) => h("p", { class: "forecast " + (tone[data.rows[n].status] || "") }, line)));
}

// --- the mood diary (D2-064) ------------------------------------------------------

const ENERGY = ["", "a terra", "stanca", "così così", "bene", "al massimo"];

function renderMood(diary) {
  $("#mood-card").hidden = !diary.enabled;
  if (!diary.enabled) return;
  const box = $("#home-mood");
  if (diary.mood) {
    const m = diary.mood;
    box.replaceChildren(h("p", {}, `Oggi: energia ${m.energy}/5 (${ENERGY[m.energy]})` +
      (m.sleep != null ? ` · ${m.sleep} ore di sonno` : "") + (m.note ? ` · \u201c${m.note}\u201d` : "")),
      h("button", { class: "btn ghost small", onclick: () => askMood(diary) }, "Cambia"));
    return;
  }
  askMood(diary);
}

function askMood(diary) {
  let energy = diary.mood ? diary.mood.energy : 0;
  const buttons = [1, 2, 3, 4, 5].map((n) => h("button", { class: "btn ghost small energy", "data-n": n,
    onclick: () => { energy = n; for (const b of buttons) b.classList.toggle("on", Number(b.dataset.n) === n); } },
    `${n} · ${ENERGY[n]}`));
  for (const b of buttons) b.classList.toggle("on", Number(b.dataset.n) === energy);
  const sleep = h("input", { type: "number", min: "0", max: "16", step: "0.5", placeholder: "ore di sonno" });
  const note = h("input", { type: "text", maxlength: "500", placeholder: "in due parole (facoltativo)" });
  if (diary.mood) { sleep.value = diary.mood.sleep ?? ""; note.value = diary.mood.note || ""; }
  const status = h("span", { class: "meta" });
  $("#home-mood").replaceChildren(h("div", { class: "row" }, buttons), h("div", { class: "row" }, sleep, note),
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: async () => {
      if (!energy) { status.textContent = "Scegli un numero da 1 a 5."; return; }
      try {
        renderMood(await api("/api/mood", { method: "PUT", json: {
          energy, sleep: sleep.value === "" ? null : Number(sleep.value), note: note.value } }));
        toast("Segnato nel diario.");
      } catch (failure) { status.textContent = `Non salvato: ${failure.message}`; }
    } }, "Salva"), status));
}

async function loadMood() {
  try { renderMood(await api("/api/mood")); } catch (failure) { /* the card stays hidden */ }
}

// --- the week's focus and the Sunday check-in (D2-060) --------------------------

function weekLabel(monday) {
  return `settimana del ${dateIt(monday)}`;
}

function planFromFocus(focus) {
  openChat();
  send(`Proponimi la ${focus.ask_week === focus.next_week ? "prossima settimana" : "settimana"} partendo dal mio focus: ` +
    `${focus.ask_week === focus.next_week ? focus.next_focus : focus.this_focus}`);
}

function renderFocus(focus) {
  const card = $("#focus-card");
  card.hidden = !focus.enabled;
  if (!focus.enabled) return;
  const box = $("#home-focus");
  const shown = [];
  if (focus.this_focus) shown.push(h("p", {}, h("b", {}, "Questa settimana: "), focus.this_focus));
  if (focus.next_focus) shown.push(h("p", {}, h("b", {}, "Prossima settimana: "), focus.next_focus));
  if (!focus.ask) {
    box.replaceChildren(...shown, h("div", { class: "row" },
      h("button", { class: "btn small", onclick: () => planFromFocus(focus) }, "Proponimi la settimana"),
      h("button", { class: "btn ghost small", onclick: () => askFocus(focus, true) }, "Cambia il focus")));
    return;
  }
  askFocus(focus, false, shown);
}

function askFocus(focus, editing, shown = []) {
  const week = editing ? (new Date().getDay() === 0 ? focus.next_week : focus.this_week) : focus.ask_week;
  const current = week === focus.next_week ? focus.next_focus : focus.this_focus;
  const question = editing ? `Il focus della ${weekLabel(week)}` : focus.question;
  const field = h("textarea", { rows: "3", placeholder: "Es. chiudere AMX-08, due candidature, 3 ore di Python" });
  field.value = current || "";
  const note = h("span", { class: "meta" });
  $("#home-focus").replaceChildren(...shown, h("p", { class: "question" }, question), field,
    h("div", { class: "row" }, h("button", { class: "btn small", onclick: async () => {
      note.textContent = "Salvo…";
      try {
        const saved = await api("/api/focus", { method: "PUT", json: { week, text: field.value } });
        renderFocus(saved);
        toast("Focus salvato.");
      } catch (failure) { note.textContent = `Non salvato: ${failure.message}`; }
    } }, "Salva"), note));
}

async function loadFocus() {
  try { renderFocus(await api("/api/focus")); } catch (failure) { /* the card stays hidden */ }
}

// --- token monitoring (D2-057) -------------------------------------------------

const tokens = (n) => n.toLocaleString("it-IT");

function usageTile(total) {
  return [h("div", { class: "big" }, tokens(total.input + total.output)),
    h("div", { class: "split" }, `entrata ${tokens(total.input)} · uscita ${tokens(total.output)} · ${total.calls} chiamate`)];
}

function usageTable(head, rows) {
  return h("table", { class: "usage-table" },
    h("thead", {}, h("tr", {}, head.map((cell) => h("th", {}, cell)))),
    h("tbody", {}, rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell))))));
}

async function loadUsage() {
  const usage = await api("/api/usage");
  $("#usage-note").textContent = usage.enabled
    ? "Ogni chiamata al modello conta i token di entrata (il prompt) e di uscita (la risposta). Salvati in Notion, database \"Dani — consumo token\"."
    : "Il conteggio dei token non è attivo su questo server.";
  if (!usage.enabled) return;
  $("#usage-today").replaceChildren(...usageTile(usage.today));
  $("#usage-week").replaceChildren(...usageTile(usage.week));
  $("#usage-month").replaceChildren(...usageTile(usage.month));
  // 30 bars, oldest left; a day without calls is an empty slot, not a missing one.
  const byDay = Object.fromEntries(usage.days.map((day) => [day.day, day]));
  const today = new Date(state ? state.now.slice(0, 10) + "T12:00:00" : Date.now());
  const days = [...Array(30)].map((_, n) => {
    const d = new Date(today); d.setDate(d.getDate() - 29 + n);
    const key = d.toISOString().slice(0, 10);
    return byDay[key] || { day: key, input: 0, output: 0, calls: 0 };
  });
  const top = Math.max(1, ...days.map((d) => d.input + d.output));
  $("#usage-chart").replaceChildren(...days.map((d, n) => {
    const total = d.input + d.output;
    const edge = n < 8 ? " start" : n > 21 ? " end" : "";  // keep the tooltip inside the card
    const bar = h("div", { class: "bar" + edge, tabindex: "0", style: `height:${total ? Math.max(2, (total / top) * 100) : 0}%` },
      h("span", { class: "tip" }, `${dateIt(d.day)}: ${tokens(total)} token (entrata ${tokens(d.input)}, uscita ${tokens(d.output)})`));
    bar.setAttribute("aria-label", `${dateIt(d.day)}: ${tokens(total)} token`);
    return bar;
  }));
  $("#usage-chart").after(h("div", { class: "usage-axis" }, h("span", {}, dateIt(days[0].day)), h("span", {}, "oggi")));
  for (const old of document.querySelectorAll(".usage-axis + .usage-axis")) old.remove();
  $("#usage-days").replaceChildren(usage.days.length
    ? usageTable(["Giorno", "Entrata", "Uscita", "Chiamate"], usage.days.map((d) => [dateIt(d.day), tokens(d.input), tokens(d.output), d.calls]))
    : h("p", { class: "muted" }, "Nessuna chiamata negli ultimi 30 giorni."));
  const kinds = Object.entries(usage.by_kind);
  $("#usage-kinds").replaceChildren(kinds.length
    ? usageTable(["Tipo · modello", "Entrata", "Uscita", "Chiamate"], kinds.map(([kind, t]) => [kind, tokens(t.input), tokens(t.output), t.calls]))
    : h("p", { class: "muted" }, "—"));
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

// D2-056: one short line per read, so she sees where an answer comes from.
function describeRead(read) {
  const a = read.arguments || {};
  const day = (value) => (/^\d{4}-\d\d-\d\d$/.test(value || "") ? dateIt(value) : String(value));
  if (read.tool === "read_calendar") return `calendario ${day(a.start)}–${day(a.end)}`;
  if (read.tool === "read_tasks") return "task" + (a.area ? ` ${a.area}` : "") + (a.contains ? ` “${a.contains}”` : "");
  if (read.tool === "read_projects") return "progetti e obiettivi";
  if (read.tool === "read_page") return `pagina “${a.name}”`;
  return read.tool;
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
    if (answer.reads && answer.reads.length) addMessage("note", "Ho letto: " + answer.reads.map(describeRead).join(" · "));
    addMessage("assistant", answer.reply);
    sayAloud(answer.reply);
    if (answer.proposal) ({ task: addTaskProposal, delete: addDeleteProposal }[answer.proposal.kind] || addProposal)(answer.proposal);
    if (answer.plan) addPlanProposal(answer.plan);  // a whole plan, one yes (D2-071)
  } catch (failure) {
    waiting.remove();
    addMessage("note", `Dani non ha risposto: ${failure.message}`);
  }
}

// A move proposed by Dani: nothing is written until Conferma is pressed.
function addProposal(proposal) {
  const when = (a, b) => `${dateIt(dayOf(a))} ${clock(a)}–${clock(b)}`;
  const buttons = h("div", { class: "row" });
  const card = h("div", { class: "msg proposal" },
    h("b", {}, proposal.title), h("div", {}, `da ${when(proposal.old_start, proposal.old_end)}`),
    h("div", {}, `a ${when(proposal.new_start, proposal.new_end)}`),
    proposal.warnings.map((warning) => h("div", { class: "warn" }, `⚠ ${warning}`)), buttons);
  const close = (text) => { buttons.replaceChildren(h("span", { class: "meta" }, text)); };
  buttons.append(
    h("button", { class: "btn small", onclick: async () => {
      close("Scrivo sul calendario…");
      try {
        const done = await api("/api/confirm", { method: "POST", json: { id: proposal.id } });
        close(done.read_back ? "Fatto: spostato, riletto dal calendario." : "Scritto, ma la rilettura non lo trova ancora.");
        history.push({ role: "user", content: "Confermo." }, { role: "assistant", content: "Spostato." });
        poll();
      } catch (failure) { close(`Non spostato: ${failure.message}`); }
    } }, "Conferma"),
    h("button", { class: "btn ghost small", onclick: async () => {
      await api("/api/reject", { method: "POST", json: { id: proposal.id } }).catch(() => {});
      close("Rifiutata: non ho cambiato nulla.");
      history.push({ role: "user", content: "No, non spostarlo." });
    } }, "Rifiuta"));
  $("#messages").append(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

// A new Notion task proposed by Dani: nothing is written until Conferma is pressed.
function addTaskProposal(proposal) {
  const details = [];
  if (proposal.area) details.push(`area ${proposal.area}`);
  if (proposal.deadline) details.push(`scadenza ${dateIt(proposal.deadline)}`);
  if (proposal.duration_minutes) details.push(`${proposal.duration_minutes} min`);
  const buttons = h("div", { class: "row" });
  const card = h("div", { class: "msg proposal" },
    h("b", {}, proposal.title),
    h("div", {}, `nuovo task in Notion${details.length ? " · " + details.join(" · ") : ""}`),
    proposal.warnings.map((warning) => h("div", { class: "warn" }, `⚠ ${warning}`)), buttons);
  const close = (text) => { buttons.replaceChildren(h("span", { class: "meta" }, text)); };
  buttons.append(
    h("button", { class: "btn small", onclick: async () => {
      close("Scrivo su Notion…");
      try {
        const done = await api("/api/confirm", { method: "POST", json: { id: proposal.id } });
        close(done.read_back ? "Fatto: creato, riletto da Notion." : "Scritto, ma la rilettura non lo trova ancora.");
        history.push({ role: "user", content: "Confermo." }, { role: "assistant", content: "Task creato." });
        poll();
      } catch (failure) { close(`Non creato: ${failure.message}`); }
    } }, "Conferma"),
    h("button", { class: "btn ghost small", onclick: async () => {
      await api("/api/reject", { method: "POST", json: { id: proposal.id } }).catch(() => {});
      close("Rifiutata: non ho scritto nulla.");
    } }, "Rifiuta"));
  $("#messages").append(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

// A study block she accepted: nothing is written until Conferma is pressed.
function addBlockProposal(proposal) {
  const buttons = h("div", { class: "row" });
  const card = h("div", { class: "msg proposal" },
    h("b", {}, proposal.title),
    h("div", {}, `${dateIt(dayOf(proposal.start))} ${clock(proposal.start)}–${clock(proposal.end)} · calendario studio`),
    proposal.why ? h("div", { class: "meta" }, proposal.why) : null,
    proposal.warnings.map((warning) => h("div", { class: "warn" }, `⚠ ${warning}`)), buttons);
  const close = (text) => { buttons.replaceChildren(h("span", { class: "meta" }, text)); };
  buttons.append(
    h("button", { class: "btn small", onclick: async () => {
      close("Scrivo sul calendario…");
      try {
        const done = await api("/api/confirm", { method: "POST", json: { id: proposal.id } });
        close(done.read_back ? "Fatto: creato, riletto dal calendario." : "Scritto, ma la rilettura non lo trova ancora.");
        poll();
      } catch (failure) { close(`Non creato: ${failure.message}`); }
    } }, "Conferma"),
    h("button", { class: "btn ghost small", onclick: async () => {
      await api("/api/reject", { method: "POST", json: { id: proposal.id } }).catch(() => {});
      close("Rifiutata: non ho scritto nulla.");
    } }, "Rifiuta"));
  $("#messages").append(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

// Events Dani proposes to delete (D2-073): the list is her message above;
// nothing is deleted until Cancella is pressed.
function addDeleteProposal(proposal) {
  const buttons = h("div", { class: "row" });
  const card = h("div", { class: "msg proposal" },
    h("b", {}, proposal.events.length === 1 ? "1 evento da cancellare" : `${proposal.events.length} eventi da cancellare`), buttons);
  const close = (text) => { buttons.replaceChildren(h("span", { class: "meta" }, text)); };
  buttons.append(
    h("button", { class: "btn small", onclick: async () => {
      close("Cancello dal calendario…");
      try {
        const done = await api("/api/confirm", { method: "POST", json: { id: proposal.id } });
        close(done.message);
        history.push({ role: "user", content: "Confermo." }, { role: "assistant", content: done.message });
        poll();
      } catch (failure) { close(`Non cancellato: ${failure.message}`); }
    } }, "Cancella"),
    h("button", { class: "btn ghost small", onclick: async () => {
      await api("/api/reject", { method: "POST", json: { id: proposal.id } }).catch(() => {});
      close("Annullato: non ho cancellato nulla.");
      history.push({ role: "user", content: "No, non cancellarli." });
    } }, "Annulla"));
  $("#messages").append(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

// A whole plan (D2-071): the day-by-day text is Dani's message above; here
// only the two buttons. Nothing is written until Conferma tutto is pressed.
function addPlanProposal(plan) {
  const buttons = h("div", { class: "row" });
  const card = h("div", { class: "msg proposal" },
    h("b", {}, `${plan.blocks.length} ${plan.blocks.length === 1 ? "blocco nuovo" : "blocchi nuovi"} nel calendario studio`), buttons);
  const close = (text, ...more) => { buttons.replaceChildren(h("span", { class: "meta" }, text), ...more); };
  const confirm = () => h("button", { class: "btn small", onclick: async () => {
    close("Scrivo sul calendario…");
    try {
      const done = await api("/api/confirm", { method: "POST", json: { id: plan.id } });
      close(done.message);
      history.push({ role: "user", content: "Confermo tutto." }, { role: "assistant", content: done.message });
      poll();
    } catch (failure) {
      // The blocks already created left the plan on the server: a retry creates only the rest.
      close(`Non finito: ${failure.message}.`, confirm());
    }
  } }, "Conferma tutto");
  buttons.append(confirm(),
    h("button", { class: "btn ghost small", onclick: async () => {
      await api("/api/reject", { method: "POST", json: { id: plan.id } }).catch(() => {});
      close("Dimmi cosa cambiare, a voce o per scritto: ti rimando il piano.");
      $("#chat-input").focus();
    } }, "Cambia qualcosa"));
  $("#messages").append(card);
  $("#messages").scrollTop = $("#messages").scrollHeight;
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

function openChat() {
  $("#chat").hidden = false; $("#chat-open").hidden = true; $("#chat-input").focus();
  if (!$("#messages").children.length) addMessage("assistant", "Eccomi, July. Dimmi cosa ti serve: la giornata, la settimana, un piano. Non cambio niente senza il tuo sì.");
}

function setupChat() {
  const panel = $("#chat"), open = $("#chat-open");
  open.addEventListener("click", openChat);
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
