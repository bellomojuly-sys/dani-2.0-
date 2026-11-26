// The calendar page (D2-072): laid out like Google Calendar — day, 3 days,
// week and month; her calendars in solid colours with white text; a red line
// for now; tap an event for its card, drag it to move it. A move is always a
// preview first (/api/move, the same checks as the chat) and is written only
// after Conferma. Uses the helpers of app.js (h, $, api, state, tick, …).

const GC = {
  HOUR_PX: 48,
  SNAP: 15,              // minutes: a drag lands on the quarter hour
  VIEWS: { day: 1, three: 3, week: 7, month: 42 },
  LABELS: { day: "Giorno", three: "3 giorni", week: "Settimana", month: "Mese" },
  // Her colours (D2-072, 26 Nov): pink tones that stay apart; shifts always yellow,
  // university light blue, theory study violet, every project its own colour.
  // bg = fill, fg = text on it, ink = text on white (Dani's dashed proposals). All ≥ 4.5:1.
  WORK: { label: "Lavoro", bg: "#FFD54F", fg: "#3E2E00", ink: "#3E2E00" },
  UNI: { label: "Università", bg: "#8EC9F5", fg: "#0B3050", ink: "#0B3050" },
  THEORY: { label: "Teoria", bg: "#6A4C93", fg: "#FFFFFF", ink: "#6A4C93" },
  PERSONAL: { label: "Personale", bg: "#F8BBD0", fg: "#5A1530", ink: "#5A1530" },
  OTHER: { label: "Altro", bg: "#8D6E7A", fg: "#FFFFFF", ink: "#6E525D" },
  PROJECTS: {
    amexio: { label: "AMEXIO", bg: "#6D1B3B", fg: "#FFFFFF", ink: "#6D1B3B" },
    betsy: { label: "Betsy", bg: "#F06292", fg: "#3D0A1E", ink: "#3D0A1E" },
    dani: { label: "Dani", bg: "#C2185B", fg: "#FFFFFF", ink: "#C2185B" },
  },
  // Any other project ("Nome · cosa"): one of these, always the same for the same name.
  MORE: [["#B5532B", "#FFFFFF"], ["#FFAB91", "#4A1A0A"], ["#B76E79", "#2B0A12"]],
  NOT_PROJECTS: ["lettura", "teoria", "studio", "palestra", "corso", "pausa"],
};

const cal = {
  view: null,            // "day" | "three" | "week" | "month"
  anchor: null,          // the day the view is built around (YYYY-MM-DD)
  events: [],            // /api/events for the shown range
  range: null,           // "start/days" of the events in memory
  loading: false,
  error: null,
  readAt: null,          // the calendar source time the events were read at
  scrolled: false,
};

// --- dates (always Amsterdam wall-clock strings, as the server sends them) -------

