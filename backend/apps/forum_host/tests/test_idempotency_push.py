"""M35 end-to-end (todo 258): a retried PATCH with the same Idempotency-Key must
produce exactly ONE revision and ONE FCM push. Runs through the REAL host URL
(/api/v1/forum/) so the full submit_edit_for_moderation → moderation_decided
signal → host receiver → send_forum_push chain is exercised, not stubbed — which
is the whole point of M35 (the mobile duplicate-push bug a flaky network would
otherwise trigger, todo 260)."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.blocks import ForumBodyBlock
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.workflow import ensure_default_workflow, submit_for_moderation

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    """The idempotency + rate-limit state share Django's cache; clear it around
    each test so keys do not bleed (LocMemCache is process-global)."""
    cache.clear()
    yield
    cache.clear()


def _member_reply():
    """A published reply by a MEMBER (trust >= autopublish) whose edits publish
    immediately and fire moderation_decided(status='published')."""
    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="ed258")
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()

    topic = Topic(board=board, title="t", slug="t", author=author, live=False)
    topic.save()
    op = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=ForumBodyBlock().to_python([{"type": "paragraph", "value": "<p>op</p>"}]),
        live=False,
    )
    op.save()
    submit_for_moderation(op, author)
    reply = Post(
        topic=topic,
        author=author,
        body=ForumBodyBlock().to_python([{"type": "paragraph", "value": "<p>r</p>"}]),
        live=False,
    )
    reply.save()
    submit_for_moderation(reply, author)
    return author, reply


@override_settings(FORUM_RATELIMITS={"post_update": "100/h"})
@pytest.mark.django_db
def test_patch_idempotent_retry_yields_one_revision_and_one_push():
    author, reply = _member_reply()
    client = APIClient()
    client.force_authenticate(author)
    payload = {"body": [{"type": "paragraph", "value": "<p>edited</p>"}]}

    # Mock only the enqueue: the setup submits above already fired their own
    # (real, swallowed) pushes — the mock counts only pushes from the two PATCHes.
    with patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push:
        first = client.patch(
            f"/api/v1/forum/posts/{reply.id}/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="edit-258",
        )
        revisions_after_first = reply.revisions.count()
        retry = client.patch(
            f"/api/v1/forum/posts/{reply.id}/",
            payload,
            format="json",
            HTTP_IDEMPOTENCY_KEY="edit-258",
        )

    assert first.status_code == 200
    assert retry.status_code == 200
    assert retry.data == first.data  # replayed, not recomputed
    # ONE revision: the replay short-circuits before submit_edit_for_moderation,
    # so no second save_revision (which is what re-fires the signal + push).
    assert reply.revisions.count() == revisions_after_first
    # ONE signal → ONE push: a second signal would enqueue a second push (there
    # is no dedup at the notification layer — idempotency is the only guard).
    mock_push.assert_called_once()


@override_settings(FORUM_RATELIMITS={"topic_create": "100/h"})
@pytest.mark.django_db
def test_topic_create_location_header_under_namespaced_host_mount():
    """L19 (258 review): the Location header must resolve under the REAL nested
    host namespace (`v1:wagtail_forum_api`), not just the bare package urlconf —
    the exact-value tests elsewhere run under the flat urlconf and only exercise
    `_created_location`'s fallback branch. Also pins that a same-key replay
    carries the identical namespaced Location."""
    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    board = index.add_child(instance=ForumBoard(title="General", slug="general"))
    author = User.objects.create_user(username="loc258")
    profile = ForumProfile.for_user(author)
    profile.trust_level = TrustLevel.MEMBER
    profile.save()
    client = APIClient()
    client.force_authenticate(author)
    payload = {
        "title": "Hi",
        "slug": "hi",
        "body": [{"type": "paragraph", "value": "<p>x</p>"}],
    }

    r1 = client.post(
        f"/api/v1/forum/boards/{board.slug}/topics/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="loc-1",
    )
    r2 = client.post(
        f"/api/v1/forum/boards/{board.slug}/topics/",
        payload,
        format="json",
        HTTP_IDEMPOTENCY_KEY="loc-1",
    )

    assert r1.status_code == 201
    # Exact value under the nested mount — a malformed namespace prefix would fail
    # here even though the flat-urlconf tests would still pass.
    assert r1["Location"] == f"http://testserver/api/v1/forum/topics/{r1.data['id']}/"
    assert r2.status_code == 201
    assert r2["Location"] == r1["Location"]  # replay carries the same Location
