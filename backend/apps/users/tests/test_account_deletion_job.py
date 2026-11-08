"""Requesting an account deletion and the resumable erase job (Plan B, task 5).

``request_account_deletion`` deactivates the account, revokes its sessions,
records a pending ``DeletedAccount`` and queues ``delete_account_task`` once,
on commit. The task runs every erase step, emails the saved address once,
then marks the record done and clears the address and Firebase uid.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from apps.users import tasks
from apps.users.constants import (
    ACCOUNT_DELETED_EMAIL_SUBJECT,
    DELETED_ACCOUNT_REASON_SELF,
    DELETED_ACCOUNT_STATUS_DONE,
    DELETED_ACCOUNT_STATUS_PENDING,
    ERASE_STEP_NOTIFIED,
)
from apps.users.deletion import DeletionRefused, email_hash, request_account_deletion
from apps.users.models import DeletedAccount
from django.contrib.auth import get_user_model
from django.core import mail
from firebase_admin import auth
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

pytestmark = pytest.mark.django_db

EMAIL = "leaving.k4@example.test"
UID = "firebase-uid-delete-5"


@pytest.fixture
def user():
    return User.objects.create_user(
        username="leaving5",
        email=EMAIL,
        password="pw-not-used-1234",  # pragma: allowlist secret
        firebase_uid=UID,
        policy_version_accepted="2026-11-06",
    )


@pytest.fixture
def queued():
    """``delete_account_task.delay`` replaced, so nothing reaches a broker."""
    with patch.object(tasks.delete_account_task, "delay") as delay:
        yield delay


@pytest.fixture
def calls():
    """Mocked Firestore client and ``auth.delete_user`` sharing one call log."""
    manager = MagicMock()
    with (
        patch("apps.users.deletion.initialize_firebase", return_value=True),
        patch("apps.users.deletion.get_firestore_client", return_value=manager.client),
        patch("firebase_admin.auth.delete_user", manager.delete_user),
    ):
        yield manager


def _request(user, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        return request_account_deletion(user, DELETED_ACCOUNT_REASON_SELF)


# --- request_account_deletion ----------------------------------------------


def test_request_deactivates_and_queues(
    user, queued, django_capture_on_commit_callbacks
):
    first = RefreshToken.for_user(user)
    second = RefreshToken.for_user(user)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        record = request_account_deletion(user, DELETED_ACCOUNT_REASON_SELF)
    # Queued on commit, never inside the transaction.
    queued.assert_not_called()
    for callback in callbacks:
        callback()

    queued.assert_called_once_with(record.pk)
    user.refresh_from_db()
    assert user.is_active is False
    blacklisted = set(BlacklistedToken.objects.values_list("token__jti", flat=True))
    assert blacklisted == {first["jti"], second["jti"]}
    assert OutstandingToken.objects.filter(user=user).count() == 2
    assert record.status == DELETED_ACCOUNT_STATUS_PENDING
    assert record.user_id == user.pk
    assert record.email == EMAIL
    assert record.email_hash == email_hash(EMAIL)
    assert record.firebase_uid == UID
    assert record.reason == DELETED_ACCOUNT_REASON_SELF
    assert record.policy_version == "2026-11-06"


def test_request_without_uid_or_policy_stores_blanks(
    queued, django_capture_on_commit_callbacks
):
    web_user = User.objects.create_user(
        username="webonly5",
        email="web.only5@example.test",
        password="pw-not-used-1234",  # pragma: allowlist secret
    )
    record = _request(web_user, django_capture_on_commit_callbacks)
    assert record.firebase_uid == ""
    assert record.policy_version == ""


def test_second_request_reuses_pending_deletion(
    user, queued, django_capture_on_commit_callbacks
):
    record = _request(user, django_capture_on_commit_callbacks)
    again = _request(user, django_capture_on_commit_callbacks)

    assert again.pk == record.pk
    assert DeletedAccount.objects.count() == 1
    queued.assert_called_once_with(record.pk)


def test_staff_and_blog_author_refused(queued, django_capture_on_commit_callbacks):
    from apps.blog.models import BlogAuthorPage, BlogPostPage
    from wagtail.models import Page

    staff = User.objects.create_user(
        username="staff5", email="staff5@example.test", is_staff=True
    )
    post_author = User.objects.create_user(
        username="author5", email="author5@example.test"
    )
    page_author = User.objects.create_user(
        username="pageauthor5", email="pageauthor5@example.test"
    )
    root = Page.get_first_root_node()
    root.add_child(
        instance=BlogPostPage(
            title="A post",
            slug="a-post-5",
            author=post_author,
            publish_date=date(2026, 11, 1),
            introduction="<p>Intro</p>",
            live=False,
        )
    )
    root.add_child(
        instance=BlogAuthorPage(
            title="An author", slug="an-author-5", author=page_author, bio="<p>Bio</p>"
        )
    )

    for refused in (staff, post_author, page_author):
        with pytest.raises(DeletionRefused):
            _request(refused, django_capture_on_commit_callbacks)
        refused.refresh_from_db()
        assert refused.is_active is True

    assert DeletedAccount.objects.count() == 0
    queued.assert_not_called()


# --- delete_account_task ---------------------------------------------------


def _pending_record(user, django_capture_on_commit_callbacks):
    with patch.object(tasks.delete_account_task, "delay"):
        return _request(user, django_capture_on_commit_callbacks)


def test_job_completes_and_emails_once(user, calls, django_capture_on_commit_callbacks):
    record = _pending_record(user, django_capture_on_commit_callbacks)

    with django_capture_on_commit_callbacks(execute=True):
        tasks.delete_account_task(record.pk)
    # A duplicate delivery of the task changes nothing and sends nothing.
    with django_capture_on_commit_callbacks(execute=True):
        tasks.delete_account_task(record.pk)

    record.refresh_from_db()
    assert record.status == DELETED_ACCOUNT_STATUS_DONE
    assert record.deleted_at is not None
    assert record.email == ""
    assert record.firebase_uid == ""
    assert record.email_hash == email_hash(EMAIL)
    assert ERASE_STEP_NOTIFIED in record.steps_done
    assert not User.objects.filter(pk=user.pk).exists()

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [EMAIL]
    assert message.subject == ACCOUNT_DELETED_EMAIL_SUBJECT
    assert message.subject == "Your Houseplant MD account has been deleted"
    body = (
        "Your account and its data have been deleted, as described in our "
        "Privacy Policy. If you didn't ask for this, reply to this email."
    )
    assert body in message.body
    html = message.alternatives[0][0]
    assert "Privacy Policy" in html


def test_retry_resumes_after_auth_failure(
    user, calls, django_capture_on_commit_callbacks
):
    record = _pending_record(user, django_capture_on_commit_callbacks)
    calls.delete_user.side_effect = [auth.UnexpectedResponseError("down"), None]

    # Called directly, a retry re-raises the original error.
    with pytest.raises(auth.UnexpectedResponseError):
        with django_capture_on_commit_callbacks(execute=True):
            tasks.delete_account_task(record.pk)
    assert len(mail.outbox) == 0
    record.refresh_from_db()
    assert record.status == DELETED_ACCOUNT_STATUS_PENDING
    assert record.email == EMAIL

    with django_capture_on_commit_callbacks(execute=True):
        tasks.delete_account_task(record.pk)

    assert calls.client.recursive_delete.call_count == 1
    assert calls.delete_user.call_count == 2
    record.refresh_from_db()
    assert record.status == DELETED_ACCOUNT_STATUS_DONE
    assert len(mail.outbox) == 1


def test_failed_send_is_not_recorded_and_retries(
    user, calls, django_capture_on_commit_callbacks
):
    record = _pending_record(user, django_capture_on_commit_callbacks)

    with patch(
        "apps.core.services.email_service.send_mail", side_effect=OSError("smtp")
    ):
        with pytest.raises(RuntimeError):
            with django_capture_on_commit_callbacks(execute=True):
                tasks.delete_account_task(record.pk)
    record.refresh_from_db()
    assert ERASE_STEP_NOTIFIED not in record.steps_done
    assert record.status == DELETED_ACCOUNT_STATUS_PENDING
    assert record.email == EMAIL

    with django_capture_on_commit_callbacks(execute=True):
        tasks.delete_account_task(record.pk)
    record.refresh_from_db()
    assert record.status == DELETED_ACCOUNT_STATUS_DONE
    assert len(mail.outbox) == 1


def test_suppressed_address_finishes_without_mail(
    user, calls, django_capture_on_commit_callbacks
):
    record = _pending_record(user, django_capture_on_commit_callbacks)

    with patch("apps.core.email_feedback.is_suppressed", return_value=True):
        with django_capture_on_commit_callbacks(execute=True):
            tasks.delete_account_task(record.pk)

    record.refresh_from_db()
    assert record.status == DELETED_ACCOUNT_STATUS_DONE
    assert ERASE_STEP_NOTIFIED in record.steps_done
    assert len(mail.outbox) == 0


def test_last_retry_alerts_sentry(user, calls, django_capture_on_commit_callbacks):
    record = _pending_record(user, django_capture_on_commit_callbacks)
    calls.delete_user.side_effect = auth.UnexpectedResponseError("down")

    task = tasks.delete_account_task
    with patch("apps.users.tasks.sentry_sdk.capture_exception") as capture:
        task.push_request(retries=task.max_retries - 1)
        try:
            with pytest.raises(auth.UnexpectedResponseError):
                task.run(record.pk)
        finally:
            task.pop_request()
        capture.assert_not_called()

        task.push_request(retries=task.max_retries)
        try:
            with pytest.raises(auth.UnexpectedResponseError):
                task.run(record.pk)
        finally:
            task.pop_request()
        capture.assert_called_once()


def test_missing_record_is_a_no_op(calls):
    tasks.delete_account_task(987654)
    assert len(mail.outbox) == 0


def test_task_retry_options():
    task = tasks.delete_account_task
    assert task.max_retries == 8
    assert task.retry_backoff is True
    assert task.retry_backoff_max == 3600
