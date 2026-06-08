import re

from ..conf import get_setting
from .base import SpamBackend, SpamResult

URL_RE = re.compile(r"https?://", re.IGNORECASE)


class HeuristicSpamBackend(SpamBackend):
    def check(self, obj) -> SpamResult:
        text = self.extract_text(obj)
        if len(URL_RE.findall(text)) > get_setting("SPAM_MAX_LINKS"):
            return SpamResult(False, "Too many links")
        lowered = text.lower()
        for word in get_setting("SPAM_BANNED_WORDS"):
            if word.lower() in lowered:
                return SpamResult(False, f"Banned term: {word}")
        return SpamResult(True)
