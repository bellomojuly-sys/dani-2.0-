"""Twilio: Dani really calls Giulia (D2-070).

Plain HTTPS to the Twilio REST API with the standard library. The Account SID
and Auth Token (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) live in the
environment and travel only in the Basic auth header; errors never repeat
them. Twilio calls back Dani's server to ask what to say (TwiML); every
callback is checked with Twilio's signature, so nobody else can mark her
"awake".
"""

import base64
import hashlib
import hmac
import json
from urllib import error, parse, request

API = "https://api.twilio.com/2010-04-01"


def start_call(account_sid, auth_token, from_number, to_number, url, opener=request.urlopen, timeout=20):
    """Ask Twilio to call ``to_number``; when she answers Twilio fetches ``url``. Returns the call SID."""
    # Only the three basic parameters: a trial account refuses the others with HTTP 400.
    # Twilio's defaults do the rest (POST to ``url``, 60 seconds of ringing).
    body = parse.urlencode({"To": to_number, "From": from_number, "Url": url}).encode()
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    req = request.Request(f"{API}/Accounts/{account_sid}/Calls.json", data=body, method="POST",
                          headers={"Authorization": f"Basic {auth}",
                                   "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(req, timeout=timeout) as response:
            return json.loads(response.read()).get("sid", "")
    except error.HTTPError as failure:
        try:
            detail = json.loads(failure.read()).get("message", "")
        except ValueError:
            detail = ""
        raise RuntimeError(f"Twilio answered HTTP {failure.code} {detail}".strip()) from None
    except error.URLError as failure:
        raise RuntimeError(f"Twilio could not be reached: {failure.reason}") from None


def signature(auth_token, url, params):
    """Twilio's request signature: HMAC-SHA1 of the URL plus the sorted POST params, base64."""
    data = url + "".join(f"{key}{params[key]}" for key in sorted(params))
    digest = hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def is_from_twilio(auth_token, url, params, given):
    return bool(given) and hmac.compare_digest(signature(auth_token, url, params), given)
