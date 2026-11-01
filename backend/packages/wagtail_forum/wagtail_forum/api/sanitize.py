"""Server-side sanitization of forum post bodies for the DRF API.

Direct API POSTs bypass the Wagtail editor's HTML filtering, so rich-text block
content is sanitized on write with an nh3 allowlist: it strips ``<script>``,
event-handler attributes (``onerror``/``onclick``/...), disallowed tags, and
non-allowlisted URL schemes (``javascript:``/``data:``/...). Plain-text blocks
(heading/quote/code) are text by contract and are left untouched — the consumer
must HTML-escape them at render time.

The body is also bounded (block count + total size) to keep validation/parse
cost and storage in check.
"""

import html
import json
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import nh3
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from wagtail.blocks import ChooserBlock, IntegerBlock, RichTextBlock, StructBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images import get_image_model
from wagtail.images.blocks import ImageBlock, ImageChooserBlock
from wagtail.rich_text import expand_db_html

from ..blocks import ForumBodyBlock, LinkPreviewBlock
from ..collections import get_forum_image_collection
from ..conf import get_setting
from ..embeds import is_supported_url, warm_embeds
from ..link_previews import fetch_snapshots, get_fetcher, is_card_url
from ..quotes import resolve_quotable_posts

# Allowlist scoped to ForumBodyBlock's RichTextBlock features (bold, italic, link,
# ol, ul, code) plus the structural tags Wagtail emits. nh3 drops everything else,
# including all event-handler attributes and <script>/<svg>/<img> etc.
ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a", "code"}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

# Bound a single post body. Generous for a forum post; caps parse cost + storage.
MAX_BODY_BLOCKS = 100
# The cap on a body's MEASURED size (``_measured_body_chars``): its JSON, with
# a link card counted as its URL alone and the link markup the server adds
# not counted, up to MAX_BODY_MARKUP_TOLERANCE (todo 535).
MAX_BODY_CHARS = 100_000
# Server-added ``<a>`` attributes not counted toward MAX_BODY_CHARS, so a
# stored body resent unchanged measures what it measured when stored, even
# when the server has since added markup to every link (``target`` did, in
# todo 448 item 13). Bounded, so markup cannot be used to grow storage.
MAX_BODY_MARKUP_TOLERANCE = 20_000
# The ceiling on the RAW JSON a client may send: it bounds parse cost before
# anything is measured. The cap, the markup tolerance and five resent cards
# at their stored field caps all fit well under it.
MAX_BODY_RAW_CHARS = 2 * MAX_BODY_CHARS
# The attributes ``sanitize_rich_text`` sets on every ``<a>``, as nh3 emits
# them.
_SERVER_LINK_ATTRIBUTES = (' target="_blank"', ' rel="noopener noreferrer nofollow"')
# An ``<a>`` start tag, attribute-aware: nh3 leaves a raw ``>`` (and ``<``)
# inside a double-quoted attribute value, so the tag ends at the first ``>``
# OUTSIDE quotes (todo 539 item 4). Outside quotes a match never crosses a
# ``<``, and every quantifier is possessive, so a scan of raw client input is
# linear: the old ``<a\b[^>]*>`` scanned to the end of the string from every
# ``<a``, about 4 s of CPU for 200k characters of ``<a ``. nh3 quotes every
# value with ``"``; a ``'``-quoted tag in raw input just earns no discount.
_ANCHOR_START_TAG = re.compile(r'<a\b(?:[^<>"]++|"[^"]*+")*+>', re.IGNORECASE)


def sanitize_rich_text(html):
    """Return an XSS-safe subset of *html* (nh3 allowlist).

    Every ``<a>`` in a body opens in a new tab, as a link card does (todo 448
    item 13; owner decision 2026-09-28: set it here, server-side, so every
    client gets it). A client-supplied ``target`` is never kept — nh3 sets
    the value. Internal forum links (mentions, a quote's "in topic" link) are
    not body ``<a>`` markup: clients render them from their own blocks."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        set_tag_attribute_values={"a": {"target": "_blank"}},
    )


class _TextWithTagBreaks(HTMLParser):
    """Collects an HTML fragment's text with every tag read as a space, so
    two links on two lines (``url<br>url``, ``<p>url</p><p>url</p>``) can
    never glue into one token. Character references are decoded.
    ``in_code`` records whether any non-blank text sat inside a ``<code>``."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._code_depth = 0
        self.in_code = False

    def handle_starttag(self, tag, attrs):
        self.parts.append(" ")
        if tag == "code":
            self._code_depth += 1

    def handle_endtag(self, tag):
        self.parts.append(" ")
        if tag == "code" and self._code_depth:
            self._code_depth -= 1

    def handle_data(self, data):
        self.parts.append(data)
        if self._code_depth and data.strip():
            self.in_code = True


def _sole_url(html, *, skip_code=False):
    """The text when a paragraph's ONLY content is one whitespace-free token
    (a candidate link), else ``None``. The mobile composer sends a bare
    ``url`` with no ``<p>`` wrapper, so the test is on the text, not the
    markup; an autolinked ``<a>`` counts too, and it is the TEXT a reader
    saw that is returned, never a differing ``href``. ``skip_code``: a token
    written as code (``<code>https://api.example.com/v1</code>``) is a code
    sample, not a link to preview — the auto-linker skips ``<code>`` too."""
    parser = _TextWithTagBreaks()
    parser.feed(sanitize_rich_text(html))
    parser.close()
    if skip_code and parser.in_code:
        return None
    text = "".join(parser.parts).strip()
    if not text or any(ch.isspace() for ch in text):
        return None
    return text


def _sole_video_url(html):
    """The URL when a paragraph's ONLY content is one video link the host's
    finders accept, else ``None`` (todo 421).

    The same rule the web composer applies before submit
    (``web/src/utils/forumBody.ts`` ``embedUrlOf``), moved to the server so
    every client gets it. The allowlist is ``is_supported_url`` (the host's
    ``WAGTAILEMBEDS_FINDERS``), not a copy of the web's regex, so a link that
    converts is exactly a link the embed validation below accepts. A URL
    written as code stays code, as on the card path (todo 448 item 10).
    """
    text = _sole_url(html, skip_code=True)
    return text if text and is_supported_url(text) else None


