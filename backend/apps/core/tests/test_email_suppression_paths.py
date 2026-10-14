"""Every send path under the suppression backstop (todo 625, review round 2).

The SMTP backend's backstop drops a suppressed recipient and ``send()``
answers 0. Each direct send path must report that as suppressed, never as
sent and never as a failure for the weekly recovery to re-run: the forum
digest, the blog newsletter and its confirmation, ``send_email`` and the
lockout notice. Also: the explicit optional-mail marker, the click redirect
under any Accept header, the rollout-safe columns, the batched prune and the
admin that lifts a suppression.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from apps.core import email_feedback
from apps.core.constants import ACCOUNT_LOCKOUT_THRESHOLD
from apps.core.models import (
    DeliveryIntent,
    EmailClick,
    EmailNotification,
    EmailProviderEvent,
    EmailSuppression,
)
from apps.core.security import SecurityMonitor
from apps.core.services.email_service import EmailOutcome, EmailService, EmailType
from apps.core.tests.test_email_feedback import BACKSTOP, _notification
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()
Reason = EmailSuppression.Reason
SITE = "https://web.example"
API = "https://api.example"


def _suppress(address, reason):
    EmailSuppression.objects.create(
        address_hash=email_feedback.address_hash(address), reason=reason
    )


@pytest.fixture
def backstop(settings):
    settings.MAILERS = BACKSTOP["MAILERS"]


# --- the forum digest and the blog newsletter ----------------------------------


@pytest.mark.django_db
@override_settings(SITE_URL="https://forum.example", WAGTAILFORUM_DIGEST_UNSUBSCRIBE="")
def test_a_suppressed_digest_is_not_stamped_or_counted_as_failed(backstop):
    from wagtail_forum.models import ForumProfile
    from wagtail_forum.tests.test_digest import (
        _board,
        _index,
        _opt_in,
        _reply_note,
        _topic,
    )

    friend = User.objects.create_user(username="sp-poster")
    topic = _topic(_board(_index(), "general"), friend, "Repotting monstera")
    member = User.objects.create_user(username="sp-member", email="sp@example.com")
    _opt_in(member)
    _reply_note(member, friend, topic)
    # A complaint stops optional mail. The unsubscribe hook is off, so the
    # digest carries no List-Unsubscribe: only the explicit marker makes it
    # optional mail for the backstop.
    _suppress("sp@example.com", Reason.COMPLAINT)
    out = StringIO()

    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert mail.outbox == []
    assert "sent=0 failed=0 suppressed=1" in out.getvalue()
    assert ForumProfile.for_user(member).last_digest_sent_at is None


@pytest.mark.django_db
def test_the_digest_and_newsletter_carry_the_optional_mail_marker():
    from django.core.mail import EmailMessage

    marked = EmailMessage(
        "s", "b", "f@example.com", ["a@example.com"], headers={"X-Optional-Mail": "1"}
    )
    assert email_feedback.has_list_unsubscribe(marked)
    assert not email_feedback.has_list_unsubscribe(
        EmailMessage("s", "b", "f@example.com", ["a@example.com"])
    )


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
def test_a_suppressed_newsletter_is_not_stamped_or_counted_as_failed(backstop):
    from datetime import date

    from apps.blog.models import BlogIndexPage, BlogNewsletter, BlogPostPage
    from wagtail.models import Page

    cache.clear()
    now = timezone.now()
    author = User.objects.create_user(username="sp-author", email="au@example.com")
    index = BlogIndexPage(title="Blog", slug="sp-blog")
    Page.objects.get(id=1).add_child(instance=index)
    post = BlogPostPage(
        title="Fresh",
        slug="sp-fresh",
        author=author,
        publish_date=date.today(),
        introduction="<p>intro</p>",
        content_blocks=[],
        live=True,
    )
    index.add_child(instance=post)
    BlogPostPage.objects.filter(pk=post.pk).update(
        first_published_at=now - timedelta(days=1)
    )
    reader = BlogNewsletter.objects.create(
        email="reader@example.com", confirmed_at=now - timedelta(days=30)
    )
    _suppress("reader@example.com", Reason.COMPLAINT)
    out = StringIO()

    call_command("send_blog_newsletter", stdout=out)

    assert mail.outbox == []
    assert "failed=0 suppressed=1" in out.getvalue()
    reader.refresh_from_db()
    assert reader.last_sent_at is None


@pytest.mark.django_db
def test_a_suppressed_confirmation_gives_its_stamp_back_and_is_not_retried(
    backstop, settings
):
    from apps.blog import newsletter
    from apps.blog.models import BlogNewsletter
    from apps.blog.tasks import send_newsletter_confirmation

    settings.SITE_URL = SITE
    _suppress("bounced@example.com", Reason.HARD_BOUNCE)

    assert (
        newsletter.request_confirmation_outcome("bounced@example.com")
        == newsletter.CONFIRMATION_SUPPRESSED
    )
    row = BlogNewsletter.objects.get(email="bounced@example.com")
    assert row.confirmation_sent_at is None

    newsletter.record_confirmation_intent("bounced@example.com")
    intent = DeliveryIntent.objects.get(
        kind=DeliveryIntent.Kind.NEWSLETTER_CONFIRMATION
    )
    send_newsletter_confirmation.apply(
        args=("bounced@example.com",), kwargs={"intent_id": intent.pk}
    )
    intent.refresh_from_db()
    assert (intent.status, intent.last_error) == ("suppressed", "address_suppressed")
    assert mail.outbox == []


# --- send_email and the lockout notice -----------------------------------------


@pytest.mark.django_db
def test_send_email_reports_a_backstop_drop_as_an_address_suppression(
    backstop, settings
):
    settings.SITE_URL = SITE
    settings.API_PUBLIC_URL = ""
    _suppress("late@example.com", Reason.HARD_BOUNCE)
    service = EmailService()
    # Suppressed after the service's own check: only the backend drops it.
    with patch.object(email_feedback, "is_suppressed", return_value=False):
        sent = service.send_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipient="late@example.com",
            subject="Hello",
            template_name="generic_notification",
            context={"notification_title": "Hello", "notification_message": "Hi"},
        )
    assert sent is False
    assert (service.last_outcome, service.last_suppression_reason) == (
        EmailOutcome.SUPPRESSED,
        "address_suppressed",
    )
    assert not EmailNotification.objects.exists()


@pytest.mark.django_db
def test_a_lockout_notice_the_backstop_drops_is_recorded_suppressed(backstop):
    from apps.users import tasks

    cache.clear()
    user = User.objects.create_user(username="lockdrop", email="lockdrop@example.com")
    with patch.object(
        tasks.send_lockout_email_task, "delay", side_effect=ConnectionError("down")
    ):
        for _ in range(ACCOUNT_LOCKOUT_THRESHOLD):
            SecurityMonitor.track_failed_login_attempt(
                username="lockdrop", ip_address="192.168.1.100"
            )
    intent = DeliveryIntent.objects.get(kind=DeliveryIntent.Kind.LOCKOUT_EMAIL)
    _suppress("lockdrop@example.com", Reason.HARD_BOUNCE)

    # Suppressed after the task's own check: only the backend drops it.
    with patch.object(tasks, "_address_suppressed", return_value=False):
        tasks.send_lockout_email_task.apply(
            args=(user.pk,), kwargs={"intent_id": intent.pk}
        )

    assert mail.outbox == []
    intent.refresh_from_db()
    assert (intent.status, intent.last_error) == ("suppressed", "address_suppressed")


# --- the click redirect --------------------------------------------------------


@pytest.mark.django_db
@override_settings(SITE_URL=SITE, API_PUBLIC_URL=API)
@pytest.mark.parametrize("accept", ["text/html", "image/png", "application/json"])
def test_the_click_redirect_answers_any_accept_header(accept):
    row = _notification()
    url = email_feedback.click_url(row.uuid, "post_url", f"{SITE}/forum/t")
    response = APIClient().get(url.removeprefix(API), HTTP_ACCEPT=accept)
    assert (response.status_code, response["Location"]) == (302, f"{SITE}/forum/t")
    assert EmailClick.objects.filter(notification=row).count() == 1


# --- the rollout, the prune and the admin --------------------------------------


@pytest.mark.django_db
def test_a_previous_release_insert_gets_the_new_column_defaults():
    """A worker on the previous release inserts the old columns and none of
    the new ones (migration 0009): the database defaults fill them."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO core_emailnotification "
            "(uuid, email_type, recipient_email, subject, template_name, status,"
            " priority, created_at, error_message, retry_count,"
            " open_count, click_count, opened_at, clicked_at) "
            "VALUES (gen_random_uuid(), 'community_update', 'old@example.com',"
            " 's', 't', 'sent', 'normal', now(), '', 0, 0, 0, NULL, NULL) "
            "RETURNING id"
        )
        (pk,) = cursor.fetchone()
    row = EmailNotification.objects.get(pk=pk)
    assert (row.message_id, row.provider_email_id) == ("", "")


