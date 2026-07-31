"""Board-list payload: `intro` welcome copy + per-board `last_post_at` (todo 278 L2).

The envelope *keys* are guarded by `test_list_envelopes.py`; this file pins what
those keys are worth — that the CMS intro actually survives the trip (expanded
and sanitized), and that `last_post_at` reflects only topics a reader can see.
"""

from datetime import datetime
from datetime import timezone as dt_timezone

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.images.tests.utils import get_test_image_file
from wagtail.models import Page, Site
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _index(intro="", slug="forum-bl"):
    root = Page.objects.get(id=1)
    return root.add_child(instance=ForumIndex(title="Forum", slug=slug, intro=intro))


def _board(index, slug="general-bl"):
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _boards_payload():
    resp = APIClient().get("/forum/boards/")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.django_db
def test_intro_reaches_the_client_as_html():
    _board(_index(intro="<p>Welcome to the <b>plant</b> forum.</p>"))

    assert _boards_payload()["intro"] == "<p>Welcome to the <b>plant</b> forum.</p>"


@pytest.mark.django_db
def test_intro_is_empty_string_when_unset():
    """Never null: a client renders `intro` directly, so the empty case is `""`."""
    _board(_index())

    assert _boards_payload()["intro"] == ""


@pytest.mark.django_db
def test_intro_is_empty_string_when_there_is_no_forum_index():
    """A host may mount boards' API before creating any ForumIndex page."""
    assert _boards_payload()["intro"] == ""


@pytest.mark.django_db
def test_intro_is_sanitized():
    """CMS-authored, but this HTML reaches mobile clients that never run DOMPurify."""
    _board(
        _index(
            intro=(
                "<p>Hi</p><script>alert(1)</script>"
                '<img src="x" onerror="alert(2)">'
                '<p><a href="javascript:alert(3)">click</a></p>'
            )
        )
    )

    intro = _boards_payload()["intro"]
    assert "<script>" not in intro
    assert "onerror" not in intro
    assert "javascript:" not in intro
    assert "<p>Hi</p>" in intro


@pytest.mark.django_db
def test_intro_expands_wagtail_page_links():
    """Wagtail stores `<a linktype="page" id=N>`; a raw dump is a dead anchor."""
    index = _index()
    board = _board(index)
    # Page.url is None without a Site rooting the tree — give it one so the
    # assertion is "the real href landed", not just "the placeholder is gone".
    Site.objects.create(hostname="forum-bl.test", root_page=index)
    index.intro = f'<p><a linktype="page" id="{board.id}">Go</a></p>'
    index.save()

    intro = _boards_payload()["intro"]
    assert "linktype" not in intro
    assert f'href="{ForumBoard.objects.get(pk=board.pk).url}"' in intro


@pytest.mark.django_db
def test_intro_comes_from_the_first_index_in_tree_order():
    """Two forum trees must resolve deterministically, not raise or pick at random.

    Also pins the documented asymmetry: `results` spans BOTH trees while
    `intro` comes from one. Asserting only `intro` would let a future change
    silently scope the board list to one index and call it a fix.
    """
    _board(_index(intro="<p>First</p>", slug="forum-a"), slug="board-a")
    _board(_index(intro="<p>Second</p>", slug="forum-b"), slug="board-b")

    payload = _boards_payload()
    assert payload["intro"] == "<p>First</p>"
    assert {b["slug"] for b in payload["results"]} == {"board-a", "board-b"}


@pytest.mark.django_db
def test_media_embeds_are_stripped_before_expansion_ever_runs(monkeypatch):
    """The oEmbed finder does a `requests.get` with NO timeout (verified in
    wagtail/embeds/finders/oembed.py). On this public, unauthenticated,
    CDN-fronted endpoint that is an unbounded hang per cache miss — and a
    failed fetch caches nothing, so it repeats. Sanitizing the *output* would
    drop the resulting <iframe> while still paying for it, so the embed has to
    go before `expand_db_html` sees it.

    Asserted by making expansion explode: any call at all fails the test.
    """
    from wagtail.embeds import embeds as wagtail_embeds

    def _explode(*args, **kwargs):
        raise AssertionError("embed expansion must never run for a forum intro")

    monkeypatch.setattr(wagtail_embeds, "get_embed", _explode)

    _board(
        _index(
            intro=(
                "<p>Hi</p>"
                '<embed embedtype="media" url="https://unreachable.example/video"/>'
            )
        )
    )

    intro = _boards_payload()["intro"]
    assert "<p>Hi</p>" in intro
    assert "embed" not in intro
    assert "iframe" not in intro