# Elements a link line is never split out of (todo 655): a URL in a list
# item, a code sample or a quotation belongs to it. ``blockquote`` and
# ``pre`` are not in ALLOWED_TAGS (sanitize_rich_text strips them, keeping
# their text), so the split reads the paragraph through an allowlist that
# keeps them, and the stored pieces are sanitized as usual afterwards.
_SPLIT_OPAQUE_TAGS = {"ul", "ol", "li", "blockquote", "pre"}
_SPLIT_ANALYSIS_TAGS = ALLOWED_TAGS | {"blockquote", "pre"}
_SPLIT_EXCLUDED_TAGS = _SPLIT_OPAQUE_TAGS | {"code"}


class _LinkLineSplitter(HTMLParser):
    """Reads sanitized paragraph HTML as a list of top-level segments, each
    a ``p`` element, a run of loose top-level content (the mobile
    composer's ``line<br>line`` shape) or an opaque element (a list, a
    quotation, a code block). A ``p`` or loose segment holds LINES, split at
    a ``<br>`` directly inside it; an opaque one is one piece of markup.
    Every line keeps its markup as parsed, and its text with every tag read
    as a space, as ``_sole_url`` reads it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segments = []
        self._stack = []
        self._segment: dict[str, Any] | None = None

    @staticmethod
    def _new_line(segment):
        segment["lines"].append({"html": [], "text": [], "code": False})

    def _open(self, kind):
        segment = {"kind": kind, "lines": [], "html": []}
        self._segment = segment
        if kind != "opaque":
            self._new_line(segment)
        self.segments.append(segment)
        return segment

    def _emit(self, markup, text=" ", in_code=False):
        segment = self._segment
        if segment is None:
            segment = self._open("loose")
        if segment["kind"] == "opaque":
            segment["html"].append(markup)
            return
        line = segment["lines"][-1]
        line["html"].append(markup)
        line["text"].append(text)
        if in_code and text.strip():
            line["code"] = True

    def _line_break(self):
        """A ``<br>``: a line boundary directly inside a top-level ``p`` or
        at the top level itself, ordinary markup anywhere else."""
        if self._stack and self._stack != ["p"]:
            self._emit("<br>")
            return
        segment = self._segment
        if segment is None:
            segment = self._open("loose")  # the line before this break is empty
        self._new_line(segment)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self._line_break()
            return
        if not self._stack:
            if tag == "p":
                self._open("p")
                self._stack.append(tag)
                return
            if tag in _SPLIT_OPAQUE_TAGS:
                self._open("opaque")
        self._emit(self.get_starttag_text())
        self._stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self._line_break()
        else:
            self._emit(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag not in self._stack:
            return
        while self._stack:
            open_tag = self._stack.pop()
            if not self._stack and open_tag == "p":
                break  # the ``p`` wrapper itself is re-emitted per piece
            self._emit(f"</{open_tag}>")
            if open_tag == tag:
                break
        if not self._stack:
            # The next top-level content starts a segment of its own.
            self._segment = (
                self._segment
                if self._segment and self._segment["kind"] == "loose"
                else None
            )

    def handle_data(self, data):
        # Text under a code sample, a list or a quotation nested inside a
        # line rules that line out, as at the top level.
        excluded = any(tag in _SPLIT_EXCLUDED_TAGS for tag in self._stack)
        self._emit(html.escape(data, quote=False), data, in_code=excluded)


def _link_line_url(line):
    """The URL when one line is a link posted on its own: its whole text is
    one URL that could be a card (or a video, which the conversion below
    then embeds), not written as code. Else ``None``."""
    if line["code"]:
        return None
    token = "".join(line["text"]).strip()
    if not token or any(ch.isspace() for ch in token):
        return None
    url = _trim_url(token)
    return url if is_card_url(url) else None


def _split_link_lines(block, take=None):
    """``block`` (a ``paragraph``) as a list of blocks: each link line its
    own paragraph, the runs of other lines between them paragraphs with
    their markup as written (todo 655). A link on its own line between
    paragraphs of text can then become a card, or a video embed, like a link
    that is the whole post. A paragraph with no link line, or one that IS a
    single link, comes back unchanged, byte for byte. ``take(url)``, when
    given, is asked once per link line in order; a line it declines stays
    an ordinary line of its run."""
    parser = _LinkLineSplitter()
    parser.feed(
        nh3.clean(
            block["value"] or "",
            tags=_SPLIT_ANALYSIS_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes=ALLOWED_URL_SCHEMES,
            link_rel=None,
        )
    )
    parser.close()

    entries = []  # (segment index, kind, html, is a link line, is blank)
    for index, segment in enumerate(parser.segments):
        if segment["kind"] == "opaque":
            entries.append((index, "opaque", "".join(segment["html"]), False, False))
            continue
        for line in segment["lines"]:
            url = _link_line_url(line)
            entries.append(
                (
                    index,
                    segment["kind"],
                    "".join(line["html"]),
                    url is not None and (take is None or take(url)),
                    not "".join(line["text"]).strip(),
                )
            )
    if not any(entry[3] for entry in entries):
        return [block]

    def wrap(kind, inner):
        return f"<p>{inner}</p>" if kind == "p" else inner

    def run_html(run):
        if all(entry[4] for entry in run):
            return ""  # only the empty line around a link: not a block
        parts = []
        position = 0
        while position < len(run):
            index, kind = run[position][:2]
            end = position
            while end < len(run) and run[end][0] == index:
                end += 1
            parts.append(
                wrap(kind, "<br>".join(entry[2] for entry in run[position:end]))
            )
            position = end
        return "".join(parts)

    values = []
    run: list[tuple] = []
    for entry in entries:
        if entry[3]:
            if run:
                values.append(run_html(run))
                run = []
            values.append(wrap(entry[1], entry[2]))
        else:
            run.append(entry)
    if run:
        values.append(run_html(run))
    values = [value for value in values if value]
    if len(values) <= 1:
        return [block]
    extra = {key: item for key, item in block.items() if key != "id"}
    return [{**block, "value": values[0]}] + [
        {**extra, "value": value} for value in values[1:]
    ]


def _split_link_paragraphs(value, budget=None):
    """Every ``paragraph`` block through ``_split_link_lines``, in order.

    Only a link line that can still become a card or an embed is split out:
    the first ``MAX_LINK_PREVIEWS_PER_BODY`` distinct card URLs and the first
    ``MAX_EMBED_URLS_PER_BODY`` distinct video URLs (when the host embeds),
    counting the body's own ``link_preview`` and embed blocks first. A
    repeat, or a link past its cap, would only ever be a link, so it stays a
    line of its run. That bounds what the split adds to a handful of blocks:
    a wall of links that saved before splitting existed (one paragraph of 101
    URL lines) still saves, as a few cards and a paragraph of links.

    ``budget`` is how many blocks the split may add (default: what
    ``MAX_BODY_BLOCKS`` leaves after ``value``). A paragraph whose split
    would go past it stays whole, its links auto-linked lines, and the card
    and video slots it would have used stay free (todo 657): the split never
    turns a body that fits into a "too many blocks" refusal.
    """
    if budget is None:
        budget = MAX_BODY_BLOCKS - len(value)
    embeds_on = get_setting("ALLOW_EMBED_BLOCKS")
    caps = {
        "card": get_setting("MAX_LINK_PREVIEWS_PER_BODY"),
        "video": get_setting("MAX_EMBED_URLS_PER_BODY"),
    }
    seen: dict[str, set[str]] = {"card": set(), "video": set()}
    for block in value:
        block_value = block.get("value")
        if block["type"] == "embed" and isinstance(block_value, str):
            seen["video"].add(block_value)
        elif block["type"] == "link_preview" and isinstance(block_value, dict):
            url = block_value.get("url")
            if isinstance(url, str):
                seen["card"].add(url.strip())

    def take(url):
        kind = "video" if embeds_on and is_supported_url(url) else "card"
        if url in seen[kind] or len(seen[kind]) >= caps[kind]:
            return False
        seen[kind].add(url)
        return True

    split = []
    for block in value:
        if block["type"] == "paragraph" and isinstance(block.get("value"), str):
            before = {kind: set(urls) for kind, urls in seen.items()}
            pieces = _split_link_lines(block, take)
            if len(pieces) - 1 > budget:
                seen.update(before)
                pieces = [block]
            budget -= len(pieces) - 1
            split.extend(pieces)
        else:
            split.append(block)
    return split


def _convert_video_paragraphs(value, embed_type):
    """Replace each URL-only ``paragraph`` block with an ``embed`` block.

    Stops at ``MAX_EMBED_URLS_PER_BODY`` distinct URLs, counting explicit
    embed blocks first: a body of bare links saved fine before this
    conversion existed, so it must never turn one into a 400. A link past
    the cap stays a paragraph, and a repeat of an already-counted URL
    converts at no cost.
    """
    counted = {block["value"] for block in value if block["type"] == embed_type}
    cap = get_setting("MAX_EMBED_URLS_PER_BODY")
    converted = []
    for block in value:
        if block["type"] == "paragraph":
            url = _sole_video_url(block["value"])
            if url and (url in counted or len(counted) < cap):
                counted.add(url)
                block = {**block, "type": embed_type, "value": url}
        converted.append(block)
    return converted


def _card_plan(value, link_type, existing):
    """``(candidates, chosen)`` for ``_convert_link_previews``: the card URL
    each block of ``value`` offers (``None`` when it offers none), and the
    first ``MAX_LINK_PREVIEWS_PER_BODY`` distinct ones, which get a card.
    Computed once per write and shared with the size check before the
    fetch, which needs to know which blocks will be reused cards (todo 539
    item 2)."""
    embeds_on = get_setting("ALLOW_EMBED_BLOCKS")
    candidates = []
    for block in value:
        url = None
        if block["type"] == link_type:
            url = block["value"]["url"].strip()
        elif block["type"] == "paragraph":
            # Trimmed like an auto-link, so "https://example.com." on its own
            # cards https://example.com, not a URL ending in "." (item 7) —
            # unless the stored body already has a card for the untrimmed
            # URL (one saved before trimming): an edit resends a card as its
            # link, and that card must be reused, not lost.
            url = _sole_url(block["value"], skip_code=True) or ""
            if url not in existing:
                url = _trim_url(url)
            if not is_card_url(url) or (embeds_on and is_supported_url(url)):
                url = None
        candidates.append(url)

    chosen = [
        url for url in dict.fromkeys(u for u in candidates if u) if is_card_url(url)
    ][: get_setting("MAX_LINK_PREVIEWS_PER_BODY")]
    return candidates, chosen


def _reused_card_urls(plan, existing):
    """``{block index: url}`` for every block that will be stored as a card
    the stored body already has: the first candidate of each chosen URL in
    ``existing``. Known before any fetch, since reuse never fetches."""
    candidates, chosen = plan
    reused = {url for url in chosen if url in existing}
    indices = {}
    for index, url in enumerate(candidates):
        if url in reused:
            reused.discard(url)
            indices[index] = url
    return indices


def _convert_link_previews(value, link_type, existing, plan=None):
    """Turn each link posted on its own into a ``link_preview`` card (todo 428).

    Candidates, in body order: a ``paragraph`` whose only content is one
    card URL (not a video the host embeds — the video conversion above runs
    first and "video wins"), and a resubmitted ``link_preview`` block, which
    is reduced to its URL. The first ``MAX_LINK_PREVIEWS_PER_BODY`` distinct
    URLs get a card: from ``existing`` (the stored body's cards, on edit —
    reused as stored, never refetched, with or without a fetcher) or from ONE
    bounded concurrent fetch. Each URL gets ONE card, at its first
    candidate. Any other candidate — a repeat of a carded URL, past the cap
    (never fetched), failed, or new while no fetcher is configured — stays or
    becomes a paragraph, which the auto-link pass then makes tappable.
    ``plan`` is ``_card_plan``'s answer for this ``value``, when the caller
    already has it.
    """
    candidates, chosen = plan or _card_plan(value, link_type, existing)
    # A card the stored body already shows is reused even with NO fetcher:
    # reuse needs no fetch, and a host that turns cards off (its kill
    # switch) must stop new cards, not strip existing ones on the next edit.
    cards = {url: existing[url] for url in chosen if url in existing}
    fetcher = get_fetcher()
    to_fetch = [url for url in chosen if url not in cards]
    if fetcher is not None and to_fetch:
        cards.update(fetch_snapshots(fetcher, to_fetch))

    # One card per URL: a repeat of a URL that already has a card stays (or
    # becomes) its link. Every size check counts a card as its URL alone,
    # which holds only while MAX_LINK_PREVIEWS_PER_BODY bounds the cards —
    # 100 blocks of one URL must not store 100 full cards (todo 535).
    carded = set()
    converted = []
    for block, url in zip(value, candidates):
        if url in cards and url not in carded:
            carded.add(url)
            block = {**block, "type": link_type, "value": cards[url]}
        elif block["type"] == link_type:
            if not url:
                continue  # a card with no link left has nothing to show
            block = {
                **block,
                "type": "paragraph",
                "value": f"<p>{html.escape(url, quote=False)}</p>",
            }
        converted.append(block)
    return converted


# Characters that end a sentence rather than a link: "see https://x.com."
_URL_TRAILING_PUNCTUATION = ".,;:!?"
_URL_BRACKETS = {")": "(", "]": "[", "}": "{"}
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _trim_url(url):
    """Drop sentence punctuation and closing brackets that belong to the
    prose around a link, not to the link: ``(https://x.com/a).`` links
    ``https://x.com/a``, while ``https://en.wikipedia.org/wiki/Foo_(bar)``
    keeps its balanced ``)``."""
    while url:
        last = url[-1]
        if last in _URL_TRAILING_PUNCTUATION:
            url = url[:-1]
        elif last in _URL_BRACKETS and url.count(last) > url.count(_URL_BRACKETS[last]):
            url = url[:-1]
        else:
            break
    return url


def _link_urls(text):
    """``text`` HTML-escaped, with each bare ``http(s)`` URL wrapped in an
    ``<a>``."""
    out = []
    position = 0
    for match in _URL_IN_TEXT.finditer(text):
        url = _trim_url(match.group())
        try:
            has_host = bool(urlsplit(url).hostname)
        except ValueError:
            has_host = False
        if not has_host:
            continue
        out.append(html.escape(text[position : match.start()], quote=False))
        out.append(f'<a href="{html.escape(url)}">{html.escape(url, quote=False)}</a>')
        position = match.start() + len(url)
    out.append(html.escape(text[position:], quote=False))
    return "".join(out)


class _AutoLinker(HTMLParser):
    """Re-emits sanitized paragraph HTML with every bare URL in its text
    turned into a link — except text already inside an ``<a>`` (it IS a
    link) or a ``<code>`` (a URL in a code sample is code). Tags are
    re-emitted as parsed; the result is sanitized again by the caller."""

    _SKIP = {"a", "code"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in self._SKIP:
            self.skip_depth += 1

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag in self._SKIP and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            self.out.append(html.escape(data, quote=False))
        else:
            self.out.append(_link_urls(data))


def autolink_rich_text(html_fragment):
    """Sanitized paragraph HTML with its bare ``http(s)`` URLs linked (todo
    428), so a link typed in prose is tappable on every client — the mobile
    composer never links, and a failed card falls back to this. Input and
    output are both passed through ``sanitize_rich_text``."""
    parser = _AutoLinker()
    parser.feed(sanitize_rich_text(html_fragment))
    parser.close()
    return sanitize_rich_text("".join(parser.out))


def _server_markup_chars(rich_text):
    """How many characters of ``rich_text``'s JSON are attributes the server
    sets on a link: each counted once per ``<a>`` start tag, and only there,
    so the same words typed as text or in a heading earn nothing."""
    total = 0
    for tag in _ANCHOR_START_TAG.findall(rich_text):
        for attribute in _SERVER_LINK_ATTRIBUTES:
            if attribute in tag:
                total += len(json.dumps(attribute)) - 2
    return total


def _measured_body_chars(value, rich_text_types, link_types):
    """A body's size as ``MAX_BODY_CHARS`` measures it (todo 535 items 1-2).

    - A ``link_preview`` card counts as its URL alone. Its other fields are
      written by the server, bounded by the field caps and by
      ``MAX_LINK_PREVIEWS_PER_BODY`` (one card per distinct URL, see
      ``_convert_link_previews``), so a card can never push a body that
      fit before the fetch over the cap after it, and the read envelope sent
      back on edit measures what the stored card did.
    - The link attributes the server sets are not counted, up to
      ``MAX_BODY_MARKUP_TOLERANCE``: an existing post near the cap stays
      editable when the server adds markup to every link.

    Shape-tolerant: it runs before the body's shape is validated."""
    measured = []
    markup = 0
    for block in value:
        if isinstance(block, dict):
            kind, inner = block.get("type"), block.get("value")
            if kind in link_types and isinstance(inner, dict):
                block = {**block, "value": {"url": inner.get("url")}}
            elif kind in rich_text_types and isinstance(inner, str):
                markup += _server_markup_chars(inner)
        measured.append(block)
    return len(json.dumps(measured)) - min(markup, MAX_BODY_MARKUP_TOLERANCE)


