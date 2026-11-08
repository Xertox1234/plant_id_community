"""The nightly privacy prune (Plan B task 8).

``apps.users.retention``: 90-day retention of email records, blog page views
and audit-log rows; release of forum posts held for a report; re-queueing of
stalled account deletions; and removal of Firebase logins with no account
behind them, which ships log-only behind ``ORPHAN_FIREBASE_PRUNE_ENABLED``.
"""

import io
import logging
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from apps.blog.models import BlogPostView
from apps.core.models import EmailNotification
from apps.core.services.email_service import EmailType
from apps.users import retention
from apps.users.constants import (
    DELETED_ACCOUNT_REASON_SELF,
    DELETED_ACCOUNT_STATUS_DONE,
    ORPHAN_FIREBASE_DELETE_CAP,
)
from apps.users.deletion import email_hash
from apps.users.models import DeletedAccount
from apps.users.tasks import privacy_retention_prune
from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from wagtail_forum.models import Post, Report, Topic
from wagtail_forum.tests.factories import make_forum

User = get_user_model()

pytestmark = pytest.mark.django_db

DAY = timedelta(days=1)


# --- fixtures ---------------------------------------------------------------


@pytest.fixture
def member(db):
    return User.objects.create_user(
        username="keeper", email="Keeper@Example.org", password="x" * 16
    )


@pytest.fixture
def reporter(db):
    return User.objects.create_user(
        username="reporter", email="reporter@example.org", password="x" * 16
    )


@pytest.fixture
def board(db):
    return make_forum(name="General", slug="general")


def _blog_post(author):
    from apps.blog.models import BlogIndexPage, BlogPostPage
    from wagtail.models import Locale, Page, Site

    locale, _ = Locale.objects.get_or_create(language_code="en")
    site = Site.objects.filter(is_default_site=True).first()
    if site is not None:
        root = site.root_page
    else:
        root = Page.objects.filter(depth=1).first() or Page.add_root(
            title="Root", locale=locale
        )
        Site.objects.create(hostname="localhost", root_page=root, is_default_site=True)
    index = BlogIndexPage(title="Blog", slug="retention-blog")
    root.add_child(instance=index)
    page = BlogPostPage(
        title="Repotting",
        slug="repotting",
        author=author,
        publish_date=timezone.now().date(),
        introduction="intro",
    )
    index.add_child(instance=page)
    return page


def _notification(age):
    row = EmailNotification.objects.create(
        email_type=EmailType.FORUM_REPLY,
        recipient_email="reader@example.com",
        subject="s",
        template_name="forum_reply",
    )
    # created_at is auto_now_add: backdate it after the insert.
    EmailNotification.objects.filter(pk=row.pk).update(created_at=timezone.now() - age)
    return row


def _view(post, age):
    row = BlogPostView.objects.create(post=post, ip_address="198.51.100.7")
    BlogPostView.objects.filter(pk=row.pk).update(viewed_at=timezone.now() - age)
    return row


def _log_entry(user, age):
    return LogEntry.objects.create(
        content_type=ContentType.objects.get_for_model(User),
        object_pk=str(user.pk),
        object_id=user.pk,
        object_repr="someone",
        action=LogEntry.Action.UPDATE,
        changes={"bio": ["", "edited"]},
        timestamp=timezone.now() - age,
    )


def _deleted_account(age, status="pending", **extra):
    record = DeletedAccount.objects.create(
        email_hash=email_hash("gone@example.org"),
        reason=DELETED_ACCOUNT_REASON_SELF,
        status=status,
        **extra,
    )
    DeletedAccount.objects.filter(pk=record.pk).update(
        requested_at=timezone.now() - age
    )
    return record


def _held_post(board, reporter, *, erase_in, report_status):
    topic = Topic.objects.create(
        board=board, title="Fern", slug=f"fern-{Topic.objects.count()}", author=None
    )
    post = Post.objects.create(
        topic=topic,
        author=None,
        live=True,
        body=[("quote", "held words")],
        erase_after=timezone.now() + erase_in,
    )
    Report.objects.create(
        post=post, reporter=reporter, reason=Report.ABUSE, status=report_status
    )
    return post


# --- retention --------------------------------------------------------------


def test_retention_deletes_rows_older_than_90_days(member, reporter):
    page = _blog_post(member)
    old = (_notification(91 * DAY), _view(page, 91 * DAY), _log_entry(member, 91 * DAY))
    young = (
        _notification(89 * DAY),
        _view(page, 89 * DAY),
        _log_entry(member, 89 * DAY),
    )

    counts = retention.prune_retention()

    for row in old:
        assert not type(row).objects.filter(pk=row.pk).exists()
    for row in young:
        assert type(row).objects.filter(pk=row.pk).exists()
    assert counts["email_notifications"] == 1
    assert counts["blog_post_views"] == 1
    assert counts["audit_log_entries"] >= 1