@pytest.mark.django_db
def test_the_prune_deletes_in_batches():
    old = timezone.now() - timedelta(days=200)
    for i in range(5):
        EmailProviderEvent.objects.create(
            svix_id=f"old-{i}", event_type="email.sent", occurred_at=old
        )
    EmailProviderEvent.objects.update(received_at=old)
    keep = EmailProviderEvent.objects.create(
        svix_id="new", event_type="email.sent", occurred_at=timezone.now()
    )

    with (
        patch.object(email_feedback, "EMAIL_FEEDBACK_PRUNE_BATCH", 2),
        patch.object(
            EmailProviderEvent.objects,
            "filter",
            wraps=EmailProviderEvent.objects.filter,
        ) as filtered,
    ):
        totals = email_feedback.prune()

    assert totals["events"] == 5
    assert list(EmailProviderEvent.objects.all()) == [keep]
    # 5 rows at 2 per DELETE: three batches, each one its own pk__in filter.
    assert sum(1 for c in filtered.call_args_list if "pk__in" in c.kwargs) == 3


@pytest.mark.django_db
def test_staff_find_a_suppression_by_its_address_and_can_only_delete_it(rf):
    from apps.core.admin import EmailSuppressionAdmin
    from django.contrib import admin

    _suppress("Bob@Example.com", Reason.HARD_BOUNCE)
    _suppress("other@example.com", Reason.COMPLAINT)
    model_admin = EmailSuppressionAdmin(EmailSuppression, admin.site)
    request = rf.get("/admin/core/emailsuppression/")

    found, _ = model_admin.get_search_results(
        request, EmailSuppression.objects.all(), "  bob@example.com "
    )
    assert [row.reason for row in found] == [Reason.HARD_BOUNCE]
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request)
    assert admin.site.is_registered(EmailSuppression)
