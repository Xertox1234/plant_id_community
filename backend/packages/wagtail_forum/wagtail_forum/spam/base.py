from dataclasses import dataclass


@dataclass
class SpamResult:
    is_clean: bool
    reason: str = ""


class SpamBackend:
    """Override check() to return a SpamResult for a Topic or Post."""

    def check(self, obj) -> SpamResult:
        raise NotImplementedError

    def extract_text(self, obj) -> str:
        parts = []
        title = getattr(obj, "title", "") or ""
        if title:
            parts.append(title)
        body = getattr(obj, "body", None)
        if body is not None:
            for block in body:
                parts.append(str(getattr(block, "value", "")))
        return " ".join(parts)
