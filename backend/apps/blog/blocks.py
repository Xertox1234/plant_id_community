"""Custom StreamField blocks for the blog (todo 306).

Wagtail's stock `ImageChooserBlock.get_api_representation()` falls back to
`Block.get_api_representation()`'s default (`get_prep_value(value)`), which
for a chooser block is just the image's bare PK integer — the API contract
documented in `wagtail.api.v2.serializers.StreamField`'s own docstring
("foreign keys are represented ... by an integer"). A client has no way to
turn that integer into a renderable URL, so any `plant_spotlight.image`
block was unrenderable on the web. Resolve it to a rendition dict instead —
same `{id, url, alt, width, height}` shape and `request.build_absolute_uri()`
mechanism the forum's `serialize_image_for_api`
(`packages/wagtail_forum/wagtail_forum/api/serializers.py`) already
established and validated in production for the identical problem
(StreamField image block -> renderable URL). `apps/blog/api/serializers.py`
originally used Wagtail's `get_full_url()` for page/author URLs instead —
that resolves the host via Wagtail's Sites framework, which this deploy
had no Site record for beyond the seeded `localhost:80` default, so every
URL it built resolved to `http://localhost/...` in production (todo 308).
That file now uses `request.build_absolute_uri()` too, for the same reason
this block always has: it reads the actual incoming request's host
directly, no Site involved.

`PlantSpotlightBlock` (todo 376) carries the stock-photo credit that
Unsplash's and Pexels' terms require on display: `image_credit` text plus an
optional `image_credit_url`. The URL is rendered as a link only when it is an
absolute http(s) URL — see `safe_http_url`.
"""

from apps.core.utils.urls import safe_http_url  # noqa: F401  (re-exported)
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock
from wagtail.images.models import SourceImageIOError

BLOG_IMAGE_BLOCK_RENDITION = "fill-800x400"


class APIImageChooserBlock(ImageChooserBlock):
    """`ImageChooserBlock` that resolves to a rendition dict in the API."""

    def get_api_representation(self, value, context=None):
        if not value:
            return None
        try:
            rendition = value.get_rendition(BLOG_IMAGE_BLOCK_RENDITION)
        except (SourceImageIOError, OSError):
            # Missing media file (e.g. wiped on redeploy) — degrade to None,
            # same as _get_post_image (api/serializers.py) for the identical
            # condition. NOT an {"error": ...} dict: that isn't a valid
            # ImageBlockValue (no id/url/width/height), so a client guarding
            # only on `value.image` truthiness would render `<img
            # src="undefined">` instead of skipping the image (code review,
            # todo 306).
            return None
        request = (context or {}).get("request")
        url = rendition.url
        if request is not None:
            url = request.build_absolute_uri(url)
        return {
            "id": value.id,
            "url": url,
            # Author-supplied Image.description (Wagtail's alt-text field),
            # not image.title (the upload filename — filename-as-alt is an
            # accessibility anti-pattern). Matches serialize_image_for_api's
            # M7 rationale.
            "alt": value.description,
            "width": rendition.width,
            "height": rendition.height,
        }


def unsplash_credit_parts(credit):
    """`(credit_lead, unsplash_href)` for a stored credit text.

    "Photo by X on Unsplash": Unsplash's guidelines want the photographer AND
    Unsplash linked (todo 438), so the lead ("Photo by X") is split off for the
    photographer's link and Unsplash gets its referral link. Both are "" for
    any other credit. This is the one place the split is derived — for the
    Wagtail template context and the API representation alike — so the web
    renders these values instead of re-deriving them from the text (todo 442).
    """
    # Lazy: importing plant_identification.services at module load would run
    # that package's __init__ (the identification stack) while the blog models
    # are still loading.
    from apps.plant_identification.services.unsplash_service import (
        UNSPLASH_CREDIT_SUFFIX,
        UNSPLASH_HOME_URL,
    )

    credit = (credit or "").strip()
    if credit.endswith(UNSPLASH_CREDIT_SUFFIX) and len(credit) > len(
        UNSPLASH_CREDIT_SUFFIX
    ):
        return credit[: -len(UNSPLASH_CREDIT_SUFFIX)], UNSPLASH_HOME_URL
    return "", ""


class PlantSpotlightBlock(blocks.StructBlock):
    """`plant_spotlight` StructBlock; exposes a vetted credit link to templates.

    The API representation carries the children plus the same derived credit
    parts the template gets (`credit_lead`, `unsplash_href`; todo 442).
    """

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        context["credit_href"] = safe_http_url(value.get("image_credit_url") or "")
        context["credit_lead"], context["unsplash_href"] = unsplash_credit_parts(
            value.get("image_credit")
        )
        return context

    def get_api_representation(self, value, context=None):
        api = super().get_api_representation(value, context=context)
        api["credit_lead"], api["unsplash_href"] = unsplash_credit_parts(
            value.get("image_credit")
        )
        return api
