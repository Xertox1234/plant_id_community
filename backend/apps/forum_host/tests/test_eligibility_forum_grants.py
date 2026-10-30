"""Send-time eligibility follows each recipient's forum grants (todo 676).

A post on a forum guests cannot read is still delivered to the members who
may read it, and suppressed as gone content for those who may not, in a
constant number of queries whatever the recipient count.
"""

import pytest
from apps.forum_host.eligibility import REASON_CONTENT, recheck
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from wagtail_forum.models import ForumGrant, ForumRole, Post, Topic
from wagtail_forum.services.forum_permissions import set_grant
from wagtail_forum.tests.factories import make_forum

User = get_user_model()
pytestmark = pytest.mark.django_db


def _private_post():
    insiders = Group.objects.create(name="Insiders")
    forum = make_forum(name="Private", slug="private")
    set_grant(forum, ForumGrant.ANONYMOUS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.MEMBERS, ForumRole.NO_ACCESS)
    set_grant(forum, ForumGrant.GROUP, ForumRole.STANDARD, group=insiders)
    author = User.objects.create_user(username="author")
    topic = Topic.objects.create(
        board=forum, title="T", slug="t", author=author, live=True
    )
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        live=True,
        body=[{"type": "paragraph", "value": "<p>hi</p>"}],
    )
    return insiders, author, post


def _users(n, prefix, group=None):
    users = [User.objects.create_user(username=f"{prefix}{i}") for i in range(n)]
    if group is not None:
        for user in users:
            user.groups.add(group)
    return users


def test_only_recipients_who_can_read_the_forum_stay_eligible():
    insiders, author, post = _private_post()
    insider, outsider = _users(1, "in", insiders)[0], _users(1, "out")[0]
    data = {"post_id": post.pk, "actor_id": author.pk}

    result = recheck("mention", [insider.pk, outsider.pk], data, "push")

    assert [u.pk for u in result.eligible] == [insider.pk]
    assert result.suppressed == {outsider.pk: REASON_CONTENT}


def test_the_query_count_does_not_grow_with_recipients():
    insiders, author, post = _private_post()
    data = {"post_id": post.pk, "actor_id": author.pk}

    def count(users):
        ids = [u.pk for u in users]
        with CaptureQueriesContext(connection) as ctx:
            recheck("mention", ids, data, "push")
        return len(ctx.captured_queries)

    few = count(_users(1, "a", insiders) + _users(1, "b"))
    many = count(_users(5, "c", insiders) + _users(5, "d"))

    assert few == many
