"""Embed blocks on the API (todo 344): the host gate, the provider allowlist,
the write-time warm-up, and the DB-only read envelope — no provider is ever
contacted on a read."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.embeds.exceptions import EmbedNotFoundException
from wagtail.embeds.models import Embed
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)

from ..test_embeds import YOUTUBE_VIMEO_FINDERS

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")

# Distinct video ids per test: warm_embed caches on a worker thread whose
# connection commits outside the test transaction (see test_embeds.py).
YT = "https://youtu.be/apiwrite001"
FAKE_OEMBED = {
    "type": "video",
    "html": '<iframe src="https://www.youtube.com/embed/apiwrite001"></iframe>',
    "title": "Repotting a monstera",
    "provider_name": "YouTube",
    "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    "author_name": "",
    "width": 200,
    "height": 113,
}


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _member(username):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER  # autopublishes, no moderation hold
    profile.save(update_fields=["trust_level"])
    return user


def _create(client, board, body, slug="embed-thread"):
    return client.post(
        f"/forum/boards/{board.slug}/topics/",
        {"title": "Video", "slug": slug, "body": body},
        format="json",
    )


@pytest.mark.django_db
def test_embed_block_is_refused_on_write_until_the_host_opts_in():
    board = _board()
    client = APIClient()
    client.force_authenticate(_member("author"))

    with override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=False):
        resp = _create(client, board, [{"type": "embed", "value": YT}])

    assert resp.status_code == 400
    assert "not enabled" in resp.data["message"]
    assert not Topic.objects.exists()


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
@pytest.mark.parametrize(
    "value",
    [
        "https://dailymotion.com/video/x1",  # a real provider, not on the host list
        "javascript:alert(1)",
        "https://youtu.be/" + "a" * 2100,
        123,
        ["https://youtu.be/dQw4w9WgXcQ"],
    ],
)
def test_unsupported_or_malformed_embed_values_are_400(value):
    board = _board()
    client = APIClient()
    client.force_authenticate(_member("author"))

    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=AssertionError("no fetch"),
    ):
        resp = _create(client, board, [{"type": "embed", "value": value}])

    assert resp.status_code == 400
    assert not Topic.objects.exists()


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_embed_is_resolved_once_at_write_and_read_without_any_fetch():
    board = _board()
    author = _member("author")
    client = APIClient()
    client.force_authenticate(author)

    Embed.objects.filter(url=YT).delete()
    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed", return_value=dict(FAKE_OEMBED)
    ) as fetch:
        resp = _create(
            client,
            board,
            [
                {"type": "paragraph", "value": "<p>How I repot.</p>"},
                {"type": "embed", "value": YT},
                {"type": "embed", "value": YT},  # same URL twice: one fetch
            ],
        )
    assert resp.status_code == 201, resp.data
    assert fetch.call_count == 1
    assert Embed.objects.filter(url=YT).count() == 1
    topic = Topic.objects.get()

    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=AssertionError("fetched on read"),
    ):
        posts = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert posts.status_code == 200
    blocks = posts.data["results"][0]["body"]
    assert [b["type"] for b in blocks] == ["paragraph", "embed", "embed"]
    assert blocks[1]["value"] == {
        "url": YT,
        "provider_name": "YouTube",
        "title": "Repotting a monstera",
        "thumbnail_url": FAKE_OEMBED["thumbnail_url"],
        "embed_url": "https://www.youtube-nocookie.com/embed/apiwrite001",
    }
    # Provider HTML is never delivered.
    assert "html" not in blocks[1]["value"]
    # Stored value is the bare URL, nothing else.
    assert Post.objects.get().body.raw_data[1]["value"] == YT


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_an_unreachable_provider_still_saves_the_post_as_a_link_card():
    board = _board()
    client = APIClient()
    client.force_authenticate(_member("author"))

    Embed.objects.filter(url="https://vimeo.com/148751763").delete()
    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=EmbedNotFoundException("down"),
    ):
        resp = _create(
            client, board, [{"type": "embed", "value": "https://vimeo.com/148751763"}]
        )

    assert resp.status_code == 201, resp.data
    topic = Topic.objects.get()
    # The read must not retry the provider on this cache miss either.
    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=AssertionError("fetched on read"),
    ):
        block = (
            APIClient()
            .get(f"/forum/topics/{topic.id}/posts/")
            .data["results"][0]["body"][0]
        )
    assert block["value"]["title"] == "" and block["value"]["thumbnail_url"] == ""
    assert block["value"]["embed_url"] == "https://player.vimeo.com/video/148751763"


@pytest.mark.django_db
def test_legacy_embed_data_reads_as_a_plain_link_when_the_host_switches_embeds_off():
    board = _board()
    author = _member("author")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "embed", "value": YT}],
    )

    with override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=False):
        block = (
            APIClient()
            .get(f"/forum/topics/{topic.id}/posts/")
            .data["results"][0]["body"][0]
        )

    assert block["type"] == "embed"
    assert block["value"]["url"] == YT
    assert block["value"]["embed_url"] is None


@pytest.mark.django_db
@override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True)
def test_post_list_query_count_is_flat_across_embed_bearing_posts():
    """One Embed lookup per PAGE, not per post (kimi-review): a page whose
    every post carries a video costs what a page with one does."""
    board = _board()
    author = _member("author")
    one = Topic.objects.create(
        board=board, title="One", slug="one", author=author, live=True
    )
    five = Topic.objects.create(
        board=board, title="Five", slug="five", author=author, live=True
    )
    Post.objects.create(
        topic=one,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "embed", "value": "https://youtu.be/flatpost001"}],
    )
    for i in range(5):
        Post.objects.create(
            topic=five,
            author=author,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "embed", "value": f"https://youtu.be/flatpost00{i + 2}"}],
        )

    anon = APIClient()
    with CaptureQueriesContext(connection) as ctx_one:
        r1 = anon.get(f"/forum/topics/{one.id}/posts/")
    with CaptureQueriesContext(connection) as ctx_five:
        r5 = anon.get(f"/forum/topics/{five.id}/posts/")

    assert r1.status_code == r5.status_code == 200
    assert len(r5.data["results"]) == 5
    assert all(b["body"][0]["type"] == "embed" for b in r5.data["results"])
    assert len(ctx_five.captured_queries) == len(ctx_one.captured_queries)
    # And with embeds OFF the page costs one query less: no Embed lookup at all.
    with override_settings(WAGTAILFORUM_ALLOW_EMBED_BLOCKS=False):
        with CaptureQueriesContext(connection) as ctx_off:
            anon.get(f"/forum/topics/{five.id}/posts/")
    assert len(ctx_off.captured_queries) == len(ctx_five.captured_queries) - 1


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_more_distinct_embed_urls_than_the_cap_is_400_before_any_fetch():
    from wagtail_forum.conf import get_setting

    board = _board()
    client = APIClient()
    client.force_authenticate(_member("author"))
    cap = get_setting("MAX_EMBED_URLS_PER_BODY")
    body = [
        {"type": "embed", "value": f"https://youtu.be/capped000{i:02d}"}
        for i in range(cap + 1)
    ]

    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed",
        side_effect=AssertionError("no fetch"),
    ) as fetch:
        resp = _create(client, board, body)

    assert resp.status_code == 400
    assert f"at most {cap} videos" in resp.data["message"]
    assert fetch.call_count == 0
    assert not Topic.objects.exists()