const gcDate = (day) => new Date(day + "T12:00:00Z");
function addDays(day, n) { const d = gcDate(day); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
const weekdayOf = (day) => gcDate(day).getUTCDay();
const mondayOf = (day) => addDays(day, -((weekdayOf(day) + 6) % 7));
const pad = (n) => String(n).padStart(2, "0");
const hhmm = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const offsetOf = (iso) => iso.slice(19) || "+01:00";

// Which colour an event or a block gets, from its calendar and its title.
function colorOf(calendar, title) {
  const where = (calendar || "").toLowerCase(), what = (title || "").toLowerCase();
  if (["lavoro", "eitje", "turno", "werk"].some((w) => where.includes(w)) || /\bturno\b/.test(what)) return { key: "work", ...GC.WORK };
  if (["univ", "fontys", "canvas"].some((w) => where.includes(w))) return { key: "uni", ...GC.UNI };
  for (const [name, color] of Object.entries(GC.PROJECTS)) {
    if (new RegExp(`\\b${name}\\b`).test(what)) return { key: name, ...color };
  }
  if (what.includes("teoria")) return { key: "theory", ...GC.THEORY };
  const parts = (title || "").split(/\s+[·–-]\s+|:\s*/);
  const prefix = parts.length > 1 ? parts[0].trim() : "";
  if (prefix && prefix.length <= 24 && !GC.NOT_PROJECTS.includes(prefix.toLowerCase())) {
    let hash = 0;
    for (const ch of prefix.toLowerCase()) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    const [bg, fg] = GC.MORE[hash % GC.MORE.length];
    return { key: "p:" + prefix.toLowerCase(), label: prefix, bg, fg, ink: fg === "#FFFFFF" ? bg : fg };
  }
  if (where.includes("studio")) return { key: "theory", ...GC.THEORY };
  if (where.includes("personal")) return { key: "personal", ...GC.PERSONAL };
  return { key: "other", ...GC.OTHER, label: calendar || GC.OTHER.label };
}
const paint = (c) => `--c:${c.bg};--f:${c.fg};--k:${c.ink}`;

function shownDays() {
  if (cal.view === "day") return [cal.anchor];
  if (cal.view === "three") return [0, 1, 2].map((n) => addDays(cal.anchor, n));
  if (cal.view === "week") { const monday = mondayOf(cal.anchor); return [0, 1, 2, 3, 4, 5, 6].map((n) => addDays(monday, n)); }
  const first = mondayOf(cal.anchor.slice(0, 8) + "01");
  return Array.from({ length: 42 }, (_, n) => addDays(first, n));
}

function gcTitle(days) {
  const month = (day) => MONTHS[Number(day.slice(5, 7)) - 1];
  const cap = (text) => text[0].toUpperCase() + text.slice(1);
  if (cal.view === "month") return `${cap(month(cal.anchor))} ${cal.anchor.slice(0, 4)}`;
  const first = days[0], last = days[days.length - 1];
  if (first.slice(0, 7) === last.slice(0, 7)) return `${cap(month(first))} ${first.slice(0, 4)}`;
  const short = (day) => cap(month(day).slice(0, 3));
  return first.slice(0, 4) === last.slice(0, 4)
    ? `${short(first)} – ${short(last)} ${last.slice(0, 4)}`
    : `${short(first)} ${first.slice(0, 4)} – ${short(last)} ${last.slice(0, 4)}`;
}

// --- reading the events of the shown range ----------------------------------------

async function loadRange(force = false) {
  const days = shownDays();
  const range = `${days[0]}/${days.length}`;
  if (!force && range === cal.range) return;
  cal.loading = true;
  try {
    const answer = await api(`/api/events?start=${days[0]}&days=${days.length}`);
    if (shownDays()[0] + "/" + shownDays().length !== range) return;  // she moved on meanwhile
    cal.events = answer.events;
    cal.range = range;
    cal.error = null;
  } catch (failure) {
    cal.error = failure.message;
  } finally {
    cal.loading = false;
  }
  drawCalendar();
}

// Called by app.js render() after every /api/state: reads again when the server
// read the calendar again (after a write, or every few minutes).
function renderCalendar() {
  if (!state) return;
  if (!cal.view) {
    let saved = null;
    try { saved = localStorage.getItem("dani-cal-view"); } catch (failure) { /* private mode */ }
    cal.view = GC.VIEWS[saved] ? saved : (window.innerWidth < 700 ? "three" : "week");
    cal.anchor = state.today;
  }
  const at = state.sources.calendar && state.sources.calendar.at;
  if (at !== cal.readAt) { cal.readAt = at; loadRange(true); return; }
  drawCalendar();
}

function setView(view) {
  cal.view = view;
  try { localStorage.setItem("dani-cal-view", view); } catch (failure) { /* private mode */ }
  cal.scrolled = false;
  drawCalendar();
  loadRange();
}

function step(direction) {
  const n = cal.view === "month" ? 0 : cal.view === "week" ? 7 : GC.VIEWS[cal.view];
  if (cal.view === "month") {
    const [year, month] = cal.anchor.split("-").map(Number);
    const next = new Date(Date.UTC(year, month - 1 + direction, 1));
    cal.anchor = next.toISOString().slice(0, 10);
  } else {
    cal.anchor = addDays(cal.anchor, direction * n);
  }
  drawCalendar();
  loadRange();
}

function goToday() { cal.anchor = state.today; cal.scrolled = false; drawCalendar(); loadRange(); }

// --- what is drawn: her events plus the planner's proposed blocks ------------------

function itemsOf(day) {
  const items = [];
  for (const e of cal.events) {
    if (gone(e.key) || e.all_day || e.start.slice(0, 10) !== day) continue;
    const to = e.end.slice(0, 10) === day ? minutes(e.end) : 24 * 60;
    items.push({ kind: "event", data: e, from: minutes(e.start), to, title: e.title, color: colorOf(e.calendar, e.title), movable: e.tickable });
  }
  for (const b of state.blocks || []) {
    if (gone(b.task_id) || b.start.slice(0, 10) !== day) continue;
    items.push({ kind: "block", data: b, from: minutes(b.start), to: minutes(b.end), title: b.title, color: colorOf("studio", b.title), movable: true });
  }
  return items;
}

function allDayOf(day) {
  return cal.events.filter((e) => e.all_day && !gone(e.key) && e.start.slice(0, 10) <= day && day < (e.end.slice(0, 10) > e.start.slice(0, 10) ? e.end.slice(0, 10) : addDays(e.start.slice(0, 10), 1)));
}

function drawCalendar() {
  if (!cal.view || !state) return;
  const days = shownDays();
  $("#gc-title").textContent = gcTitle(days);
  for (const button of document.querySelectorAll(".gc-views button")) {
    button.setAttribute("aria-pressed", String(button.dataset.view === cal.view));
  }
  // The legend: the colours actually on screen, by what they mean.
  const shown = new Map();
  for (const e of cal.events) { const c = colorOf(e.calendar, e.title); shown.set(c.key, c); }
  for (const b of state.blocks || []) { const c = colorOf("studio", b.title); shown.set(c.key, c); }
  $("#gc-cals").replaceChildren(...[...shown.values()].sort((a, b) => a.label.localeCompare(b.label))
    .map((c) => h("span", { class: "gc-cal" }, h("i", { style: `background:${c.bg}` }), c.label)),
    h("span", { class: "gc-cal" }, h("i", { class: "tentative" }), "proposto da Dani"),
    ...(cal.error ? [h("span", { class: "gc-err" }, `Calendario non letto: ${cal.error}`)] : []));
  const before = $("#gc-body .gc-scroll");
  const kept = before ? before.scrollTop : 0;
  $("#gc-body").replaceChildren(cal.view === "month" ? drawMonth(days) : drawGrid(days));
  const month = $("#gc-body .gc-month");
  if (month) fitHeight(month);
  const scroller = $("#gc-body .gc-scroll");
  if (!scroller) return;
  fitHeight(scroller);
  if (!cal.scrolled && scroller.clientHeight) {
    // Like Google: open on the morning, or a little before now when today is shown.
    scroller.scrollTop = Math.max(0, (days.includes(state.today) ? minutes(state.now) - 90 : 7.5 * 60) / 60 * GC.HOUR_PX);
    cal.scrolled = true;
  } else {
    scroller.scrollTop = kept;
  }
}

// The hour grid fills the screen down to the bottom bar (phone) or the window edge.
function fitHeight(node) {
  const top = node.getBoundingClientRect().top;
  if (!node.offsetParent) return;  // the page is hidden: fitted again when it opens
  let bottom = window.innerHeight - 16;
  for (const selector of [".nav", "#fresh"]) {
    const other = document.querySelector(selector);
    const box = other && other.getBoundingClientRect();
    if (box && box.top > top + 100 && box.top < bottom) bottom = box.top - 8;  // a bar at the bottom (phone)
  }
  node.style.height = `${Math.max(320, bottom - top)}px`;
}
window.addEventListener("resize", () => { const node = $("#gc-body .gc-scroll, #gc-body .gc-month"); if (node) fitHeight(node); });

function dayHead(day) {
  const today = day === state.today;
  return h("button", { class: "gc-dayhead" + (today ? " today" : ""), onclick: () => { cal.anchor = day; setView("day"); },
    "aria-label": dateIt(day) },
    h("span", { class: "gc-dow" }, WEEKDAYS[weekdayOf(day)]), h("span", { class: "gc-num" }, String(Number(day.slice(8)))));
}

function drawGrid(days) {
  const columns = `56px repeat(${days.length}, minmax(0, 1fr))`;
  const head = h("div", { class: "gc-head", style: `grid-template-columns:${columns}` }, h("div", { class: "gc-tz" }, `GMT${state.now.slice(19, 22)}`), ...days.map(dayHead));
  const allDay = h("div", { class: "gc-allday", style: `grid-template-columns:${columns}` }, h("div"),
    ...days.map((day) => h("div", { class: "gc-allday-cell" }, allDayOf(day).map((e) => h("button", {
      class: "gc-chip", style: paint(colorOf(e.calendar, e.title)), onclick: () => openCard({ kind: "event", data: e }) }, e.title)))));
  const height = 24 * GC.HOUR_PX;
  const gutter = h("div", { class: "gc-gutter", style: `height:${height}px` });
  for (let hour = 1; hour < 24; hour++) gutter.append(h("span", { style: `top:${hour * GC.HOUR_PX}px` }, `${pad(hour)}:00`));
  const body = h("div", { class: "gc-grid", style: `grid-template-columns:${columns}` }, gutter);
  days.forEach((day, index) => body.append(drawColumn(day, index, height)));
  const scroller = h("div", { class: "gc-scroll" }, body);
  swipeToStep(scroller);
  return h("div", { class: "gc-week" }, head, allDay, scroller);
}

// Google's layout: events that start together share the width side by side;
// an event that starts later (30 min or more) inside another is drawn on top
// of it, a little indented, so the first one keeps its full width.
function layout(items) {
  const CASCADE_MIN = 30, INDENT_PX = 14;
  items.sort((a, b) => a.from - b.from || b.to - a.to);
  for (const item of items) {
    const overlapping = items.filter((o) => o !== item && o.from < item.to && o.to > item.from);
    item.depth = overlapping.filter((o) => item.from - o.from >= CASCADE_MIN).length;
    const peers = [item, ...overlapping.filter((o) => Math.abs(o.from - item.from) < CASCADE_MIN)];
    peers.sort((a, b) => a.from - b.from || b.to - a.to);
    item.slots = peers.length;
    item.slot = peers.indexOf(item);
    item.indent = item.depth * INDENT_PX;
  }
  return items;
}

function drawColumn(day, index, height) {
  const column = h("div", { class: "gc-col", "data-day": day, "data-index": String(index), style: `height:${height}px` });
  column.addEventListener("click", (event) => {
    if (event.target !== column) return;
    const at = Math.floor(event.offsetY / GC.HOUR_PX * 60 / 30) * 30;
    prefillChat(`Nuovo evento ${dateIt(day)} alle ${hhmm(at)}: `);
  });
  for (const item of layout(itemsOf(day))) {
    const length = item.to - item.from;
    const short = length < 45;
    const time = `${hhmm(item.from)} – ${hhmm(Math.min(item.to, 24 * 60))}`;
    const node = h("div", {
      class: "gc-ev" + (item.kind === "block" ? " tentative" : "") + (short ? " short" : ""),
      role: "button", tabindex: "0", "aria-label": `${item.title}, ${dateIt(day)} ${time}`,
      style: `top:${item.from / 60 * GC.HOUR_PX}px;height:${Math.max(length / 60 * GC.HOUR_PX - 2, 18)}px;` +
        `left:calc(${item.indent}px + (100% - 10px - ${item.indent}px) * ${item.slot / item.slots});` +
        `width:calc((100% - 10px - ${item.indent}px) * ${1 / item.slots} - 1px);z-index:${item.depth + 1};${paint(item.color)}`,
    }, short ? h("span", { class: "gc-line" }, h("b", {}, item.title), `, ${hhmm(item.from)}`)
      : [h("b", {}, item.title), h("span", { class: "gc-time" }, time)]);
    node.addEventListener("keydown", (event) => { if (event.key === "Enter") openCard(item); });
    dragOrTap(node, item, day);
    column.append(node);
  }
  if (day === state.today) {
    column.append(h("div", { class: "gc-now", style: `top:${minutes(state.now) / 60 * GC.HOUR_PX}px` }));
  }
  return column;
}

function drawMonth(days) {
  const month = cal.anchor.slice(0, 7);
  const head = h("div", { class: "gc-mhead" }, ...["lun", "mar", "mer", "gio", "ven", "sab", "dom"].map((d) => h("div", {}, d)));
  const grid = h("div", { class: "gc-month" });
  for (const day of days) {
    const timed = cal.events.filter((e) => !e.all_day && !gone(e.key) && e.start.slice(0, 10) === day);
    const chips = [...allDayOf(day).map((e) => ({ e, all: true })), ...timed.map((e) => ({ e, all: false }))];
    const cell = h("div", { class: "gc-mcell" + (day.slice(0, 7) !== month ? " other" : "") },
      h("button", { class: "gc-mnum" + (day === state.today ? " today" : ""), onclick: () => { cal.anchor = day; setView("day"); } },
        String(Number(day.slice(8)))));
    for (const { e, all } of chips.slice(0, 3)) {
      cell.append(h("button", { class: "gc-mchip" + (all ? " all" : ""), style: paint(colorOf(e.calendar, e.title)),
        onclick: () => openCard({ kind: "event", data: e }) },
        all ? e.title : [h("i"), h("span", { class: "gc-mt" }, clock(e.start)), e.title]));
    }
    if (chips.length > 3) {
      cell.append(h("button", { class: "gc-more", onclick: () => { cal.anchor = day; setView("day"); } }, `+${chips.length - 3} altri`));
    }
    grid.append(cell);
  }
  swipeToStep(grid);
  return h("div", {}, head, grid);
}

function swipeToStep(node) {
  let start = null;
  node.addEventListener("touchstart", (event) => { start = drag.active ? null : [event.touches[0].clientX, event.touches[0].clientY]; }, { passive: true });
  node.addEventListener("touchend", (event) => {
    if (!start || drag.active) return;
    const dx = event.changedTouches[0].clientX - start[0], dy = event.changedTouches[0].clientY - start[1];
    if (Math.abs(dx) > 70 && Math.abs(dy) < 40) step(dx < 0 ? 1 : -1);
    start = null;
  });
}

// --- drag to move (a mouse drag, or a long press on the phone) -------------------

const drag = { active: false };

function dragOrTap(node, item, day) {
  let press = null;
  const cancelPress = () => { if (press && press.timer) clearTimeout(press.timer); };
  node.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    press = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, touch: event.pointerType !== "mouse", started: false, timer: null };
    if (press.touch && item.movable) {
      press.timer = setTimeout(() => { press.started = true; beginDrag(node, item, day, press); }, 350);
    }
  });
  node.addEventListener("pointermove", (event) => {
    if (!press) return;
    const moved = Math.hypot(event.clientX - press.x, event.clientY - press.y);
    if (!press.started && press.touch && moved > 8) { cancelPress(); press = null; return; }  // she is scrolling
    if (!press.started && !press.touch && item.movable && moved > 5) { press.started = true; beginDrag(node, item, day, press); }
    if (press.started) moveDrag(event);
  });
  node.addEventListener("pointerup", (event) => {
    if (!press) return;
    cancelPress();
    if (press.started) endDrag(event); else openCard(item);
    press = null;
  });
  node.addEventListener("pointercancel", () => { cancelPress(); if (press && press.started) abortDrag(); press = null; });
  node.addEventListener("touchmove", (event) => { if (drag.active) event.preventDefault(); }, { passive: false });
}

