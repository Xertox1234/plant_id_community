"""Avatar follow-ups from PR #1028 (todo 587 items 1 and 7).

Item 1: deleting a thumbnail must also drop imagekit's cached "it exists"
state, or an avatar later stored under the freed name is never given one.
Item 7 (owner decision 2026-10-11): a wide-gamut photo is converted to sRGB
before its metadata, ICC profile included, is stripped.
"""

import io
import struct
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

User = get_user_model()

UPDATE_URL = "/api/v1/auth/user/update/"


def _png(name: str = "me.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 120, 40)).save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def _s15(value: float) -> bytes:
    return struct.pack(">i", round(value * 65536))


def _xyz(x: float, y: float, z: float) -> bytes:
    return b"XYZ \0\0\0\0" + _s15(x) + _s15(y) + _s15(z)


def _display_p3_profile() -> bytes:
    """A minimal ICC v2 matrix/TRC profile with Display P3's primaries
    (D50-adapted) and a 2.2 gamma: wide-gamut, like an iPhone photo's.
    Built here because Pillow can only create sRGB, LAB and XYZ profiles."""
    description = b"Test Display P3\0"
    desc = (
        b"desc\0\0\0\0"
        + struct.pack(">I", len(description))
        + description
        + b"\0" * 12  # no Unicode description
        + b"\0" * 70  # no ScriptCode description
    )
    gamma = b"curv\0\0\0\0" + struct.pack(">IH", 1, 0x0233) + b"\0\0"
    tags = [
        (b"desc", desc),
        (b"wtpt", _xyz(0.9642, 1.0, 0.8249)),
        (b"rXYZ", _xyz(0.5151, 0.2412, -0.0011)),
        (b"gXYZ", _xyz(0.2920, 0.6922, 0.0419)),
        (b"bXYZ", _xyz(0.1571, 0.0666, 0.7841)),
        (b"rTRC", gamma),
        (b"gTRC", gamma),
        (b"bTRC", gamma),
    ]
    offset = 128 + 4 + 12 * len(tags)
    table, data = b"", b""
    for signature, body in tags:
        body += b"\0" * (-len(body) % 4)
        table += signature + struct.pack(">II", offset + len(data), len(body))
        data += body
    size = offset + len(data)
    header = (
        struct.pack(">I", size)
        + b"\0\0\0\0"  # preferred CMM
        + bytes([2, 0x10, 0, 0])  # version 2.1
        + b"mntr"
        + b"RGB "
        + b"XYZ "
        + b"\0" * 12  # creation date
        + b"acsp"
        + b"\0" * 24  # platform, flags, manufacturer, model, attributes
        + b"\0\0\0\0"  # rendering intent: perceptual
        + _s15(0.9642)
        + _s15(1.0)
        + _s15(0.8249)
        + b"\0" * 48  # creator + reserved
    )
    assert len(header) == 128
    return header + struct.pack(">I", len(tags)) + table + data


# A saturated orange, as the camera recorded it in Display P3.
P3_ORANGE = (200, 100, 50)


class _AvatarTestCase(TestCase):
    client: APIClient  # DRF test client; TestCase declares Django's Client

    def setUp(self) -> None:
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="cy", password="TestPass123!"  # pragma: allowlist secret
        )
        self.client.force_authenticate(user=self.user)
        self._media = tempfile.TemporaryDirectory()
        self.addCleanup(self._media.cleanup)
        override = override_settings(MEDIA_ROOT=self._media.name)
        override.enable()
        self.addCleanup(override.disable)

    def _upload(self, upload: SimpleUploadedFile) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.patch(UPDATE_URL, {"avatar": upload}, format="multipart")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.user.refresh_from_db()

    def _stored_pixel(self) -> tuple:
        name = self.user.avatar.name
        assert name is not None, "no avatar stored"
        with default_storage.open(name, "rb") as stored:
            data = stored.read()
        with Image.open(io.BytesIO(data)) as image:
            self.assertNotIn("icc_profile", image.info)
            pixel = image.convert("RGB").getpixel((10, 10))
        assert isinstance(pixel, tuple)
        return pixel


