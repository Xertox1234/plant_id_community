"""Visibility negatives for the read/write API (2026-06-10 audit M6, M7, M17).

- Pending-moderation (live=False) topics must be invisible to list/search/sync.
- An unpublished board's topics must stop accepting replies/reactions and
  disappear from search/sync (board-level takedown must be effective).
- Boards behind a Wagtail PageViewRestriction are invisible to the whole API.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumIndex, Post, Topic
from wagtail_forum.tests.factories import hide_forum, make_forum
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = ForumIndex.objects.first()
    if index is None:
        index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return make_forum(name=slug.title(), slug=slug)


def _live_topic(board, slug="t", body=None):
    author = User.objects.create_user(username=f"op-{slug}")
    topic = Topic.objects.create(board=board, title=slug, slug=slug, author=author)
    kwargs = {"topic": topic, "author": author, "is_opening_post": True}
    if body is not None:
        kwargs["body"] = body
    post = Post.objects.create(**kwargs)
    post.save_revision().publish()
    return topic, post


@pytest.mark.django_db
def test_pending_topics_are_excluded_from_list_search_and_sync():
    board = _board()
    _live_topic(board, slug="visible")
    author = User.objects.create_user(username="spammer")
    hidden_topic = Topic.objects.create(
        board=board, title="hidden spam", slug="hidden-spam", author=author, live=False
    )
    # Add a live post whose body contains the search term "hidden" so the
    # post-search visibility filter (topic__live=True) is genuinely exercised.
    # Without this post, searched.data["posts"] == [] is vacuously true.
    Post.objects.create(
        topic=hidden_topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hidden spam body</p>"}],
    )
    client = APIClient()

    listed = client.get(f"/forum/boards/{board.slug}/topics/")
    slugs = [t["slug"] for t in listed.data["results"]]
    assert slugs == ["visible"]

    synced = client.get("/forum/sync/")
    assert [t["slug"] for t in synced.data["topics"]] == ["visible"]

    searched = client.get("/forum/search/?q=hidden")
    # Search shape is {topics, posts} (Spec 2). A live=False topic and any of
    # its posts must be absent from BOTH lists.
    assert searched.data["topics"] == []
    assert searched.data["posts"] == []


@pytest.mark.django_db
def test_unpublished_board_takedown_is_effective():
    ensure_default_workflow()
    board = _board()
    topic, post = _live_topic(board)
    hide_forum(board)
    client = APIClient()
    user = User.objects.create_user(username="r")
    client.force_authenticate(user)

    reply = client.post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": "<p>hi</p>"}]},
        format="json",
    )
    react = client.post(
        f"/forum/posts/{post.id}/reactions/", {"type": "like"}, format="json"
    )
    synced = client.get("/forum/sync/")

    assert reply.status_code == 404
    assert react.status_code == 404
    assert synced.data["topics"] == []


@pytest.mark.django_db
def test_view_restricted_board_is_invisible_to_the_api():
    board = _board()
    _live_topic(board)
    hide_forum(board)
    client = APIClient()

    boards = client.get("/forum/boards/")
    topics = client.get(f"/forum/boards/{board.slug}/topics/")
    synced = client.get("/forum/sync/")

    assert boards.data["results"] == []
    assert topics.status_code == 404
    assert synced.data["topics"] == []


@pytest.mark.django_db
def test_a_board_slug_can_no_longer_be_ambiguous():
    # Page slugs were unique only among siblings, so two boards named
    # "general" under different ForumIndex pages once 500'd, then 409'd
    # (audit M8). Forum slugs are unique forum-wide since todo 665: the
    # second board cannot be created, so the lookup always resolves one.
    from django.db import IntegrityError, transaction
    from wagtail_forum.tests.factories import make_category

    make_forum(name="General", slug="general")
    with pytest.raises(IntegrityError), transaction.atomic():
        make_forum(name="General", slug="general", category=make_category(slug="b"))

    resp = APIClient().get("/forum/boards/general/topics/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_search_excludes_taken_down_board():
    # SearchView must gate on board visibility too — deleting its
    # _visible_boards() filter has to fail a test (review finding 10).
    board = _board(slug="searchable")
    # Give the opening post a body containing the search term so the
    # post-search path (topic__board__in=_visible_boards()) is genuinely exercised.
    _live_topic(
        board,
        slug="findme",
        body=[{"type": "paragraph", "value": "<p>findme body text</p>"}],
    )
    hide_forum(board)

    resp = APIClient().get("/forum/search/?q=findme")
    # A taken-down (unpublished) board must be excluded from BOTH search lists.
    assert resp.data["topics"] == []
    assert resp.data["posts"] == []
