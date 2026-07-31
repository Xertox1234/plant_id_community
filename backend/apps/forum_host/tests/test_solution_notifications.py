"""Accepted-answer notification wiring (audit H6, roadmap Wave 2 slice 2).

The package owns the state change; the host owns telling the answer's author.
What is pinned here is the seam: the `solution_marked` signal reaches
`dispatch("answer_accepted", …)`, that branch persists exactly one Notification
for the ANSWER's author, and it stays silent in the two cases where a push
would be wrong (self-accept, re-accept).

**Context-manager order matters in every test here.** The whole chain
(`on_commit` → `notify` → `dispatch` → the push enqueue) only runs when
`django_capture_on_commit_callbacks` executes its collected callbacks, which
happens in its own `__exit__`. Two consequences: `patch` must be the OUTER
context or it is already undone by then and the real `.delay()` fires past the
mock; and nothing that reads or clears notification rows may sit INSIDE the
capture block, because at that point the callbacks have not run yet.
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Notification,
    NotificationVerb,
    Post,
    Topic,
)

User = get_user_model()


def _thread(slug):
    """A live topic (asker) with an opening post and one live reply (answerer)."""
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    asker = User.objects.create_user(username=f"asker-{slug}")
    answerer = User.objects.create_user(username=f"answerer-{slug}")
    topic = Topic.objects.create(
        board=board, title="How do I repot?", slug=f"t-{slug}", author=asker, live=True
    )
    Post.objects.create(topic=topic, author=asker, is_opening_post=True, live=True)
    reply = Post.objects.create(topic=topic, author=answerer, live=True)
    return topic, reply, asker, answerer


def _accept(user, topic, post):
    client = APIClient()
    client.force_authenticate(user)
    return client.post(
        f"/api/v1/forum/topics/{topic.id}/solution/",
        {"post_id": post.id},
        format="json",
    )


@pytest.mark.django_db
def test_accepting_an_answer_notifies_its_author(django_capture_on_commit_callbacks):
    topic, reply, asker, answerer = _thread("notify")

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push,
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert _accept(asker, topic, reply).status_code == 200

    notification = Notification.objects.get(recipient=answerer)
    assert notification.verb == NotificationVerb.SOLUTION
    assert notification.actor_id == asker.pk
    assert notification.post_id == reply.pk
    assert notification.topic_id == topic.pk

    mock_push.assert_called_once()
    event, recipient_pk, payload = mock_push.call_args[0]
    assert event == "answer_accepted"
    assert recipient_pk == answerer.pk
    # The actor is whoever ACCEPTED, not the post's author — otherwise the tray
    # line reads "You accepted your answer".
    assert payload["actor_name"] == asker.display_name
    # Deep-link target: the accepted post, inside its topic.
    assert payload["post_id"] == str(reply.pk)
    assert payload["topic_id"] == str(topic.pk)
    assert payload["topic_title"] == "How do I repot?"


@pytest.mark.django_db
def test_accepting_your_own_reply_notifies_nobody(django_capture_on_commit_callbacks):
    # The self-answer case is common (someone solves their own problem and
    # posts the fix) — it must not push a "your answer was accepted" at them.
    topic, _, asker, _ = _thread("self")
    own_reply = Post.objects.create(topic=topic, author=asker, live=True)

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push,
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert _accept(asker, topic, own_reply).status_code == 200

    assert Notification.objects.filter(verb=NotificationVerb.SOLUTION).count() == 0
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_reaccepting_the_same_answer_does_not_push_again(
    django_capture_on_commit_callbacks,
):
    # `create_notifications` dedupes the bell entry on (recipient, verb, post),
    # but FCM has no such backstop — a double-tap would tray-popup twice unless
    # the view short-circuits.
    topic, reply, asker, answerer = _thread("double")

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push,
        django_capture_on_commit_callbacks(execute=True),
    ):
        _accept(asker, topic, reply)
        _accept(asker, topic, reply)

    assert mock_push.call_count == 1
    assert Notification.objects.filter(recipient=answerer).count() == 1


@pytest.mark.django_db
def test_clearing_an_answer_notifies_nobody(django_capture_on_commit_callbacks):
    # There is no "your answer was un-accepted" product decision — unmarking is
    # silent by design.
    topic, reply, asker, _ = _thread("clear")
    client = APIClient()
    client.force_authenticate(asker)

    # Separate capture block for the accept, so its notification + push have
    # actually fired before the clear is measured (see the module docstring).
    with (
        patch("apps.forum_host.tasks.send_forum_push.delay"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        _accept(asker, topic, reply)
    Notification.objects.all().delete()

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push,
        django_capture_on_commit_callbacks(execute=True),
    ):
        resp = client.delete(f"/api/v1/forum/topics/{topic.id}/solution/")

    assert resp.status_code == 200
    assert Notification.objects.count() == 0
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_the_answer_authors_deleted_account_is_not_a_500(
    django_capture_on_commit_callbacks,
):
    # Post.author is SET_NULL, so an account deletion leaves an authorless
    # answer. Accepting it must still work — there is simply nobody to tell.
    topic, reply, asker, answerer = _thread("ghost")
    answerer.delete()
    reply.refresh_from_db()
    assert reply.author_id is None

    with (
        patch("apps.forum_host.tasks.send_forum_push.delay") as mock_push,
        django_capture_on_commit_callbacks(execute=True),
    ):
        assert _accept(asker, topic, reply).status_code == 200

    topic.refresh_from_db()
    assert topic.solved_post_id == reply.pk
    assert Notification.objects.count() == 0
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_the_endpoint_is_reachable_through_the_host_mount():
    # Package tests exercise the unwrapped class; only a request against the
    # real /api/v1/forum/ path proves the throttled wrapper ships (docs/rules
    # /forum.md — route parity alone does not prove the view answers).
    topic, reply, asker, _ = _thread("mounted")

    resp = _accept(asker, topic, reply)

    assert resp.status_code == 200
    assert resp.data["is_solved"] is True
