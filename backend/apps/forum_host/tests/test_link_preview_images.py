"""Preview-card images (todo 428 slice B).

A card's image is the page's og:image, downloaded once at write time through
the SSRF-pinned path, validated like an upload, re-encoded and stored on our
own media storage. No test here touches the network: page previews are
patched, image connections are fakes (or, for the watchdog, a loopback
server), and storage is Django's in-memory backend on a media origin of our
own.
"""

import hashlib
import io
import os
import socket
import threading
import time
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import pytest
from apps.forum_host import constants
from apps.forum_host import link_preview as lp
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.test import override_settings
from PIL import Image
from rest_framework.test import APIClient
from wagtail_forum.link_previews import is_cached_image_name, link_preview_envelope

User = get_user_model()

MEDIA_URL = "https://media.houseplant.test/media/"
PAGE_URL = "https://93.184.216.34/article"
IMAGE_URL = "https://93.184.216.34/og.png"
IMAGE_NAME = (
    "forum/link-previews/" + hashlib.sha256(IMAGE_URL.encode()).hexdigest() + ".webp"
)


@pytest.fixture(autouse=True)
def media_storage():
    with override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            },
        },
        MEDIA_URL=MEDIA_URL,
    ):
        yield


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


# --- fakes ---------------------------------------------------------------------


def png(size=(64, 32), mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, size).save(buffer, "PNG")
    return buffer.getvalue()


def noise_png(side):
    """Incompressible, so the PNG is about 3 bytes per pixel."""
    buffer = io.BytesIO()
    Image.frombytes("RGB", (side, side), os.urandom(side * side * 3)).save(
        buffer, "PNG"
    )
    return buffer.getvalue()


def bmp():
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16)).save(buffer, "BMP")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status=200, headers=None, body=b""):
        self.status = status
        self.headers = headers or {}
        self.body = body

    def getheader(self, name):
        return self.headers.get(name)

    def read1(self, size):
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def read(self, size):
        raise AssertionError("the image path must read with read1")

    def close(self):
        pass


class FakeConnection:
    """Stands in for ``_open_connection``'s result. ``sock`` is a real
    (socketpair) socket, so the deadline watchdog has something to shut."""

    def __init__(self, response):
        self.response = response
        self.sock, self._peer = socket.socketpair()

    def connect(self):
        pass

    def request(self, method, path, headers):
        pass

    def getresponse(self):
        return self.response

    def close(self):
        self.sock.close()
        self._peer.close()


def serve(*responses):
    return patch.object(
        lp,
        "_open_connection",
        side_effect=[FakeConnection(response) for response in responses],
    )


def image_response(body, content_type="image/png", **headers):
    return FakeResponse(200, {"Content-Type": content_type, **headers}, body)


def redirect(location):
    return FakeResponse(302, {"Location": location})


def page(image_url=IMAGE_URL):
    return patch.object(
        lp,
        "fetch_link_preview",
        return_value={
            "url": PAGE_URL,
            "title": "Monstera care",
            "description": "Light, water, soil.",
            "image_url": image_url,
            "site_name": "Plant Library",
            "domain": "93.184.216.34",
            "available": True,
        },
    )


def stored_names():
    try:
        return default_storage.listdir("forum/link-previews")[1]
    except FileNotFoundError:
        return []


# --- the stored copy -------------------------------------------------------------


def test_the_card_image_is_our_re_encoded_copy_on_our_media_origin():
    with page(), serve(image_response(png())):
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["title"] == "Monstera care"
    assert snapshot["image"] == IMAGE_NAME
    assert is_cached_image_name(snapshot["image"])
    with default_storage.open(IMAGE_NAME) as stored:
        assert Image.open(stored).format == "WEBP"

    envelope = link_preview_envelope({"url": PAGE_URL, **snapshot})
    assert envelope["image_url"] == MEDIA_URL + IMAGE_NAME
    assert urlsplit(envelope["image_url"]).netloc == urlsplit(MEDIA_URL).netloc
    assert "93.184.216.34" not in envelope["image_url"]


def test_a_second_post_with_the_same_image_does_not_download_it_again():
    with page(), serve(image_response(png())) as opened:
        first = lp.link_preview_snapshot(PAGE_URL)
        second = lp.link_preview_snapshot("https://93.184.216.34/other-article")

    assert first["image"] == second["image"] == IMAGE_NAME
    assert opened.call_count == 1


def test_exif_is_stripped_and_orientation_applied_before_storing():
    exif = Image.Exif()
    exif[0x0112] = 6  # orientation: rotate 90 degrees
    exif[0x010F] = "CameraMaker"
    exif[0x8825] = {1: "N", 2: (37.0, 46.0, 30.0)}  # GPS latitude
    source = io.BytesIO()
    Image.new("RGB", (20, 10), "red").save(source, "JPEG", exif=exif)
    assert Image.open(io.BytesIO(source.getvalue())).getexif()  # the fixture has EXIF

    # image/jpg is not a registered type, but CDNs send it; it is accepted.
    with page(), serve(image_response(source.getvalue(), "image/jpg")):
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    with default_storage.open(snapshot["image"]) as stored:
        image = Image.open(stored)
        image.load()
    assert dict(image.getexif()) == {}
    assert not {"exif", "xmp", "icc_profile"} & set(image.info)
    assert image.size == (10, 20)


