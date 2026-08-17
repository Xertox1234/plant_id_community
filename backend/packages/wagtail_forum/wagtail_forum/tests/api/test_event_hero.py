"""Landing-page "Community event" hero signal: GET event/ (todo 304).

Backend-owned replacement for the retired client-side inference
(`recentTopics.find(t => t.is_pinned && t.slug.startsWith('bloom-watch'))`).
Sourced from `ForumIndex.featured_topic`/`-eyebrow`/`-description` — these
tests pin the visibility re-check (a featured topic can be moderated away or
its board restricted after being featured) alongside the happy path.
"""

import pytest
from rest_framework.test import APIClient
from wagtail.models import Page, PageViewRestriction
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _index_and_board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum-event"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general-event"))
    return index, board


@pytest.mark.django_db
def test_event_hero_no_forum_index_returns_null():
    resp = APIClient().get("/forum/event/")
    assert resp.status_code == 200
    assert resp.data == {"topic": None}


@pytest.mark.django_db
def test_event_hero_no_featured_topic_returns_null():
    _index_and_board()
    resp = APIClient().get("/forum/event/")
    assert resp.status_code == 200
    assert resp.data == {"topic": None}


@pytest.mark.django_db
def test_event_hero_returns_featured_topic_with_hero_copy():
    index, board = _index_and_board()
    topic = Topic.objects.create(
        board=board, title="Bloom Watch 2026", slug="bloom-watch-2026", live=True
    )
    index.featured_eyebrow = "Community event"
    index.featured_description = "Track what's flowering this season."
    index.featured_topic = topic
    index.save()

    resp = APIClient().get("/forum/event/")
    assert resp.status_code == 200
    assert resp.data == {
        "topic": {
            "id": topic.id,
            "slug": "bloom-watch-2026",
            "title": "Bloom Watch 2026",
            "board": {"id": board.id, "name": "General", "slug": "general-event"},
            "eyebrow": "Community event",
            "description": "Track what's flowering this season.",
        }
    }


@pytest.mark.django_db
def test_event_hero_default_eyebrow_when_not_customized():
    """`featured_eyebrow` has a model default — a moderator who only sets the
    topic (not the copy) still gets a sensible eyebrow, not an empty string."""
    index, board = _index_and_board()
    topic = Topic.objects.create(
        board=board, title="Bloom Watch", slug="bloom-watch", live=True
    )
    index.featured_topic = topic
    index.save()

    resp = APIClient().get("/forum/event/")
    assert resp.data["topic"]["eyebrow"] == "Community event"


@pytest.mark.django_db
def test_event_hero_unpublished_featured_topic_returns_null():
    """A featured topic that gets moderated away (unpublished) after being
    featured must not leak through the hero — re-checked on every read, not
    trusted from the FK alone."""
    index, board = _index_and_board()
    topic = Topic.objects.create(
        board=board, title="Bloom Watch", slug="bloom-watch", live=False
    )
    index.featured_topic = topic
    index.save()

    resp = APIClient().get("/forum/event/")
    assert resp.status_code == 200
    assert resp.data == {"topic": None}


@pytest.mark.django_db
def test_event_hero_restricted_board_returns_null():
    """A featured topic whose board gains a view restriction after being
    featured must not leak through the hero either."""
    index, board = _index_and_board()
    topic = Topic.objects.create(
        board=board, title="Bloom Watch", slug="bloom-watch", live=True
    )
    index.featured_topic = topic
    index.save()
    PageViewRestriction.objects.create(page=board, restriction_type="login")

    resp = APIClient().get("/forum/event/")
    assert resp.status_code == 200
    assert resp.data == {"topic": None}