def test_retention_leaves_deletion_records_and_reports(member, reporter, board):
    record = _deleted_account(200 * DAY, status=DELETED_ACCOUNT_STATUS_DONE)
    post = _held_post(board, reporter, erase_in=DAY, report_status=Report.DISMISSED)
    report = Report.objects.get(post=post)
    Report.objects.filter(pk=report.pk).update(created_at=timezone.now() - 200 * DAY)

    retention.prune_retention()

    assert DeletedAccount.objects.filter(pk=record.pk).exists()
    assert Report.objects.filter(pk=report.pk).exists()


def test_retention_dry_run_deletes_nothing(member):
    row = _notification(91 * DAY)

    counts = retention.prune_retention(dry_run=True)

    assert counts["email_notifications"] == 1
    assert EmailNotification.objects.filter(pk=row.pk).exists()


# --- held posts -------------------------------------------------------------


def test_held_post_with_closed_report_is_erased(board, reporter):
    post = _held_post(board, reporter, erase_in=10 * DAY, report_status=Report.ACTIONED)

    assert retention.release_held_posts() == 1

    post.refresh_from_db()
    assert len(post.body) == 0
    assert post.erase_after is None


def test_held_post_with_open_report_before_its_date_is_kept(board, reporter):
    post = _held_post(board, reporter, erase_in=10 * DAY, report_status=Report.OPEN)

    assert retention.release_held_posts() == 0

    post.refresh_from_db()
    assert len(post.body) == 1
    assert post.erase_after is not None


def test_held_post_with_auto_hidden_report_is_kept(board, reporter):
    post = _held_post(
        board, reporter, erase_in=10 * DAY, report_status=Report.AUTO_HIDDEN
    )

    assert retention.release_held_posts() == 0

    post.refresh_from_db()
    assert len(post.body) == 1


def test_held_post_past_its_date_is_erased_despite_open_report(board, reporter):
    post = _held_post(board, reporter, erase_in=-DAY, report_status=Report.OPEN)

    assert retention.release_held_posts() == 1

    post.refresh_from_db()
    assert len(post.body) == 0


def test_release_dry_run_erases_nothing(board, reporter):
    post = _held_post(board, reporter, erase_in=-DAY, report_status=Report.OPEN)

    assert retention.release_held_posts(dry_run=True) == 1

    post.refresh_from_db()
    assert len(post.body) == 1


# --- stalled deletions (ruling R12) -----------------------------------------


def test_stale_pending_deletion_is_queued_once():
    stale = _deleted_account(2 * timedelta(hours=1))
    _deleted_account(timedelta(minutes=10))  # fresh
    _deleted_account(5 * DAY, status=DELETED_ACCOUNT_STATUS_DONE)

    with patch("apps.users.tasks.delete_account_task.delay") as delay:
        assert retention.requeue_stale_deletions() == 1

    delay.assert_called_once_with(stale.pk)


def test_stale_requeue_dry_run_queues_nothing():
    _deleted_account(2 * timedelta(hours=1))

    with patch("apps.users.tasks.delete_account_task.delay") as delay:
        assert retention.requeue_stale_deletions(dry_run=True) == 1

    delay.assert_not_called()


# --- orphaned Firebase logins -----------------------------------------------


def _fb_user(uid, *, age, email=None):
    created_ms = int((timezone.now() - age).timestamp() * 1000)
    return SimpleNamespace(
        uid=uid,
        email=email,
        user_metadata=SimpleNamespace(creation_timestamp=created_ms),
    )


def _firebase(users):
    """Patch a configured Firebase whose list_users() pages over ``users``."""
    page = SimpleNamespace(iterate_all=lambda: iter(users))
    return (
        patch("apps.users.retention.initialize_firebase", return_value=True),
        patch("firebase_admin.auth.list_users", return_value=page),
        patch("firebase_admin.auth.delete_user"),
    )


