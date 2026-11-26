"""The wake-up call (D2-070): questions, answers, retries, the Twilio signature."""

import random
from datetime import datetime, timedelta

from models import AMSTERDAM
from twilio_client import is_from_twilio, signature
from wake_call import MAX_CALLS, RETRY_MINUTES, Morning, heard_number, new_question, twiml_question, wake_time_today

MORNING = datetime(2026, 11, 25, 6, 45, tzinfo=AMSTERDAM)  # a Wednesday


def test_she_can_answer_by_keypad_by_voice_or_in_words():
    assert heard_number("68", None) == 68
    assert heard_number(None, "fa 68.") == 68
    assert heard_number("", "sessantotto") is None  # only simple words are understood: then a new question
    assert heard_number(None, "dodici") == 12
    assert heard_number(None, "") is None


def test_a_question_is_a_real_calculation():
    question = new_question(random.Random(1))
    a, b = (int(n) for n in question["text"].removeprefix("Quanto fa ").removesuffix("?").split(" per "))
    assert question["answer"] == a * b and 12 <= a <= 49 and 3 <= b <= 9


def test_the_right_answer_wakes_her_and_stops_the_calls():
    morning = Morning(MORNING.date(), random.Random(2))
    assert morning.due(MORNING, MORNING) is True
    morning.calling(MORNING)
    result, _ = morning.answer(str(morning.question["answer"]), None)
    assert result == "awake" and morning.awake
    assert morning.due(MORNING + timedelta(minutes=10), MORNING) is False


def test_a_wrong_answer_asks_again_and_three_wrong_end_the_call():
    morning = Morning(MORNING.date(), random.Random(3))
    morning.calling(MORNING)
    first = morning.question
    assert morning.answer("1", None)[0] == "wrong" and morning.question != first
    assert morning.answer("1", None)[0] == "wrong"
    assert morning.answer("1", None)[0] == "again"  # hang up, the retry calls her back
    assert not morning.awake


def test_no_answer_means_a_call_every_three_minutes_at_most_ten_times():
    morning = Morning(MORNING.date())
    now, calls = MORNING, 0
    while now < MORNING + timedelta(hours=1):
        if morning.due(now, MORNING):
            morning.calling(now)
            calls += 1
        now += timedelta(minutes=1)
    assert calls == MAX_CALLS and morning.gave_up
    assert morning.next_call is None and RETRY_MINUTES == 3


def test_a_snooze_calls_at_once_even_after_giving_up_and_sunday_has_no_wake_time():
    morning = Morning(MORNING.date())
    morning.gave_up = True
    morning.snoozed(MORNING)
    assert morning.due(MORNING, None) is True
    assert wake_time_today("06:45", MORNING) == MORNING
    assert wake_time_today("06:45", datetime(2026, 11, 29, 6, 0, tzinfo=AMSTERDAM)) is None
    assert wake_time_today(None, MORNING) is None


def test_the_twiml_speaks_italian_and_escapes_text():
    xml = twiml_question("Buongiorno July & co", "Quanto fa 2 per 3?", "https://dani/answer")
    assert 'language="it-IT"' in xml and "July &amp; co" in xml and 'action="https://dani/answer"' in xml


def test_only_a_request_signed_by_twilio_is_accepted():
    params = {"Digits": "68", "CallSid": "CA1"}
    good = signature("token", "https://dani/twilio/x/answer", params)
    assert is_from_twilio("token", "https://dani/twilio/x/answer", params, good)
    assert not is_from_twilio("token", "https://dani/twilio/x/answer", {**params, "Digits": "1"}, good)
    assert not is_from_twilio("other", "https://dani/twilio/x/answer", params, good)
    assert not is_from_twilio("token", "https://dani/twilio/x/answer", params, "")


def test_a_restart_long_after_the_wake_time_does_not_ring_her():
    now = datetime(2026, 11, 26, 15, 30, tzinfo=AMSTERDAM)  # Thursday
    morning = Morning(now.date())
    assert morning.due(now, now.replace(hour=15, minute=0))  # 30 minutes late: still her wake-up
    assert not morning.due(now, now.replace(hour=6, minute=45))  # hours later: no call
