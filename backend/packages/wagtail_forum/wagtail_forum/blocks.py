from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class CodeBlock(blocks.StructBlock):
    language = blocks.CharBlock(required=False)
    code = blocks.TextBlock()

    class Meta:
        icon = "code"


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
    code = CodeBlock()
    image = ImageChooserBlock()

    class Meta:
        required = False
