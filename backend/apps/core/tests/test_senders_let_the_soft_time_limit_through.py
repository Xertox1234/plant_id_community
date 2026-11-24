"""The Celery soft time limit is the calling task's deadline, never one
send's failure (audit 2026-11-21 M3).

Each shared sender wrapped its send in ``except Exception``, so the limit was
logged as a failed (transient) send and the batch ran on until the hard kill,
losing every outcome it had not yet written. Every sender here must let it
through, as it already lets a ``RemovedInDjango70Warning`` through (todo 454).
"""

from unittest.mock import MagicMock, patch

import pytest
from apps.core.services.email_service import EmailService, EmailType
from apps.core.services.notification_service import NotificationService
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage

# Forum email goes only to a verified address (audit 2026-11-24 F211).
pytestmark = pytest.mark.usefixtures("verified_accounts")

User = get_user_model()


@pytest.fixture
def send_hits_the_limit(monkeypatch):
    def send(self, *args, **kwargs):
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr(EmailMessage, "send", send)


@pytest.mark.django_db
def test_send_email_lets_the_soft_time_limit_through(send_hits_the_limit):
    user = User.objects.create_user(username="limit", email="limit@example.com")

    with pytest.raises(SoftTimeLimitExceeded):
        EmailService().send_welcome_email(user)


@pytest.mark.django_db
def test_bulk_send_lets_the_soft_time_limit_through(send_hits_the_limit):
    user = User.objects.create_user(username="bulklimit", email="bl@example.com")

    with pytest.raises(SoftTimeLimitExceeded):
        EmailService().send_bulk_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipients=[user],
            subject="Bulk",
            template_name="welcome_email",
            context_factory=lambda recipient: {},
            respect_preferences=False,
        )


@pytest.mark.django_db
def test_a_template_render_lets_the_soft_time_limit_through():
    user = User.objects.create_user(username="renderlimit", email="rl@example.com")

    with (
        patch(
            "apps.core.services.email_service.render_to_string",
            side_effect=SoftTimeLimitExceeded(),
        ),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        EmailService().send_welcome_email(user)


@pytest.mark.django_db
def test_transactional_email_lets_the_soft_time_limit_through():
    with (
        patch(
            "apps.core.services.email_service.send_mail",
            side_effect=SoftTimeLimitExceeded(),
        ),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        EmailService().send_transactional_email("tx@example.com", "Subject", "Body")


@pytest.mark.django_db
def test_a_forum_notification_lets_the_soft_time_limit_through(send_hits_the_limit):
    # NotificationService.send_notification wraps each channel in its own
    # except Exception (the todo 537 shape).
    user = User.objects.create_user(username="notelimit", email="nl@example.com")

    with pytest.raises(SoftTimeLimitExceeded):
        NotificationService().send_forum_reply_notification(
            user=user,
            topic_title="Yellow leaves",
            reply_author="fern",
            reply_excerpt="Check the drainage.",
            topic_url="https://web.example/forum/t/1",
        )


@pytest.mark.django_db
def test_web_push_lets_the_soft_time_limit_through(settings):
    from apps.users.models import PushSubscription
    from apps.users.services import NotificationService as PushService

    settings.VAPID_PUBLIC_KEY = "BPub"
    settings.VAPID_PRIVATE_KEY = "priv"  # pragma: allowlist secret
    settings.VAPID_CLAIMS_EMAIL = "ops@example.com"
    user = User.objects.create_user(username="pushlimit")
    subscription = PushSubscription.objects.create(
        user=user,
        endpoint="https://fcm.googleapis.com/fcm/send/pushlimit",
        p256dh_key="BPk-key",
        auth_key="auth-secret",  # pragma: allowlist secret
    )

    with (
        patch("apps.users.services.webpush", side_effect=SoftTimeLimitExceeded()),
        pytest.raises(SoftTimeLimitExceeded),
    ):
        PushService.send_web_push_notification(
            subscription, title="t", body="b", requests_session=MagicMock()
        )
