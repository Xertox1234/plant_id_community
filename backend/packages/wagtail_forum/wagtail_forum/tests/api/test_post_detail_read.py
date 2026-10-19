"""GET /posts/<id>/ — one post, as the list serves it (forum live replies).

A live client hears "post N changed" and fetches that one post as itself, so
this read must apply the list's visibility and per-viewer fields exactly.
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from wagtail.models import PageViewRestriction
from wagtail_forum.models import Post, UserBlock

from .test_post_list import _topic_with_image_posts, _topic_with_posts

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


def _client(username="reader"):
    client = APIClient()
    client.force_authenticate(User.objects.create_user(username=username))
    return client


def _first_post(topic):
    return topic.posts.order_by("pk").first()


@pytest.mark.django_db
def test_get_post_returns_list_item_shape():
    topic = _topic_with_posts(2)
    client = _client()
    listed = client.get(f"/forum/topics/{topic.id}/posts/").data["results"][1]
    resp = client.get(f"/forum/posts/{listed['id']}/")
    assert resp.status_code == 200
    assert resp.data == listed


@pytest.mark.django_db
def test_get_post_with_images_matches_list_item():
    topic = _topic_with_image_posts(1)
    client = _client()
    listed = client.get(f"/forum/topics/{topic.id}/posts/").data["results"][0]
    resp = client.get(f"/forum/posts/{listed['id']}/")
    assert resp.status_code == 200
    assert resp.data == listed


@pytest.mark.django_db
def test_get_post_anonymous_401():
    topic = _topic_with_posts(1)
    resp = APIClient().get(f"/forum/posts/{_first_post(topic).id}/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_get_unpublished_post_404():
    topic = _topic_with_posts(2)
    post = topic.posts.order_by("pk").last()
    Post.objects.filter(pk=post.pk).update(live=False)
    assert _client().get(f"/forum/posts/{post.id}/").status_code == 404


@pytest.mark.django_db
def test_get_post_in_unpublished_topic_404():
    topic = _topic_with_posts(1)
    type(topic).objects.filter(pk=topic.pk).update(live=False)
    resp = _client().get(f"/forum/posts/{_first_post(topic).id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_post_on_restricted_board_404():
    topic = _topic_with_posts(1)
    PageViewRestriction.objects.create(page=topic.board, restriction_type="login")
    resp = _client().get(f"/forum/posts/{_first_post(topic).id}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_get_post_by_blocked_author_has_is_blocked_true():
    topic = _topic_with_posts(1)
    viewer = User.objects.create_user(username="blocker")
    UserBlock.block(viewer, topic.author)
    client = APIClient()
    client.force_authenticate(viewer)
    resp = client.get(f"/forum/posts/{_first_post(topic).id}/")
    assert resp.status_code == 200
    assert resp.data["is_blocked"] is True


@pytest.mark.django_db
def test_get_post_cache_control_private_no_store():
    topic = _topic_with_posts(1)
    resp = _client().get(f"/forum/posts/{_first_post(topic).id}/")
    assert resp.status_code == 200
    cache_control = resp["Cache-Control"]
    assert "private" in cache_control and "no-store" in cache_control


@pytest.mark.django_db
def test_get_post_query_count_flat():
    topic = _topic_with_image_posts(1)
    client = _client()
    post_id = _first_post(topic).id
    # Warm renditions so the pin measures the steady state.
    assert client.get(f"/forum/posts/{post_id}/").status_code == 200
    # The presence touch is one UPDATE gated by cache.add() on a key that can
    # outlive a DB rebuild; clear it so a recycled pk can't drop the count.
    cache.delete(f"forum:presence:{client.handler._force_user.pk}")
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(f"/forum/posts/{post_id}/")
    assert resp.status_code == 200
    # 6, pinned EXACTLY (docs/rules/testing.md); explain any change:
    # presence UPDATE, the board view-restriction prefetch (.public()), the
    # post itself (topic + board visibility as a subquery, author and avatar
    # joined), the viewer's reactions, the batched image fetch and its
    # renditions. Flat: the same maps the list builds for a page.
    assert len(ctx.captured_queries) == 6, [
        q["sql"][:120] for q in ctx.captured_queries
    ]