def _autolinked(memo, html_fragment):
    """``autolink_rich_text(html_fragment)``, computed once per write: the
    size check before the fetch and the cleaned pass see the same rich text,
    and the auto-linker is the costly step of both (todo 539 item 1)."""
    if html_fragment not in memo:
        memo[html_fragment] = autolink_rich_text(html_fragment)
    return memo[html_fragment]


def _stored_without_cards(
    value,
    rich_text_types,
    link_types,
    *,
    reused_cards=None,
    image_types=(),
    image_descriptions=None,
    autolinked=None,
):
    """``value`` as it would be stored if no NEW link became a card: a card
    the stored body already has (``reused_cards``, from
    ``_reused_card_urls``) stays a card, measured as its URL as the stored
    card was (todo 539 item 2); any other resent card is its fallback
    paragraph; every rich-text block is auto-linked; and an image is
    normalised as it will be stored, so a legacy bare PK measures its
    recovered alt (todo 539 item 3). A fetched card measures less than the
    auto-linked paragraph it replaces, so this measures at least what the
    stored body will, and can be checked BEFORE any page fetch (todo 535
    item 1)."""
    reused_cards = reused_cards or {}
    autolinked = {} if autolinked is None else autolinked
    link_type = min(link_types) if link_types else None
    stored = []
    for index, block in enumerate(value):
        if index in reused_cards:
            stored.append(
                {**block, "type": link_type, "value": {"url": reused_cards[index]}}
            )
            continue
        if block["type"] in link_types:
            url = block["value"]["url"].strip()
            if not url:
                continue
            block = {
                **block,
                "type": "paragraph",
                "value": f"<p>{html.escape(url, quote=False)}</p>",
            }
        if block["type"] in rich_text_types:
            block = {**block, "value": _autolinked(autolinked, block["value"] or "")}
        elif block["type"] in image_types:
            block = {
                **block,
                "value": _normalise_image_value(
                    block["value"], image_descriptions or {}
                ),
            }
        stored.append(block)
    return stored