def _run_orphans(users, **kwargs):
    init, listing, delete = _firebase(users)
    with init, listing, delete as delete_user:
        result = retention.prune_orphan_firebase_users(**kwargs)
    return result, delete_user


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_an_8_day_old_orphan_is_deleted():
    result, delete_user = _run_orphans(
        [_fb_user("orphan-uid", age=8 * DAY, email="nobody@example.org")]
    )

    assert result == 1
    delete_user.assert_called_once_with("orphan-uid")


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_an_8_day_old_uid_with_a_user_is_kept(member):
    member.firebase_uid = "linked-uid"
    member.save(update_fields=["firebase_uid"])

    result, delete_user = _run_orphans(
        [_fb_user("linked-uid", age=8 * DAY, email="different@example.org")]
    )

    assert result == 0
    delete_user.assert_not_called()


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_a_uid_pending_deletion_is_kept():
    _deleted_account(timedelta(minutes=5), firebase_uid="leaving-uid")

    result, delete_user = _run_orphans(
        [_fb_user("leaving-uid", age=8 * DAY, email="leaving@example.org")]
    )

    assert result == 0
    delete_user.assert_not_called()


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_a_6_day_old_orphan_is_kept():
    result, delete_user = _run_orphans(
        [_fb_user("young-uid", age=6 * DAY, email="nobody@example.org")]
    )

    assert result == 0
    delete_user.assert_not_called()


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_an_unmatched_uid_whose_email_has_a_user_is_kept(member):
    # The account's uid was never stored, but the address is the member's
    # (case differs): its login must survive.
    result, delete_user = _run_orphans(
        [_fb_user("unstored-uid", age=8 * DAY, email="keeper@example.ORG")]
    )

    assert result == 0
    delete_user.assert_not_called()


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_orphan_prune_aborts_over_cap():
    users = [
        _fb_user(f"orphan-{n}", age=8 * DAY, email=f"n{n}@example.org")
        for n in range(ORPHAN_FIREBASE_DELETE_CAP + 1)
    ]

    with patch("apps.users.retention.sentry_sdk.capture_message") as capture:
        result, delete_user = _run_orphans(users)

    assert result == 0
    delete_user.assert_not_called()
    capture.assert_called_once()


def test_orphan_prune_is_log_only_by_default(caplog):
    assert settings.ORPHAN_FIREBASE_PRUNE_ENABLED is False

    # apps.* loggers do not propagate, so caplog only sees them attached.
    logger = logging.getLogger("apps.users.retention")
    logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger="apps.users.retention"):
            result, delete_user = _run_orphans(
                [_fb_user("orphan-uid", age=8 * DAY, email="nobody@example.org")]
            )
    finally:
        logger.removeHandler(caplog.handler)

    delete_user.assert_not_called()
    assert result == 1
    assert "orphan-uid" in caplog.text
    assert "nobody@example.org" not in caplog.text


@override_settings(ORPHAN_FIREBASE_PRUNE_ENABLED=True)
def test_orphan_dry_run_deletes_nothing():
    result, delete_user = _run_orphans(
        [_fb_user("orphan-uid", age=8 * DAY, email="nobody@example.org")],
        dry_run=True,
    )

    assert result == 1
    delete_user.assert_not_called()


def test_orphan_prune_returns_0_when_firebase_is_unconfigured():
    with (
        patch("apps.users.retention.initialize_firebase", return_value=False),
        patch("firebase_admin.auth.list_users") as list_users,
    ):
        assert retention.prune_orphan_firebase_users() == 0

    list_users.assert_not_called()


# --- the task, the beat entry and the command -------------------------------


def test_beat_entry_names_the_registered_task():
    entry = settings.CELERY_BEAT_SCHEDULE["privacy-retention-prune"]

    assert entry["task"] == privacy_retention_prune.name
    assert entry["schedule"].hour == {3}
    assert entry["schedule"].minute == {50}


def test_task_runs_every_part(board, reporter):
    old = _notification(91 * DAY)
    post = _held_post(board, reporter, erase_in=-DAY, report_status=Report.OPEN)
    stale = _deleted_account(2 * timedelta(hours=1))

    with (
        patch("apps.users.retention.initialize_firebase", return_value=False),
        patch("apps.users.tasks.delete_account_task.delay") as delay,
    ):
        privacy_retention_prune.apply()

    assert not EmailNotification.objects.filter(pk=old.pk).exists()
    post.refresh_from_db()
    assert len(post.body) == 0
    delay.assert_called_once_with(stale.pk)


def test_command_dry_run_changes_nothing_and_prints_counts(board, reporter):
    old = _notification(91 * DAY)
    post = _held_post(board, reporter, erase_in=-DAY, report_status=Report.OPEN)
    _deleted_account(2 * timedelta(hours=1))
    out = io.StringIO()

    with (
        patch("apps.users.retention.initialize_firebase", return_value=False),
        patch("apps.users.tasks.delete_account_task.delay") as delay,
    ):
        call_command("privacy_prune", "--dry-run", stdout=out)

    assert EmailNotification.objects.filter(pk=old.pk).exists()
    post.refresh_from_db()
    assert len(post.body) == 1
    delay.assert_not_called()
    text = out.getvalue()
    assert "email_notifications=1" in text
    assert "held posts (would erase): 1" in text
    assert "stale deletions (would re-queue): 1" in text
    assert "orphaned Firebase logins (would delete): 0" in text
