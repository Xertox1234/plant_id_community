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
def test_mark_read_falls_back_on_integrity_error(monkeypatch):
    """Mirrors TopicSubscription's identical race test: simulate a lost
    create race where update_or_create raises IntegrityError because a
    concurrent request already inserted the row — mark_read must recover by
    updating the existing row rather than propagating the error (load-bearing
    for callers inside an ambient transaction, though this one only ever runs
    from transaction.on_commit today)."""
    user = User.objects.create_user(username="ada5")
    topic = _topic(slug="t5")
    existing = TopicRead.objects.create(
        user=user, topic=topic, last_read_at=timezone.now() - datetime.timedelta(days=1)
    )

    def _raise(**kwargs):
        raise IntegrityError("duplicate key")

    monkeypatch.setattr(TopicRead.objects, "update_or_create", _raise)
    when = timezone.now()

    recovered = TopicRead.mark_read(user, topic.id, when=when)

    assert recovered.pk == existing.pk
    assert recovered.last_read_at == when
