import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic, TopicSubscription

User = get_user_model()


def _topic(author=None, slug="t"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    return Topic.objects.create(board=board, title="T", slug=slug, author=author)


@pytest.mark.django_db
def test_subscribe_creates_row():
    user = User.objects.create_user(username="ada")
    topic = _topic()

    sub = TopicSubscription.subscribe(user, topic)

    assert sub.pk is not None
    assert TopicSubscription.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_subscribe_is_idempotent():
    user = User.objects.create_user(username="ada2")
    topic = _topic(slug="t2")

    first = TopicSubscription.subscribe(user, topic)
    second = TopicSubscription.subscribe(user, topic)

    assert first.pk == second.pk
    assert TopicSubscription.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_unsubscribe_removes_row():
    user = User.objects.create_user(username="ada3")
    topic = _topic(slug="t3")
    TopicSubscription.subscribe(user, topic)

    TopicSubscription.unsubscribe(user, topic)

    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unsubscribe_when_not_subscribed_is_noop():
    user = User.objects.create_user(username="ada4")
    topic = _topic(slug="t4")

    TopicSubscription.unsubscribe(user, topic)  # must not raise

    assert not TopicSubscription.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_row():
    user = User.objects.create_user(username="ada5")
    topic = _topic(slug="t5")
    TopicSubscription.objects.create(user=user, topic=topic)

    with pytest.raises(IntegrityError):
        TopicSubscription.objects.create(user=user, topic=topic)


@pytest.mark.django_db
def test_backfill_author_subscriptions_subscribes_existing_topic_authors():
    """Migration 0014's data backfill (todo 253 slice 3, decision 2): without
    it, every pre-existing topic would silently stop notifying its author on
    the next reply once fan-out becomes subscription-driven. Author-only —
    NOT past repliers (see the migration's own docstring for why). Calls the
    RunPython function directly against the real app registry rather than a
    historical migration-state one — simplest option available (no
    migration-testing library in this project) and safe here since nothing
    after 0014 changes Topic/TopicSubscription's shape."""
    import importlib

    from django.apps import apps

    # "0014_topicsubscription" is not a valid Python identifier — a normal
    # `from ... import` statement can't reach it; migration modules are
    # loaded this way throughout Django's own migration executor.
    migration = importlib.import_module(
        "wagtail_forum.migrations.0014_topicsubscription"
    )
    backfill_author_subscriptions = migration.backfill_author_subscriptions

    author = User.objects.create_user(username="orig-author")
    replier = User.objects.create_user(username="past-replier")
    authored_topic = _topic(author=author, slug="authored")
    orphan_topic = _topic(author=None, slug="orphan")

    backfill_author_subscriptions(apps, None)

    assert TopicSubscription.objects.filter(user=author, topic=authored_topic).exists()
    assert not TopicSubscription.objects.filter(topic=orphan_topic).exists()
    # Past repliers are deliberately NOT backfilled.
    assert not TopicSubscription.objects.filter(user=replier).exists()
    assert TopicSubscription.objects.count() == 1


@pytest.mark.django_db
def test_backfill_author_subscriptions_is_idempotent():
    import importlib

    from django.apps import apps

    migration = importlib.import_module(
        "wagtail_forum.migrations.0014_topicsubscription"
    )
    backfill_author_subscriptions = migration.backfill_author_subscriptions

    author = User.objects.create_user(username="orig-author2")
    _topic(author=author, slug="authored2")

    backfill_author_subscriptions(apps, None)
    backfill_author_subscriptions(apps, None)

    assert TopicSubscription.objects.count() == 1


@pytest.mark.django_db
def test_subscribe_falls_back_on_integrity_error(monkeypatch):
    """Mirrors ForumProfile.for_user's race test (test_profiles.py): simulate
    a lost create race where get_or_create raises IntegrityError because a
    concurrent request already inserted the row — subscribe() must recover by
    returning the existing row rather than propagating the error (load-bearing
    for callers inside the ambient publish transaction's savepoint)."""
    user = User.objects.create_user(username="ada6")
    topic = _topic(slug="t6")
    existing = TopicSubscription.objects.create(user=user, topic=topic)

    def _raise(**kwargs):
        raise IntegrityError("duplicate key")

    monkeypatch.setattr(TopicSubscription.objects, "get_or_create", _raise)

    recovered = TopicSubscription.subscribe(user, topic)

    assert recovered.pk == existing.pk