function beginDrag(node, item, day, press) {
  const rect = node.getBoundingClientRect();
  drag.active = true;
  drag.item = item;
  drag.node = node;
  drag.day = day;
  drag.length = item.to - item.from;
  drag.grab = press.y - rect.top;
  drag.columns = [...document.querySelectorAll(".gc-col")];
  drag.ghost = node.cloneNode(true);
  drag.ghost.classList.add("ghost");
  drag.ghost.style.left = "0";
  drag.ghost.style.width = "calc(100% - 12px)";
  node.classList.add("dragging");
  try { node.setPointerCapture(press.pointerId); } catch (failure) { /* not needed for touch */ }
  if (navigator.vibrate) navigator.vibrate(15);
  moveDrag({ clientX: press.x, clientY: press.y });
}

function moveDrag(event) {
  const column = drag.columns.find((c) => { const r = c.getBoundingClientRect(); return event.clientX >= r.left && event.clientX < r.right; })
    || drag.columns.find((c) => c.dataset.day === drag.day);
  const top = column.getBoundingClientRect().top;
  const raw = (event.clientY - drag.grab - top) / GC.HOUR_PX * 60;
  const from = Math.min(Math.max(0, Math.round(raw / GC.SNAP) * GC.SNAP), 24 * 60 - drag.length);
  drag.target = { day: column.dataset.day, from };
  drag.ghost.style.top = `${from / 60 * GC.HOUR_PX}px`;
  const time = drag.ghost.querySelector(".gc-time");
  if (time) time.textContent = `${hhmm(from)} – ${hhmm(from + drag.length)}`;
  if (drag.ghost.parentNode !== column) column.append(drag.ghost);
}

