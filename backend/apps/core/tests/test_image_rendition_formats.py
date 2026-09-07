"""
Rendition output formats (todo 363, Wagtail 8.0).

Wagtail 8.0 stopped converting AVIF and WebP originals to PNG when building
renditions: `Filter.run()`'s `default_conversions` dropped from
`{"avif": "png", "bmp": "png", "webp": "png", "heic": "jpeg"}` (7.4.3) to
`{"bmp": "png", "heic": "jpeg"}` (8.0), so those two formats now fall through
to `output_format = original_format`.

We deliberately took the new default rather than pinning the old behaviour
with `WAGTAILIMAGES_FORMAT_CONVERSIONS` — browser support for WebP is
universal and the smaller renditions are the point. This test is that
decision's guardrail: it fails loudly if a future upgrade (or a stray
`WAGTAILIMAGES_FORMAT_CONVERSIONS` setting) silently changes what format
users' images are served in.

Note the change is invisible on already-rendered images: renditions are
cached on `(image, filter_spec, focal_point_key)`, not on output format, so
existing WebP originals keep serving their previously-cached PNG renditions
until something invalidates them. Mixed formats coexisting is expected.
"""

import io

import pytest
from django.core.files.images import ImageFile
from PIL import Image as PILImage
from wagtail.images import get_image_model


@pytest.fixture(autouse=True)
def _isolated_media_root(settings, tmp_path):
    """Keep probe uploads and their renditions out of the real MEDIA_ROOT.

    The DB rows roll back with the transaction but the written files do not,
    so without this every run leaves orphans behind.
    """
    settings.MEDIA_ROOT = str(tmp_path)


def _upload(pil_format, filename):
    """Create a real Wagtail Image from an in-memory file of the given format."""
    buf = io.BytesIO()
    PILImage.new("RGB", (400, 300), (10, 120, 60)).save(buf, format=pil_format)
    buf.seek(0)
    return get_image_model().objects.create(
        title=filename, file=ImageFile(buf, name=filename)
    )


def _rendition_extension(image):
    return image.get_rendition("width-200").file.name.rsplit(".", 1)[-1].lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pil_format,filename",
    [("WEBP", "rendition-probe.webp"), ("AVIF", "rendition-probe.avif")],
)
def test_modern_format_original_keeps_its_format_in_the_rendition(pil_format, filename):
    """The Wagtail 8.0 change: both of these produced 'png' on 7.4.3.

    AVIF is asserted as well as WebP because the two were removed from
    `default_conversions` together, and AVIF additionally needs a Pillow
    build with an AVIF *encoder* — a rendition-time requirement that an
    upload-time check would not catch. Pillow 12.3.0 (our pin) bundles one.
    """
    assert _rendition_extension(_upload(pil_format, filename)) == pil_format.lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pil_format,filename,expected",
    [
        ("PNG", "rendition-probe.png", {"png"}),
        ("JPEG", "rendition-probe.jpg", {"jpg", "jpeg"}),
    ],
)
def test_formats_unaffected_by_the_8_0_change_are_unchanged(
    pil_format, filename, expected
):
    """PNG and JPEG were never in `default_conversions`; they must not move."""
    assert _rendition_extension(_upload(pil_format, filename)) in expected
