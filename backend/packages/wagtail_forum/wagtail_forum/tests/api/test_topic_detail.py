import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Topic

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


@pytest.mark.django_db
def test_topic_detail_returns_live_topic():
    board = _board()
    author = User.objects.create_user(username="ada", password="x")
    topic = Topic.objects.create(
        board=board, title="Hello", slug="hello", author=author, live=True
    )
    opening = Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=True
    )

    resp = APIClient().get(f"/forum/topics/{topic.id}/")

    assert resp.status_code == 200
    assert resp.data["id"] == topic.id
    assert resp.data["title"] == "Hello"
    assert resp.data["board"]["slug"] == "general"
    assert resp.data["author"] == "ada"
    assert resp.data["opening_post_id"] == opening.id


@pytest.mark.django_db
def test_topic_detail_hides_draft_topic():
    board = _board()
    topic = Topic.objects.create(board=board, title="Draft", slug="draft", live=False)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404


@pytest.mark.django_db
def test_topic_detail_hides_topic_on_unpublished_board():
    board = _board()
    board.live = False
    board.save()
    topic = Topic.objects.create(board=board, title="X", slug="x", live=True)
    assert APIClient().get(f"/forum/topics/{topic.id}/").status_code == 404
