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

import json

import nh3
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from wagtail.blocks import ChooserBlock, IntegerBlock, RichTextBlock, StructBlock
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images import get_image_model
from wagtail.images.blocks import ImageChooserBlock
from wagtail.rich_text import expand_db_html

from ..blocks import ForumBodyBlock
from ..collections import get_forum_image_collection
from ..conf import get_setting
from ..embeds import is_supported_url, warm_embeds
from ..quotes import resolve_quotable_posts

# Allowlist scoped to ForumBodyBlock's RichTextBlock features (bold, italic, link,
# ol, ul, code) plus the structural tags Wagtail emits. nh3 drops everything else,
# including all event-handler attributes and <script>/<svg>/<img> etc.
ALLOWED_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a", "code"}
ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}

# Bound a single post body. Generous for a forum post; caps parse cost + storage.
MAX_BODY_BLOCKS = 100
MAX_BODY_CHARS = 100_000


def sanitize_rich_text(html):
    """Return an XSS-safe subset of *html* (nh3 allowlist)."""
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
    )


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


def validate_forum_body(value, allowed_uploader_ids, user=None, existing_quote_ids=()):
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

    Returns the cleaned value so the caller stores the safe version.
    """
    # Raise bare messages: this runs inside a field-level validator, and DRF
    # already keys field errors under the field name — a dict here would
    # double-nest the response as {"body": {"body": [...]}} (audit M14).
    if not isinstance(value, list):
        raise serializers.ValidationError(_("Invalid post body."))
    if len(value) > MAX_BODY_BLOCKS:
        raise serializers.ValidationError(_("Post body has too many blocks."))
    if len(json.dumps(value)) > MAX_BODY_CHARS:
        raise serializers.ValidationError(_("Post body is too large."))
    body_block = ForumBodyBlock()
    image_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, ImageChooserBlock)
    }

    # Reject unknown block types explicitly: StreamBlock.to_python silently
    # DROPS them (the client's content would vanish without an error). Also
    # enforce value types here — to_python/clean do NOT: an int paragraph
    # value reaches nh3.clean() and raises TypeError (500), and an int heading
    # persists, breaking the text-by-contract render assumption.
    struct_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, StructBlock)
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
            # An image chooser value is the referenced image's integer PK; bool
            # is an int subclass, so exclude it. Membership is verified below.
            if not isinstance(block_value, int) or isinstance(block_value, bool):
                raise serializers.ValidationError(_("Invalid post body."))
        elif not isinstance(block_value, str):
            raise serializers.ValidationError(_("Invalid post body."))

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
        warm_embeds(distinct)  # concurrently, one timeout window for the lot

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
        quotable = resolve_quotable_posts(new_ids, user) if new_ids else {}
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
    image_ids = [
        block["value"]
        for block in value
        if isinstance(block, dict) and block.get("type") in image_types
    ]
    if image_ids:
        # `uploaded_by_user_id__in={..., None}` would silently match nothing for
        # the None member — SQL's `IN (NULL)` is never true, even for a NULL
        # column value. isnull=True is the only correct way to include it.
        uploader_ids = {uid for uid in allowed_uploader_ids if uid is not None}
        uploader_match = Q(uploaded_by_user_id__in=uploader_ids)
        if None in allowed_uploader_ids:
            uploader_match |= Q(uploaded_by_user_id__isnull=True)
        valid_ids = set(
            get_image_model()
            .objects.filter(
                uploader_match,
                id__in=image_ids,
                collection=get_forum_image_collection(),
            )
            .values_list("id", flat=True)
        )
        if any(image_id not in valid_ids for image_id in image_ids):
            raise serializers.ValidationError(
                _(
                    "Post body references an image that is not in the forum "
                    "image collection."
                )
            )

    try:
        body_block.to_python(value)
    except Exception as exc:  # malformed StreamField payload
        raise serializers.ValidationError(_("Invalid post body.")) from exc

    # Sanitize every rich-text block type, not a hardcoded name — a future
    # RichTextBlock added to ForumBodyBlock must not silently bypass sanitization.
    rich_text_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, RichTextBlock)
    }
    cleaned = []
    for block in value:
        if isinstance(block, dict) and block.get("type") in rich_text_types:
            block = {**block, "value": sanitize_rich_text(block.get("value") or "")}
        cleaned.append(block)
    return cleaned
