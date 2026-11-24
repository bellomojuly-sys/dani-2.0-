"""The evaluation harness with a fake model: what passes, and that a
deliberate break makes it fail (the D2-032 verify)."""

from evals import CASES, check_answer, fixture_state, run_evals

# One answer per question that states every required fact (first spelling).
GOOD_ANSWERS = {
    case["question"]: ". ".join(spellings[0] for spellings in case["facts"]) for case in CASES
}


def test_there_are_five_cases_and_the_fixture_state_backs_their_facts():
    assert len(CASES) == 5
    state = fixture_state()
    titles = {task["title"] for task in state["tasks"]}
    events = {event["title"] for event in state["events"]}
    assert "Finish the Notion client" in titles and "Book the dentist" in titles
    assert {"Lezione MA-AAI", "Call con Ruud", "Demo Sprint 3"} <= events


def test_answers_with_the_facts_pass_all_five():
    results = run_evals(lambda question: GOOD_ANSWERS[question])
    assert [row["passed"] for row in results] == [True] * 5
    assert all(row["missing"] == [] for row in results)


def test_a_deliberate_break_makes_it_fail_and_names_what_is_missing():
    broken = dict(GOOD_ANSWERS)
    question = CASES[1]["question"]  # the call with Ruud
    broken[question] = "La call con Ruud è il 12 novembre."  # right day, no time
    results = run_evals(lambda q: broken[q])
    failed = next(row for row in results if row["question"] == question)
    assert failed["passed"] is False
    assert failed["missing"] == [CASES[1]["facts"][1]]  # exactly the time is missing
    assert sum(row["passed"] for row in results) == 4


def test_facts_match_any_spelling_and_ignore_case():
    facts = [["15:00", "alle 15"], ["mercoledì"]]
    assert check_answer("La call è MERCOLEDÌ alle 15.", facts) == []
    assert check_answer("La call è mercoledì.", facts) == [["15:00", "alle 15"]]


def test_each_question_is_asked_exactly_once_in_order():
    asked = []

    def ask(question):
        asked.append(question)
        return GOOD_ANSWERS[question]

    run_evals(ask)
    assert asked == [case["question"] for case in CASES]


# --- D2-059: planning cases --------------------------------------------------------

from datetime import datetime as _dt  # noqa: E402

from evals import PLAN_CASES, run_plan_evals  # noqa: E402
from models import AMSTERDAM as _AMS, Event as _Event  # noqa: E402

_SHIFT = _Event(calendar="lavoro", title="Turno", start=_dt(2026, 11, 11, 17, 0, tzinfo=_AMS),
                end=_dt(2026, 11, 11, 23, 0, tzinfo=_AMS))


def _turn(*blocks):
    return {"text": "ok", "plan": {"blocks": [
        {"title": t, "start": s, "end": e} for t, s, e in blocks]}}


def test_a_plan_with_invested_time_and_no_broken_rule_passes():
    good = _turn(("AMX-08", "2026-11-11T09:30", "2026-11-11T12:00"), ("Lettura", "2026-11-11T13:00", "2026-11-11T14:00"))
    assert all(row["passed"] for row in run_plan_evals(lambda q: good, [_SHIFT]))


def test_each_broken_planning_rule_makes_a_case_fail():
    no_plan = run_plan_evals(lambda q: {"text": "ciao"}, [])
    assert no_plan[0]["missing"] == ["no plan was proposed"]
    on_shift = run_plan_evals(lambda q: _turn(("Lettura", "2026-11-11T16:00", "2026-11-11T18:00")), [_SHIFT])
    assert any("Turno" in problem for problem in on_shift[0]["missing"])
    no_free_time = run_plan_evals(lambda q: _turn(("AMX-08", "2026-11-12T10:00", "2026-11-12T11:00")), [])
    assert no_free_time[0]["missing"] == ["no block of invested free time"]
    refused = run_plan_evals(lambda q: {"plan": {"blocks": []}}, [])
    assert refused[0]["missing"][0].startswith("the plan was refused")
    assert len(no_plan) == len(PLAN_CASES)
