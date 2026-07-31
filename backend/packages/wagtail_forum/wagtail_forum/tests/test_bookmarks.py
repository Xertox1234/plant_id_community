"""TopicBookmark model behaviour (todo 283 / audit M2)."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail.models import Page
from wagtail_forum.models import (
    ForumBoard,
    ForumIndex,
    Topic,
    TopicBookmark,
    TopicSubscription,
)

User = get_user_model()


def _topic(slug="t"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    return Topic.objects.create(board=board, title="T", slug=slug)


@pytest.mark.django_db
def test_add_creates_row():
    user = User.objects.create_user(username="bmm1")
    topic = _topic("bmm-t1")

    bookmark = TopicBookmark.add(user, topic)

    assert bookmark.pk is not None
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_add_is_idempotent():
    user = User.objects.create_user(username="bmm2")
    topic = _topic("bmm-t2")

    first = TopicBookmark.add(user, topic)
    second = TopicBookmark.add(user, topic)

    assert first.pk == second.pk
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_remove_deletes_row_and_tolerates_absence():
    user = User.objects.create_user(username="bmm3")
    topic = _topic("bmm-t3")
    TopicBookmark.add(user, topic)

    TopicBookmark.remove(user, topic)
    TopicBookmark.remove(user, topic)  # must not raise

    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_row():
    user = User.objects.create_user(username="bmm4")
    topic = _topic("bmm-t4")
    TopicBookmark.objects.create(user=user, topic=topic)

    with pytest.raises(IntegrityError):
        TopicBookmark.objects.create(user=user, topic=topic)


@pytest.mark.django_db
def test_add_recovers_from_a_lost_create_race():
    """Two concurrent first-touch requests can both miss the SELECT and race to
    INSERT. `add` carries no explicit try/except because Django's own
    `get_or_create` already wraps the INSERT in a savepoint and re-runs the
    get when the unique constraint fires. This drives that path for real —
    simulating the race by pre-inserting the row the way the winning request
    would have, between the SELECT and the INSERT.
    """
    user = User.objects.create_user(username="bmm5")
    topic = _topic("bmm-t5")
    original_get = TopicBookmark.objects.get_queryset().__class__.get
    state = {"raced": False}

    def racing_get(self, *args, **kwargs):
        # First call is get_or_create's initial lookup: report "missing" AND
        # concurrently insert the row, so the follow-up INSERT hits the
        # constraint exactly as a lost race would.
        if not state["raced"] and self.model is TopicBookmark:
            state["raced"] = True
            TopicBookmark.objects.create(user=user, topic=topic)
            raise TopicBookmark.DoesNotExist()
        return original_get(self, *args, **kwargs)

    TopicBookmark.objects.get_queryset().__class__.get = racing_get
    try:
        recovered = TopicBookmark.add(user, topic)
    finally:
        TopicBookmark.objects.get_queryset().__class__.get = original_get

    assert state["raced"], "the race path was never driven"
    assert recovered.pk is not None
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_bookmark_and_subscription_are_independent():
    """The two models look identical but carry different intent: saving a
    thread must not sign you up for its replies, and muting a thread must not
    silently drop it out of your saved list.
    """
    user = User.objects.create_user(username="bmm6")
    topic = _topic("bmm-t6")

    TopicBookmark.add(user, topic)

    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()

    TopicSubscription.subscribe(user, topic)
    TopicSubscription.unsubscribe(user, topic)

    assert TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_deleting_a_topic_removes_its_bookmarks():
    user = User.objects.create_user(username="bmm7")
    topic = _topic("bmm-t7")
    TopicBookmark.add(user, topic)

    topic.delete()

    assert not TopicBookmark.objects.filter(user=user).exists()
