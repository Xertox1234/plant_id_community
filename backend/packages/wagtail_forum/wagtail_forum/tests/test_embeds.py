"""Embed helpers (todo 344): player-URL derivation, the host-finder
allowlist, the bounded write-time warm-up, and the DB-only read envelope."""

import time
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.utils import timezone
from wagtail.embeds.embeds import get_embed_hash
from wagtail.embeds.exceptions import EmbedNotFoundException
from wagtail.embeds.models import Embed
from wagtail_forum.embeds import (
    derive_embed_url,
    embed_envelope,
    is_supported_url,
    warm_embed,
    warm_embeds,
)

YOUTUBE_VIMEO_FINDERS = [
    {
        "class": "wagtail_forum.embeds.TimeoutOEmbedFinder",
        "providers": [
            {
                "endpoint": "https://www.youtube.com/oembed",
                "urls": [
                    r"^https?://(?:[-\w]+\.)?youtube\.com/watch.+$",
                    r"^https?://youtu\.be/.+$",
                ],
            },
            {
                "endpoint": "https://www.vimeo.com/api/oembed.{format}",
                "urls": [r"^https?://(?:www\.)?vimeo\.com/.+$"],
            },
        ],
    }
]


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ?t=42",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/watch?feature=share&v=dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://youtube.com/shorts/dQw4w9WgXcQ",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/live/dQw4w9WgXcQ?feature=share",
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
        ("https://vimeo.com/148751763", "https://player.vimeo.com/video/148751763"),
        (
            "https://player.vimeo.com/video/148751763?h=abc",
            "https://player.vimeo.com/video/148751763",
        ),
        ("https://example.com/video/1", None),
        (
            "https://www.youtube.com/user/someone",
            None,
        ),  # allowed by the finder, no player id
        (
            'https://youtu.be/dQw4w9WgXcQ"><script>',
            "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ",
        ),
    ],
)
def test_derive_embed_url_only_ever_yields_the_two_known_player_hosts(url, expected):
    assert derive_embed_url(url) == expected


@override_settings(WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS)
def test_is_supported_url_is_the_hosts_finder_allowlist_plus_scheme_and_length():
    # (Wagtail's setting_changed receiver clears get_finders' cache itself.)
    assert is_supported_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
    assert is_supported_url("https://youtu.be/dQw4w9WgXcQ?t=42&list=PL1") is True
    assert is_supported_url("https://vimeo.com/148751763") is True
    assert (
        is_supported_url("https://dailymotion.com/video/x1") is False
    )  # not in the host list
    assert is_supported_url("ftp://youtu.be/dQw4w9WgXcQ") is False
    assert is_supported_url("javascript:alert(1)") is False
    assert is_supported_url("https://youtu.be/" + "a" * 2100) is False
    assert is_supported_url(123) is False
    # Accepted by the provider regex (`.+$`) but not a URL: never stored.
    assert is_supported_url('https://youtu.be/dQw4w9WgXcQ"><script>') is False
    assert is_supported_url("https://youtu.be/dQw4w9WgXcQ <b>") is False


# warm_embed's worker thread commits on its OWN DB connection, outside the
# test transaction — so its rows outlive the test. Each test below uses its
# own video id and clears any leftover from a previous run.
@pytest.mark.django_db
def test_warm_embed_caches_the_row_and_swallows_provider_failure_and_timeout():
    url = "https://youtu.be/warm0000001"
    Embed.objects.filter(
        url__in=[url, "https://youtu.be/missing00000", "https://youtu.be/slow00000000"]
    ).delete()
    fake = {
        "type": "video",
        "html": "<iframe></iframe>",
        "title": "T",
        "provider_name": "YouTube",
        "thumbnail_url": "https://i/t.jpg",
        "width": 1,
        "height": 1,
        "author_name": "",
    }

    with patch("wagtail.embeds.embeds.get_finder_for_embed", return_value=dict(fake)):
        warm_embed(url)
    assert Embed.objects.filter(hash=get_embed_hash(url)).exists()

    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=EmbedNotFoundException("down"),
    ):
        warm_embed("https://youtu.be/missing00000")  # no raise, nothing cached
    assert not Embed.objects.filter(url="https://youtu.be/missing00000").exists()

    def slow(*a, **k):
        time.sleep(0.5)
        return dict(fake)

    with (
        override_settings(WAGTAILFORUM_EMBED_FETCH_TIMEOUT_SECONDS=0.05),
        patch("wagtail.embeds.embeds.get_finder_for_embed", side_effect=slow),
    ):
        started = time.monotonic()
        warm_embed("https://youtu.be/slow00000000")  # returns within the bound
        assert time.monotonic() - started < 0.4


