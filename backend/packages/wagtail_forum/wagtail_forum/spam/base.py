import html
import re
from dataclasses import dataclass

from wagtail.embeds.blocks import EmbedValue
from wagtail.rich_text import RichText

# `<a href="X">X</a>` — a link whose visible text IS its address.
_SELF_LINK = re.compile(r'<a\b[^>]*?\bhref="([^"]*)"[^>]*>([^<]*)</a>', re.IGNORECASE)


def _collapse_self_links(markup: str) -> str:
    """Write each link whose text is its own address as that address once.

    The server auto-links bare URLs (todo 428), so one typed link is stored
    as ``<a href="X">X</a>`` and a raw-markup count would see it twice —
    two links in a post would read as four against ``SPAM_MAX_LINKS``. Only
    a link whose text equals its href collapses: ``<a href="spam">click</a>``
    keeps its hidden destination, so nothing a spammer hides gets cheaper.
    """

    def collapse(match):
        href, text = match.group(1), match.group(2)
        if html.unescape(text).strip() == html.unescape(href):
            return href
        return match.group(0)

    return _SELF_LINK.sub(collapse, markup)


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
            value = getattr(block, "value", "")
            # str(EmbedValue) is the provider's iframe HTML, fetched through
            # the embed finder on a cache miss — a second network call inside
            # the request, screening markup the author never wrote (todo 426).
            # The URL is what they wrote, and the link heuristic counts it.
            if isinstance(value, EmbedValue):
                value = value.url
            # A link card's title and description were written by the linked
            # page, not the author; screening them could reject a post for a
            # stranger's words (todo 428). The URL is what the author wrote.
            elif getattr(block, "block_type", None) == "link_preview":
                value = value.get("url") or ""
            elif isinstance(value, RichText):
                value = _collapse_self_links(str(value))
            parts.append(str(value))
    return " ".join(parts)


class SpamBackend:
    """Override check() to return a SpamResult for a Topic or Post."""

    def check(self, obj) -> SpamResult:
        raise NotImplementedError

    def extract_text(self, obj) -> str:
        return extract_text(obj)
