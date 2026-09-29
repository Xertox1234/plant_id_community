"""Superusers and forum moderators publish without moderation (todo 423).

The owner's own post (topic 44, post 289) sat as a draft because trust came
only from post count: ``plantadmin`` had one live post, so trust Basic, so the
spam check held it. Owner decision 2026-09-28: a superuser, or an author
holding the forum moderator permission (``MODERATION_BYPASS_PERMISSION``,
default ``wagtail_forum.publish_post``, which the bootstrapped "Forum
Moderators" group holds), is trusted, checked at request time. Plain
``is_staff`` without that permission is not.

These drive the real HTTP API, which is also what the mobile app calls
(``plant_community_mobile`` posts to the same ``/forum/`` endpoints), so the
create and edit paths are pinned for both clients. The content is spam the
heuristic check holds (five links), so a "published" here can only come from
the bypass, never from the spam check passing it.

Trust stays the AUTHOR's: a moderator acting on an untrusted member's content
must not publish it on the moderator's standing.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    ForumProfile,
    Message,
    Post,
    Topic,
    TrustLevel,
)
from wagtail_forum.tests.api.test_direct_messages_api import _RECORDING_PATH
from wagtail_forum.tests.api.test_direct_messages_api import (
    _RecordingSpamBackend as RecordingSpamBackend,
)
from wagtail_forum.workflow import (
    author_bypasses_moderation,
    ensure_default_workflow,
    submit_for_moderation,
)

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]

SPAM = "http://a.com http://b.com http://c.com http://d.com http://e.com"


@pytest.fixture(autouse=True)
def clear_idempotency_cache():
    cache.clear()
    yield
    cache.clear()


def _board():
    ensure_default_workflow()
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug="forum"))
    return index.add_child(instance=ForumBoard(title="General", slug="general"))


def _new_member(username, **extra):
    """Trust NEW (0): below TRUST_AUTOPUBLISH_LEVEL, so screened by default."""
    user = User.objects.create_user(username=username, **extra)
    assert ForumProfile.for_user(user).trust_level == TrustLevel.NEW
    return user


def _superuser(username):
    user = User.objects.create_superuser(username=username, email=f"{username}@x.io")
    assert ForumProfile.for_user(user).trust_level == TrustLevel.NEW
    return user


def _staff_moderator(username):
    """A staff account in the bootstrapped "Forum Moderators" group: how a
    real staff moderator is provisioned (forum_host/bootstrap.py)."""
    user = _new_member(username, is_staff=True)
    user.groups.add(Group.objects.get(name="Forum Moderators"))
    return User.objects.get(pk=user.pk)  # fresh instance: no stale perm cache


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _create_topic(user, board, slug="t"):
    return _client(user).post(
        f"/forum/boards/{board.slug}/topics/",
        {
            "title": "My topic",
            "slug": slug,
            "body": [{"type": "paragraph", "value": f"<p>{SPAM}</p>"}],
        },
        format="json",
    )


def _live_topic(author, board):
    """A live thread by ``author`` with clean content, built directly."""
    topic = Topic.objects.create(
        board=board, title="Live", slug="live", author=author, live=False
    )
    post = Post(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>clean</p>"}],
    )
    post.save()
    post.save_revision(user=author).publish(user=author, skip_permission_checks=True)
    topic.refresh_from_db()
    post.refresh_from_db()
    assert topic.live and post.live
    return topic, post


def _patch_spam(client, post):
    return client.patch(
        f"/forum/posts/{post.id}/",
        {"body": [{"type": "paragraph", "value": f"<p>edited {SPAM}</p>"}]},
        format="json",
    )


# --- create path ------------------------------------------------------------


def test_untrusted_member_topic_is_held_the_control():
    board = _board()
    resp = _create_topic(_new_member("newbie"), board)

    assert resp.status_code == 201
    assert resp.data["status"] == "pending"
    assert Topic.objects.get(pk=resp.data["id"]).live is False


def test_superuser_topic_publishes_immediately_with_its_opening_post():
    board = _board()
    resp = _create_topic(_superuser("plantadmin"), board)

    assert resp.status_code == 201
    assert resp.data["status"] == "published"
    topic = Topic.objects.get(pk=resp.data["id"])
    assert topic.live is True
    assert topic.posts.get(is_opening_post=True).live is True


def test_staff_moderator_topic_publishes_immediately():
    board = _board()
    resp = _create_topic(_staff_moderator("staffmod"), board)

    assert resp.data["status"] == "published"
    assert Topic.objects.get(pk=resp.data["id"]).live is True


def test_superuser_reply_publishes_immediately():
    board = _board()
    member = User.objects.create_user(username="member")
    topic, _ = _live_topic(member, board)

    resp = _client(_superuser("plantadmin")).post(
        f"/forum/topics/{topic.id}/posts/",
        {"body": [{"type": "paragraph", "value": f"<p>{SPAM}</p>"}]},
        format="json",
    )

    assert resp.status_code == 201, resp.data
    assert resp.data["status"] == "published"


def test_plain_staff_without_the_moderator_permission_is_still_moderated():
    # Owner decision 2026-09-28: superusers plus the forum moderator
    # permission. is_staff alone is not a moderation right.
    board = _board()
    resp = _create_topic(_new_member("staffonly", is_staff=True), board)

    assert resp.data["status"] == "pending"


def test_bypass_is_computed_at_request_time_not_stored_as_trust():
    board = _board()
    user = _new_member("promoted")
    assert _create_topic(user, board, slug="before").data["status"] == "pending"

    user.groups.add(Group.objects.get(name="Forum Moderators"))
    user = User.objects.get(pk=user.pk)

    assert _create_topic(user, board, slug="after").data["status"] == "published"
    # Nothing was backfilled into the stored trust level: it is only what one
    # live post earns (Basic), still below the autopublish level.
    assert ForumProfile.for_user(user).trust_level == TrustLevel.BASIC


@override_settings(WAGTAILFORUM_MODERATION_BYPASS_PERMISSION=None)
def test_a_host_can_limit_the_bypass_to_superusers():
    board = _board()

    assert _create_topic(_staff_moderator("mod"), board, "m").data["status"] == (
        "pending"
    )
    assert _create_topic(_superuser("root"), board, "r").data["status"] == ("published")


def test_inactive_superuser_does_not_bypass():
    user = _superuser("gone")
    user.is_active = False

    assert author_bypasses_moderation(user) is False
    assert author_bypasses_moderation(None) is False


# --- edit path ------------------------------------------------------------


def test_superuser_edit_of_own_post_publishes_immediately():
    board = _board()
    admin = _superuser("plantadmin")
    _topic, post = _live_topic(admin, board)

    resp = _patch_spam(_client(admin), post)

    assert resp.status_code == 200, resp.data
    assert resp.data["moderation_status"] == "published"
    post.refresh_from_db()
    assert "edited" in post.body.raw_data[0]["value"]


def test_staff_moderator_edit_of_own_post_publishes_immediately():
    board = _board()
    mod = _staff_moderator("staffmod")
    _topic, post = _live_topic(mod, board)

    resp = _patch_spam(_client(mod), post)

    assert resp.data["moderation_status"] == "published"


# --- author-based, never caller-based --------------------------------------


def test_superuser_editing_an_untrusted_members_post_leaves_it_held():
    board = _board()
    member = _new_member("newbie")
    _topic, post = _live_topic(member, board)

    resp = _patch_spam(_client(_superuser("plantadmin")), post)

    assert resp.status_code == 200, resp.data
    assert resp.data["moderation_status"] == "pending"
    post.refresh_from_db()
    assert "clean" in post.body.raw_data[0]["value"]  # live body unchanged


def test_moderator_editing_an_untrusted_members_post_leaves_it_held():
    board = _board()
    member = _new_member("newbie")
    _topic, post = _live_topic(member, board)

    resp = _patch_spam(_client(_staff_moderator("staffmod")), post)

    assert resp.data["moderation_status"] == "pending"


def test_superuser_submitting_an_untrusted_members_draft_does_not_publish_it():
    board = _board()
    member = _new_member("newbie")
    topic = Topic.objects.create(
        board=board, title="T", slug="t", author=member, live=False
    )
    post = Post(
        topic=topic,
        author=member,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": f"<p>{SPAM}</p>"}],
    )
    post.save()

    status = submit_for_moderation(post, _superuser("plantadmin"))

    assert status == "pending"
    assert post.live is False


# --- direct messages share the same notion of trusted ----------------------


@override_settings(WAGTAILFORUM_SPAM_BACKEND=_RECORDING_PATH)
def test_moderator_dm_skips_the_configured_backend_like_a_trusted_member():
    RecordingSpamBackend.calls = []
    sender = _staff_moderator("staffmod")
    recipient = User.objects.create_user(username="rcpt")

    resp = _client(sender).post(
        f"/forum/users/{recipient.username}/messages/", {"body": "hello"}
    )

    assert resp.status_code == 201, resp.data
    assert RecordingSpamBackend.calls == []
    assert Message.objects.get().body == "hello"


def test_the_bypass_permission_is_the_moderators_publish_right():
    # The default permission is one the bootstrapped group actually holds, so
    # "forum moderator" means the same people everywhere.
    group = Group.objects.get(name="Forum Moderators")
    assert group.permissions.filter(
        pk=Permission.objects.get(
            content_type__app_label="wagtail_forum", codename="publish_post"
        ).pk
    ).exists()
