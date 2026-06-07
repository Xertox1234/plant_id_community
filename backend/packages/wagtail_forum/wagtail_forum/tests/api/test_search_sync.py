import datetime

import pytest
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


@pytest.mark.django_db
def test_search_returns_matching_topics():
    board = _board()
    Topic.objects.create(board=board, title="Monstera care", slug="m", live=True)

    resp = APIClient().get("/forum/search/?q=Monstera")
    assert resp.status_code == 200
    assert any(r["slug"] == "m" for r in resp.data["results"])


@pytest.mark.django_db
def test_sync_returns_topics_changed_since():
    board = _board()
    old = Topic.objects.create(board=board, title="old", slug="old", live=True)
    Topic.objects.filter(id=old.id).update(
        updated_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)
    )
    Topic.objects.create(board=board, title="fresh", slug="fresh", live=True)

    since = "2021-01-01T00:00:00Z"
    resp = APIClient().get(f"/forum/sync/?since={since}&board={board.slug}")
    assert resp.status_code == 200
    slugs = [t["slug"] for t in resp.data["topics"]]
    assert "fresh" in slugs and "old" not in slugs
