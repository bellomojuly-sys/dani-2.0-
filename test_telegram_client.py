"""The Telegram Bot API client (D2-069), with a fake opener: no network."""

import io
import json
from urllib import error

import pytest

from telegram_client import call, read_update, send_message


class Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_message_posts_text_and_buttons_to_the_bot_api():
    seen = {}

    def opener(req, timeout):
        seen.update(url=req.full_url, body=json.loads(req.data))
        return Answer(b'{"ok": true, "result": {"message_id": 1}}')

    assert send_message("TOKEN", "42", "Ciao July", [("Conferma", "c:a1")], opener=opener) == {"message_id": 1}
    assert seen["url"] == "https://api.telegram.org/botTOKEN/sendMessage"
    assert seen["body"]["chat_id"] == "42" and seen["body"]["text"] == "Ciao July"
    assert seen["body"]["reply_markup"] == {"inline_keyboard": [[{"text": "Conferma", "callback_data": "c:a1"}]]}


def test_errors_never_show_the_token():
    def refuse(req, timeout):
        raise error.HTTPError(req.full_url, 401, "no", {}, io.BytesIO(b'{"description": "Unauthorized"}'))

    with pytest.raises(RuntimeError) as caught:
        call("SECRET-TOKEN", "getMe", opener=refuse)
    assert "401 Unauthorized" in str(caught.value) and "SECRET-TOKEN" not in str(caught.value)
    with pytest.raises(RuntimeError, match="refused"):
        call("T", "getMe", opener=lambda req, timeout: Answer(b'{"ok": false, "description": "bad"}'))


def test_read_update_knows_text_voice_and_buttons_and_ignores_the_rest():
    assert read_update({"message": {"chat": {"id": 42}, "text": "ciao"}}) == {"kind": "text", "chat_id": "42", "text": "ciao"}
    assert read_update({"message": {"chat": {"id": 42}, "voice": {"file_id": "v1"}}})["file_id"] == "v1"
    button = read_update({"callback_query": {"id": "q1", "data": "c:a1", "message": {"chat": {"id": 42}}}})
    assert button == {"kind": "button", "chat_id": "42", "callback_id": "q1", "data": "c:a1"}
    assert read_update({"message": {"chat": {"id": 42}, "sticker": {}}}) is None
    assert read_update({"edited_message": {}}) is None