@pytest.mark.django_db
def test_embed_envelope_reads_the_cache_row_and_never_fetches():
    url = "https://youtu.be/envelope001"
    Embed.objects.filter(url=url).delete()
    Embed.objects.create(
        url=url,
        hash=get_embed_hash(url),
        type="video",
        html="<iframe></iframe>",
        title="Repotting a monstera",
        provider_name="YouTube",
        thumbnail_url="https://i/t.jpg",
    )
    with (
        override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True),
        patch(
            "wagtail.embeds.embeds.get_finder_for_embed",
            side_effect=AssertionError("fetched on read"),
        ),
    ):
        assert embed_envelope(url) == {
            "url": url,
            "provider_name": "YouTube",
            "title": "Repotting a monstera",
            "thumbnail_url": "https://i/t.jpg",
            "embed_url": "https://www.youtube-nocookie.com/embed/envelope001",
        }
        # An uncached (or expired) URL is still a well-formed link card.
        uncached = embed_envelope("https://vimeo.com/148751763")
        assert uncached["embed_url"] == "https://player.vimeo.com/video/148751763"
        assert uncached["title"] == "" and uncached["thumbnail_url"] == ""
        Embed.objects.filter(url=url).update(
            cache_until=timezone.now() - timezone.timedelta(days=1)
        )
        assert embed_envelope(url)["title"] == ""

    # Host switched embeds off: legacy data is a plain link, no player URL.
    with override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=False):
        assert embed_envelope(url)["embed_url"] is None
        assert embed_envelope(url)["title"] == ""


@pytest.mark.django_db
def test_warm_embeds_resolves_a_bodys_urls_concurrently_in_one_window():
    """The author waits ONE timeout window for the lot, not one per URL."""
    urls = [f"https://youtu.be/concur0000{i}" for i in range(1, 4)]
    Embed.objects.filter(url__in=urls).delete()

    def slow(url, *a, **k):
        time.sleep(0.5)
        return {
            "type": "video",
            "html": "<i></i>",
            "title": url,
            "author_name": "",
            "provider_name": "YouTube",
            "thumbnail_url": "",
            "width": 1,
            "height": 1,
        }

    with (
        override_settings(WAGTAILFORUM_EMBED_FETCH_TIMEOUT_SECONDS=5),
        patch("wagtail.embeds.embeds.get_finder_for_embed", side_effect=slow),
    ):
        started = time.monotonic()
        warm_embeds(urls + urls)  # duplicates collapse
        elapsed = time.monotonic() - started

    assert elapsed < 1.2, elapsed  # sequential would be >= 1.5
    assert Embed.objects.filter(url__in=urls).count() == 3


@override_settings(
    WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS,
    WAGTAILFORUM_EMBED_FETCH_TIMEOUT_SECONDS=7,
)
def test_timeout_finder_passes_a_real_socket_timeout_to_the_provider_request():
    """The stock OEmbedFinder calls requests.get with no timeout; ours must
    carry the setting so a stalled provider cannot hang a worker (or the
    admin chooser, which bypasses warm_embeds entirely)."""
    from wagtail.embeds.finders import get_finders
    from wagtail_forum.embeds import TimeoutOEmbedFinder

    finder = get_finders()[0]
    assert isinstance(finder, TimeoutOEmbedFinder)

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "type": "video",
                "html": "<iframe></iframe>",
                "title": "T",
                "cache_age": "60",
            }

    with patch("wagtail_forum.embeds.requests.get", return_value=FakeResponse()) as get:
        result = finder.find_embed("https://youtu.be/dQw4w9WgXcQ")

    assert get.call_args.kwargs["timeout"] == 7
    assert get.call_args.args[0] == "https://www.youtube.com/oembed"
    assert result["title"] == "T" and "cache_until" in result
    assert get.call_args.kwargs["params"]["url"] == "https://youtu.be/dQw4w9WgXcQ"
