"""A paragraph whose only content is a video link becomes an ``embed`` block
on the server (todo 421), so every client gets the card, not only the web
composer (which converts before submit). The mobile composer sends a bare
URL with no ``<p>`` wrapper; the web sends ``<p>URL</p>``. Both convert."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.embeds.models import Embed
from wagtail.models import Page
from wagtail_forum.conf import get_setting
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

EMBEDS_ON = override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=True, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _member(username="author"):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER  # autopublishes, no moderation hold
    profile.save(update_fields=["trust_level"])
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create(client, board, body, slug="video-thread"):
    return client.post(
        f"/forum/boards/{board.slug}/topics/",
        {"title": "Video", "slug": slug, "body": body},
        format="json",
    )


def _paragraph(html):
    return {"type": "paragraph", "value": html}


def _stored(post=None):
    post = post or Post.objects.get()
    return [(b["type"], b["value"]) for b in post.body.raw_data]


@pytest.fixture
def no_fetch():
    """Every conversion warms the embed cache at write time; never let a test
    reach a provider. Returns the mock so a test can count the fetches."""
    with patch("wagtail_forum.api.sanitize.warm_embeds") as warm:
        yield warm


@pytest.mark.django_db
@EMBEDS_ON
@pytest.mark.parametrize(
    ("html", "url"),
    [
        # The mobile composer: bare text, no <p> (generateForumRichHtml).
        ("https://youtu.be/d2Xc8uupb9E", "https://youtu.be/d2Xc8uupb9E"),
        # Production topic 44 / post 289: the share sheet's ?si= tracker.
        (
            "https://youtu.be/d2Xc8uupb9E?si=Ab12Cd34Ef56Gh78",
            "https://youtu.be/d2Xc8uupb9E?si=Ab12Cd34Ef56Gh78",
        ),
        # The web shape, if a client ever skips its own conversion.
        ("<p>https://vimeo.com/148751763</p>", "https://vimeo.com/148751763"),
        # Whitespace and an autolinked URL are still "only a URL".
        (
            '  <p><a href="https://youtu.be/dQw4w9WgXcQ">https://youtu.be/dQw4w9WgXcQ</a></p> ',
            "https://youtu.be/dQw4w9WgXcQ",
        ),
        # An escaped query separator is stored unescaped, as the web does.
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&amp;t=42",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42",
        ),
    ],
)
def test_a_url_only_paragraph_is_stored_as_an_embed(html, url, no_fetch):
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    assert _stored() == [("embed", url)]
    no_fetch.assert_called_once_with([url])


@pytest.mark.django_db
@EMBEDS_ON
@pytest.mark.parametrize(
    "html",
    [
        # A link inside prose stays a paragraph (the web rule).
        "Look at this https://youtu.be/dQw4w9WgXcQ",
        "<p>Look at this: https://youtu.be/dQw4w9WgXcQ</p>",
        # Mobile multi-line: the lines join with <br>, so it is not URL-only.
        "Repotting day<br>https://youtu.be/dQw4w9WgXcQ",
        # Two links on two lines must not glue into one bogus URL.
        "https://youtu.be/dQw4w9WgXcQ<br>https://youtu.be/d2Xc8uupb9E",
        "<p>https://youtu.be/dQw4w9WgXcQ</p><p>https://vimeo.com/148751763</p>",
        # A link whose text is not the URL keeps its words.
        '<p><a href="https://youtu.be/dQw4w9WgXcQ">my repotting video</a></p>',
        # Not a provider the host allows, or not a video URL at all.
        "https://example.com/video.mp4",
        "https://dailymotion.com/video/x1",
        "https://youtube.com/",
    ],
)
def test_anything_but_a_lone_allowed_video_url_stays_a_paragraph(html, no_fetch):
    resp = _create(_client(_member()), _board(), [_paragraph(html)])

    assert resp.status_code == 201, resp.data
    assert [t for t, _ in _stored()] == ["paragraph"]
    no_fetch.assert_not_called()


@pytest.mark.django_db
@override_settings(
    WAGTAILFORUM_ALLOW_EMBED_BLOCKS=False, WAGTAILEMBEDS_FINDERS=YOUTUBE_VIMEO_FINDERS
)
def test_with_embeds_off_a_video_link_stays_a_paragraph_and_still_saves(no_fetch):
    resp = _create(
        _client(_member()), _board(), [_paragraph("https://youtu.be/dQw4w9WgXcQ")]
    )

    assert resp.status_code == 201, resp.data
    assert [t for t, _ in _stored()] == ["paragraph"]
    no_fetch.assert_not_called()


@pytest.mark.django_db
@EMBEDS_ON
def test_only_the_url_only_paragraphs_of_a_mixed_body_convert(no_fetch):
    resp = _create(
        _client(_member()),
        _board(),
        [
            _paragraph("<p>How I repot.</p>"),
            _paragraph("https://youtu.be/dQw4w9WgXcQ"),
            _paragraph("<p>Questions welcome.</p>"),
        ],
    )

    assert resp.status_code == 201, resp.data
    assert [t for t, _ in _stored()] == ["paragraph", "embed", "paragraph"]


@pytest.mark.django_db
@EMBEDS_ON
def test_a_reply_converts_too(no_fetch):
    author = _member()
    client = _client(author)
    assert _create(client, _board(), [_paragraph("<p>Opening.</p>")]).status_code == 201
    topic = Topic.objects.get()

    resp = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [_paragraph("https://vimeo.com/148751763")]},
        format="json",
    )

    assert resp.status_code == 201, resp.data
    assert _stored(Post.objects.get(pk=resp.data["id"])) == [
        ("embed", "https://vimeo.com/148751763")
    ]


@pytest.mark.django_db
@EMBEDS_ON
def test_an_edit_goes_through_the_same_conversion(no_fetch):
    client = _client(_member())
    assert (
        _create(client, _board(), [_paragraph("<p>Video soon.</p>")]).status_code == 201
    )
    post = Post.objects.get()

    resp = client.patch(
        f"/forum/posts/{post.id}/",
        {"body": [_paragraph("https://youtu.be/d2Xc8uupb9E?si=x")]},
        format="json",
    )

    assert resp.status_code == 200, resp.data
    post.refresh_from_db()
    assert _stored(post) == [("embed", "https://youtu.be/d2Xc8uupb9E?si=x")]


@pytest.mark.django_db
@EMBEDS_ON
def test_conversion_stops_at_the_embed_cap_instead_of_rejecting_the_post(no_fetch):
    """A body of bare links saved fine before conversion existed, so the cap
    must not turn it into a 400. Explicit embed blocks count toward the cap;
    a repeat of an already-counted URL costs nothing."""
    cap = get_setting("MAX_EMBED_URLS_PER_BODY")
    explicit = "https://youtu.be/capexplic01"
    bare = [f"https://youtu.be/capbare00{i:02d}" for i in range(cap)]
    body = [
        {"type": "embed", "value": explicit},
        *(_paragraph(url) for url in bare),
        _paragraph(explicit),  # already counted: converts at no cost
    ]

    resp = _create(_client(_member()), _board(), body)

    assert resp.status_code == 201, resp.data
    stored = _stored()
    assert [t for t, _ in stored] == (
        ["embed"] + ["embed"] * (cap - 1) + ["paragraph"] + ["embed"]
    )
    assert stored[cap][1] == bare[-1]  # the one over the cap keeps its text


@pytest.mark.django_db
@EMBEDS_ON
def test_a_converted_link_is_warmed_and_read_back_as_a_card():
    """End to end with the real warm-up (the provider call mocked at
    Wagtail's finder, as test_embeds_api.py does): the read envelope the
    clients render is the same one an explicit embed block gets."""
    url = "https://youtu.be/autocvt0001"
    Embed.objects.filter(url=url).delete()
    oembed = {
        "type": "video",
        "html": "<iframe></iframe>",
        "title": "Repotting a monstera",
        "provider_name": "YouTube",
        "thumbnail_url": "https://i.ytimg.com/vi/autocvt0001/hqdefault.jpg",
        "author_name": "",
        "width": 200,
        "height": 113,
    }
    with patch(
        "wagtail.embeds.embeds.get_finder_for_embed", return_value=dict(oembed)
    ) as fetch:
        resp = _create(_client(_member()), _board(), [_paragraph(url)])
    assert resp.status_code == 201, resp.data
    assert fetch.call_count == 1

    topic = Topic.objects.get()
    block = (
        APIClient()
        .get(f"/forum/topics/{topic.id}/posts/")
        .data["results"][0]["body"][0]
    )
    assert block["type"] == "embed"
    assert block["value"]["title"] == "Repotting a monstera"
    assert block["value"]["embed_url"] == (
        "https://www.youtube-nocookie.com/embed/autocvt0001"
    )
