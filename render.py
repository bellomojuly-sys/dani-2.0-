"""Turn the week's data into ``dashboard.html``: pure string building.

No framework, no server (Decision Log 2026-11-05): the HTML file is the visible
output of a run. The look follows the Dani 2.0 app mockup (Claude Design,
"Dani 2.0 App"): the blush liquid background, the day strip, the italic serif
greeting, glass cards, the "Your day" timeline of blocks and the context chips.
Its design tokens (colours, fonts, radii) are copied into STYLE below, so the
dashboard and the future app share one palette.

Every value from outside (task titles, event names, the model's reasons) goes
through ``html.escape`` so it is shown as text, never run as HTML. The function
has no I/O and is deterministic, so a test can check the exact page for a
given input.
"""

from html import escape

WEEKDAYS_IT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
WEEKDAYS_SHORT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MONTHS_IT = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

# Notion "Area" -> the mockup's context chip (pastel fill, dark dot, label).
AREA_CONTEXT = {
    "University": "uni",
    "Heemia": "work",
    "MG Integration": "work",
    "Carriera / ICT": "work",
    "health": "gym",
    "Personal": "personal",
}

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Manrope:wght@400;600;700&display=swap');
:root{--pearl:#F7F2EF;--blush:#F4D3DA;--rose-quartz:#E8A9B8;--peony:#D46A8C;--berry:#9E2F5A;--berry-deep:#7A1F45;
--lilac-mist:#CDB8E6;--plum-ink:#2B1A24;--white:#FFFFFF;--ink-2:#5A3A4A;--ink-3:#6B4F5E;--ink-on-berry-muted:#F9E3EA;
--ctx-uni-bg:#F4D3DA;--ctx-uni-dot:#9E2F5A;--ctx-work-bg:#EDE4F7;--ctx-work-dot:#6E4FA0;
--ctx-gym-bg:#FBE3D6;--ctx-gym-dot:#B5532B;--ctx-personal-bg:#E9EBEF;--ctx-personal-dot:#4C5361;
--font-serif:'Instrument Serif',Georgia,serif;--font-sans:'Manrope',system-ui,-apple-system,sans-serif;
--glass-fill:rgba(255,255,255,0.28);--glass-border:1px solid rgba(255,255,255,0.7);
--glass-filter:blur(32px) saturate(180%);
--shadow-glass:inset 0 1px 0 rgba(255,255,255,0.95),inset 0 -1px 0 rgba(255,255,255,0.35),inset 0 0 24px rgba(255,255,255,0.25),0 20px 40px rgba(158,47,90,0.14);
--shadow-glass-block:inset 0 1px 0 #FFFFFF,inset 0 -1px 0 rgba(255,255,255,0.3),inset 0 0 18px rgba(255,255,255,0.22),0 12px 28px rgba(158,47,90,0.12)}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font-family:var(--font-sans);color:var(--plum-ink);background:#F4D3DA;
background-image:radial-gradient(circle at 20% 15%,#FFFFFF 0%,#F4D3DA 35%,#E8A9B8 75%,#D46A8C 120%);background-attachment:fixed}
.blob{position:fixed;border-radius:50%;filter:blur(60px);opacity:.85;pointer-events:none;z-index:-1}
.screen{max-width:430px;margin:0 auto;padding:40px 20px 64px;display:flex;flex-direction:column;gap:20px}
.strip{display:flex;justify-content:space-between}
.strip div{width:44px;padding:8px 0;border-radius:22px;display:flex;flex-direction:column;align-items:center;gap:2px;color:var(--ink-2)}
.strip div.today{background:rgba(43,26,36,0.88);color:#fff}
.strip span:first-child{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em}
.strip span:last-child{font-size:16px;font-weight:700}
.eyebrow{font-size:13px;letter-spacing:.16em;text-transform:uppercase;font-weight:700;color:var(--berry)}
.eyebrow.deep{color:var(--berry-deep)}
.greeting{font-family:var(--font-serif);font-size:52px;line-height:1;font-style:italic;margin:6px 0}
.greeting i{color:var(--berry)}
.lead{font-size:16px;color:var(--ink-2);margin-top:6px;line-height:1.45}
.glass{padding:20px;border-radius:32px;display:flex;flex-direction:column;gap:12px;background:var(--glass-fill);
border:var(--glass-border);box-shadow:var(--shadow-glass);backdrop-filter:var(--glass-filter);-webkit-backdrop-filter:var(--glass-filter)}
.rows{display:flex;flex-direction:column;gap:12px;font-size:16px;line-height:1.4}
.rows div{display:flex;gap:12px}.rows b{width:118px;flex-shrink:0;color:var(--berry-deep)}
.tip{padding:20px 20px 22px;border-radius:32px;display:flex;flex-direction:column;gap:14px;
background:linear-gradient(150deg,rgba(255,255,255,0.42) 0%,rgba(244,211,218,0.28) 45%,rgba(205,184,230,0.26) 100%);
border:1px solid rgba(255,255,255,0.75);box-shadow:inset 0 1px 0 #FFFFFF,inset 0 0 28px rgba(255,255,255,0.3),0 20px 40px rgba(158,47,90,0.14);
backdrop-filter:var(--glass-filter);-webkit-backdrop-filter:var(--glass-filter)}
.tip .head{display:flex;align-items:center;gap:10px}
.orb{width:28px;height:28px;border-radius:50%;flex-shrink:0;
background:radial-gradient(circle at 32% 26%,#FFFFFF 0%,#E6E8EC 18%,#A7ACB6 42%,#F4D3DA 62%,#D46A8C 85%,#9E2F5A 100%);
box-shadow:0 6px 12px rgba(122,31,69,0.3),inset 0 -3px 6px rgba(122,31,69,0.3)}
.tip p{margin:0;font-family:var(--font-serif);font-size:24px;line-height:1.2}.tip p i{color:var(--berry)}
.day{display:flex;flex-direction:column;gap:10px}
.row{display:flex;gap:16px;align-items:stretch}
.row .time{width:56px;flex-shrink:0;font-size:13px;font-weight:600;color:var(--ink-2);padding-top:18px}
.block{flex-grow:1;min-width:0;padding:18px 20px;border-radius:24px;display:flex;flex-direction:column;gap:4px;
background:rgba(255,255,255,0.32);color:var(--plum-ink);border:1px solid rgba(255,255,255,0.75);
box-shadow:var(--shadow-glass-block);backdrop-filter:var(--glass-filter);-webkit-backdrop-filter:var(--glass-filter)}
.block .title{font-size:18px;font-weight:700}.block .meta{font-size:14px;color:var(--ink-2)}
.block.study{background:linear-gradient(160deg,rgba(212,106,140,0.92) 0%,rgba(158,47,90,0.94) 55%,rgba(122,31,69,0.96) 100%);
color:var(--white);border:1px solid rgba(255,255,255,0.35);box-shadow:inset 0 1px 0 rgba(255,255,255,0.45),0 12px 28px rgba(158,47,90,0.28)}
.block.study .meta{color:var(--ink-on-berry-muted)}
.buffer{flex-grow:1;padding:12px 18px;border-radius:20px;background:rgba(255,255,255,0.16);border:1px dashed rgba(122,31,69,0.35);
font-size:14px;color:var(--ink-2)}.row .time.short{padding-top:14px}
.chip{padding:6px 12px;border-radius:999px;font-size:13px;font-weight:600;display:inline-flex;align-items:center;gap:8px;color:var(--plum-ink)}
.chip i{width:10px;height:10px;border-radius:5px;flex-shrink:0}
.chip.uni{background:var(--ctx-uni-bg)}.chip.uni i{background:var(--ctx-uni-dot)}
.chip.work{background:var(--ctx-work-bg)}.chip.work i{background:var(--ctx-work-dot)}
.chip.gym{background:var(--ctx-gym-bg)}.chip.gym i{background:var(--ctx-gym-dot)}
.chip.personal{background:var(--ctx-personal-bg)}.chip.personal i{background:var(--ctx-personal-dot)}
.list{display:flex;flex-direction:column;gap:10px}
.item{display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:26px;background:var(--glass-fill);border:var(--glass-border);
box-shadow:var(--shadow-glass-block);backdrop-filter:var(--glass-filter);-webkit-backdrop-filter:var(--glass-filter)}
.item .n{font-family:var(--font-serif);font-size:28px;line-height:1;color:var(--peony);width:34px;flex-shrink:0;text-align:center}
.item .body{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}
.item .t{font-size:16px;font-weight:700}.item .why{font-size:13px;color:var(--ink-2)}
.item .why i{font-family:var(--font-serif);font-size:15px;color:var(--berry-deep)}
.item .due{font-size:13px;font-weight:700;color:var(--ink-2);padding:6px 10px;border-radius:14px;background:rgba(255,255,255,0.4);white-space:nowrap}
.warn{color:var(--berry)}.ok{color:#1F6B4A}
footer{font-size:12px;color:var(--ink-3);text-align:center;padding-top:8px}
"""

BLOBS = (
    "<div class='blob' style='background:#D46A8C;width:300px;height:300px;left:-80px;top:-60px'></div>"
    "<div class='blob' style='background:#CDB8E6;width:280px;height:280px;right:-60px;top:160px'></div>"
    "<div class='blob' style='background:#E8A9B8;width:340px;height:340px;left:-60px;top:520px'></div>"
    "<div class='blob' style='background:#FFFFFF;width:260px;height:260px;right:-40px;top:-40px'></div>"
)


def _hhmm(moment):
    return moment.strftime("%H:%M")


def _span(start, end):
    return f"{_hhmm(start)} – {_hhmm(end)}"


def _date_it(day):
    return f"{WEEKDAYS_IT[day.weekday()]} {day.day} {MONTHS_IT[day.month - 1]}"


def _chip(area):
    context = AREA_CONTEXT.get(area or "", "personal")
    return f'<span class="chip {context}"><i></i>{escape(area or "—")}</span>'


def _day_strip(days, today):
    cells = []
    for day in days:
        css = ' class="today"' if day == today else ""
        cells.append(f"<div{css}><span>{WEEKDAYS_SHORT[day.weekday()]}</span><span>{day.day}</span></div>")
    return f'<div class="strip">{"".join(cells)}</div>'


def _greeting(today, tasks, events, plan):
    today_events = [event for event in events if event.start.date() == today and not event.all_day]
    today_blocks = [block for block in plan["blocks"] if block.start.date() == today]
    if today.weekday() == 6:
        lead = "Domenica: nessun blocco di studio. Oggi è tutto per te."
    elif today_blocks:
        minutes = sum((block.end - block.start).total_seconds() for block in today_blocks) / 60
        lead = (
            f"{len(today_events)} impegni in agenda e {len(today_blocks)} blocchi di studio "
            f"({int(minutes)} min). Il resto della giornata è libero."
        )
    else:
        lead = f"{len(today_events)} impegni in agenda e nessun blocco di studio oggi."
    return (
        f'<div><div class="eyebrow">{_date_it(today)}</div>'
        f'<div class="greeting">Buongiorno, <i>Giulia</i></div>'
        f'<div class="lead">{escape(lead)}</div></div>'
    )


def _briefing(tasks, events, plan, outcome):
    priority = "verificata dal modello" if outcome["ok"] else f"non verificata ({outcome['reason']})"
    unplaced = len(plan["unplaced"])
    rows = [
        ("Task aperti", f"{len(tasks)} su Notion"),
        ("Agenda", f"{len(events)} eventi nei prossimi 7 giorni"),
        ("Studio", f"{len(plan['blocks'])} blocchi piazzati" + (f", {unplaced} non piazzati" if unplaced else "")),
        ("Priorità", priority),
    ]
    body = "".join(f"<div><b>{label}</b><span>{escape(value)}</span></div>" for label, value in rows)
    return (
        '<div class="glass"><div class="eyebrow deep">Il tuo briefing</div>'
        f'<div class="rows">{body}</div></div>'
    )


def _tip(outcome, tasks_by_id):
    """Dani's advice: the first verified priority and its reason. Only shown
    when the model's priority was validated; otherwise nothing is claimed."""
    if not outcome["ok"] or not outcome["priority"]:
        return ""
    first = outcome["priority"][0]
    task = tasks_by_id.get(first["id"])
    return (
        '<div class="tip"><div class="head"><span class="orb"></span>'
        '<span class="eyebrow deep">Il mio consiglio</span></div>'
        f"<p>Prima di tutto: <i>{escape(first['title'])}</i>. {escape(first['reason'])}</p></div>"
    )


def _day_rows(day, events, blocks):
    """The day's timeline: events and study blocks merged by start time."""
    entries = [("event", event.start, event) for event in events] + [
        ("study", block.start, block) for block in blocks
    ]
    entries.sort(key=lambda entry: (entry[2].start, entry[0]))
    rows = []
    for kind, _, item in entries:
        if kind == "event":
            when = "giorno" if item.all_day else _hhmm(item.start)
            span = "tutto il giorno" if item.all_day else _span(item.start, item.end)
            rows.append(
                f'<div class="row"><div class="time">{when}</div><div class="block">'
                f'<div class="title">{escape(item.title)}</div>'
                f'<div class="meta">{span} · {escape(item.calendar)}</div></div></div>'
            )
        else:
            minutes = int((item.end - item.start).total_seconds() / 60)
            rows.append(
                f'<div class="row"><div class="time">{_hhmm(item.start)}</div><div class="block study">'
                f'<div class="title">{escape(item.title)}</div>'
                f'<div class="meta">{_span(item.start, item.end)} · studio · {minutes} min</div></div></div>'
            )
    if not rows:
        note = "domenica, niente in agenda" if day.weekday() == 6 else "niente in agenda"
        rows.append(f'<div class="row"><div class="time short"></div><div class="buffer">{note}</div></div>')
    return "".join(rows)


def _week(days, today, events, plan):
    sections = []
    for day in days:
        label = "La tua giornata" if day == today else _date_it(day)
        rows = _day_rows(
            day,
            [event for event in events if event.start.date() == day],
            [block for block in plan["blocks"] if block.start.date() == day],
        )
        sections.append(f'<div class="day"><div class="eyebrow deep">{label}</div>{rows}</div>')
    return "".join(sections)


def _priority_section(outcome, tasks_by_id):
    """The LLM's priority, shown ONLY when final_outcome verified it."""
    if not outcome["ok"]:
        return (
            '<div class="glass"><div class="eyebrow deep">Priorità</div>'
            f'<div class="lead warn">Nessuna priorità verificata: {escape(outcome["reason"])}. '
            "I blocchi di studio seguono l'ordine per scadenza.</div></div>"
        )
    items = []
    for row in outcome["priority"]:
        task = tasks_by_id.get(row["id"])
        due = task.deadline.strftime("%d/%m") if task and task.deadline else "—"
        items.append(
            f'<div class="item"><div class="n">{row["rank"]}</div><div class="body">'
            f'<div class="t">{escape(row["title"])}</div>'
            f'<div class="why">Dani · <i>{escape(row["reason"])}</i></div></div>'
            f'<span class="due">{due}</span></div>'
        )
    return (
        '<div class="day"><div class="eyebrow deep">Priorità <span class="ok">· verificata</span></div>'
        f'<div class="list">{"".join(items)}</div></div>'
    )


def _tasks_section(tasks, unplaced):
    unplaced_ids = {task.id for task in unplaced}
    items = []
    for task in tasks:
        flag = ' <span class="warn">· non piazzato</span>' if task.id in unplaced_ids else ""
        minutes = f"{task.duration_minutes} min" if task.duration_minutes else "stima mancante"
        due = task.deadline.strftime("%d/%m") if task.deadline else "—"
        items.append(
            f'<div class="item"><div class="body"><div class="t">{escape(task.title)}</div>'
            f'<div class="why">{escape(task.status)} · {minutes}{flag}</div>'
            f"<div>{_chip(task.area)}</div></div>"
            f'<span class="due">{due}</span></div>'
        )
    return (
        f'<div class="day"><div class="eyebrow deep">Task aperti su Notion · {len(tasks)}</div>'
        f'<div class="list">{"".join(items)}</div></div>'
    )


def render_dashboard(today, days, tasks, events, plan, outcome, run):
    """Build the whole page. ``run`` is the trace envelope (run id, timestamps)."""
    tasks_by_id = {task.id: task for task in tasks}
    return (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
        f"<title>Dani — {today.isoformat()}</title><style>{STYLE}</style></head><body>"
        f"{BLOBS}<div class='screen'>"
        f"{_day_strip(days, today)}"
        f"{_greeting(today, tasks, events, plan)}"
        f"{_briefing(tasks, events, plan, outcome)}"
        f"{_tip(outcome, tasks_by_id)}"
        f"{_week(days, today, events, plan)}"
        f"{_priority_section(outcome, tasks_by_id)}"
        f"{_tasks_section(tasks, plan['unplaced'])}"
        f"<footer>run {escape(run.run_id)} · {escape(run.started_at[:19])}</footer>"
        "</div></body></html>"
    )
