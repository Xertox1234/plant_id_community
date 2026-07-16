import datetime

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic, TopicRead

User = get_user_model()


def _topic(author=None, slug="t"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    return Topic.objects.create(board=board, title="T", slug=slug, author=author)


@pytest.mark.django_db
def test_mark_read_creates_row():
    user = User.objects.create_user(username="ada")
    topic = _topic()

    read = TopicRead.mark_read(user, topic.id)

    assert read.pk is not None
    assert TopicRead.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_mark_read_defaults_to_now_when_omitted():
    user = User.objects.create_user(username="ada2")
    topic = _topic(slug="t2")
    before = timezone.now()

    read = TopicRead.mark_read(user, topic.id)

    after = timezone.now()
    assert before <= read.last_read_at <= after


@pytest.mark.django_db
def test_mark_read_updates_existing_row_not_a_duplicate():
    user = User.objects.create_user(username="ada3")
    topic = _topic(slug="t3")
    first_at = timezone.now() - datetime.timedelta(hours=1)
    second_at = timezone.now()

    first = TopicRead.mark_read(user, topic.id, when=first_at)
    second = TopicRead.mark_read(user, topic.id, when=second_at)

    assert first.pk == second.pk
    assert TopicRead.objects.filter(user=user, topic=topic).count() == 1
    second.refresh_from_db()
    assert second.last_read_at == second_at


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_row():
    user = User.objects.create_user(username="ada4")
    topic = _topic(slug="t4")
    TopicRead.objects.create(user=user, topic=topic, last_read_at=timezone.now())

    with pytest.raises(IntegrityError):
        TopicRead.objects.create(user=user, topic=topic, last_read_at=timezone.now())


@pytest.mark.django_db
def test_mark_read_lets_integrity_error_propagate_uncorrupted(monkeypatch):
    """Django's own get_or_create already retries its internal `.get()` once
    after a failed create() before giving up (empirically confirmed against
    this Django version, docs/LEARNINGS.md 2026-07-16) — a caller only ever
    sees IntegrityError when that retry ALSO failed, i.e. a genuinely
    unrecoverable case (e.g. a stale topic_id whose Topic no longer exists),
    not a lost create race. mark_read must let this surface as-is rather
    than following up with its own `.get()`, which would instead raise a
    confusing masked DoesNotExist (the pre-fix behavior)."""
    user = User.objects.create_user(username="ada5")

    def _raise(**kwargs):
        raise IntegrityError("simulated unrecoverable failure")

    monkeypatch.setattr(TopicRead.objects, "get_or_create", _raise)

    with pytest.raises(IntegrityError):
        TopicRead.mark_read(user, topic_id=999999999)


@pytest.mark.django_db
def test_mark_read_is_monotonic_and_never_moves_last_read_at_backward():
    """A later mark_read call with an EARLIER `when` (e.g. a delayed
    notifications.py signal write landing after a fresher detail-view visit
    already recorded a later read) must not regress last_read_at."""
    user = User.objects.create_user(username="ada7")
    topic = _topic(slug="t7")
    later = timezone.now()
    earlier = later - datetime.timedelta(hours=1)

    first = TopicRead.mark_read(user, topic.id, when=later)
    second = TopicRead.mark_read(user, topic.id, when=earlier)

    assert first.pk == second.pk
    second.refresh_from_db()
    assert second.last_read_at == later  # not regressed to `earlier`