function abortDrag() {
  drag.active = false;
  if (drag.ghost) drag.ghost.remove();
  if (drag.node) drag.node.classList.remove("dragging");
}

function endDrag(event) {
  moveDrag(event);
  const { item, target } = drag;
  abortDrag();
  if (!target || (target.day === item.data.start.slice(0, 10) && target.from === item.from)) return;
  const offset = offsetOf(item.data.start);
  const start = `${target.day}T${hhmm(target.from)}:00${offset}`;
  const end = `${target.day}T${hhmm(target.from + drag.length)}:00${offset}`;
  previewMove(item, start, end);
}

// --- the event card (Google's popover; a bottom sheet on the phone) --------------

function closeCard() { $("#gc-sheet").hidden = true; $("#gc-sheet").replaceChildren(); }

function cardShell(item, ...content) {
  const color = colorOf(item.kind === "block" ? "studio" : item.data.calendar, item.data.title).bg;
  const sheet = $("#gc-sheet");
  sheet.replaceChildren(h("div", { class: "gc-card", role: "dialog", "aria-modal": "true", "aria-label": item.data.title },
    h("div", { class: "gc-card-actions" }, ...cardActions(item), h("button", { class: "gc-icon", "aria-label": "Chiudi", onclick: closeCard }, "✕")),
    h("div", { class: "gc-card-title" }, h("i", { style: `background:${color}` + (item.kind === "block" ? ";opacity:.45" : "") }), h("h3", {}, item.data.title)),
    ...content));
  sheet.hidden = false;
  sheet.onclick = (event) => { if (event.target === sheet) closeCard(); };
}