class ThumbnailStateTests(_AvatarTestCase):
    """Item 1."""

    def _thumbnail_name_after_a_get(self) -> str:
        # The serializer generates the thumbnail, as the app's GET does.
        resp = self.client.get("/api/v1/auth/user/")
        self.assertIsNotNone(resp.data["avatar_thumbnail"])
        self.user.refresh_from_db()
        name: str = self.user.avatar_thumbnail.name
        return name

    def test_an_avatar_stored_under_a_freed_name_gets_a_thumbnail(self) -> None:
        self._upload(_png())
        first = self._thumbnail_name_after_a_get()
        self.assertTrue(default_storage.exists(first))

        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(
                self.client.delete("/api/v1/auth/user/avatar/").status_code, 200
            )
        self.assertFalse(default_storage.exists(first))

        # The same file name again: the same thumbnail name.
        self._upload(_png())
        second = self._thumbnail_name_after_a_get()
        self.assertEqual(second, first)
        self.assertTrue(
            default_storage.exists(second),
            "imagekit still thought the deleted thumbnail existed",
        )

    def test_a_replaced_avatar_frees_its_thumbnail_state_too(self) -> None:
        self._upload(_png())
        first = self._thumbnail_name_after_a_get()

        self._upload(_png(name="other.png"))  # deletes me.png and its thumbnail
        self.assertFalse(default_storage.exists(first))
        self._upload(_png())

        self.assertEqual(self._thumbnail_name_after_a_get(), first)
        self.assertTrue(default_storage.exists(first))


class WideGamutTests(_AvatarTestCase):
    """Item 7."""

    def _tagged(self, fmt: str, name: str, mode: str = "RGB") -> SimpleUploadedFile:
        colour = P3_ORANGE + ((255,) if mode == "RGBA" else ())
        buf = io.BytesIO()
        Image.new(mode, (64, 64), colour).save(
            buf, format=fmt, icc_profile=_display_p3_profile()
        )
        return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt}")

    def assert_converted_to_srgb(self, pixel: tuple) -> None:
        # In sRGB the same colour needs a stronger red and a weaker blue;
        # stored untagged as is, it would read back near P3_ORANGE.
        red, _green, blue = pixel[:3]
        self.assertGreater(red, P3_ORANGE[0] + 8, pixel)
        self.assertLess(blue, P3_ORANGE[2] - 8, pixel)

    def test_the_profile_is_usable(self) -> None:
        from PIL import ImageCms

        profile = ImageCms.ImageCmsProfile(io.BytesIO(_display_p3_profile()))
        self.assertEqual(profile.profile.xcolor_space, "RGB ")

    def test_a_display_p3_jpeg_is_stored_as_srgb(self) -> None:
        self._upload(self._tagged("JPEG", "me.jpg"))

        self.assert_converted_to_srgb(self._stored_pixel())

    def test_a_display_p3_png_with_alpha_is_stored_as_srgb(self) -> None:
        self._upload(self._tagged("PNG", "me.png", mode="RGBA"))

        self.assert_converted_to_srgb(self._stored_pixel())

    def test_an_untagged_photo_keeps_its_pixels(self) -> None:
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), P3_ORANGE).save(buf, format="PNG")

        self._upload(SimpleUploadedFile("me.png", buf.getvalue()))

        self.assertEqual(self._stored_pixel(), P3_ORANGE)

    def test_a_malformed_profile_is_stored_untagged_not_refused(self) -> None:
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), P3_ORANGE).save(
            buf, format="PNG", icc_profile=b"not an ICC profile"
        )

        self._upload(SimpleUploadedFile("me.png", buf.getvalue()))

        self.assertEqual(self._stored_pixel(), P3_ORANGE)
