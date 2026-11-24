"""Estimate the current phase of Giulia's menstrual cycle.

With a hormonal IUD the start day is not precise, so this is an *estimate*:
it starts from the start date she enters (expected or real), the mean cycle
length and the mean period length, and says which phase today probably falls
in. ``confirmed`` tells whether the start date really happened or is only
expected; while it is not confirmed and the date has passed, the answer says
"expected, not started yet" instead of pretending to know.

A pure function: same inputs, same answer, testable without a clock.
"""

from datetime import date, timedelta

from pydantic import BaseModel, Field

# What each phase usually means for planning (shown under the phase name).
HINTS = {
    "mestruale": "Energia più bassa e crampi probabili: blocchi corti, niente allenamenti pesanti.",
    "follicolare": "Energia in salita: buon momento per il lavoro difficile e gli allenamenti intensi.",
    "ovulatoria": "Picco di energia: chiamate, presentazioni, cose sociali.",
    "luteale": "Energia in calo verso la fine: tieni margine e chiudi le cose aperte.",
    "in arrivo": "Il ciclo è atteso a breve: possibili crampi e meno energia, tieni la giornata leggera.",
}


class CycleSettings(BaseModel):
    """What Giulia enters in Settings. Lengths are in days."""

    start: date
    cycle_length: int = Field(default=28, ge=20, le=45)
    period_length: int = Field(default=5, ge=2, le=10)
    confirmed: bool = False


def estimate_phase(today, settings):
    """Return {"phase", "day", "late_days", "hint", "estimated", "next_start"} for ``today``.

    ``day`` is the cycle day (1 = first day of the period). When the start is
    only expected (not confirmed) and is today or already past, the phase is
    "in arrivo": the period is due but has not been confirmed, so we do not
    count days of a period that may not have begun. When the start is in the
    future, we count back one cycle from it.
    """
    start = settings.start
    if not settings.confirmed and start <= today:
        late = (today - start).days
        return {
            "phase": "in arrivo",
            "day": None,
            "late_days": late,
            "hint": HINTS["in arrivo"],
            "estimated": True,
            "next_start": start,
        }
    while start > today:  # a future start: the current cycle began one length earlier
        start -= timedelta(days=settings.cycle_length)
    day = (today - start).days % settings.cycle_length + 1
    ovulation = settings.cycle_length - 14  # the luteal phase is ~14 days long
    if day <= settings.period_length:
        phase = "mestruale"
    elif day < ovulation - 1:
        phase = "follicolare"
    elif day <= ovulation + 1:
        phase = "ovulatoria"
    else:
        phase = "luteale"
    if settings.cycle_length - day < 3 and phase == "luteale":
        phase = "in arrivo"
    cycles_done = (today - start).days // settings.cycle_length
    next_start = start + timedelta(days=settings.cycle_length * (cycles_done + 1))
    return {
        "phase": phase,
        "day": day,
        "late_days": 0,
        "hint": HINTS[phase],
        # A confirmed start is a fact only for its own cycle: every later cycle
        # is counted forward from it, so it is an estimate again.
        "estimated": not settings.confirmed or cycles_done > 0,
        "next_start": next_start,
    }
