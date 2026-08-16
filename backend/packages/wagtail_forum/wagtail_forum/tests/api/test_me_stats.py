"""Authenticated user's forum statistics endpoint."""

import io

import pytest
from django.contrib.auth import get_user_model
from PIL import Image as PILImage
from rest_framework.test import APIClient
from wagtail.images import get_image_model
from wagtail.models import Page
from wagtail_forum.collections import get_forum_image_collection
from wagtail_forum.models import (
    ForumBoard,
    ForumIdentificationAttachment,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
)

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """Prevent idempotency cache from bleeding between tests (LocMemCache is process-global)."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _jpeg_bytes():
    buf = io.BytesIO()
    PILImage.new("RGB", (10, 10), color="green").save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _forum_image(uploader):
    """An image row for testing identification attachments."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    return get_image_model().objects.create(
        title="plant.jpg",
        file=SimpleUploadedFile("plant.jpg", _jpeg_bytes(), content_type="image/jpeg"),
        collection=get_forum_image_collection(),
        uploaded_by_user=uploader,
    )


@pytest.mark.django_db
def test_me_stats_requires_auth():
    """Anonymous GET /forum/me/stats/ returns 401 or 403."""
    resp = APIClient().get("/forum/me/stats/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_me_stats_fresh_user_all_zeros():
    """Fresh authenticated user with no activity returns all zeros."""
    user = User.objects.create_user(username="fresh")
    ForumProfile.for_user(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.get("/forum/me/stats/")
    assert resp.status_code == 200
    assert resp.data["posts"] == 0
    assert resp.data["solutions_accepted"] == 0
    assert resp.data["identifications_shared"] == 0


@pytest.mark.django_db
def test_me_stats_full_path():
    """Full path: user posts replies, one accepted as solution, creates identification."""
    # Setup: board and users
    board = _board()
    other_user = User.objects.create_user(username="other")
    requester = User.objects.create_user(username="requester")
    ForumProfile.for_user(requester)

    # Create a topic authored by other_user
    topic = Topic.objects.create(
        board=board, title="Help needed", slug="help-needed", author=other_user
    )
    opening = Post.objects.create(
        topic=topic, author=other_user, is_opening_post=True, live=False
    )
    opening.save_revision().publish()  # publish the opening post

    # Create a reply by requester
    reply1 = Post.objects.create(
        topic=topic, author=requester, is_opening_post=False, live=False
    )
    reply1.save_revision().publish()  # publish the reply — counts as 1 post

    # Create another reply by requester (so total posts = 2)
    reply2 = Post.objects.create(
        topic=topic, author=requester, is_opening_post=False, live=False
    )
    reply2.save_revision().publish()  # publish the second reply — counts as 1 more

    # Set reply1 as the solution
    topic.solved_post = reply1
    topic.save(update_fields=["solved_post"])

    # Create a topic authored by requester with an identification attachment
    own_topic = Topic.objects.create(
        board=board, title="What is this?", slug="what-is-this", author=requester
    )
    own_opening = Post.objects.create(
        topic=own_topic, author=requester, is_opening_post=True, live=False
    )
    own_opening.save_revision().publish()  # publish own opening post — counts as 1

    # Create identification attachment on requester's topic
    image = _forum_image(requester)
    ForumIdentificationAttachment.objects.create(
        topic=own_topic,
        image=image,
        provider="plant_id",
        candidates=[
            {
                "name": "Monstera deliciosa",
                "scientific_name": "Monstera deliciosa",
                "confidence": 0.95,
            }
        ],
    )

    # Query stats
    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/me/stats/")

    assert resp.status_code == 200
    # Total posts by requester: reply1, reply2, own_opening = 3
    assert resp.data["posts"] == 3
    # Solutions accepted: reply1 is solution on other_user's topic (counts)
    assert resp.data["solutions_accepted"] == 1
    # Identifications shared: 1 on own_topic
    assert resp.data["identifications_shared"] == 1


@pytest.mark.django_db
def test_me_stats_another_users_solution_does_not_count():
    """Another user's solution marked on their topic does not count."""
    board = _board()
    requester = User.objects.create_user(username="requester")
    ForumProfile.for_user(requester)
    other_user = User.objects.create_user(username="other")

    # Create a topic by other_user
    topic = Topic.objects.create(
        board=board, title="Other's topic", slug="others-topic", author=other_user
    )
    opening = Post.objects.create(
        topic=topic, author=other_user, is_opening_post=True, live=False
    )
    opening.save_revision().publish()

    # other_user's reply
    other_reply = Post.objects.create(
        topic=topic, author=other_user, is_opening_post=False, live=False
    )
    other_reply.save_revision().publish()

    # Set other_user's reply as the solution
    topic.solved_post = other_reply
    topic.save(update_fields=["solved_post"])

    # Query requester's stats
    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/me/stats/")

    assert resp.status_code == 200
    assert resp.data["posts"] == 0
    assert resp.data["solutions_accepted"] == 0
    assert resp.data["identifications_shared"] == 0


@pytest.mark.django_db
def test_me_stats_unpublished_posts_not_counted():
    """Unpublished (draft) posts are not counted toward post_count."""
    board = _board()
    requester = User.objects.create_user(username="requester")
    other_user = User.objects.create_user(username="other")
    ForumProfile.for_user(requester)

    # Create topic by other_user
    topic = Topic.objects.create(
        board=board, title="Topic", slug="topic", author=other_user
    )
    opening = Post.objects.create(
        topic=topic, author=other_user, is_opening_post=True, live=False
    )
    opening.save_revision().publish()

    # Create unpublished draft reply by requester (never published)
    Post.objects.create(
        topic=topic, author=requester, is_opening_post=False, live=False
    )

    # Create published reply by requester
    published_reply = Post.objects.create(
        topic=topic, author=requester, is_opening_post=False, live=False
    )
    published_reply.save_revision().publish()

    # Query stats
    client = APIClient()
    client.force_authenticate(requester)
    resp = client.get("/forum/me/stats/")

    assert resp.status_code == 200
    # Only published_reply counts; draft_reply is ignored (live=False, never published)
    assert resp.data["posts"] == 1
    assert resp.data["solutions_accepted"] == 0
    assert resp.data["identifications_shared"] == 0
