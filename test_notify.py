"""Sending through ntfy (D2-061), with a fake opener: no network."""

import base64
from urllib import error

import pytest

from notify import header_text, send_ntfy


class Answer:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_the_message_goes_to_the_topic_with_title_click_and_token():
    seen = {}

    def opener(req, timeout):
        seen.update(url=req.full_url, data=req.data, headers=dict(req.header_items()), method=req.get_method())
        return Answer()

    assert send_ntfy("dani-abc123", "Buongiorno", "Oggi come stai?", click="https://dani", token="tk", opener=opener) == 200
    assert seen["url"] == "https://ntfy.sh/dani-abc123" and seen["method"] == "POST"
    assert seen["data"] == "Oggi come stai?".encode()
    assert seen["headers"]["Title"] == "Buongiorno" and seen["headers"]["Click"] == "https://dani"
    assert seen["headers"]["Authorization"] == "Bearer tk"


def test_an_accented_title_is_rfc2047_encoded_and_decodes_back():
    encoded = header_text("Buongiorno Giulia · martedì")
    assert encoded.isascii() and encoded.startswith("=?UTF-8?B?")
    assert base64.b64decode(encoded[10:-2]).decode() == "Buongiorno Giulia · martedì"


def test_errors_never_show_the_topic_and_a_bad_topic_is_refused():
    def refuse(req, timeout):
        raise error.HTTPError(req.full_url, 403, "forbidden", {}, None)

    with pytest.raises(RuntimeError) as caught:
        send_ntfy("secret-topic", "t", "x", opener=refuse)
    assert "403" in str(caught.value) and "secret-topic" not in str(caught.value)

    def offline(req, timeout):
        raise error.URLError("no route")

    with pytest.raises(RuntimeError, match="could not be reached"):
        send_ntfy("t", "t", "x", opener=offline)
    for bad in ("", "a/b"):
        with pytest.raises(ValueError):
            send_ntfy(bad, "t", "x", opener=lambda req, timeout: Answer())


def test_a_later_delivery_and_a_priority_are_sent_as_ntfy_headers():
    from datetime import datetime

    from models import AMSTERDAM

    seen = {}

    def opener(req, timeout):
        seen.update(dict(req.header_items()))
        return Answer()

    when = datetime(2026, 11, 24, 14, 45, tzinfo=AMSTERDAM)
    send_ntfy("t", "Tra 15 minuti", "x", at=when, priority=5, opener=opener)
    assert seen["At"] == str(int(when.timestamp())) and seen["Priority"] == "5"
    with pytest.raises(ValueError, match="time zone"):
        send_ntfy("t", "t", "x", at=datetime(2026, 11, 24, 14, 45), opener=opener)
    with pytest.raises(ValueError, match="1 to 5"):
        send_ntfy("t", "t", "x", priority=9, opener=opener)