# --- refusals: a card without an image, never a broken card ----------------------


REFUSED = {
    "an html content type": lambda: image_response(png(), "text/html"),
    "no content type": lambda: FakeResponse(200, {}, png()),
    "a declared size over the cap": lambda: image_response(
        png(), **{"Content-Length": str(constants.LINK_PREVIEW_IMAGE_MAX_BYTES + 1)}
    ),
    "a streamed size over the cap": lambda: image_response(noise_png(1000)),
    "bytes that are not an image": lambda: image_response(b"<svg></svg>"),
    "a truncated image": lambda: image_response(noise_png(64)[:2000]),
    "a format outside the allowlist": lambda: image_response(bmp()),
    "a decompression bomb": lambda: image_response(png((4000, 4000), mode="1")),
    "a side over the limit": lambda: image_response(
        png((constants.LINK_PREVIEW_IMAGE_MAX_SIDE + 1, 8))
    ),
    "a non-2xx status": lambda: FakeResponse(404, {"Content-Type": "image/png"}, png()),
}


@pytest.mark.parametrize("response", REFUSED.values(), ids=REFUSED.keys())
def test_a_refused_image_leaves_the_card_without_an_image(response):
    with page(), serve(response()):
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["title"] == "Monstera care"
    assert snapshot["image"] == ""
    assert stored_names() == []


def test_a_plain_http_image_url_is_not_downloaded():
    """The page parser already keeps only HTTPS og:images; the image cache
    checks again rather than trusting its caller."""
    with page("http://93.184.216.34/og.png"), serve(image_response(png())) as opened:
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["image"] == ""
    opened.assert_not_called()


def test_the_streamed_cap_fixture_is_a_valid_image_over_the_cap():
    """Keeps the streamed-cap case honest: without the cap it would store."""
    body = noise_png(1000)
    assert len(body) > constants.LINK_PREVIEW_IMAGE_MAX_BYTES
    assert lp._reencode_image(body) is not None


def test_an_image_bug_still_returns_the_card():
    with (
        page(),
        patch.object(lp, "_cache_preview_image", side_effect=RuntimeError("boom")),
    ):
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot == {
        "title": "Monstera care",
        "description": "Light, water, soil.",
        "site_name": "Plant Library",
        "domain": "93.184.216.34",
        "image": "",
    }


# --- redirects -----------------------------------------------------------------


def test_up_to_three_redirects_are_followed():
    hops = [redirect(f"https://93.184.216.34/hop{n}") for n in range(1, 4)]
    with page(), serve(*hops, image_response(png())) as opened:
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["image"] == IMAGE_NAME
    assert opened.call_count == 4


def test_a_fourth_redirect_is_not_followed():
    hops = [redirect(f"https://93.184.216.34/hop{n}") for n in range(1, 5)]
    with page(), serve(*hops, image_response(png())) as opened:
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["image"] == ""
    assert opened.call_count == 4


@pytest.mark.parametrize(
    "location",
    [
        "http://93.184.216.34/og.png",  # a downgrade to plain HTTP
        "https://127.0.0.1/og.png",  # SSRF: loopback
        "https://169.254.169.254/latest/meta-data/",  # SSRF: cloud metadata
    ],
)
def test_a_redirect_off_public_https_is_not_followed(location):
    with page(), serve(redirect(location), image_response(png())) as opened:
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["image"] == ""
    assert opened.call_count == 1


# --- the budget ----------------------------------------------------------------


def test_no_download_starts_without_time_left_in_the_budget():
    with (
        page(),
        serve() as opened,
        patch.object(constants, "LINK_PREVIEW_SNAPSHOT_MARGIN_SECONDS", 4.5),
    ):
        snapshot = lp.link_preview_snapshot(PAGE_URL)

    assert snapshot["title"] == "Monstera care"
    assert snapshot["image"] == ""
    opened.assert_not_called()


class DripResponse(FakeResponse):
    """One byte per read1, 50 ms apart, for up to 10 s."""

    def __init__(self):
        super().__init__(200, {"Content-Type": "image/png"})
        self.reads = 0

    def read1(self, size):
        time.sleep(0.05)
        self.reads += 1
        return b"x" if self.reads < 200 else b""


def test_a_body_that_drips_past_the_deadline_is_abandoned():
    target = lp._Target(IMAGE_URL, "https", "93.184.216.34", 443, "93.184.216.34")
    started = time.monotonic()
    with serve(DripResponse()):
        assert lp._fetch_image(target, time.monotonic() + 0.3) is None

    assert time.monotonic() - started < 1.0


