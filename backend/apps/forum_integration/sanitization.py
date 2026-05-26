"""Authoritative server-side HTML sanitization for forum content (nh3).

Allowlist mirrors web/src/utils/sanitize.ts SANITIZE_PRESETS.FORUM.
If the React preset changes, update both files together.
"""

import nh3

# Tags: parity with SANITIZE_PRESETS.FORUM ALLOWED_TAGS.
ALLOWED_TAGS = {
    "p",
    "br",
    "span",
    "div",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "a",
    "img",
}

# Attributes per tag.  React uses a flat ALLOWED_ATTR list; nh3 requires per-tag mapping.
# data-mention / data-mention-id: needed for @mention spans rendered by TipTap.
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},  # rel is controlled by link_rel= below
    "img": {"src", "alt", "title", "width", "height"},
    "span": {"class", "data-mention", "data-mention-id"},
    "code": {"class"},
    "pre": {"class"},
    "div": {"class"},
}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_forum_html(html: str | None) -> str | None:
    """Return an XSS-safe subset of *html*.

    Applied on every write (create/update). The returned value is safe for
    direct storage and for rendering via dangerouslySetInnerHTML.
    Accepts Machina MarkupText or any str-coercible value.
    """
    if not html:
        return html
    return nh3.clean(
        str(html),  # coerce Machina MarkupText to plain str
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )
