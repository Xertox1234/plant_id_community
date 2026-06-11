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
from rest_framework import serializers
from wagtail.blocks import ChooserBlock, RichTextBlock, StructBlock

from ..blocks import ForumBodyBlock

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


def validate_forum_body(value):
    """Validate + sanitize a forum post body (raw StreamField list-of-dicts).

    1. Reject an oversized body (block count / total size) — bounds parse cost.
    2. Reject a structurally malformed body (``to_python`` dry-run) — 400, not 500.
    3. Sanitize each rich-text ("paragraph") block's HTML, stripping scripts,
       event-handler attributes, and disallowed tags/schemes.

    Returns the cleaned value so the caller stores the safe version.
    """
    # Raise bare messages: this runs inside a field-level validator, and DRF
    # already keys field errors under the field name — a dict here would
    # double-nest the response as {"body": {"body": [...]}} (audit M14).
    if not isinstance(value, list):
        raise serializers.ValidationError("Invalid post body.")
    if len(value) > MAX_BODY_BLOCKS:
        raise serializers.ValidationError("Post body has too many blocks.")
    if len(json.dumps(value)) > MAX_BODY_CHARS:
        raise serializers.ValidationError("Post body is too large.")
    body_block = ForumBodyBlock()

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
            raise serializers.ValidationError("Invalid post body.")
        block_value = block.get("value")
        if block["type"] in struct_types:
            if not isinstance(block_value, dict) or not all(
                isinstance(v, str) for v in block_value.values()
            ):
                raise serializers.ValidationError("Invalid post body.")
        elif not isinstance(block_value, str):
            raise serializers.ValidationError("Invalid post body.")

    # Reject chooser blocks (image, …) outright on the API path: the dry-run
    # below does not resolve the referenced PK, so a caller could store a
    # nonexistent ID (breaks rendering) or reference a restricted-collection
    # asset by guessing IDs — an IDOR-by-reference (audit L5). There is no
    # forum upload path yet; Spec 2 adds one with collection validation.
    chooser_types = {
        name
        for name, block in body_block.child_blocks.items()
        if isinstance(block, ChooserBlock)
    }
    for block in value:
        if isinstance(block, dict) and block.get("type") in chooser_types:
            raise serializers.ValidationError(
                "Blocks referencing site objects (e.g. images) cannot be "
                "submitted via the API."
            )

    try:
        body_block.to_python(value)
    except Exception as exc:  # malformed StreamField payload
        raise serializers.ValidationError("Invalid post body.") from exc

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
