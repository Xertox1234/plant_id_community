"""A coalesced reply notification counts the folded replies by each
recipient's own forum grants, the recheck's rule (audit 2026-11-21 M5).

The fold count used the guest view, so on a forum guests cannot read every
folded reply looked gone: the member was told about 1 reply of 4 and the
other rows were suppressed as coalesced.
"""

import datetime

import pytest
from apps.forum_host.pacing import Send, _count_folds
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from wagtail_forum.models import ForumGrant, ForumRole, Post, Topic
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.django_db


def _private_thread(n_replies):
    insiders = Group.objects.create(name="Insiders")
    forum = make_forum(name="Private", slug="private")
    set_grant(forum, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.GROUP, ForumRole.STANDARD, group=insiders)
    author = User.objects.create_user(username="author")
    topic = Topic.objects.create(
        board=forum, title="T", slug="t", author=author, live=True
    )
    start = timezone.now() - datetime.timedelta(minutes=30)
    replies = [
        Post.objects.create(
            topic=topic,
            author=author,
            live=True,
            first_published_at=start + datetime.timedelta(minutes=i),
            body=[{"type": "paragraph", "value": f"<p>reply {i}</p>"}],
        )
        for i in range(n_replies)
    ]
    return insiders, replies


def test_a_member_who_reads_a_private_forum_is_told_every_folded_reply():
    insiders, replies = _private_thread(4)
    insider = User.objects.create_user(username="insider")
    insider.groups.add(insiders)
    dispatched, *held = replies
    send = Send(user=insider, folded={i: post.pk for i, post in enumerate(held)})

    _count_folds([send], dispatched.pk)

    assert send.count == 4
    assert send.latest == held[-1]


def test_a_recipient_who_cannot_read_the_forum_is_told_none_of_them():
    _insiders, replies = _private_thread(3)
    outsider = User.objects.create_user(username="outsider")
    dispatched, *held = replies
    send = Send(user=outsider, folded={i: post.pk for i, post in enumerate(held)})

    _count_folds([send], dispatched.pk)

    assert send.count == 1
    assert send.latest is None


def test_a_folded_push_names_the_newest_replier_by_forum_name():
    """Never the legal name sign-in copied into first_name (audit H1)."""
    from apps.forum_host.pacing import folded_data

    _insiders, replies = _private_thread(1)
    named = User.objects.create_user(
        username="member_fold0001", first_name="Ada", last_name="Lovelace"
    )
    replies[0].author = named
    send = Send(user=named, count=2, latest=replies[0])

    assert folded_data({"post_id": "1"}, send)["actor_name"] == "member_fold0001"