@pytest.mark.django_db
def test_image_embeds_are_stripped_before_a_rendition_is_generated():
    """Same reasoning as the media case, different side effect: expanding an
    image block does a real PIL resize + storage write + Rendition row, all of
    it then discarded by the output allowlist.

    The rendition COUNT is the assertion that can fail — a missing/invalid
    image id would make this pass either way, since Wagtail's handler swallows
    DoesNotExist and returns empty.
    """
    image = get_image_model().objects.create(title="leaf", file=get_test_image_file())
    _board(
        _index(
            intro=(
                "<p>Hi</p>"
                f'<embed embedtype="image" id="{image.id}" format="left" alt="x"/>'
            )
        )
    )

    intro = _boards_payload()["intro"]
    assert "<p>Hi</p>" in intro
    assert "<img" not in intro
    assert image.renditions.count() == 0


@pytest.mark.django_db
def test_intro_field_does_not_offer_the_features_the_api_strips():
    """The editor-side half of the same guard: a toolbar button whose output
    silently vanishes from every client is its own bug.
    """
    features = ForumIndex._meta.get_field("intro").features

    assert "image" not in features
    assert "embed" not in features
    # And what survives the API is actually authorable.
    assert {"h2", "h3", "h4", "link", "bold", "italic", "ol", "ul", "hr"} <= set(
        features
    )


@pytest.mark.django_db
def test_last_post_at_is_the_newest_live_topic_activity():
    board = _board(_index())
    older = datetime(2026, 1, 1, 12, 0, tzinfo=dt_timezone.utc)
    newer = datetime(2026, 6, 1, 12, 0, tzinfo=dt_timezone.utc)
    Topic.objects.create(
        board=board, title="Old", slug="old-bl", live=True, last_post_at=older
    )
    Topic.objects.create(
        board=board, title="New", slug="new-bl", live=True, last_post_at=newer
    )

    (payload,) = _boards_payload()["results"]
    assert payload["last_post_at"] == "2026-06-01T12:00:00Z"


@pytest.mark.django_db
def test_last_post_at_is_null_for_a_board_with_no_topics():
    _board(_index())

    (payload,) = _boards_payload()["results"]
    assert payload["last_post_at"] is None


@pytest.mark.django_db
def test_last_post_at_ignores_non_live_topics():
    """A draft/unpublished topic must not make a silent board look active."""
    board = _board(_index())
    Topic.objects.create(
        board=board,
        title="Draft",
        slug="draft-bl",
        live=False,
        last_post_at=datetime(2026, 6, 1, 12, 0, tzinfo=dt_timezone.utc),
    )

    (payload,) = _boards_payload()["results"]
    assert payload["last_post_at"] is None


@pytest.mark.django_db
def test_last_post_at_ignores_a_live_topic_that_has_no_posts_yet():
    """Postgres sorts DESC as NULLS FIRST — without the isnull filter this wins."""
    board = _board(_index())
    Topic.objects.create(
        board=board, title="Empty", slug="empty-bl", live=True, last_post_at=None
    )
    Topic.objects.create(
        board=board,
        title="Real",
        slug="real-bl",
        live=True,
        last_post_at=datetime(2026, 6, 1, 12, 0, tzinfo=dt_timezone.utc),
    )

    (payload,) = _boards_payload()["results"]
    assert payload["last_post_at"] == "2026-06-01T12:00:00Z"


@pytest.mark.django_db
def test_last_post_at_does_not_add_a_query_per_board():
    """The annotation is a correlated subquery — it must fold into the one SELECT.

    Pinned as a delta, not an absolute count: the fixed cost (page-restriction
    lookup for `.public()`, the ForumIndex fetch for `intro`) is not what this
    guards. What it guards is that going from one board to three does not add
    three queries — the N+1 an `Iterable`/property implementation would cause.
    """
    index = _index()
    _board(index, slug="board-1")
    with CaptureQueriesContext(connection) as one_board:
        _boards_payload()

    _board(index, slug="board-2")
    _board(index, slug="board-3")
    with CaptureQueriesContext(connection) as three_boards:
        _boards_payload()

    assert len(three_boards) == len(one_board)
