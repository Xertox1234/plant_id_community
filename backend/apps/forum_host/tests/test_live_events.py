"""Live forum events: which writes broadcast what (forum live replies, slice 2).

Every write runs inside ``django_capture_on_commit_callbacks(execute=True)``:
the broadcast waits for commit, and in a plain ``django_db`` test nothing ever
commits. ``live._send`` is replaced by a recorder, so these tests pin the
(group, event) pairs and never touch a channel layer.
"""

import logging
from unittest import mock

import pytest
from apps.forum_host import live
from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail.actions.unpublish import UnpublishAction
from wagtail.models import Page
from wagtail_forum.admin_views import approve_pending_post
from wagtail_forum.models import ForumBoard, ForumIndex, Post, Report, Topic
from wagtail_forum.signals import _refresh_topic_counters

User = get_user_model()
# The real sender, kept before the autouse fixture swaps in the recorder.
_REAL_SEND = live._send


@pytest.fixture(autouse=True)
def sent():
    calls = []
    with override_settings(FORUM_LIVE_UPDATES_ENABLED=True), mock.patch.object(
        live, "_send", lambda group, event: calls.append((group, event))
    ):
        yield calls


def _thread(slug):
    """A topic and its opening post, both published once (first publish)."""
    author = User.objects.create_user(username=f"author-{slug}")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    topic = Topic.objects.create(
        board=board, title="T", slug=f"t-{slug}", author=author, live=False
    )
    opening = Post.objects.create(
        topic=topic, author=author, is_opening_post=True, live=False
    )
    opening.save_revision().publish()
    topic.refresh_from_db()
    if not topic.live:
        topic.save_revision().publish()
    topic.refresh_from_db()
    # publish() saves a copy built from the revision; reload, as every real
    # edit path does, or a later save_revision() snapshots stale timestamps.
    opening.refresh_from_db()
    return topic, opening, author


def _reply(topic, username):
    replier = User.objects.create_user(username=username)
    reply = Post.objects.create(topic=topic, author=replier, live=False)
    reply.save_revision().publish()
    reply.refresh_from_db()
    return reply


def _event(kind, topic_id, post_id=None):
    return (live.topic_group(topic_id), live.build_event(kind, topic_id, post_id))


def test_build_event_shapes():
    assert live.build_event("post.created", 3, 9) == {
        "v": 1,
        "type": "post.created",
        "topic_id": 3,
        "post_id": 9,
    }
    assert live.build_event("topic.updated", 3) == {
        "v": 1,
        "type": "topic.updated",
        "topic_id": 3,
    }
    assert live.topic_group(3) == "forum.topic.3"
    with pytest.raises(ValueError):
        live.build_event("post.liked", 3, 9)
    with pytest.raises(ValueError):
        live.build_event("topic.updated", 3, 9)
    with pytest.raises(ValueError):
        live.build_event("post.created", 3)


