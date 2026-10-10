"""Todo 454: a deprecated mail argument planted at a send site fails the run.

pytest.ini turns RemovedInDjango70Warning into an exception (todo 364). Each
send site below catches ``Exception`` so one bad send does not stop a batch,
and ``Warning`` subclasses ``Exception``: without an ``except Warning: raise``
ahead of it, a first-party deprecation there was logged as "[EMAIL] ...
failed" and the suite stayed green. Each test plants a real deprecated
argument (``fail_silently=True``, deprecated in Django 6.1) into the call the
site makes, and expects the warning to reach the test.

The forum digest site lives in the package, so its test is in
``wagtail_forum/tests/test_digest.py``.
"""

import pytest
from apps.blog import newsletter, newsletter_digest
from apps.blog.models import BlogNewsletter
from apps.core.security import SecurityMonitor
from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.mail import EmailMessage
from django.test import override_settings
from django.utils import timezone
from django.utils.deprecation import RemovedInDjango70Warning

User = get_user_model()


@pytest.fixture
def planted_message_send(monkeypatch):
    """Every ``EmailMessage.send()`` (EmailMultiAlternatives included) is
    called with the deprecated ``fail_silently=True``, from a frame outside
    Django, so Django's warn_about_external_use fires."""
    real_send = EmailMessage.send

    def send(self, *args, **kwargs):
        kwargs["fail_silently"] = True
        return real_send(self, *args, **kwargs)

    monkeypatch.setattr(EmailMessage, "send", send)


def _plant_send_mail(monkeypatch, module_path):
    """Replace ``send_mail`` as the module imported it with a call that adds
    the deprecated ``fail_silently=True``."""
    from django.core.mail import send_mail as real_send_mail

    def send_mail(*args, **kwargs):
        kwargs["fail_silently"] = True
        return real_send_mail(*args, **kwargs)

    monkeypatch.setattr(f"{module_path}.send_mail", send_mail)


def test_the_planted_argument_is_deprecated(planted_message_send):
    # The plant itself: proves fail_silently=True is what raises, so the
    # tests below fail for the gate and not for some other reason.
    with pytest.raises(RemovedInDjango70Warning):
        EmailMessage("s", "b", None, ["to@example.com"]).send()


@pytest.mark.django_db
def test_lockout_notification_lets_a_deprecation_through(monkeypatch):
    _plant_send_mail(monkeypatch, "apps.core.security")
    User.objects.create_user(username="locked", email="locked@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        SecurityMonitor._send_lockout_notification(
            "locked", {"attempts_count": 10, "ip_addresses": ["203.0.113.9"]}
        )


@pytest.mark.django_db
def test_lockout_notification_still_sends_without_the_plant():
    User.objects.create_user(username="locked2", email="locked2@example.com")
    SecurityMonitor._send_lockout_notification(
        "locked2", {"attempts_count": 10, "ip_addresses": ["203.0.113.9"]}
    )
    assert [m.to for m in mail.outbox] == [["locked2@example.com"]]


@pytest.mark.django_db
def test_newsletter_confirmation_lets_a_deprecation_through(planted_message_send):
    subscriber = BlogNewsletter.objects.create(email="confirm@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        newsletter._send_confirmation_email(subscriber)


@pytest.mark.django_db
@override_settings(SITE_URL="https://web.example", API_PUBLIC_URL="https://api.example")
def test_newsletter_send_lets_a_deprecation_through(planted_message_send):
    subscriber = BlogNewsletter.objects.create(
        email="reader@example.com", confirmed_at=timezone.now()
    )

    with pytest.raises(RemovedInDjango70Warning):
        newsletter_digest.send(subscriber, [])


@pytest.mark.django_db
def test_email_service_send_email_lets_a_deprecation_through(planted_message_send):
    user = User.objects.create_user(username="svc", email="svc@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        EmailService().send_welcome_email(user)


@pytest.mark.django_db
def test_email_service_bulk_send_lets_a_deprecation_through(planted_message_send):
    # send_bulk_email wraps send_email in its own except Exception.
    user = User.objects.create_user(username="bulk", email="bulk@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        EmailService().send_bulk_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipients=[user],
            subject="Bulk",
            template_name="welcome_email",
            context_factory=lambda recipient: {},
            respect_preferences=False,
        )


@pytest.mark.django_db
def test_email_service_transactional_lets_a_deprecation_through(monkeypatch):
    _plant_send_mail(monkeypatch, "apps.core.services.email_service")

    with pytest.raises(RemovedInDjango70Warning):
        EmailService().send_transactional_email("tx@example.com", "Subject", "Body")


def _forum_reply(user):
    return NotificationService().send_forum_reply_notification(
        user=user,
        topic_title="Yellow leaves",
        reply_author="fern",
        reply_excerpt="Check the drainage.",
        topic_url="https://web.example/forum/t/1",
    )


@pytest.mark.django_db
def test_forum_reply_notification_lets_a_deprecation_through(planted_message_send):
    # Todo 537: send_notification wrapped the send in its own except Exception.
    user = User.objects.create_user(username="reply", email="reply@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        _forum_reply(user)


@pytest.mark.django_db
def test_forum_reply_notification_still_sends_without_the_plant():
    # The control: the path above reaches .send(), so its test fails for
    # the gate and not for a preference or template that skips the send.
    user = User.objects.create_user(username="reply2", email="reply2@example.com")

    assert _forum_reply(user) is True
    assert [m.to for m in mail.outbox] == [["reply2@example.com"]]


@pytest.mark.django_db
def test_scheduled_notification_lets_a_deprecation_through(planted_message_send):
    # _schedule_notification sends at once, in a loop of its own (todo 537).
    user = User.objects.create_user(username="later", email="later@example.com")

    with pytest.raises(RemovedInDjango70Warning):
        NotificationService().send_notification(
            notification_type=EmailType.FORUM_REPLY,
            recipient=user,
            title="Later",
            message="Body",
            context={"topic_title": "t", "author_name": "a", "post_excerpt": "e"},
            schedule_for=timezone.now() + timezone.timedelta(hours=1),
        )


@pytest.mark.django_db
def test_a_deprecation_in_newsletter_confirmation_gives_the_stamp_back(
    planted_message_send,
):
    # Todo 537: request_confirmation stamps the row before sending; a
    # re-raised Warning must not leave the address throttled.
    with pytest.raises(RemovedInDjango70Warning):
        newsletter.request_confirmation("stamp@example.com")

    subscriber = BlogNewsletter.objects.get(email="stamp@example.com")
    assert subscriber.confirmation_sent_at is None
