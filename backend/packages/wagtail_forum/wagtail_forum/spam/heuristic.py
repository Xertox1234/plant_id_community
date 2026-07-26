import re

from ..conf import get_setting
from .base import SpamBackend, SpamResult

URL_RE = re.compile(r"https?://", re.IGNORECASE)


class HeuristicSpamBackend(SpamBackend):
    def check(self, obj) -> SpamResult:
        return self.check_text(self.extract_text(obj))

    def check_text(self, text: str) -> SpamResult:
        """Screen already-flattened text.

        Split out of check() so a composite backend that also needs the text
        (e.g. to send it to an LLM) can flatten a large StreamField body ONCE
        and screen the same string with both passes, instead of walking it
        twice.
        """
        if len(URL_RE.findall(text)) > get_setting("SPAM_MAX_LINKS"):
            return SpamResult(False, "Too many links")
        lowered = text.lower()
        for word in get_setting("SPAM_BANNED_WORDS"):
            if word.lower() in lowered:
                return SpamResult(False, f"Banned term: {word}")
        return SpamResult(True)