# The forum index's welcome copy is CMS-authored, not user-submitted, so the
# allowlist is wider than a post body's: headings and a rule survive. Media
# embeds and images do not — the intro is a short welcome blurb, not an article,
# and an <iframe> from `expand_db_html` is not something a forum nav header
# should be able to inject into every client. Mirrors `ForumIndex.intro`'s
# `features` list, which is what an editor can actually author.
INTRO_ALLOWED_TAGS = ALLOWED_TAGS | {"h2", "h3", "h4", "hr"}

# Pre-expansion pass: everything above, minus Wagtail's `<embed>` placeholder,
# plus the two attributes `expand_db_html` needs to resolve a link.
INTRO_PRE_EXPAND_ATTRIBUTES = {
    **ALLOWED_ATTRIBUTES,
    "a": ALLOWED_ATTRIBUTES["a"] | {"linktype", "id"},
}


def serialize_forum_intro(html: str) -> str:
    """Expand + sanitize a ``RichTextField`` intro for API delivery.

    Wagtail stores rich text in a DB representation whose page/document links
    are ``<a linktype="page" id="N">`` placeholders — a client rendering it raw
    gets a dead anchor. ``expand_db_html`` resolves those to real hrefs (it
    hits the DB per referenced page; the intro is a handful of links on a
    publicly-cacheable response, so that cost is bounded).

    Sanitized TWICE, and the first pass is the load-bearing one. Expanding an
    ``<embed embedtype="media">`` calls Wagtail's oEmbed finder, which does a
    `requests.get` with **no timeout** — on this public, unauthenticated,
    CDN-fronted endpoint an unreachable provider would hang the request, and a
    failed fetch caches nothing, so every cache miss pays it again. An
    ``<embed embedtype="image">`` likewise triggers a real rendition (PIL
    resize + storage write + DB row). Both costs land *before* the output pass
    drops the resulting ``<iframe>``/``<img>``. So embeds are stripped
    BEFORE expansion, not after — sanitizing only the output would discard the
    markup while still paying for it.

    Stripping here rather than relying on `ForumIndex.intro`'s `features` list
    alone: that list governs the editor's toolbar, not what a fixture, an
    import, or a direct DB write can put in the column.

    The second pass is defense in depth against a CMS editor, not distrust of
    one: this payload reaches web *and* mobile clients, and only the web one
    runs DOMPurify.
    """
    if not html:
        return ""
    without_embeds = nh3.clean(
        html,
        tags=INTRO_ALLOWED_TAGS,
        attributes=INTRO_PRE_EXPAND_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
    )
    return nh3.clean(
        expand_db_html(without_embeds),
        tags=INTRO_ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )


