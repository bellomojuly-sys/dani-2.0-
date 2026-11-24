"""Giulia's life context (D2-058): who she is, her goals, projects and rules.

It lives in a Notion page she owns ("Dani — chi sono e come pianifico"), not
in the code: she can read and correct every sentence from her phone, Notion
keeps the page history, and the Render disk (wiped on every restart) holds
nothing. Dani re-reads the page in the background loop and puts it, together
with what she wrote in Settings, into the system prompt of every chat.
"""

import threading


class LifeContext:
    """The last good text of the page. A failed read keeps the previous text."""

    def __init__(self, fetch_text):
        self.fetch_text = fetch_text  # () -> str, the page text
        self.text = ""
        self.error = None
        self.lock = threading.Lock()

    def refresh(self):
        try:
            text = self.fetch_text()
        except Exception as failure:  # Notion down or the page not shared
            with self.lock:
                self.error = f"{type(failure).__name__}: {failure}"
            return False
        with self.lock:
            self.text, self.error = text.strip(), None
        return True

    def current(self):
        with self.lock:
            return self.text


def combine(life, settings_text, character=""):
    """The context paragraph for the prompt: Dani's character page (D2-062),
    then the life page, then Settings."""
    parts = []
    if character.strip():
        parts.append("Your full character, written by Giulia (page \"Dani — chi è Dani\"):\n" + character.strip())
    if life.strip():
        parts.append("Her life plan, projects and planning rules (her Notion page, she keeps it up to date):\n"
                     + life.strip())
    if settings_text.strip():
        parts.append("What she wrote in Settings:\n" + settings_text.strip())
    return "\n\n".join(parts)
