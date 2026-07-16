from dataclasses import dataclass


@dataclass
class SpamResult:
    is_clean: bool
    reason: str = ""


def extract_text(obj) -> str:
    """Flatten a Topic or Post's title + StreamField body into one string.

    Shared by spam heuristics and mention resolution (todo 253 slice 4, H4) —
    one walker, not two.
    """
    parts = []
    title = getattr(obj, "title", "") or ""
    if title:
        parts.append(title)
    # A Post has no title field, and the Topic's own workflow is never
    # started (the opening post's publish flips it live) — so the topic
    # title must be screened WITH the opening post or title spam publishes
    # unscreened (audit M1).
    if getattr(obj, "is_opening_post", False):
        parts.append(obj.topic.title)
    body = getattr(obj, "body", None)
    if body is not None:
        for block in body:
            parts.append(str(getattr(block, "value", "")))
    return " ".join(parts)


class SpamBackend:
    """Override check() to return a SpamResult for a Topic or Post."""

    def check(self, obj) -> SpamResult:
        raise NotImplementedError

    def extract_text(self, obj) -> str:
        return extract_text(obj)
