import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _topic_with_posts(n):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    for i in range(n):
        Post.objects.create(
            topic=topic,
            author=author,
            is_opening_post=(i == 0),
            live=True,
            body=[{"type": "paragraph", "value": "<p>hi</p>"}],
        )
    return topic


@pytest.mark.django_db
def test_post_list_serializes_streamfield_body():
    topic = _topic_with_posts(1)
    resp = APIClient().get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    post = resp.data["results"][0]
    assert post["topic_id"] == topic.id
    assert post["author"]["username"] == "ada"
    assert post["is_opening_post"] is True
    assert post["body"] == [
        {"type": "paragraph", "value": "<p>hi</p>", "id": post["body"][0]["id"]}
    ]
    assert post["reaction_counts"] == {}
    assert post["can_edit"] is False  # anonymous


@pytest.mark.django_db
def test_post_list_is_cursor_paginated_with_bounded_queries():
    topic = _topic_with_posts(25)
    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/topics/{topic.id}/posts/")
    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None
    # Q1: PageViewRestriction prefetch (from _visible_boards().public())
    # Q2: topic lookup (wagtail_forum_topic with board__in=_visible_boards() subquery)
    # Q3: posts page with select_related author (cursor fetches page_size+1 rows; the
    #     extra row is the has-next probe — no separate COUNT query)
    # Pinned EXACTLY (docs/rules/testing.md). If this changes, explain the new number.
    assert len(ctx.captured_queries) == 3


@pytest.mark.django_db
def test_post_list_hides_posts_on_hidden_topic():
    topic = _topic_with_posts(1)
    topic.live = False
    topic.save()
    assert APIClient().get(f"/forum/topics/{topic.id}/posts/").status_code == 404