# ImageBlock's stored keys. `image` is the PK; `alt_text`/`decorative` are the
# per-usage accessibility pair that ImageChooserBlock could not express.
_IMAGE_BLOCK_KEYS = {"image", "alt_text", "decorative"}
# Alt is TRUNCATED to this on write, never rejected — matching the upload
# endpoint's idiom for the same value ("a too-long alt is a UI slip, not a
# malformed request"). Rejecting would also be unenforceable: Wagtail's
# ImageBlock.alt_text is a bare CharBlock with no max_length, so a moderator can
# save a longer one in /cms/ and the API must still serve that post.
MAX_ALT_TEXT_LENGTH = 255


def image_block_pk(block_value):
    """The referenced image PK, or ``None`` if *block_value* holds no usable id.

    DELIBERATELY PERMISSIVE, because this is the READ-side accessor
    (build_forum_image_map, serialize_forum_body, the recent-topics thumbnail
    extractor) and read has the opposite failure mode to write: a rejection here
    does not surface as a 400, it makes the block serialise as
    ``{"type": "image", "value": null}`` and the image disappears from the post
    with no error anywhere. So this checks only what it needs to resolve the row.
    Shape enforcement belongs on the write path — see _valid_image_block_value.

    Accepts BOTH the ImageBlock dict and the pre-0037 bare PK: a body written
    before migration 0037 — or restored from an older revision, or sent by a web
    build deployed before the frontend switched shapes — still carries the int.
    """
    if isinstance(block_value, bool):  # bool is an int subclass
        return None
    if isinstance(block_value, int):
        return block_value
    if not isinstance(block_value, dict):
        return None
    pk = block_value.get("image")
    if not isinstance(pk, int) or isinstance(pk, bool):
        return None
    return pk


def _valid_image_block_value(block_value):
    """Strict WRITE-side shape check for an image block value (-> 400 on False).

    Unlike image_block_pk this rejects unknown keys and wrong sub-value types,
    because on write a malformed body should fail loudly rather than be stored.
    Length is not checked — _normalise_image_value truncates instead.
    """
    if image_block_pk(block_value) is None:
        return False
    if isinstance(block_value, int):
        return True
    if set(block_value) - _IMAGE_BLOCK_KEYS:
        return False
    # `alt_text`/`decorative` may be None, not just absent: Wagtail's own
    # ImageBlock._image_to_struct_value writes
    # `{"alt_text": image and image.contextual_alt_text, "decorative": ...}`,
    # which is None whenever an Image INSTANCE is assigned to the block rather
    # than a raw dict — the CMS admin, fixtures and `Post(body=[("image", img)])`
    # all take that path.
    alt = block_value.get("alt_text")
    if alt is not None and not isinstance(alt, str):
        return False
    decorative = block_value.get("decorative")
    if decorative is not None and not isinstance(decorative, bool):
        return False
    return True


