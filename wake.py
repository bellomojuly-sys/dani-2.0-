"""The wake-up guard (D2-067): Dani gets Giulia out of bed.

An iPhone Shortcuts automation ("when an alarm is snoozed / stopped") calls
POST /api/wake. A snooze gets a max-priority push at once, stronger each
time ("Chief. Hai ignorato tre volte. Alzati." from the third), with the
first appointment of the day, plus two follow-ups at +5 and +10 minutes
(ntfy delivers them while Render sleeps; they cannot be withdrawn, so they
say "se sei già in piedi, ignora"). Stopping the alarm after a snooze gets a
"brava". The words follow her page "Dani — chi è Dani".
"""

from datetime import timedelta

FOLLOW_UPS = (5, 10)  # minutes after a snooze


def first_commitment(events, now):
    """The first timed event still ahead today, or None."""
    ahead = sorted((e for e in events if not e.all_day and e.start.date() == now.date() and e.start > now),
                   key=lambda e: e.start)
    return ahead[0] if ahead else None


def snooze_messages(count, now, events):
    """The messages for the ``count``-th snooze of the day: [{"at", "title", "text", "priority"}]."""
    first = first_commitment(events, now)
    reason = f" Alle {first.start:%H:%M} hai «{first.title}»." if first else " La giornata ti aspetta."
    if count >= 3:
        title, text = "Chief. Alzati.", f"Chief. Hai ignorato la sveglia {count} volte. Alzati.{reason}"
    elif count == 2:
        title, text = "July, seconda volta", f"July, è la seconda volta. Piedi giù dal letto, adesso.{reason}"
    else:
        title, text = "Buongiorno July, sveglia", f"July, sveglia: la donna che vuoi diventare è già in piedi.{reason}"
    messages = [{"at": None, "title": title, "text": text, "priority": 5}]
    for minutes in FOLLOW_UPS:
        messages.append({
            "at": now + timedelta(minutes=minutes),
            "title": "Sei in piedi?",
            "text": f"Sono passati {minutes} minuti. Se sei già in piedi, brava: ignora questo messaggio.{reason}",
            "priority": 5 if minutes == FOLLOW_UPS[-1] else 4,
        })
    return messages


def stopped_message(snoozes):
    """After the alarm is stopped: a short "brava" only if there were snoozes."""
    if not snoozes:
        return None
    return {"at": None, "title": "Brava, July", "priority": 3,
            "text": "Brava. Acqua, luce, e poi partiamo: il programma di oggi arriva tra poco."}