function whenLine(data) {
  if (data.all_day) return dateIt(data.start.slice(0, 10)) + " · tutto il giorno";
  return `${dateIt(data.start.slice(0, 10))} · ${clock(data.start)} – ${clock(data.end)}`;
}

function cardActions(item) {
  const actions = [];
  if (item.kind === "event" && item.data.tickable && !item.data.all_day) {
    actions.push(h("button", { class: "gc-icon", title: "Sposta", "aria-label": "Sposta", onclick: () => moveForm(item) }, "✎"));
  }
  if (item.kind === "event" && item.data.tickable) {
    actions.push(h("button", { class: "gc-icon", title: "Elimina", "aria-label": "Elimina", onclick: () => {
      closeCard();
      tick("event", item.data.key, item.data.title);
    } }, "🗑"));
  }
  actions.push(h("button", { class: "gc-icon", title: "Chiedi a Dani", "aria-label": "Chiedi a Dani", onclick: () => {
    closeCard();
    prefillChat(`Sull'evento «${item.data.title}» (${whenLine(item.data)}): `);
  } }, "💬"));
  return actions;
}

function openCard(item) {
  const data = item.data;
  if (item.kind === "block") {
    cardShell(item, h("p", { class: "gc-card-when" }, whenLine(data)),
      h("p", { class: "gc-card-meta" }, "Blocco proposto da Dani · calendario studio"),
      data.why ? h("p", { class: "gc-card-meta" }, data.why) : null,
      h("div", { class: "gc-card-buttons" },
        h("button", { class: "gc-btn primary", onclick: () => { closeCard(); acceptBlock(data); } }, "Accetta"),
        h("button", { class: "gc-btn", onclick: () => { closeCard(); rejectBlock(data); } }, "Rifiuta")));
    return;
  }
  cardShell(item, h("p", { class: "gc-card-when" }, whenLine(data)),
    h("p", { class: "gc-card-meta" }, `📅 ${data.calendar}`),
    data.tickable ? null : h("p", { class: "gc-card-meta" }, "Impegno fisso: da qui non si sposta e non si cancella."));
}

