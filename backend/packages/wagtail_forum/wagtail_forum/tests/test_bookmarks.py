import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from wagtail.models import Page
from wagtail_forum.models import ForumBoard, ForumIndex, Topic, TopicBookmark

User = get_user_model()


def _topic(author=None, slug="t"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    return Topic.objects.create(board=board, title="T", slug=slug, author=author)


@pytest.mark.django_db
def test_bookmark_creates_row():
    user = User.objects.create_user(username="ada")
    topic = _topic()

    bookmark = TopicBookmark.bookmark(user, topic)

    assert bookmark.pk is not None
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_bookmark_is_idempotent():
    user = User.objects.create_user(username="ada2")
    topic = _topic(slug="t2")

    first = TopicBookmark.bookmark(user, topic)
    second = TopicBookmark.bookmark(user, topic)

    assert first.pk == second.pk
    assert TopicBookmark.objects.filter(user=user, topic=topic).count() == 1


@pytest.mark.django_db
def test_unbookmark_removes_row():
    # Gives TopicBookmark.unbookmark() a real caller — the view itself does a
    # direct .filter().delete() (matching TopicSubscriptionView.delete's own
    # precedent), so this classmethod's only exerciser is this test, same as
    # TopicSubscription.unsubscribe's (code review, todo 283).
    user = User.objects.create_user(username="ada3")
    topic = _topic(slug="t3")
    TopicBookmark.bookmark(user, topic)

    TopicBookmark.unbookmark(user, topic)

    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unbookmark_when_not_bookmarked_is_noop():
    user = User.objects.create_user(username="ada4")
    topic = _topic(slug="t4")

    TopicBookmark.unbookmark(user, topic)  # must not raise

    assert not TopicBookmark.objects.filter(user=user, topic=topic).exists()


@pytest.mark.django_db
def test_unique_constraint_prevents_duplicate_row():
    user = User.objects.create_user(username="ada5")
    topic = _topic(slug="t5")
    TopicBookmark.objects.create(user=user, topic=topic)

    with pytest.raises(IntegrityError):
        TopicBookmark.objects.create(user=user, topic=topic)
