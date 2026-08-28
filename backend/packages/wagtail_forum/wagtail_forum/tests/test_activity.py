"""Day-streak activity tracking (todo 300) — record() idempotency and
streak_for_user()'s date math.
"""

from datetime import date

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time
from wagtail.models import Page
from wagtail_forum.models import ForumActivityDate, ForumBoard, ForumIndex, Post, Topic

User = get_user_model()


def _topic(author, slug="t"):
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="Forum", slug=f"forum-{slug}"))
    board = index.add_child(instance=ForumBoard(title="General", slug=slug))
    return Topic.objects.create(board=board, title="T", slug=slug, author=author)


@pytest.mark.django_db
def test_record_creates_a_row():
    user = User.objects.create_user(username="ada")

    with freeze_time("2026-08-20 10:00:00"):
        ForumActivityDate.record(user.id)

    assert ForumActivityDate.objects.filter(user=user, date=date(2026, 8, 20)).exists()


@pytest.mark.django_db
def test_record_same_day_is_idempotent():
    """Two publishes on the same day must not create two rows (unique_together)."""
    user = User.objects.create_user(username="ada2")

    with freeze_time("2026-08-20 09:00:00"):
        ForumActivityDate.record(user.id)
    with freeze_time("2026-08-20 21:00:00"):
        ForumActivityDate.record(user.id)

    assert ForumActivityDate.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_streak_zero_for_no_activity():
    user = User.objects.create_user(username="ada3")
    assert ForumActivityDate.streak_for_user(user.id) == 0


@pytest.mark.django_db
def test_streak_counts_consecutive_days_ending_today():
    user = User.objects.create_user(username="ada4")
    for day in ("2026-08-18", "2026-08-19", "2026-08-20"):
        with freeze_time(f"{day} 12:00:00"):
            ForumActivityDate.record(user.id)

    with freeze_time("2026-08-20 23:00:00"):
        assert ForumActivityDate.streak_for_user(user.id) == 3


@pytest.mark.django_db
def test_streak_stays_alive_through_today_before_todays_post():
    """A streak through yesterday, with nothing posted yet today, is still live."""
    user = User.objects.create_user(username="ada5")
    for day in ("2026-08-18", "2026-08-19"):
        with freeze_time(f"{day} 12:00:00"):
            ForumActivityDate.record(user.id)

    # "Today" is the 20th; nothing recorded yet today.
    with freeze_time("2026-08-20 08:00:00"):
        assert ForumActivityDate.streak_for_user(user.id) == 2


@pytest.mark.django_db
def test_streak_resets_after_a_gap():
    """A day with no activity in between breaks the streak — only the
    trailing run counts, not the total distinct days."""
    user = User.objects.create_user(username="ada6")
    for day in ("2026-08-10", "2026-08-11", "2026-08-15", "2026-08-16"):
        with freeze_time(f"{day} 12:00:00"):
            ForumActivityDate.record(user.id)

    with freeze_time("2026-08-16 23:00:00"):
        assert ForumActivityDate.streak_for_user(user.id) == 2  # 15th + 16th only


@pytest.mark.django_db
def test_streak_zero_when_gap_is_more_than_a_day_old():
    """Two full days with no activity — even a streak "through yesterday" is
    gone, not just frozen."""
    user = User.objects.create_user(username="ada7")
    with freeze_time("2026-08-18 12:00:00"):
        ForumActivityDate.record(user.id)

    with freeze_time("2026-08-20 12:00:00"):  # 2 days later, nothing since
        assert ForumActivityDate.streak_for_user(user.id) == 0


@pytest.mark.django_db
def test_unpublishing_a_post_does_not_record_activity():
    """A takedown must never fabricate a streak entry (spec §9 honesty).

    Regression test for a real bug caught by test_post_edit_delete.py's
    pinned query-count tests during development: activity-recording was
    first added inside `_refresh_for_post`, a helper `unpublish`/`delete`
    ALSO call — which would have recorded a "day of activity" for content
    being removed, not contributed. Moved to the `published` signal's Post
    branch only; this test pins that placement directly, not just via the
    incidental query-count delta.
    """
    author = User.objects.create_user(username="unpublisher")
    topic = _topic(author, slug="unpub")

    with freeze_time("2026-08-20 10:00:00"):
        post = Post.objects.create(
            topic=topic, author=author, is_opening_post=True, live=False
        )
        post.save_revision().publish()

    assert (
        ForumActivityDate.objects.filter(user=author, date=date(2026, 8, 20)).count()
        == 1
    )

    with freeze_time("2026-08-21 10:00:00"):
        post.unpublish()

    # Still exactly one row — unpublishing on a LATER day added nothing.
    assert ForumActivityDate.objects.filter(user=author).count() == 1
    assert not ForumActivityDate.objects.filter(
        user=author, date=date(2026, 8, 21)
    ).exists()


@pytest.mark.django_db
def test_editing_an_already_live_post_does_not_record_a_new_activity_day():
    """A later-day edit-republish of already-live content must not fabricate
    a streak day (code review MEDIUM finding) — only the FIRST publish ever
    should record activity. Gated on `_is_first_publish` in signals.py.
    """
    author = User.objects.create_user(username="editor")
    topic = _topic(author, slug="editreactivity")

    with freeze_time("2026-08-20 10:00:00"):
        post = Post.objects.create(
            topic=topic, author=author, is_opening_post=True, live=False
        )
        post.save_revision().publish()  # first publish

    # Refresh: save_revision() serializes the CURRENT in-memory object, and a
    # stale `post` (still carrying first_published_at=None from before the
    # publish above) would make the second publish below look like a first
    # publish too, defeating the very thing this test is pinning.
    post.refresh_from_db()
    assert (
        ForumActivityDate.objects.filter(user=author, date=date(2026, 8, 20)).count()
        == 1
    )

    with freeze_time("2026-08-25 10:00:00"):
        from wagtail_forum.blocks import ForumBodyBlock

        post.body = ForumBodyBlock().to_python(
            [{"type": "paragraph", "value": "<p>edited</p>"}]
        )
        post.save_revision().publish()  # edit-republish, days later

    # Still exactly one row — the 25th never got one.
    assert ForumActivityDate.objects.filter(user=author).count() == 1
    assert not ForumActivityDate.objects.filter(
        user=author, date=date(2026, 8, 25)
    ).exists()
