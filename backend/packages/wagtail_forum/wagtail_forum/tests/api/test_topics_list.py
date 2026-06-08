import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_topics_list_is_cursor_paginated_with_bounded_queries():
    board = _board()
    author = User.objects.create_user(username="ada", password="x")
    # Live topics with DISTINCT last_post_at so the activity-ordered cursor is
    # deterministic. t0 is the most recent.
    base = timezone.now()
    for i in range(25):
        Topic.objects.create(
            board=board,
            title=f"T{i}",
            slug=f"t{i}",
            author=author,
            live=True,
            last_post_at=base - datetime.timedelta(minutes=i),
        )

    client = APIClient()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 20  # page_size
    assert resp.data["next"] is not None  # cursor link
    assert resp.data["results"][0]["slug"] == "t0"  # most-recent activity first
    # Denormalized counters + select_related → no per-row author/board lookups.
    assert len(ctx.captured_queries) <= 6