@pytest.mark.django_db
def test_published_reply_sends_post_created_once(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("created")
    with django_capture_on_commit_callbacks(execute=True):
        reply = _reply(topic, "replier-created")
    assert sent == [_event("post.created", topic.pk, reply.pk)]


@pytest.mark.django_db
def test_held_reply_sends_nothing_until_approved(
    sent, django_capture_on_commit_callbacks
):
    """A pending (spam-held) reply is a never-published draft: nothing is sent
    until a moderator approves it, which arrives as a first publish."""
    topic, _opening, _author = _thread("held")
    replier = User.objects.create_user(username="replier-held")
    moderator = User.objects.create_superuser(username="mod-held")
    with django_capture_on_commit_callbacks(execute=True):
        pending = Post.objects.create(topic=topic, author=replier, live=False)
        pending.save_revision()
    assert sent == []
    with django_capture_on_commit_callbacks(execute=True):
        approve_pending_post(pending, moderator)
    assert sent == [_event("post.created", topic.pk, pending.pk)]


@pytest.mark.django_db
def test_trusted_edit_sends_post_updated(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("edit")
    reply = _reply(topic, "replier-edit")
    with django_capture_on_commit_callbacks(execute=True):
        reply.save_revision().publish()
    assert sent == [_event("post.updated", topic.pk, reply.pk)]


@pytest.mark.django_db
def test_opening_post_edit_sends_post_updated(sent, django_capture_on_commit_callbacks):
    topic, opening, _author = _thread("edit-opening")
    with django_capture_on_commit_callbacks(execute=True):
        opening.save_revision().publish()
    assert sent == [_event("post.updated", topic.pk, opening.pk)]


@pytest.mark.django_db
def test_edit_held_for_moderation_sends_nothing(
    sent, django_capture_on_commit_callbacks
):
    """A held edit is a revision nobody published yet: readers keep the last
    approved body, and nothing is sent."""
    topic, _opening, _author = _thread("edit-held")
    reply = _reply(topic, "replier-edit-held")
    with django_capture_on_commit_callbacks(execute=True):
        reply.save_revision()
    assert sent == []


@pytest.mark.django_db
def test_author_delete_sends_post_removed(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("author-delete")
    reply = _reply(topic, "replier-author-delete")
    client = APIClient()
    client.force_authenticate(reply.author)
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.delete(f"/api/v1/forum/posts/{reply.pk}/")
    assert resp.status_code in (200, 204), resp.content
    assert sent == [_event("post.removed", topic.pk, reply.pk)]


@pytest.mark.django_db
def test_report_auto_hide_sends_post_removed(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("auto-hide")
    reply = _reply(topic, "replier-auto-hide")
    reporters = [User.objects.create_user(username=f"rep-{i}") for i in range(3)]
    with django_capture_on_commit_callbacks(execute=True):
        for reporter in reporters:
            Report.file(reply, reporter, Report.SPAM)
    reply.refresh_from_db()
    assert reply.live is False
    assert sent == [_event("post.removed", topic.pk, reply.pk)]


@pytest.mark.django_db
def test_hard_delete_reply_sends_post_removed(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("hard-delete")
    reply = _reply(topic, "replier-hard-delete")
    reply_id = reply.pk
    with django_capture_on_commit_callbacks(execute=True):
        reply.delete()
    assert sent == [_event("post.removed", topic.pk, reply_id)]


@pytest.mark.django_db
def test_hard_delete_of_a_draft_reply_sends_nothing(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, author = _thread("hard-delete-draft")
    draft = Post.objects.create(topic=topic, author=author, live=False)
    with django_capture_on_commit_callbacks(execute=True):
        draft.delete()
    assert sent == []


@pytest.mark.django_db
def test_topic_hard_delete_sends_one_topic_removed(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("topic-delete")
    for i in range(3):
        _reply(topic, f"replier-topic-delete-{i}")
    topic_id = topic.pk
    with django_capture_on_commit_callbacks(execute=True):
        topic.delete()
    assert sent == [_event("topic.removed", topic_id)]


@pytest.mark.django_db
def test_topic_unpublish_sends_topic_removed(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("topic-unpublish")
    with django_capture_on_commit_callbacks(execute=True):
        UnpublishAction(topic, user=None).execute(skip_permission_checks=True)
    assert sent == [_event("topic.removed", topic.pk)]


def _accept(topic, reply):
    client = APIClient()
    client.force_authenticate(topic.author)
    return client, client.post(
        f"/api/v1/forum/topics/{topic.pk}/solution/",
        {"post_id": reply.pk},
        format="json",
    )


@pytest.mark.django_db
def test_mark_and_unmark_solution_send_topic_updated(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("solution")
    reply = _reply(topic, "replier-solution")
    with django_capture_on_commit_callbacks(execute=True):
        client, resp = _accept(topic, reply)
    assert resp.status_code == 200, resp.content
    assert sent == [_event("topic.updated", topic.pk)]
    sent.clear()
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.delete(f"/api/v1/forum/topics/{topic.pk}/solution/")
    assert resp.status_code == 200, resp.content
    assert sent == [_event("topic.updated", topic.pk)]


@pytest.mark.django_db
def test_unpublish_solution_post_sends_post_removed_and_topic_updated(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("solution-unpublish")
    reply = _reply(topic, "replier-solution-unpublish")
    with django_capture_on_commit_callbacks(execute=True):
        _accept(topic, reply)
    sent.clear()
    with django_capture_on_commit_callbacks(execute=True):
        UnpublishAction(reply, user=None).execute(skip_permission_checks=True)
    assert sorted(sent, key=lambda c: c[1]["type"]) == [
        _event("post.removed", topic.pk, reply.pk),
        _event("topic.updated", topic.pk),
    ]


@pytest.mark.django_db
def test_topic_title_edit_publish_sends_topic_updated(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("title")
    topic.title = "A better title"
    with django_capture_on_commit_callbacks(execute=True):
        topic.save_revision().publish()
    assert sent == [_event("topic.updated", topic.pk)]


@pytest.mark.django_db
def test_topic_close_publish_sends_topic_updated(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("close")
    topic.is_closed = True
    with django_capture_on_commit_callbacks(execute=True):
        topic.save_revision().publish()
    assert sent == [_event("topic.updated", topic.pk)]


@pytest.mark.django_db
def test_topic_lock_and_unlock_send_topic_updated(
    sent, django_capture_on_commit_callbacks
):
    """Wagtail's lock/unlock views save exactly these fields and send no
    signal of their own."""
    topic, _opening, author = _thread("lock")
    for locked in (True, False):
        topic.locked = locked
        topic.locked_by = author if locked else None
        with django_capture_on_commit_callbacks(execute=True):
            topic.save(update_fields=["locked", "locked_by", "locked_at"])
    assert sent == [_event("topic.updated", topic.pk)] * 2


@pytest.mark.django_db
def test_counter_and_view_count_saves_send_nothing(
    sent, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("counters")
    with django_capture_on_commit_callbacks(execute=True):
        resp = APIClient().get(f"/api/v1/forum/topics/{topic.pk}/")
        _refresh_topic_counters(topic.pk)
        Topic.objects.get(pk=topic.pk).save()
    assert resp.status_code == 200
    assert sent == []


@pytest.mark.django_db
def test_rollback_sends_nothing(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("rollback")
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(RuntimeError):
            with transaction.atomic():
                _reply(topic, "replier-rollback")
                raise RuntimeError("roll back")
    assert sent == []


@pytest.mark.django_db
def test_flag_off_sends_nothing(sent, django_capture_on_commit_callbacks):
    topic, _opening, _author = _thread("flag-off")
    with override_settings(FORUM_LIVE_UPDATES_ENABLED=False):
        with django_capture_on_commit_callbacks(execute=True):
            _reply(topic, "replier-flag-off")
    assert sent == []


@pytest.mark.django_db
def test_send_failure_does_not_fail_the_write(
    caplog, django_capture_on_commit_callbacks
):
    topic, _opening, _author = _thread("send-fails")

    class BrokenLayer:
        async def group_send(self, group, message):
            raise ConnectionError("redis is down")

    live_logger = logging.getLogger(live.__name__)
    live_logger.addHandler(caplog.handler)
    caplog.set_level(logging.WARNING, logger=live_logger.name)
    try:
        with mock.patch.object(live, "_send", _REAL_SEND):
            with mock.patch.object(live, "get_channel_layer", BrokenLayer):
                with django_capture_on_commit_callbacks(execute=True):
                    reply = _reply(topic, "replier-send-fails")
    finally:
        live_logger.removeHandler(caplog.handler)
    reply.refresh_from_db()
    assert reply.live is True
    assert "[FORUM_LIVE] send failed" in caplog.text
