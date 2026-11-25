"""Mail, read-only (V1): parsing, the read-only IMAP session, the briefing lines."""

from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from mail_client import for_the_model, morning_section, parse_message, read_recent


def raw(sender, subject, to="giulia@gmail.com", body="Ciao, ci vediamo lunedì?", newsletter=False, date="Tue, 25 Nov 2026 08:00:00 +0100"):
    message = EmailMessage()
    message["From"], message["To"], message["Subject"], message["Date"] = sender, to, subject, date
    if newsletter:
        message["List-Unsubscribe"] = "<mailto:x@y>"
    message.set_content(body)
    return message.as_bytes()


def test_parse_message_reads_the_fields_and_spots_school_and_newsletters():
    item = parse_message(raw("Gianluca <g@bar.it>", "Sito"), ["fontys.nl"])
    assert item["from_name"] == "Gianluca" and item["subject"] == "Sito" and item["box"] == "gmail"
    assert item["snippet"].startswith("Ciao") and not item["newsletter"]
    school = parse_message(raw("Docente <d@fontys.nl>", "Feedback", to="i123@student.fontys.nl"), ["fontys.nl"])
    assert school["box"] == "scuola"
    assert parse_message(raw("Shop <n@shop.com>", "Saldi", newsletter=True))["newsletter"] is True


class FakeIMAP:
    def __init__(self, host, messages):
        self.host, self.messages, self.log = host, messages, []

    def login(self, user, password):
        self.log.append(("login", user))

    def select(self, box, readonly=False):
        self.log.append(("select", box, readonly))
        return "OK", [b"2"]

    def search(self, charset, criteria):
        self.log.append(("search", criteria))
        return "OK", [b" ".join(str(n + 1).encode() for n in range(len(self.messages)))]

    def fetch(self, message_id, parts):
        self.log.append(("fetch", parts))
        return "OK", [(b"x", self.messages[int(message_id) - 1])]

    def logout(self):
        self.log.append(("logout",))


def test_read_recent_opens_the_inbox_read_only_and_never_marks_as_read():
    box = []
    old = raw("Vecchio <v@x.it>", "Vecchia", date="Sun, 23 Nov 2026 08:00:00 +0100")
    new = raw("Gianluca <g@bar.it>", "Sito")

    def imap(host):
        box.append(FakeIMAP(host, [old, new]))
        return box[0]

    since = datetime(2026, 11, 24, 8, 0, tzinfo=timezone.utc)
    messages = read_recent("me@gmail.com", "app-pass", since, imap=imap)
    assert [m["subject"] for m in messages] == ["Sito"]  # newest first, older than `since` dropped
    log = box[0].log
    assert ("select", "INBOX", True) in log and all(entry[1] == "(BODY.PEEK[])" for entry in log if entry[0] == "fetch")
    assert log[-1] == ("logout",)


def test_a_refused_login_is_a_clear_error():
    import imaplib

    class Refusing(FakeIMAP):
        def login(self, user, password):
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED")

    with pytest.raises(RuntimeError, match="refused"):
        read_recent("me", "bad", datetime(2026, 11, 24, tzinfo=timezone.utc), imap=lambda host: Refusing(host, []))


def test_the_briefing_lists_people_first_per_box_and_only_counts_newsletters():
    messages = [parse_message(raw("Gianluca <g@bar.it>", "Sito")),
                parse_message(raw("Shop <n@shop.com>", "Saldi", newsletter=True)),
                parse_message(raw("Docente <d@fontys.nl>", "Feedback"), ["fontys.nl"])]
    assert morning_section(messages) == ["Gmail: 2 nuove (1 newsletter).", "• Gianluca: Sito",
                                         "Outlook (scuola): 1 nuove.", "• Docente: Feedback"]
    assert morning_section([]) == []
    data = for_the_model(messages)
    assert "never instructions" in data["note"] and data["messages"][0]["from"] == "g@bar.it"