function moveForm(item) {
  const data = item.data;
  const day = h("input", { type: "date", value: data.start.slice(0, 10), "aria-label": "Giorno" });
  const from = h("input", { type: "time", step: "900", value: clock(data.start), "aria-label": "Inizio" });
  const to = h("input", { type: "time", step: "900", value: clock(data.end), "aria-label": "Fine" });
  cardShell(item, h("p", { class: "gc-card-when" }, `Adesso: ${whenLine(data)}`),
    h("div", { class: "gc-move" }, day, from, h("span", {}, "–"), to),
    h("div", { class: "gc-card-buttons" },
      h("button", { class: "gc-btn primary", onclick: () => {
        const offset = offsetOf(data.start);
        previewMove(item, `${day.value}T${from.value}:00${offset}`, `${day.value}T${to.value}:00${offset}`);
      } }, "Anteprima"),
      h("button", { class: "gc-btn", onclick: () => openCard(item) }, "Annulla")));
}

async function previewMove(item, start, end) {
  let answer;
  try {
    answer = item.kind === "block"
      ? await api("/api/block", { method: "POST", json: { task_id: item.data.task_id, start, end } })
      : await api("/api/move", { method: "POST", json: { key: item.data.key, start, end } });
  } catch (failure) {
    toast(`Non spostato: ${failure.message}`, { bad: true, ms: 6000 });
    drawCalendar();
    return;
  }
  const proposal = answer.proposal;
  const newStart = proposal.new_start || proposal.start, newEnd = proposal.new_end || proposal.end;
  cardShell(item,
    h("p", { class: "gc-card-when" }, `${item.kind === "block" ? "Metto" : "Sposto"} a ${dateIt(newStart.slice(0, 10))} · ${clock(newStart)} – ${clock(newEnd)}`),
    item.kind === "block" ? null : h("p", { class: "gc-card-meta" }, `Era ${whenLine(item.data)}`),
    ...proposal.warnings.map((warning) => h("p", { class: "gc-warn" }, `⚠ ${warning}`)),
    h("p", { class: "gc-card-meta" }, "Nessuna notifica agli invitati; se si ripete, solo questa volta."),
    h("div", { class: "gc-card-buttons" },
      h("button", { class: "gc-btn primary", onclick: async (event) => {
        event.target.disabled = true;
        try {
          const done = await api("/api/confirm", { method: "POST", json: { id: proposal.id } });
          closeCard();
          toast(done.read_back ? "Fatto: riletto dal calendario." : "Scritto; la rilettura non lo trova ancora.");
          await poll();
          loadRange(true);
        } catch (failure) {
          event.target.disabled = false;
          toast(`Non scritto: ${failure.message}`, { bad: true, ms: 6000 });
        }
      } }, "Conferma"),
      h("button", { class: "gc-btn", onclick: async () => {
        await api("/api/reject", { method: "POST", json: { id: proposal.id } }).catch(() => {});
        closeCard();
        drawCalendar();
      } }, "Annulla")));
}

// --- the bar on top ---------------------------------------------------------------

function setupCalendar() {
  $("#gc-today").addEventListener("click", goToday);
  $("#gc-prev").addEventListener("click", () => step(-1));
  $("#gc-next").addEventListener("click", () => step(1));
  // On the phone only the current view shows; a tap opens the list, like Google's menu.
  const views = document.querySelector(".gc-views");
  for (const button of views.querySelectorAll("button")) {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      if (window.innerWidth <= 700 && !views.classList.contains("open")) { views.classList.add("open"); return; }
      views.classList.remove("open");
      setView(button.dataset.view);
    });
  }
  document.addEventListener("click", () => views.classList.remove("open"));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("#gc-sheet").hidden) closeCard();
  });
}
setupCalendar();