def normalise_alt_text(alt: str) -> str:
    """The stored form of an image alt: a fixed point of the web composer's
    round trip (todos 443 and 554).

    The composer carries the alt through an HTML attribute, and the
    browser's parser normalises attribute values on the way in: CR and CRLF
    become LF, NUL becomes U+FFFD. No escape preserves a NUL (``&#0;`` also
    parses as U+FFFD), and a CR means nothing in alt text, so the API
    normalises on write instead: CRLF and lone CR become LF, and NUL
    (U+0000) is deleted rather than replaced, because Postgres refuses it in
    jsonb and in text columns (the save raised, and the API answered 500).
    U+FEFF is deleted too: JavaScript's ``trim()`` removes it and Python's
    ``str.strip()`` does not. The value is stripped, capped and stripped
    again, because a cap landing on whitespace would otherwise store a
    trailing space the composer's ``.trim()`` drops, and re-saving an
    untouched post would PATCH a changed alt.

    Before strip and cap: the cap must apply to the final form, and an alt
    of only NULs must not count as authored text. Shared by the body's image
    blocks and the upload's ``alt`` part (``api.views._alt_text``)."""
    alt = alt.replace("\r\n", "\n").replace("\r", "\n")
    alt = alt.replace("\x00", "").replace("\ufeff", "")
    return alt.strip()[:MAX_ALT_TEXT_LENGTH].rstrip()


def _without_nul(block):
    """``block`` with NUL (U+0000) deleted from every string in its value
    (todo 554): Postgres refuses NUL in the jsonb body, so a heading, quote,
    code or post-quote text carrying one raised on save and the API answered
    500, not 400. Deleted, like an alt's (``normalise_alt_text``)."""
    block_value = block.get("value")
    if isinstance(block_value, str):
        return {**block, "value": block_value.replace("\x00", "")}
    if isinstance(block_value, dict):
        return {
            **block,
            "value": {
                k: v.replace("\x00", "") if isinstance(v, str) else v
                for k, v in block_value.items()
            },
        }
    return block


def _normalise_image_value(block_value, descriptions):
    """Rewrite a validated image block value into the ImageBlock dict shape.

    Three things this closes:

    1. **Blank alt becomes ``decorative=True``, never ``alt_text=""``.**
       ``ImageBlock.clean()`` rejects "no alt text and not decorative". The API
       never reaches that clean() — block validation runs only through the admin
       form's ``BlockField``, not model ``full_clean()`` — so without this the
       API could mint posts a moderator cannot open in the CMS. A blank alt IS a
       decorative declaration; it is exactly what the composer's "Skip" means.
    2. **A legacy bare PK keeps its alt.** Pre-0037 bodies stored alt on
       ``Image.description``; normalising them to a blank ``alt_text`` would
       silently drop the author's words. *descriptions* carries the descriptions
       already fetched by the ownership query below, so this costs no extra
       query.
    3. **The alt is normalised on write (``normalise_alt_text``), so the alt
       the composer reads back is the alt that was stored.** See that
       function for what and why.
    """
    if isinstance(block_value, int):
        pk = block_value
        alt = descriptions.get(pk) or ""
        decorative = None
    else:
        pk = block_value["image"]
        # Both may be None — see image_block_pk on Wagtail writing that shape.
        alt = block_value.get("alt_text") or ""
        decorative = block_value.get("decorative")
    alt = normalise_alt_text(alt)
    # A blank alt IS decorative, whatever flag the client sent: `alt_text=""`
    # with `decorative=False` is exactly the pair ImageBlock.clean() refuses, so
    # honouring an explicit False here would store the one state the CMS cannot
    # open. An explicit True likewise wins, and blanks any supplied alt.
    decorative = bool(decorative) or not alt
    if decorative:
        alt = ""
    return {"image": pk, "alt_text": alt, "decorative": decorative}


