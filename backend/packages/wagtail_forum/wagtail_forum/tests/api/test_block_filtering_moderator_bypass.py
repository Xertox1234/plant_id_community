"""A moderator's OWN blocks are inert on every HIDE surface (todo 284/M9).

The AC only requires that ANOTHER user's blocks never affect a moderator's
view (true by construction — the per-viewer filter never reads anyone else's
UserBlock rows). This file goes further and consolidates the stronger,
deliberately uniform version: a moderator's own blocklist is inert
everywhere too, mirroring test_post_edit_delete.py::test_moderator_bypasses_post_lock.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, ForumProfile, Topic, UserBlock

User = get_user_model()
pytestmark = [pytest.mark.django_db, pytest.mark.urls("wagtail_forum.tests.api.urls")]


def _board(slug="general"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    return index.add_child(instance=ForumBoard(title="General", slug=slug))


def _moderator(username):
    u = User.objects.create_user(username=username)
    ForumProfile.for_user(u)
    perm = Permission.objects.get(
        content_type__app_label="wagtail_forum", codename="change_post"
    )
    u.user_permissions.add(perm)
    return User.objects.get(pk=u.pk)  # re-fetch to clear the permission cache


def test_topic_list_moderator_sees_content_from_own_blocklist():
    board = _board("topic-list")
    blocked = User.objects.create_user(username="mod-blocks-topiclist")
    mod = _moderator("mod-topiclist")
    UserBlock.block(mod, blocked)
    Topic.objects.create(board=board, title="T", slug="t", author=blocked, live=True)

    client = APIClient()
    client.force_authenticate(mod)
    resp = client.get(f"/forum/boards/{board.slug}/topics/")

    assert resp.status_code == 200
    assert {t["slug"] for t in resp.data["results"]} == {"t"}


def test_search_moderator_sees_content_from_own_blocklist():
    board = _board("search")
    blocked = User.objects.create_user(username="mod-blocks-search")
    mod = _moderator("mod-search")
    UserBlock.block(mod, blocked)
    Topic.objects.create(
        board=board, title="Monstera repotting", slug="t2", author=blocked, live=True
    )

    client = APIClient()
    client.force_authenticate(mod)
    resp = client.get("/forum/search/?q=Monstera")

    assert resp.status_code == 200
    assert {t["slug"] for t in resp.data["topics"]} == {"t2"}


def test_experts_moderator_sees_a_user_from_own_blocklist():
    _board("experts")
    blocked_expert = User.objects.create_user(username="mod-blocks-expert")
    profile = ForumProfile.for_user(blocked_expert)
    profile.trust_level = 3
    profile.save()
    mod = _moderator("mod-experts")
    UserBlock.block(mod, blocked_expert)

    client = APIClient()
    client.force_authenticate(mod)
    resp = client.get("/forum/users/experts/")

    assert resp.status_code == 200
    assert {row["username"] for row in resp.data["results"]} == {"mod-blocks-expert"}


def test_mentions_typeahead_moderator_sees_a_user_from_own_blocklist():
    blocked = User.objects.create_user(username="mod-blocks-mention")
    mod = _moderator("modmention")
    UserBlock.block(mod, blocked)

    client = APIClient()
    client.force_authenticate(mod)
    resp = client.get("/forum/users/search/?q=mod-blocks")

    assert resp.status_code == 200
    assert {row["username"] for row in resp.data} == {"mod-blocks-mention"}


def test_notifications_moderator_sees_a_notification_from_own_blocklist():
    from wagtail_forum.models import Notification, NotificationVerb, Post
    from wagtail_forum.notifications import create_notifications

    board = _board("notif")
    blocked_actor = User.objects.create_user(username="mod-blocks-actor")
    mod = _moderator("modnotif")
    UserBlock.block(mod, blocked_actor)
    topic = Topic.objects.create(board=board, title="T", slug="t3", author=mod)
    post = Post.objects.create(topic=topic, author=blocked_actor)
    create_notifications(
        recipients=[mod],
        verb=NotificationVerb.REPLY,
        actor=blocked_actor,
        topic=topic,
        post=post,
    )

    client = APIClient()
    client.force_authenticate(mod)
    resp = client.get("/forum/notifications/")

    assert resp.status_code == 200
    assert len(resp.data["results"]) == 1
    assert Notification.objects.filter(recipient=mod, actor=blocked_actor).exists()
