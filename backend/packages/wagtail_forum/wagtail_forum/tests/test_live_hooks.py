"""Package hooks a host uses for live updates (forum live replies, slice 2).

Plain Django signals and helpers only: the package stays Channels-free. The
host turns these into socket events; these tests pin what the package sends.
"""

import pytest
from django.db.models.signals import post_delete
from rest_framework.test import APIClient
from wagtail_forum.api.views import visible_topics
from wagtail_forum.models import ForumBoard, Post, Topic
from wagtail_forum.signals import (
    _is_first_publish,
    is_first_publish,
    is_topic_deleting,
    solution_unmarked,
)

from .api.test_solutions import _board, _mark, _thread

pytestmark = pytest.mark.urls("wagtail_forum.tests.api.urls")


@pytest.fixture
def unmarked():
    calls = []

    def receiver(sender, **kwargs):
        calls.append(kwargs)

    solution_unmarked.connect(receiver, dispatch_uid="test_live_hooks")
    yield calls
    solution_unmarked.disconnect(dispatch_uid="test_live_hooks")


def _solved(slug):
    topic, reply, asker, _ = _thread(slug)
    client = APIClient()
    client.force_authenticate(asker)
    assert _mark(client, topic, reply).status_code == 200
    return topic, reply, client


@pytest.mark.django_db
def test_unmark_via_api_sends_solution_unmarked_once(
    unmarked, django_capture_on_commit_callbacks
):
    topic, _reply, client = _solved("unmark")
    with django_capture_on_commit_callbacks(execute=True):
        resp = client.delete(f"/forum/topics/{topic.id}/solution/")
    assert resp.status_code == 200
    assert [c["topic_id"] for c in unmarked] == [topic.id]


@pytest.mark.django_db
def test_unmark_via_api_sends_nothing_on_rollback(unmarked):
    """The API send waits for commit: no captured callback ran, nothing sent."""
    topic, _reply, client = _solved("unmark-nocommit")
    client.delete(f"/forum/topics/{topic.id}/solution/")
    assert unmarked == []


@pytest.mark.django_db
def test_unmark_when_not_solved_sends_nothing(
    unmarked, django_capture_on_commit_callbacks
):
    topic, _reply, asker, _ = _thread("unmark-none")
    client = APIClient()
    client.force_authenticate(asker)
    with django_capture_on_commit_callbacks(execute=True):
        client.delete(f"/forum/topics/{topic.id}/solution/")
    assert unmarked == []


@pytest.mark.django_db
def test_unpublishing_solution_post_sends_solution_unmarked(unmarked):
    topic, reply, _client = _solved("unpub-solution")
    reply.unpublish()
    assert [c["topic_id"] for c in unmarked] == [topic.id]


@pytest.mark.django_db
def test_deleting_solution_post_sends_solution_unmarked(unmarked):
    topic, reply, _client = _solved("del-solution")
    reply.delete()
    assert [c["topic_id"] for c in unmarked] == [topic.id]


@pytest.mark.django_db
def test_unpublishing_other_post_sends_nothing(unmarked):
    topic, _reply, _client = _solved("unpub-other")
    other = Post.objects.create(topic=topic, author=topic.author, live=True)
    other.unpublish()
    assert unmarked == []


@pytest.mark.django_db
def test_is_topic_deleting_true_only_during_cascade():
    topic, _reply, _asker, _ = _thread("deleting")
    seen = []

    def receiver(sender, instance, **kwargs):
        seen.append(is_topic_deleting(instance.topic_id))

    post_delete.connect(receiver, sender=Post, dispatch_uid="test_deleting")
    try:
        topic_id = topic.pk
        topic.delete()
    finally:
        post_delete.disconnect(sender=Post, dispatch_uid="test_deleting")
    assert seen and all(seen)
    assert is_topic_deleting(topic_id) is False


@pytest.mark.django_db
def test_visible_topics_excludes_hidden_board_and_unpublished_topic():
    live_topic, _r, asker, _ = _thread("visible")
    draft = Topic.objects.create(
        board=live_topic.board, title="D", slug="d-visible", author=asker, live=False
    )
    hidden_board = _board("hidden-visible")
    ForumBoard.objects.filter(pk=hidden_board.pk).update(live=False)
    on_hidden = Topic.objects.create(
        board=hidden_board, title="H", slug="h-visible", author=asker, live=True
    )
    ids = set(visible_topics().values_list("pk", flat=True))
    assert live_topic.pk in ids
    assert draft.pk not in ids
    assert on_hidden.pk not in ids


def test_is_first_publish_keeps_its_private_alias():
    assert _is_first_publish is is_first_publish
