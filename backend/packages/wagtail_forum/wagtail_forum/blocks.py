from wagtail import blocks
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images.blocks import ImageBlock


class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False)
    code = blocks.TextBlock()

    class Meta:
        icon = "code"


class PostQuoteBlock(blocks.StructBlock):
    """A quote OF A SPECIFIC POST (todo 342): the quoted post's id plus the
    quoted text. `text` is plain text by the same contract as `quote`
    (consumers escape at render time); `post` is validated on write
    (visible topic, author not block-paired with the writer, capped per
    body — api/sanitize.py) and resolved on read into a safe attribution
    envelope (api/serializers.py serialize_forum_body). The legacy `quote`
    block stays for free-form quotes."""

    post = blocks.IntegerBlock(min_value=1)
    text = blocks.TextBlock()

    class Meta:
        icon = "openquote"


class ForumBodyBlock(blocks.StreamBlock):
    """The only blocks a forum post may contain. No raw HTML."""

    heading = blocks.CharBlock(form_classname="title", max_length=200)
    # SECURITY: the "link" feature stores hrefs verbatim in the block's source
    # HTML. The DRF API (Plan 1C) MUST serialize this body via expand_db_html()
    # (so the link rewriter runs) — NOT raw `value.source` — and must sanitize
    # rich text on write, since direct API POSTs bypass the editor's javascript:
    # href filtering. See project memory note for Plan 1C.
    paragraph = blocks.RichTextBlock(
        features=["bold", "italic", "link", "ol", "ul", "code"]
    )
    quote = blocks.BlockQuoteBlock()
    post_quote = PostQuoteBlock()
    code = CodeBlock()
    # ImageBlock (Wagtail 6.3+), not ImageChooserBlock: alt text belongs to the
    # USAGE, not the Image row. A chooser stores a bare PK and leaves alt on
    # Image.description, so one photo carries identical alt everywhere it
    # appears, cannot be re-worded without re-uploading, and has no way to say
    # "decorative" as distinct from "nobody filled this in". ImageBlock stores
    # {image, alt_text, decorative} per usage and fixes all three.
    #
    # Wagtail reads the OLD bare-PK shape transparently (ImageBlock.to_python /
    # bulk_to_python special-case an int), so this swap stays readable with no
    # data migration — but 0037 normalises anyway, because bulk_to_python's
    # legacy path requires EVERY value in a batch to be an int: one stale PK
    # sharing a batch with a new dict falls through to StructBlock.
    # bulk_to_python and raises on int.get(). That batch is Wagtail's own
    # (admin listings, search indexing, ReferenceIndex) — the forum's read path
    # walks raw_data and never resolves the StreamValue, so an unmigrated row
    # would break the CMS while every API test stayed green.
    image = ImageBlock(required=True)
    # Video/oEmbed (todo 344). Declared unconditionally — a StreamField's
    # block list is schema (migration 0031) and must not vary per host —
    # but INERT unless the host sets WAGTAILFORUM_ALLOW_EMBED_BLOCKS: the API
    # refuses the block on write, and the read envelope carries no player
    # URL, so a CMS-inserted embed on a host that has not opted in renders
    # as a plain link. See wagtail_forum/embeds.py for the posture.
    embed = EmbedBlock(help_text="A video URL from a provider the site allows")

    class Meta:
        required = False
