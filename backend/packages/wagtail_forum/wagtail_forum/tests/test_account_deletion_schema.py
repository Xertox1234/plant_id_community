"""Account deletion keeps other people's DM threads and the reports a deleted
user filed (Plan B, task 2).

``user.delete()`` must not CASCADE through ``Conversation.participant_a/b``,
``Message.sender`` or ``Report.reporter``. The survivors read through the
existing ``[deleted]`` sentinel, and a NULL side never lets a stranger into the
thread. The ``RagAnswerReport`` half lives in the host app's tests
(``apps/forum_host/tests/test_account_deletion_schema.py``): this package must
not import the host.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient
from wagtail_forum.models import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
    Post,
    Report,
    Topic,
)
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

pytestmark = pytest.mark.django_db


def _api(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _group(creator, others, title="crew"):
    conversation = Conversation.create_group(creator, title, others)
    return conversation


@pytest.fixture
def world():
    a = User.objects.create_user(username="ada")
    b = User.objects.create_user(username="babbage")
    c = User.objects.create_user(username="curie")
    direct = Conversation.between(a, b)
    Message.objects.create(conversation=direct, sender=a, body="from a direct")
    Message.objects.create(conversation=direct, sender=b, body="from b direct")
    group = _group(b, [a, c])
    Message.objects.create(conversation=group, sender=a, body="from a group")
    Message.objects.create(conversation=group, sender=b, body="from b group")
    return a, b, c, direct, group


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_conversations_survive_participant_deletion(world):
    a, b, c, direct, group = world

    a.delete()

    assert Conversation.objects.filter(pk__in=[direct.pk, group.pk]).count() == 2
    assert Message.objects.filter(conversation=direct).count() == 2
    assert Message.objects.filter(conversation=group).count() == 2
    direct.refresh_from_db()
    assert direct.participant_a_id is None
    assert direct.participant_b_id == b.pk

    client = _api(b)
    listing = client.get("/forum/conversations/")
    assert listing.status_code == 200
    ids = {row["id"] for row in listing.data["results"]}
    assert ids == {direct.pk, group.pk}
    row = next(r for r in listing.data["results"] if r["id"] == direct.pk)
    assert row["other_participant"]["username"] == "[deleted]"

    unread = client.get("/forum/conversations/unread-count/")
    assert unread.status_code == 200
    # (before any thread is opened) the deleted sender's messages still count as unread for B
    assert unread.data["count"] == 2

    for conversation in (direct, group):
        resp = client.get(f"/forum/conversations/{conversation.pk}/messages/")
        assert resp.status_code == 200
        by_body = {m["body"]: m["sender"]["username"] for m in resp.data["results"]}
        assert by_body[f"from a {'direct' if conversation == direct else 'group'}"] == (
            "[deleted]"
        )
        assert "babbage" in by_body.values()

    assert client.get(f"/forum/conversations/{direct.pk}/").status_code == 200
    # the group lost only A's membership row
    assert group.participant_ids() == {b.pk, c.pk}


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_orphaned_direct_thread_is_closed_to_strangers(world):
    a, b, c, direct, group = world
    a.delete()

    stranger = _api(c)
    assert (
        stranger.get(f"/forum/conversations/{direct.pk}/messages/").status_code == 404
    )
    assert (
        stranger.post(
            f"/forum/conversations/{direct.pk}/messages/", {"body": "hi"}
        ).status_code
        == 404
    )
    assert stranger.get(f"/forum/conversations/{direct.pk}/").status_code == 404
    listing = stranger.get("/forum/conversations/")
    assert direct.pk not in {r["id"] for r in listing.data["results"]}


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_survivor_cannot_send_into_a_thread_whose_other_side_is_gone(world):
    a, b, c, direct, group = world
    a.delete()

    resp = _api(b).post(
        f"/forum/conversations/{direct.pk}/messages/", {"body": "hello?"}
    )

    assert resp.status_code == 403
    assert Message.objects.filter(conversation=direct, body="hello?").count() == 0


@pytest.mark.urls("wagtail_forum.tests.api.urls")
def test_both_sides_deleted_leaves_an_unreachable_row(world):
    a, b, c, direct, group = world
    a.delete()
    b.delete()

    direct.refresh_from_db()
    assert direct.participant_a_id is None and direct.participant_b_id is None
    assert _api(c).get(f"/forum/conversations/{direct.pk}/messages/").status_code == 404


def test_new_pair_after_deletion_does_not_collide_with_the_orphan(world):
    a, b, c, direct, group = world
    a.delete()

    other = Conversation.between(b, c)
    assert other.pk != direct.pk


def test_direct_shape_check_still_rejects_a_group_with_a_participant():
    a = User.objects.create_user(username="x1")
    with pytest.raises(IntegrityError), transaction.atomic():
        Conversation.objects.create(kind=ConversationKind.GROUP, participant_a=a)


def test_reports_survive_reporter_deletion():
    reporter = User.objects.create_user(username="reporter")
    author = User.objects.create_user(username="author")
    forum = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=forum, title="T", slug="t", author=author)
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>x</p>"}],
    )
    other = User.objects.create_user(username="other")
    conversation = Conversation.between(author, other)
    message = Message.objects.create(conversation=conversation, sender=author, body="m")
    post_report = Report.objects.create(
        post=post, reporter=reporter, reason=Report.SPAM
    )
    msg_report = Report.objects.create(
        message=message, reporter=reporter, reason=Report.ABUSE
    )

    reporter.delete()

    post_report.refresh_from_db()
    msg_report.refresh_from_db()
    assert post_report.reporter_id is None
    assert msg_report.reporter_id is None
    assert Report.objects.count() == 2


def test_two_deleted_reporters_may_report_the_same_post():
    """Unique (post, reporter) must not collapse NULL reporters."""
    r1 = User.objects.create_user(username="r1")
    r2 = User.objects.create_user(username="r2")
    author = User.objects.create_user(username="auth2")
    forum = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=forum, title="T", slug="t", author=author)
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>x</p>"}],
    )
    Report.objects.create(post=post, reporter=r1, reason=Report.SPAM)
    Report.objects.create(post=post, reporter=r2, reason=Report.SPAM)

    r1.delete()
    r2.delete()

    assert Report.objects.filter(post=post, reporter__isnull=True).count() == 2


def test_post_has_a_nullable_indexed_erase_after():
    field = Post._meta.get_field("erase_after")
    assert field.null and field.blank and field.db_index


def test_moderation_queue_renders_null_reporter(client):
    reporter = User.objects.create_user(username="reporter")
    author = User.objects.create_user(username="author")
    other = User.objects.create_user(username="other")
    forum = make_forum(name="General", slug="general")
    topic = Topic.objects.create(board=forum, title="T", slug="t", author=author)
    post = Post.objects.create(
        topic=topic,
        author=author,
        is_opening_post=True,
        body=[{"type": "paragraph", "value": "<p>x</p>"}],
    )
    conversation = Conversation.between(author, other)
    message = Message.objects.create(conversation=conversation, sender=author, body="m")
    post_report = Report.objects.create(
        post=post, reporter=reporter, reason=Report.SPAM
    )
    msg_report = Report.objects.create(
        message=message, reporter=reporter, reason=Report.ABUSE
    )
    reporter.delete()
    # a deleted DM sender too: the message summary must not print "None"
    author.delete()

    moderator = User.objects.create_user(username="moderator")
    moderator.groups.add(Group.objects.get(name="Forum Moderators"))
    client.force_login(moderator)

    resp = client.get(reverse("wagtail_forum_reports:moderation_queue"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "[deleted]" in body
    assert ": m" in body or "[deleted]: m" in body

    csv = client.get(
        reverse("wagtail_forum_reports:moderation_queue"), {"export": "csv"}
    )
    assert csv.status_code == 200

    for report in (post_report, msg_report):
        inspect = reverse(
            Report.snippet_viewset.get_url_name("inspect"), args=[report.pk]
        )
        assert client.get(inspect).status_code == 200
    snippet_list = reverse(Report.snippet_viewset.get_url_name("list"))
    assert client.get(snippet_list).status_code == 200
    assert client.get(snippet_list, {"export": "csv"}).status_code == 200


def test_membership_row_of_deleted_user_is_the_only_cascade(world):
    a, b, c, direct, group = world
    before = ConversationParticipant.objects.count()
    a.delete()
    assert ConversationParticipant.objects.count() == before - 2  # direct + group
