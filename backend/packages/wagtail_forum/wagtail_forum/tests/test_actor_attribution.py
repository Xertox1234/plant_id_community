"""Audit 2026-07-11 M15: API-driven publish/unpublish must attribute the acting
user in Wagtail's audit log (visible on the snippet History tab) instead of
logging user=None ("system"). Wagtail's LogContext only activates inside admin
views, so the DRF paths must pass the user explicitly (with
skip_permission_checks=True — the trust logic, not Wagtail editor permissions,
is the publish authority)."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from wagtail.models import ModelLogEntry, Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow

User = get_user_model()
pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    cache.clear()
    yield
    cache.clear()


def _board():
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _member(username):
    user = User.objects.create_user(username=username)
    profile = ForumProfile.for_user(user)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    return user


@pytest.mark.django_db
def test_trusted_api_publish_logs_acting_user():
    ensure_default_workflow()
    board = _board()
    user = _member("ada")
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "Attribution",
            "slug": "attribution",
            "body": [{"type": "paragraph", "value": "<p>hello</p>"}],
        },
        format="json",
        **{"HTTP_IDEMPOTENCY_KEY": "attr-1"},
    )
    assert resp.status_code == 201
    assert resp.data["status"] == "published"

    post = Post.objects.get(topic__slug="attribution")
    entry = (
        ModelLogEntry.objects.filter(action="wagtail.publish", object_id=str(post.pk))
        .order_by("-timestamp")
        .first()
    )
    assert entry is not None
    assert entry.user == user  # was None ("system") before the M15 fix


@pytest.mark.django_db
def test_api_delete_unpublish_logs_acting_user():
    ensure_default_workflow()
    board = _board()
    author = _member("bea")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=author, live=True
    )
    reply = Post.objects.create(
        topic=topic,
        author=author,
        live=True,
        body=[{"type": "paragraph", "value": "<p>reply</p>"}],
    )

    client = APIClient()
    client.force_authenticate(author)
    resp = client.delete(f"/forum/posts/{reply.id}/")

    assert resp.status_code == 204
    entry = (
        ModelLogEntry.objects.filter(
            action="wagtail.unpublish", object_id=str(reply.pk)
        )
        .order_by("-timestamp")
        .first()
    )
    assert entry is not None
    assert entry.user == author  # was None ("system") before the M15 fix
