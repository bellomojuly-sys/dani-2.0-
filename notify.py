"""Send a notification to Giulia's phone (D2-061) through ntfy.

ntfy (ntfy.sh, open source) is an app on the phone that shows the messages
published to a "topic". No account and no key: the topic name is the secret,
so it lives in ``.env`` (NTFY_TOPIC) and never in the code. Without it the
sender is off and the briefing is only shown by /api/briefing.

Privacy: the text goes through the ntfy server (or a self-hosted one, with
NTFY_SERVER). The briefing holds her day and her cycle phase, so the topic
must be long and random, and NTFY_TOKEN can protect it with an access token.
"""

import base64
from urllib import error, request

DEFAULT_SERVER = "https://ntfy.sh"


def header_text(text):
    """HTTP headers are ASCII: a title with "ì" or "·" is sent RFC 2047-encoded,
    which ntfy decodes back to the original text."""
    if text.isascii():
        return text
    return "=?UTF-8?B?" + base64.b64encode(text.encode("utf-8")).decode("ascii") + "?="


def send_ntfy(topic, title, text, server=DEFAULT_SERVER, click=None, token=None,
              opener=request.urlopen, timeout=20):
    """Publish one message; raise RuntimeError when it is not accepted.

    The topic is in the URL, so an error never repeats the URL: only the code.
    """
    if not topic or "/" in topic:
        raise ValueError("NTFY_TOPIC must be a plain topic name")
    headers = {"Title": header_text(title), "Tags": "sunrise"}
    if click:
        headers["Click"] = click
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(f"{server.rstrip('/')}/{topic}", data=text.encode("utf-8"), headers=headers, method="POST")
    try:
        with opener(req, timeout=timeout) as response:
            return response.status
    except error.HTTPError as failure:
        raise RuntimeError(f"ntfy answered HTTP {failure.code}") from None
    except error.URLError as failure:
        raise RuntimeError(f"ntfy could not be reached: {failure.reason}") from None