def validate_forum_body(
    value,
    allowed_uploader_ids,
    user=None,
    existing_quote_ids=(),
    existing_link_previews=None,
    request=None,
):
    """Validate + sanitize a forum post body (raw StreamField list-of-dicts).

    1. Reject an oversized body (block count / total size) — bounds parse cost.
    2. Reject a structurally malformed body (``to_python`` dry-run) — 400, not 500.
    3. Sanitize each rich-text ("paragraph") block's HTML, stripping scripts,
       event-handler attributes, and disallowed tags/schemes.

    ``allowed_uploader_ids`` bounds which images an ``image`` block may
    reference: an image must live in the forum collection (audit L5 IDOR-by-
    reference) AND have been uploaded by one of these user ids (audit L21 —
    collection membership alone lets any member embed any other member's
    upload by guessing/observing its PK). Pass a set; ``None`` is a valid
    member for an account-deleted author's grandfathered images — Wagtail's
    ``Image.uploaded_by_user`` and ``Post.author`` both go ``SET_NULL`` on
    account deletion in the same operation, so a deleted author's pre-existing
    uploads carry ``uploaded_by_user_id=None`` right alongside the post.

    ``existing_quote_ids`` (edit only) lists the posts the stored body ALREADY
    quotes: they are exempt from the availability re-check, because an edit
    resends the whole body and a quoted post that has since been unpublished
    (or whose author has since blocked the editor) must not lock the author
    — or a moderator — out of saving any other change. Shape and caps still
    apply to every block; only NEWLY added quotes must resolve (todo 342).

    ``existing_link_previews`` (edit only) maps each URL the stored body
    already shows as a card to its stored value (``link_preview_snapshots``):
    an edit that keeps the link keeps that card as stored, with no fetch.

    Returns the cleaned value so the caller stores the safe version.
    """
    # Raise bare messages: this runs inside a field-level validator, and DRF
    # already keys field errors under the field name — a dict here would
    # double-nest the response as {"body": {"body": [...]}} (audit M14).
    if not isinstance(value, list):
        raise serializers.ValidationError(_("Invalid post body."))
    if len(value) > MAX_BODY_BLOCKS:
        raise serializers.ValidationError(_("Post body has too many blocks."))
    body_block = ForumBodyBlock()
    # Sanitize every rich-text block type, not a hardcoded name — a future
    # RichTextBlock added to ForumBodyBlock must not silently bypass sanitization.
    rich_text_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, RichTextBlock)
    }
    # A link_preview card is re-derived from its URL on every write (see
    # _convert_link_previews), so only the URL's type is checked below — the
    # read envelope (image_url: null) sent straight back must not 400.
    link_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, LinkPreviewBlock)
    }
    if (
        len(json.dumps(value)) > MAX_BODY_RAW_CHARS
        or _measured_body_chars(value, rich_text_types, link_types) > MAX_BODY_CHARS
    ):
        raise serializers.ValidationError(_("Post body is too large."))
    # ImageBlock is a StructBlock, ImageChooserBlock is a ChooserBlock — both
    # count as image blocks here, and BOTH must be recognised: bodies written
    # before migration 0037 (and any revision reverted to) still carry the bare
    # PK. Order matters below: `image` must be excluded from struct_types, or
    # the generic StructBlock branch would demand str sub-values and reject
    # every image (`image` is an int, `decorative` a bool).
    image_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, (ImageChooserBlock, ImageBlock))
    }

    # Reject unknown block types explicitly: StreamBlock.to_python silently
    # DROPS them (the client's content would vanish without an error). Also
    # enforce value types here — to_python/clean do NOT: an int paragraph
    # value reaches nh3.clean() and raises TypeError (500), and an int heading
    # persists, breaking the text-by-contract render assumption.
    struct_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, StructBlock) and name not in image_types | link_types
    }
    for block in value:
        if (
            not isinstance(block, dict)
            or block.get("type") not in body_block.child_blocks
        ):
            raise serializers.ValidationError(_("Invalid post body."))
        block_value = block.get("value")
        if block["type"] in struct_types:
            # Sub-values are typed per child block: an IntegerBlock (the
            # post_quote's `post`, todo 342) takes an int (never a bool),
            # everything else a string — so a text-by-contract sub-block
            # can never persist a non-string.
            children = body_block.child_blocks[block["type"]].child_blocks
            if not isinstance(block_value, dict) or not all(
                (
                    isinstance(v, int) and not isinstance(v, bool)
                    if isinstance(children.get(k), IntegerBlock)
                    else isinstance(v, str)
                )
                for k, v in block_value.items()
            ):
                raise serializers.ValidationError(_("Invalid post body."))
        elif block["type"] in image_types:
            # Either the ImageBlock dict or the pre-0037 bare PK. Membership and
            # uploader identity are verified below; shape only, here.
            if not _valid_image_block_value(block_value):
                raise serializers.ValidationError(_("Invalid post body."))
        elif block["type"] in link_types:
            if not isinstance(block_value, dict) or not isinstance(
                block_value.get("url"), str
            ):
                raise serializers.ValidationError(_("Invalid post body."))
        elif not isinstance(block_value, str):
            raise serializers.ValidationError(_("Invalid post body."))
    value = [_without_nul(block) for block in value]
    # A link on its own line becomes its own paragraph (todo 655), so the
    # video and card conversions below see it as a link posted on its own.
    # The split stays within what MAX_BODY_BLOCKS leaves, so a body that
    # passed the cap above never fails it after splitting (todo 657).
    value = _split_link_paragraphs(value)

    # Embed blocks (todo 344): a URL string, only when the host opted in,
    # only from a provider the host's finders accept. Then the ONE network
    # call this feature makes — resolving the provider's oEmbed data into
    # Wagtail's cache table — happens here at write time, bounded, so reads
    # never fetch (wagtail_forum/embeds.py).
    embed_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, EmbedBlock)
    }
    # A paragraph that is only a video link becomes an embed block here, on
    # the server, so every client gets the card (todo 421). Before the embed
    # checks below, so a converted block is capped and warmed like any
    # other. Only when the host allows embeds: with the flag off, the link
    # stays a paragraph and the post still saves.
    if get_setting("ALLOW_EMBED_BLOCKS") and embed_types:
        value = _convert_video_paragraphs(value, min(embed_types))
    embeds_to_warm = []
    embed_urls = [
        block["value"]
        for block in value
        if isinstance(block, dict) and block.get("type") in embed_types
    ]
    if embed_urls:
        if not get_setting("ALLOW_EMBED_BLOCKS"):
            raise serializers.ValidationError(_("Embeds are not enabled on this site."))
        for url in embed_urls:
            if not is_supported_url(url):
                raise serializers.ValidationError(
                    _(
                        "Unsupported embed URL — only links from allowed video providers work."
                    )
                )
        distinct = list(dict.fromkeys(embed_urls))  # each distinct URL once
        max_embeds = get_setting("MAX_EMBED_URLS_PER_BODY")
        if len(distinct) > max_embeds:
            raise serializers.ValidationError(
                _("A post may embed at most %(n)d videos.") % {"n": max_embeds}
            )
        # The provider fetch waits until nothing else can refuse the body
        # (below, before the card fetch): a refused body costs no fetch
        # (todo 539 item 3).
        embeds_to_warm = distinct

    # Structured post quotes (todo 342): a dict {post, text}; the quoted post
    # must exist, be visible and not be authored by someone block-paired
    # with the writer — a failure is a 400, never a silent strip. Distinct
    # quoted posts are capped, and the text is bounded (plain text by the
    # same contract as `quote`: consumers escape it at render time).
    quote_blocks = [
        block
        for block in value
        if isinstance(block, dict) and block.get("type") == "post_quote"
    ]
    if quote_blocks:
        max_quotes = get_setting("QUOTES_MAX_PER_POST")
        max_chars = get_setting("QUOTE_MAX_CHARS")
        ids = []
        for block in quote_blocks:
            qv = block.get("value")
            pid = qv.get("post") if isinstance(qv, dict) else None
            text = qv.get("text") if isinstance(qv, dict) else None
            if (
                not isinstance(pid, int)
                or isinstance(pid, bool)
                or pid < 1
                or not isinstance(text, str)
                or not text.strip()
            ):
                raise serializers.ValidationError(_("Invalid quote."))
            if len(text) > max_chars:
                raise serializers.ValidationError(
                    _("A quote may be at most %(n)d characters.") % {"n": max_chars}
                )
            if pid not in ids:
                ids.append(pid)
        if len(ids) > max_quotes:
            raise serializers.ValidationError(
                _("A post may quote at most %(n)d other posts.") % {"n": max_quotes}
            )
        new_ids = [pid for pid in ids if pid not in set(existing_quote_ids)]
        quotable = (
            resolve_quotable_posts(new_ids, user, request=request) if new_ids else {}
        )
        if any(pid not in quotable for pid in new_ids):
            # One message for missing, unpublished, restricted and blocked —
            # the endpoint must not be an oracle for what exists.
            raise serializers.ValidationError(
                _("One of the quoted posts is not available.")
            )

    # Non-image chooser blocks stay rejected outright: there is no upload/
    # validation path for them, so a caller could store a nonexistent PK
    # (breaks rendering) or reference a restricted asset by guessing IDs.
    other_chooser_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, ChooserBlock) and name not in image_types
    }
    for block in value:
        if isinstance(block, dict) and block.get("type") in other_chooser_types:
            raise serializers.ValidationError(
                _(
                    "Blocks referencing site objects (e.g. images) cannot be "
                    "submitted via the API."
                )
            )

    # Image blocks ARE allowed, but only when every referenced PK is an image in
    # the forum collection AND uploaded by an allowed user — the to_python
    # dry-run never resolves chooser PKs, so an unchecked id is an IDOR-by-
    # reference (audit L5); collection membership alone is not enough to stop
    # cross-member reuse (audit L21). One bulk query.
    # Shape validation above guarantees every one of these resolves to an int.
    image_ids = [
        image_block_pk(block["value"])
        for block in value
        if isinstance(block, dict) and block.get("type") in image_types
    ]
    image_descriptions = {}
    if image_ids:
        # `uploaded_by_user_id__in={..., None}` would silently match nothing for
        # the None member — SQL's `IN (NULL)` is never true, even for a NULL
        # column value. isnull=True is the only correct way to include it.
        uploader_ids = {uid for uid in allowed_uploader_ids if uid is not None}
        uploader_match = Q(uploaded_by_user_id__in=uploader_ids)
        if None in allowed_uploader_ids:
            uploader_match |= Q(uploaded_by_user_id__isnull=True)
        # `description` rides along so _normalise_image_value can recover the
        # alt of a legacy bare-PK block without a second query.
        image_descriptions = dict(
            get_image_model()
            .objects.filter(
                uploader_match,
                id__in=image_ids,
                collection=get_forum_image_collection(),
            )
            .values_list("id", "description")
        )
        valid_ids = set(image_descriptions)
        if any(image_id not in valid_ids for image_id in image_ids):
            raise serializers.ValidationError(
                _(
                    "Post body references an image that is not in the forum "
                    "image collection."
                )
            )

    # The cap holds for what is STORED, and auto-linking grows a body (todo
    # 448 item 4). Checked on the body as stored WITHOUT new cards, before
    # any network call: a fetched card measures less than the link it
    # replaces, so a body that passes here cannot go over the cap through
    # its cards, and a body refused here has cost no page or provider fetch
    # (todo 535 item 1, todo 539 items 2-3).
    existing_link_previews = existing_link_previews or {}
    card_plan = (
        _card_plan(value, min(link_types), existing_link_previews)
        if link_types
        else None
    )
    autolinked: dict[str, str] = {}
    if (
        _measured_body_chars(
            _stored_without_cards(
                value,
                rich_text_types,
                link_types,
                reused_cards=(
                    _reused_card_urls(card_plan, existing_link_previews)
                    if card_plan
                    else None
                ),
                image_types=image_types,
                image_descriptions=image_descriptions,
                autolinked=autolinked,
            ),
            rich_text_types,
            link_types,
        )
        > MAX_BODY_CHARS
    ):
        raise serializers.ValidationError(_("Post body is too large."))

    if embeds_to_warm:
        warm_embeds(embeds_to_warm)  # concurrently, one timeout window for the lot

    # Link cards (todo 428) last, after everything that can 400, so a body
    # that is about to be refused never costs a page fetch — but before the
    # dry-run, which then validates the blocks this produced.
    if link_types:
        value = _convert_link_previews(
            value, min(link_types), existing_link_previews, card_plan
        )

    try:
        body_block.to_python(value)
    except Exception as exc:  # malformed StreamField payload
        raise serializers.ValidationError(_("Invalid post body.")) from exc

    cleaned = []
    for block in value:
        if isinstance(block, dict) and block.get("type") in rich_text_types:
            block = {
                **block,
                "value": _autolinked(autolinked, block.get("value") or ""),
            }
        elif isinstance(block, dict) and block.get("type") in image_types:
            # Normalise to the ImageBlock dict on the way in, so a body written
            # by a pre-0037 client never persists a bare PK. That keeps
            # Wagtail's bulk_to_python off its mixed-shape path (its legacy
            # branch needs EVERY value in a batch to be an int) — the same
            # invariant migration 0037 establishes for existing rows.
            block = {
                **block,
                "value": _normalise_image_value(block["value"], image_descriptions),
            }
        cleaned.append(block)
    # Again on what is STORED, with the same measure: a stored body over the
    # cap would be refused when its author resends it unchanged on edit (todo
    # 448 item 4). The check before the fetch already bounds this, so it can
    # only fire on a link the auto-linker splits differently from the card
    # converter; a backstop, not the rule.
    if _measured_body_chars(cleaned, rich_text_types, link_types) > MAX_BODY_CHARS:
        raise serializers.ValidationError(_("Post body is too large."))
    return cleaned
