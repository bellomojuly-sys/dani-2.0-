"""Telegram: Dani as a contact Giulia talks to (D2-069).

Plain HTTPS to the Bot API with the standard library, like notion_client.
The bot token (TELEGRAM_BOT_TOKEN, from @BotFather) lives in the environment
and travels only in the URL path of Telegram's own API; an error never
repeats the URL, only the status code and Telegram's description.

Dani talks only to Giulia: messages from any other chat are ignored
(TELEGRAM_CHAT_ID). Until that id is set, Dani answers the first message
with the chat id, so she can copy it into Render.
"""

import json
from urllib import error, request

API = "https://api.telegram.org"
MAX_TEXT = 4000  # Telegram refuses messages over 4096 characters


def call(token, method, payload=None, opener=request.urlopen, timeout=30):
    """POST one Bot API method and return its "result"; RuntimeError when not ok."""
    data = json.dumps(payload or {}).encode()
    req = request.Request(f"{API}/bot{token}/{method}", data=data,
                          headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener(req, timeout=timeout) as response:
            answer = json.loads(response.read())
    except error.HTTPError as failure:
        try:
            detail = json.loads(failure.read()).get("description", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"Telegram answered HTTP {failure.code} {detail}".strip()) from None
    except error.URLError as failure:
        raise RuntimeError(f"Telegram could not be reached: {failure.reason}") from None
    if not answer.get("ok"):
        raise RuntimeError(f"Telegram refused {method}: {answer.get('description', '')}")
    return answer.get("result")


def send_message(token, chat_id, text, buttons=None, silent=False, opener=request.urlopen):
    """Send a message; ``buttons`` is [(label, callback_data), ...] shown under it."""
    payload = {"chat_id": chat_id, "text": text[:MAX_TEXT], "disable_notification": silent}
    if buttons:
        payload["reply_markup"] = {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in buttons]]}
    return call(token, "sendMessage", payload, opener)


def answer_button(token, callback_id, text="", opener=request.urlopen):
    """Close the little clock on a pressed button."""
    return call(token, "answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:200]}, opener)


def download_voice(token, file_id, opener=request.urlopen, timeout=30):
    """Return the bytes of a voice message (Telegram stores it as .ogg)."""
    info = call(token, "getFile", {"file_id": file_id}, opener)
    req = request.Request(f"{API}/file/bot{token}/{info['file_path']}")
    try:
        with opener(req, timeout=timeout) as response:
            return response.read()
    except (error.HTTPError, error.URLError):
        raise RuntimeError("the voice message could not be downloaded") from None


def set_webhook(token, url, secret, opener=request.urlopen):
    """Tell Telegram where to deliver her messages; ``secret`` comes back in a header."""
    return call(token, "setWebhook", {"url": url, "secret_token": secret,
                                      "allowed_updates": ["message", "callback_query"]}, opener)


def read_update(update):
    """Turn one Telegram update into what Dani needs, or None for anything else.

    Returns {"chat_id", "kind": "text"|"voice"|"button", ...}.
    """
    if "callback_query" in update:
        query = update["callback_query"]
        return {"kind": "button", "chat_id": str(query["message"]["chat"]["id"]),
                "callback_id": query["id"], "data": query.get("data", "")}
    message = update.get("message")
    if not message:
        return None
    chat_id = str(message["chat"]["id"])
    if message.get("voice"):
        return {"kind": "voice", "chat_id": chat_id, "file_id": message["voice"]["file_id"]}
    if message.get("text"):
        return {"kind": "text", "chat_id": chat_id, "text": message["text"]}
    return None