def test_a_body_the_deadline_cut_off_is_not_an_image():
    """The watchdog's shutdown ends a read as an empty read, like a normal
    end of body; the bytes read so far are not an image."""

    class CutOff(FakeResponse):
        def read1(self, size):
            time.sleep(0.2)
            return b""

    response = CutOff(200, {"Content-Type": "image/png"})
    assert lp._read_image(response, time.monotonic() + 0.1) is None


def test_a_body_short_of_its_content_length_is_not_an_image():
    response = image_response(png())
    response.length = 100  # http.client's count of bytes still owed
    assert lp._read_image(response, time.monotonic() + 5) is None


def _loopback_drip(prefix):
    """A server that answers with ``prefix`` then drips a byte every 50 ms
    for 3 s. Returns (server, port, thread)."""
    server = socket.create_server(("127.0.0.1", 0))

    def drip():
        connection, _ = server.accept()
        with connection:
            connection.recv(4096)
            connection.sendall(prefix)
            for _ in range(60):
                try:
                    connection.sendall(b"X")
                except OSError:
                    return
                time.sleep(0.05)

    thread = threading.Thread(target=drip, daemon=True)
    thread.start()
    return server, server.getsockname()[1], thread


@pytest.mark.parametrize(
    "scheme, prefix",
    [
        # The status line arrives, the headers never finish.
        ("http", b"HTTP/1.1 200 OK\r\n"),
        # A TLS handshake record announcing 16 KB, then dripped.
        ("https", b"\x16\x03\x03\x40\x00"),
    ],
    ids=["headers", "tls-handshake"],
)
def test_the_watchdog_ends_a_response_that_drips_past_the_deadline(scheme, prefix):
    """Nothing dripped outlives the deadline. Headers: a socket timeout
    bounds each recv, not the request, so only the watchdog shutting the
    socket ends it on time (without it, the drip runs its full 3 s).
    Handshake: CPython bounds the WHOLE handshake by the socket timeout,
    which ``_fetch_image`` caps at the time left; this pins that, since the
    watchdog is only armed after ``connect()``."""
    server, port, thread = _loopback_drip(prefix)
    target = lp._Target(
        f"{scheme}://127.0.0.1:{port}/og.png", scheme, "127.0.0.1", port, "127.0.0.1"
    )
    started = time.monotonic()
    try:
        assert lp._fetch_image(target, time.monotonic() + 0.3) is None
        elapsed = time.monotonic() - started
    finally:
        server.close()
        thread.join(5)

    assert elapsed < 1.5


# --- storage -------------------------------------------------------------------


@pytest.mark.parametrize("canonical_exists", [True, False])
def test_a_racing_duplicate_is_dropped_for_the_canonical_name(canonical_exists):
    """Two posts storing the same image at once: storage gives the second a
    suffixed name (R2 runs with file_overwrite=False). A suffixed name never
    passes is_cached_image_name, so it is deleted, and the card uses the
    canonical file when it exists, else no image."""
    suffixed = IMAGE_NAME.removesuffix(".webp") + "_a1B2c3D.webp"
    storage = Mock()
    storage.save.return_value = suffixed
    storage.exists.return_value = canonical_exists
    with patch.object(lp, "default_storage", storage):
        result = lp._store_image(IMAGE_NAME, b"webp bytes")

    storage.delete.assert_called_once_with(suffixed)
    assert result == (IMAGE_NAME if canonical_exists else "")
    assert not is_cached_image_name(suffixed)


# --- end to end through the host mount -----------------------------------------


@override_settings(
    WAGTAILFORUM_LINK_PREVIEW_FETCHER=(
        "apps.forum_host.link_preview.link_preview_snapshot"
    ),
    FORUM_RATELIMITS={"topic_create": "100/h"},
)
@pytest.mark.django_db
def test_a_posted_link_card_serves_our_image_through_the_host_mount():
    """The fetcher is turned on for this test only: the host settings leave
    it unset until slice C ships the readers and both edit round trips."""
    from wagtail.models import Page
    from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, TrustLevel
    from wagtail_forum.workflow import ensure_default_workflow

    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-card"))
    board = index.add_child(instance=ForumBoard(title="General", slug="card-board"))
    author = User.objects.create_user(username="card-author")
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(author)

    with page(), serve(image_response(png())):
        created = client.post(
            f"/api/v1/forum/boards/{board.slug}/topics/",
            {
                "title": "A card",
                "slug": "a-card",
                "body": [{"type": "paragraph", "value": f"<p>{PAGE_URL}</p>"}],
            },
            format="json",
        )
    assert created.status_code == 201, created.data

    posts = client.get(f"/api/v1/forum/topics/{created.data['id']}/posts/")
    assert posts.status_code == 200
    block = posts.data["results"][0]["body"][0]
    assert block["type"] == "link_preview"
    assert block["value"]["title"] == "Monstera care"
    assert block["value"]["image_url"] == MEDIA_URL + IMAGE_NAME
