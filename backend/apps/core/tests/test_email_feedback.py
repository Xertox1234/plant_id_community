"""Email provider feedback, suppression and click attribution (todo 625).

AC1: the Resend webhook is authenticated by its Svix signature, refuses a
malformed or stale event, applies a duplicate once and an out-of-order event
safely, and matches events to the email they report on. A hard bounce or a
complaint suppresses later sends under the recorded policy, without changing
what an account-security flow does.

AC2: first-party click attribution through a signed redirect, with an
attribution window, one count per email and link, a 90-day retention and
deletion with the account. Opens are never collected.
"""

import base64
import inspect
import json
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from apps.core import email_feedback
from apps.core.constants import (
    ACCOUNT_LOCKOUT_THRESHOLD,
    EMAIL_CLICK_ATTRIBUTION_DAYS,
    EMAIL_FEEDBACK_RETENTION_DAYS,
    LOCKOUT_STATUS_KEY,
)
from apps.core.mail_backends import SuppressionFilterMixin
from apps.core.models import (
    DeliveryIntent,
    EmailClick,
    EmailNotification,
    EmailProviderEvent,
    EmailSuppression,
)
from apps.core.security import SecurityMonitor
from apps.core.services.email_service import EmailOutcome, EmailService, EmailType
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

User = get_user_model()

# An obviously fake signing secret: 24 "x" bytes, base64.
SECRET = "whsec_" + base64.b64encode(b"x" * 24).decode()  # pragma: allowlist secret
WEBHOOK = "/api/v1/email/webhooks/resend/"
# A v1 entry made with a retired key, as Svix sends during a rotation.
STALE_SIGNATURE = "v1," + base64.b64encode(b"not-this-one").decode()
# Not base64 after the prefix: a misconfiguration, never "accept".
MALFORMED_SECRET = "whsec_" + "not base64!"  # pragma: allowlist secret
SITE = "https://web.example"
API = "https://api.example"
Reason = EmailSuppression.Reason


class SuppressingLocmemBackend(SuppressionFilterMixin, LocmemBackend):
    """The production SMTP backend's filter on the test outbox."""


BACKSTOP = {
    "MAILERS": {
        "default": {
            "BACKEND": "apps.core.tests.test_email_feedback.SuppressingLocmemBackend"
        }
    }
}


def _event(event_type, to="reader@example.com", *, created_at=None, **data):
    return {
        "type": event_type,
        "created_at": created_at or timezone.now().isoformat(),
        "data": {
            "email_id": data.pop("email_id", "re-email-1"),
            "message_id": data.pop("message_id", ""),
            "to": [to] if isinstance(to, str) else to,
            **data,
        },
    }


def _post(payload, *, svix_id="msg_1", secret=SECRET, timestamp=None, raw=None):
    body = raw if raw is not None else json.dumps(payload).encode()
    ts = str(int(time.time()) if timestamp is None else timestamp)
    signature = email_feedback.sign(secret, msg_id=svix_id, timestamp=ts, body=body)
    return APIClient().post(
        WEBHOOK,
        data=body,
        content_type="application/json",
        HTTP_SVIX_ID=svix_id,
        HTTP_SVIX_TIMESTAMP=ts,
        HTTP_SVIX_SIGNATURE=signature,
    )


def _suppression(address):
    return EmailSuppression.objects.filter(
        address_hash=email_feedback.address_hash(address)
    ).first()


def _hard_bounce(address, svix_id="msg_bounce"):
    return _post(
        _event(
            EVENT_BOUNCED, address, bounce={"type": "Permanent", "subType": "General"}
        ),
        svix_id=svix_id,
    )


@pytest.fixture
def webhook_on(settings):
    settings.RESEND_WEBHOOK_SECRET = SECRET


@pytest.fixture
def no_click_tracking(settings):
    settings.SITE_URL = SITE
    settings.API_PUBLIC_URL = ""


@pytest.fixture
def click_tracking(settings):
    settings.SITE_URL = SITE
    settings.API_PUBLIC_URL = API


@pytest.fixture
def backstop(settings):
    settings.MAILERS = BACKSTOP["MAILERS"]


EVENT_BOUNCED = email_feedback.EVENT_BOUNCED
EVENT_DELIVERED = email_feedback.EVENT_DELIVERED
EVENT_COMPLAINED = email_feedback.EVENT_COMPLAINED


# ---------------------------------------------------------------------------
# AC1: authentication and malformed-event refusal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWebhookAuthentication:
    def test_no_secret_configured_means_disabled(self):
        with override_settings(RESEND_WEBHOOK_SECRET=""):
            response = _post(_event(EVENT_DELIVERED))
        assert response.status_code == 503
        assert not EmailProviderEvent.objects.exists()

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_a_correctly_signed_event_is_accepted(self):
        response = _post(_event(EVENT_DELIVERED))
        assert response.status_code == 200
        assert response.json() == {"status": "processed"}
        assert EmailProviderEvent.objects.get().svix_id == "msg_1"

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_a_wrong_secret_is_refused(self):
        other = (
            "whsec_" + base64.b64encode(b"y" * 24).decode()
        )  # pragma: allowlist secret
        response = _post(_event(EVENT_DELIVERED), secret=other)
        assert response.status_code == 401
        assert not EmailProviderEvent.objects.exists()

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_missing_signature_headers_are_refused(self):
        response = APIClient().post(
            WEBHOOK,
            data=json.dumps(_event(EVENT_DELIVERED)),
            content_type="application/json",
        )
        assert response.status_code == 401

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_a_tampered_body_is_refused(self):
        body = json.dumps(_event(EVENT_DELIVERED)).encode()
        ts = str(int(time.time()))
        signature = email_feedback.sign(SECRET, msg_id="msg_1", timestamp=ts, body=body)
        tampered = body.replace(b"reader@", b"victim@")
        response = APIClient().post(
            WEBHOOK,
            data=tampered,
            content_type="application/json",
            HTTP_SVIX_ID="msg_1",
            HTTP_SVIX_TIMESTAMP=ts,
            HTTP_SVIX_SIGNATURE=signature,
        )
        assert response.status_code == 401

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_a_replayed_old_request_is_refused(self):
        """A captured request replayed after the five-minute window."""
        response = _post(_event(EVENT_BOUNCED), timestamp=int(time.time()) - 6 * 60)
        assert response.status_code == 401
        assert not EmailSuppression.objects.exists()

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_one_matching_signature_among_several_is_enough(self):
        """During a secret rotation Svix sends one signature per secret."""
        body = json.dumps(_event(EVENT_DELIVERED)).encode()
        ts = str(int(time.time()))
        good = email_feedback.sign(SECRET, msg_id="msg_1", timestamp=ts, body=body)
        response = APIClient().post(
            WEBHOOK,
            data=body,
            content_type="application/json",
            HTTP_SVIX_ID="msg_1",
            HTTP_SVIX_TIMESTAMP=ts,
            HTTP_SVIX_SIGNATURE=f"{STALE_SIGNATURE} {good}",
        )
        assert response.status_code == 200

    @override_settings(RESEND_WEBHOOK_SECRET=MALFORMED_SECRET)
    def test_a_malformed_secret_disables_rather_than_accepts(self):
        response = APIClient().post(
            WEBHOOK,
            data=b"{}",
            content_type="application/json",
            HTTP_SVIX_ID="msg_1",
            HTTP_SVIX_TIMESTAMP=str(int(time.time())),
            HTTP_SVIX_SIGNATURE="v1,AAAA",
        )
        assert response.status_code == 503

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    @pytest.mark.parametrize(
        "raw",
        [
            b"not json",
            b"[1, 2]",
            json.dumps(
                {"type": "email.bounced", "created_at": "now", "data": {}}
            ).encode(),
            json.dumps(
                {"type": "email.bounced", "created_at": "2026-10-12T17:50:00Z"}
            ).encode(),
            json.dumps(
                {
                    "type": "email.bounced",
                    "created_at": "2026-10-12T17:50:00Z",
                    "data": {"to": "a@example.com, b@example.com".split(",") + [3]},
                }
            ).encode(),
            json.dumps(
                {
                    "type": "email.bounced",
                    "created_at": "2026-10-12T17:50:00Z",
                    "data": {"to": []},
                }
            ).encode(),
            json.dumps(
                {"created_at": "2026-10-12T17:50:00Z", "data": {"to": ["a@x.io"]}}
            ).encode(),
        ],
        ids=[
            "not-json",
            "array",
            "bad-time",
            "no-data",
            "to-not-strings",
            "no-recipient",
            "no-type",
        ],
    )
    def test_a_malformed_event_is_refused(self, raw):
        response = _post(None, raw=raw)
        assert response.status_code == 400
        assert not EmailProviderEvent.objects.exists()
        assert not EmailSuppression.objects.exists()

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_an_overlong_svix_id_is_refused(self):
        response = _post(_event(EVENT_DELIVERED), svix_id="m" * 65)
        assert response.status_code == 400

    @override_settings(RESEND_WEBHOOK_SECRET=SECRET)
    def test_an_event_this_app_does_not_act_on_is_ignored(self):
        """Opens are never collected, even if the provider reports them."""
        response = _post(_event("email.opened"))
        assert response.json() == {"status": "ignored"}
        assert not EmailSuppression.objects.exists()


# ---------------------------------------------------------------------------
# AC1: duplicates, ordering and correlation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("webhook_on", "no_click_tracking")
class TestEventsAndCorrelation:
    def _send(self, address="reader@example.com"):
        assert EmailService().send_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipient=address,
            subject="Hello",
            template_name="generic_notification",
            context={"notification_title": "Hello", "notification_message": "Hi"},
        )
        message = mail.outbox[-1]
        return EmailNotification.objects.get(), message.extra_headers["Message-ID"]

    def test_the_message_id_names_the_row(self):
        row, message_id = self._send()
        assert row.message_id == message_id
        assert row.uuid.hex in message_id

    def test_an_event_is_matched_by_message_id_then_by_provider_id(self):
        row, message_id = self._send()
        _post(
            _event(EVENT_DELIVERED, message_id=message_id, email_id="re-42"),
            svix_id="a",
        )
        row.refresh_from_db()
        assert (row.status, row.provider_email_id) == ("delivered", "re-42")
        assert row.delivered_at is not None

        # A later event that carries only Resend's id still finds the row.
        _post(_event(EVENT_COMPLAINED, message_id="", email_id="re-42"), svix_id="b")
        row.refresh_from_db()
        assert row.status == "complained"
        assert EmailProviderEvent.objects.get(svix_id="b").notification == row

    def test_an_unmatched_event_still_suppresses_the_address(self):
        _hard_bounce("stranger@example.com")
        event = EmailProviderEvent.objects.get()
        assert event.notification is None
        assert _suppression("stranger@example.com").reason == Reason.HARD_BOUNCE

    def test_a_duplicate_event_is_applied_once(self):
        row, message_id = self._send()
        payload = _event(
            EVENT_BOUNCED, message_id=message_id, bounce={"type": "Permanent"}
        )
        first = _post(payload, svix_id="dup")
        bounced_at = EmailNotification.objects.get().bounced_at
        second = _post(payload, svix_id="dup")
        assert first.json() == {"status": "processed"}
        assert second.status_code == 200
        assert second.json() == {"status": "duplicate"}
        assert EmailProviderEvent.objects.count() == 1
        assert EmailSuppression.objects.count() == 1
        assert EmailNotification.objects.get().bounced_at == bounced_at

    def test_events_out_of_order_settle_on_the_same_state(self):
        """The bounce is reported first, the earlier delivery report last:
        the status stays bounced and each time is the event's own."""
        row, message_id = self._send()
        delivered = timezone.now() - timedelta(minutes=5)
        bounced = timezone.now() - timedelta(minutes=1)
        _post(
            _event(
                EVENT_BOUNCED,
                message_id=message_id,
                created_at=bounced.isoformat(),
                bounce={"type": "Transient"},
            ),
            svix_id="late-bounce",
        )
        _post(
            _event(
                EVENT_DELIVERED, message_id=message_id, created_at=delivered.isoformat()
            ),
            svix_id="early-delivery",
        )
        row.refresh_from_db()
        assert row.status == "bounced"
        assert row.delivered_at == delivered
        assert row.bounced_at == bounced

    def test_a_transient_bounce_suppresses_nothing(self):
        _post(
            _event(
                EVENT_BOUNCED, bounce={"type": "Transient", "subType": "MailboxFull"}
            )
        )
        assert not EmailSuppression.objects.exists()
        event = EmailProviderEvent.objects.get()
        assert (event.bounce_type, event.bounce_subtype) == ("Transient", "MailboxFull")

    def test_a_complaint_never_weakens_a_hard_bounce(self):
        _hard_bounce("reader@example.com", svix_id="b1")
        _post(_event(EVENT_COMPLAINED), svix_id="c1")
        assert _suppression("reader@example.com").reason == Reason.HARD_BOUNCE

    def test_a_hard_bounce_strengthens_a_complaint(self):
        _post(_event(EVENT_COMPLAINED), svix_id="c1")
        _hard_bounce("reader@example.com", svix_id="b1")
        assert _suppression("reader@example.com").reason == Reason.HARD_BOUNCE

    def test_resend_suppressed_event_is_a_hard_bounce(self):
        _post(_event(email_feedback.EVENT_SUPPRESSED))
        assert _suppression("reader@example.com").reason == Reason.HARD_BOUNCE

    def test_no_address_is_stored(self):
        _hard_bounce("Reader@Example.com")
        stored = json.dumps(
            list(EmailSuppression.objects.values())
            + list(EmailProviderEvent.objects.values()),
            default=str,
        )
        assert "example.com" not in stored.lower()
        # The hash ignores case and display names.
        assert _suppression("Someone <reader@example.com>") is not None


# ---------------------------------------------------------------------------
# AC1: the suppression policy at send time
# ---------------------------------------------------------------------------


def _suppress(address, reason):
    EmailSuppression.objects.create(
        address_hash=email_feedback.address_hash(address), reason=reason
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("no_click_tracking")
class TestSuppressionPolicy:
    def _optional(self, service, address):
        return service.send_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipient=address,
            subject="Hello",
            template_name="generic_notification",
            context={"notification_title": "Hello", "notification_message": "Hi"},
        )

    def _account(self, service, address):
        return service.send_email(
            email_type=EmailType.ACCOUNT_VERIFICATION,
            recipient=address,
            subject="Confirm",
            template_name="generic_notification",
            context={"notification_title": "Confirm", "notification_message": "Hi"},
            respect_preferences=False,
        )

    def test_a_hard_bounce_stops_every_kind_of_mail(self):
        _suppress("gone@example.com", Reason.HARD_BOUNCE)
        service = EmailService()
        assert not self._optional(service, "gone@example.com")
        assert service.last_outcome == EmailOutcome.SUPPRESSED
        assert not self._account(service, "gone@example.com")
        assert service.last_outcome == EmailOutcome.SUPPRESSED
        assert not service.send_transactional_email("gone@example.com", "Reset", "x")
        assert service.last_outcome == EmailOutcome.SUPPRESSED
        assert mail.outbox == []
        # Never recorded as sent.
        assert not EmailNotification.objects.exists()

    def test_a_complaint_stops_optional_mail_only(self):
        _suppress("annoyed@example.com", Reason.COMPLAINT)
        service = EmailService()
        assert not self._optional(service, "annoyed@example.com")
        assert service.last_outcome == EmailOutcome.SUPPRESSED
        assert self._account(service, "annoyed@example.com")
        assert service.send_transactional_email("annoyed@example.com", "Reset", "x")
        assert len(mail.outbox) == 2

    def test_another_address_is_unaffected(self):
        _suppress("gone@example.com", Reason.HARD_BOUNCE)
        assert self._optional(EmailService(), "fine@example.com")

    def test_a_database_error_fails_open(self):
        from django.db import DatabaseError

        with patch.object(
            email_feedback, "blocked_reasons", side_effect=DatabaseError("down")
        ):
            assert email_feedback.is_suppressed("x@example.com", optional=True) is False


@pytest.mark.django_db
@pytest.mark.usefixtures("backstop")
class TestBackendBackstop:
    """Send paths that never call is_suppressed (digests, the newsletter,
    the package's own mail) are filtered in the mail backend."""

    def _message(self, to, *, list_unsubscribe=False):
        headers = {"List-Unsubscribe": "<https://x/u>"} if list_unsubscribe else {}
        return EmailMessage("s", "b", "from@example.com", to, headers=headers)

    def test_optional_mail_to_a_complained_address_is_dropped(self):
        _suppress("annoyed@example.com", Reason.COMPLAINT)
        sent = self._message(["annoyed@example.com"], list_unsubscribe=True).send()
        assert sent == 0
        assert mail.outbox == []

    def test_account_mail_to_a_complained_address_still_goes(self):
        _suppress("annoyed@example.com", Reason.COMPLAINT)
        assert self._message(["annoyed@example.com"]).send() == 1

    def test_a_hard_bounced_recipient_is_removed_and_the_others_kept(self):
        _suppress("gone@example.com", Reason.HARD_BOUNCE)
        message = self._message(["gone@example.com", "fine@example.com"])
        message.cc = ["gone@example.com"]
        assert message.send() == 1
        [sent] = mail.outbox
        assert (sent.to, sent.cc) == (["fine@example.com"], [])

    def test_a_clean_address_is_untouched(self):
        assert self._message(["fine@example.com"], list_unsubscribe=True).send() == 1

    def test_the_production_backend_carries_the_filter(self):
        from apps.core.mail_backends import ConfiguredSMTPBackend

        assert issubclass(ConfiguredSMTPBackend, SuppressionFilterMixin)


# ---------------------------------------------------------------------------
# AC1: account-security controls are not bypassed
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountSecurityUnchanged:
    def setup_method(self):
        cache.clear()

    def test_verification_for_a_bounced_address_is_terminal_and_changes_nothing_else(
        self, django_capture_on_commit_callbacks
    ):
        from apps.users import tasks
        from apps.users.email_verification import is_email_verified

        user = User.objects.create_user(
            username="ada",
            email="ada@example.com",
            password="x-Pass-123!",  # pragma: allowlist secret
        )
        _suppress("ada@example.com", Reason.HARD_BOUNCE)
        client = APIClient()
        client.force_authenticate(user=user)
        with patch.object(
            tasks.send_verification_email_task,
            "delay",
            side_effect=lambda *a: tasks.send_verification_email_task.apply(args=a),
        ):
            with django_capture_on_commit_callbacks(execute=True):
                response = client.post("/api/v1/auth/verify-email/resend/")

        # The flow answers as before and charges the allowance as before.
        assert response.status_code == 200
        assert response.data["sent"] is True
        user.refresh_from_db()
        assert user.verification_emails_sent == 1
        # The mail is not sent, not retried, and not recorded as sent.
        assert mail.outbox == []
        intent = DeliveryIntent.objects.get(kind=DeliveryIntent.Kind.VERIFICATION_EMAIL)
        assert (intent.status, intent.last_error) == (
            "suppressed",
            "address_suppressed",
        )
        # The address is still unverified: suppression grants nothing.
        assert not is_email_verified(user)

    def test_a_lockout_is_enforced_whether_or_not_its_mail_can_go(self):
        from apps.users import tasks

        user = User.objects.create_user(username="locked", email="locked@example.com")
        _suppress("locked@example.com", Reason.HARD_BOUNCE)
        # The enqueue fails, so the lockout mail is a durable outbox row.
        with patch.object(
            tasks.send_lockout_email_task,
            "delay",
            side_effect=ConnectionError("broker down"),
        ):
            for _ in range(ACCOUNT_LOCKOUT_THRESHOLD):
                SecurityMonitor.track_failed_login_attempt(
                    username="locked", ip_address="192.168.1.100"
                )
        intent = DeliveryIntent.objects.get(kind=DeliveryIntent.Kind.LOCKOUT_EMAIL)

        with patch("apps.core.security.send_mail") as smtp:
            tasks.send_lockout_email_task.apply(
                args=(user.pk,), kwargs={"intent_id": intent.pk}
            )

        smtp.assert_not_called()
        intent.refresh_from_db()
        assert (intent.status, intent.last_error) == (
            "suppressed",
            "address_suppressed",
        )
        # The lockout itself is untouched.
        assert SecurityMonitor.is_account_locked("locked")[0]
        assert cache.get(LOCKOUT_STATUS_KEY.format(username="locked"))


# ---------------------------------------------------------------------------
# AC2: click attribution
# ---------------------------------------------------------------------------


def _notification(sent_at=None, user=None):
    return EmailNotification.objects.create(
        email_type=EmailType.FORUM_REPLY,
        recipient_email="reader@example.com",
        user=user,
        subject="s",
        template_name="forum_reply",
        status=EmailNotification.STATUS_SENT,
        sent_at=sent_at or timezone.now(),
    )


@pytest.mark.django_db
@pytest.mark.usefixtures("click_tracking")
class TestClickLinks:
    def test_a_site_link_is_wrapped_in_a_signed_redirect(self):
        url = email_feedback.click_url("u-1", "post_url", f"{SITE}/forum/t#post-1")
        assert url.startswith(f"{API}/api/v1/email/click/")
        token = url.removeprefix(f"{API}/api/v1/email/click/").rstrip("/")
        assert email_feedback.read_click_token(token) == {
            "n": "u-1",
            "l": "post_url",
            "u": f"{SITE}/forum/t#post-1",
        }

    def test_an_external_link_is_never_wrapped(self):
        assert email_feedback.click_url("u", "post_url", "https://evil.example/x") == (
            "https://evil.example/x"
        )

    @override_settings(API_PUBLIC_URL="")
    def test_no_api_origin_means_no_tracking(self):
        assert email_feedback.click_url("u", "post_url", f"{SITE}/x") == f"{SITE}/x"

    @override_settings(EMAIL_CLICK_TRACKING_ENABLED=False)
    def test_the_kill_switch_turns_tracking_off(self):
        assert email_feedback.click_url("u", "post_url", f"{SITE}/x") == f"{SITE}/x"

    def test_a_forged_or_off_site_token_is_refused(self):
        from django.core import signing

        assert email_feedback.read_click_token("forged") is None
        off_site = signing.dumps(
            {"n": "u", "l": "post_url", "u": "https://evil.example/"},
            salt=email_feedback.CLICK_SALT,
        )
        assert email_feedback.read_click_token(off_site) is None

    def test_the_reply_email_tracks_content_links_only(self):
        """The real reply email: its content links are redirects, its
        unsubscribe link, header and settings link are not."""
        from apps.forum_host.tests.test_reply_email_links import _reply, _send

        owner, _board, _topic, post = _reply("ck")
        message, html = _send(owner, post)
        row = EmailNotification.objects.get(user=owner)
        tracked = f"{API}/api/v1/email/click/"
        assert html.count(tracked) == 2  # "Read the reply" + "View topic"
        assert f"Read the reply: {tracked}" in message.body
        unsubscribe = message.extra_headers["List-Unsubscribe"]
        assert tracked not in unsubscribe
        assert f'href="{SITE}/settings"' in html
        assert row.message_id == message.extra_headers["Message-ID"]


@pytest.mark.django_db
@pytest.mark.usefixtures("click_tracking")
class TestClickRedirect:
    def _click(self, row, link="post_url", *, method="get"):
        url = email_feedback.click_url(row.uuid, link, f"{SITE}/forum/t")
        return getattr(APIClient(), method)(url.removeprefix(API))

    def test_a_click_redirects_and_counts_once(self):
        row = _notification()
        first = self._click(row)
        second = self._click(row)
        assert (first.status_code, first["Location"]) == (302, f"{SITE}/forum/t")
        assert second.status_code == 302
        assert EmailClick.objects.filter(notification=row).count() == 1

    def test_each_link_counts_once(self):
        row = _notification()
        self._click(row, "post_url")
        self._click(row, "topic_url")
        self._click(row, "topic_url")
        assert sorted(row.clicks.values_list("link", flat=True)) == [
            "post_url",
            "topic_url",
        ]

    def test_a_click_inside_the_window_counts(self):
        row = _notification(
            sent_at=timezone.now()
            - timedelta(days=EMAIL_CLICK_ATTRIBUTION_DAYS, hours=-1)
        )
        self._click(row)
        assert row.clicks.count() == 1

    def test_a_click_after_the_window_redirects_but_is_not_counted(self):
        row = _notification(
            sent_at=timezone.now()
            - timedelta(days=EMAIL_CLICK_ATTRIBUTION_DAYS, hours=1)
        )
        response = self._click(row)
        assert response.status_code == 302
        assert response["Location"] == f"{SITE}/forum/t"
        assert not row.clicks.exists()

    def test_a_head_request_is_not_a_click(self):
        row = _notification()
        assert self._click(row, method="head").status_code == 302
        assert not row.clicks.exists()

    def test_a_forged_token_goes_home_and_counts_nothing(self):
        response = APIClient().get(reverse("v1:email-click", args=["forged"]))
        assert (response.status_code, response["Location"]) == (302, f"{SITE}/")
        assert not EmailClick.objects.exists()

    def test_a_click_for_an_unknown_email_still_redirects(self):
        url = email_feedback.click_url(
            "00000000-0000-4000-8000-000000000000", "post_url", f"{SITE}/x"
        )
        response = APIClient().get(url.removeprefix(API))
        assert (response.status_code, response["Location"]) == (302, f"{SITE}/x")
        assert not EmailClick.objects.exists()

    def test_the_click_carries_the_user_and_no_request_details(self):
        user = User.objects.create_user(username="clicker", email="c@example.com")
        row = _notification(user=user)
        self._click(row)
        click = EmailClick.objects.get()
        assert click.user == user
        assert {f.name for f in EmailClick._meta.get_fields()} == {
            "id",
            "notification",
            "user",
            "link",
            "clicked_at",
        }


@pytest.mark.django_db
class TestRetentionAndDeletion:
    def test_prune_removes_only_rows_past_the_retention(self):
        now = timezone.now()
        row = _notification()
        old = EmailClick.objects.create(
            notification=row,
            link="post_url",
            clicked_at=now - timedelta(days=EMAIL_FEEDBACK_RETENTION_DAYS + 1),
        )
        recent = EmailClick.objects.create(
            notification=row, link="topic_url", clicked_at=now - timedelta(days=30)
        )
        old_event = EmailProviderEvent.objects.create(
            svix_id="old", event_type=EVENT_DELIVERED, occurred_at=now
        )
        EmailProviderEvent.objects.filter(pk=old_event.pk).update(
            received_at=now - timedelta(days=EMAIL_FEEDBACK_RETENTION_DAYS + 1)
        )
        EmailProviderEvent.objects.create(
            svix_id="new", event_type=EVENT_DELIVERED, occurred_at=now
        )

        assert email_feedback.prune() == {"clicks": 1, "events": 1}
        assert list(EmailClick.objects.all()) == [recent]
        assert not EmailClick.objects.filter(pk=old.pk).exists()
        assert list(EmailProviderEvent.objects.values_list("svix_id", flat=True)) == [
            "new"
        ]

    def test_the_prune_runs_on_a_schedule(self):
        from django.conf import settings

        entry = settings.CELERY_BEAT_SCHEDULE["email-feedback-prune"]
        assert entry["task"] == "apps.core.tasks.prune_email_feedback"

    def test_clicks_are_deleted_with_the_account(self):
        user = User.objects.create_user(username="leaver", email="l@example.com")
        row = _notification(user=user)
        EmailClick.objects.create(notification=row, user=user, link="post_url")
        user.delete()
        assert not EmailClick.objects.exists()


# ---------------------------------------------------------------------------
# AC2: opens are not collected
# ---------------------------------------------------------------------------


def test_opens_are_not_collected():
    """Owner decision 2026-10-12: no open tracking. The unused track_opens
    parameter and the open fields, state and method are gone."""
    assert "track_opens" not in inspect.signature(EmailService.send_email).parameters
    fields = {f.name for f in EmailNotification._meta.get_fields()}
    assert not fields & {"opened_at", "open_count", "clicked_at", "click_count"}
    assert "opened" not in dict(EmailNotification.STATUS_CHOICES)
    assert not hasattr(EmailNotification, "mark_opened")
    assert not hasattr(EmailNotification, "mark_clicked")


# ---------------------------------------------------------------------------
# Review round 1 (PR #1133)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.usefixtures("webhook_on", "no_click_tracking")
class TestReviewRoundOne:
    def _send(self):
        assert EmailService().send_email(
            email_type=EmailType.COMMUNITY_UPDATE,
            recipient="reader@example.com",
            subject="Hello",
            template_name="generic_notification",
            context={"notification_title": "Hello", "notification_message": "Hi"},
        )
        return (
            EmailNotification.objects.get(),
            mail.outbox[-1].extra_headers["Message-ID"],
        )

    @pytest.mark.parametrize(
        "spell",
        [
            lambda mid: mid.strip("<>"),
            lambda mid: f"  {mid.upper()} ",
            lambda mid: mid.strip("<>").upper(),
        ],
        ids=["bracketless", "upper-spaced", "bare-upper"],
    )
    def test_a_message_id_is_matched_in_any_spelling(self, spell):
        row, message_id = self._send()
        _post(_event(EVENT_DELIVERED, message_id=spell(message_id), email_id="re-9"))
        row.refresh_from_db()
        assert (row.status, row.provider_email_id) == ("delivered", "re-9")

    def test_the_stored_message_id_is_lowercased(self, settings):
        settings.DEFAULT_FROM_EMAIL = "Houseplant MD <News@Example.COM>"
        row, message_id = self._send()
        assert message_id == row.message_id
        assert message_id.endswith("@example.com>")

    def test_every_spelling_of_a_suppressed_address_is_blocked(self, backstop):
        _suppress("Bob@Example.com", Reason.HARD_BOUNCE)
        message = EmailMessage(
            "s",
            "b",
            "from@example.com",
            ["bob@example.com", "Bob <BOB@example.com>", "fine@example.com"],
        )
        assert message.send() == 1
        [sent] = mail.outbox
        assert sent.to == ["fine@example.com"]
        assert email_feedback.is_suppressed("Bob <BOB@EXAMPLE.COM>", optional=False)

    def test_the_removed_count_ignores_blank_entries(self, backstop):
        _suppress("gone@example.com", Reason.HARD_BOUNCE)
        gone = EmailMessage("s", "b", "f@example.com", ["gone@example.com"])
        clean = EmailMessage("s", "b", "f@example.com", ["", "fine@example.com"])
        with patch.object(email_feedback.logger, "info") as info:
            assert email_feedback.filter_suppressed_messages([gone, clean]) == [clean]
        # One line, for the one address removed: never "-1" for the blank.
        assert [c.args[0] for c in info.call_args_list] == [
            "[EMAIL] 1 suppressed recipient(s) removed from a message"
        ]

    def test_a_transactional_send_the_backstop_drops_is_not_a_send(self, backstop):
        # Suppressed after the service's own check: the backend drops it.
        _suppress("late@example.com", Reason.HARD_BOUNCE)
        service = EmailService()
        with patch.object(email_feedback, "is_suppressed", return_value=False):
            sent = service.send_transactional_email(
                recipient="late@example.com", subject="s", message="m"
            )
        assert sent is False
        assert (service.last_outcome, service.last_suppression_reason) == (
            EmailOutcome.SUPPRESSED,
            "address_suppressed",
        )
        assert mail.outbox == []


@pytest.mark.django_db
@pytest.mark.usefixtures("click_tracking")
def test_a_database_error_while_counting_a_click_still_redirects():
    from django.db import OperationalError

    row = _notification()
    url = email_feedback.click_url(row.uuid, "post_url", f"{SITE}/forum/t")
    with patch.object(
        EmailClick.objects, "create", side_effect=OperationalError("db down")
    ):
        response = APIClient().get(url.removeprefix(API))
    assert (response.status_code, response["Location"]) == (302, f"{SITE}/forum/t")
    assert not EmailClick.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("webhook_on")
class TestWebhookBodyLimit:
    def _raw(self, body, **extra):
        return APIClient().generic(
            "POST", WEBHOOK, body, content_type="application/json", **extra
        )

    def test_an_oversized_content_length_is_refused(self):
        from apps.core.constants import EMAIL_WEBHOOK_MAX_BODY_BYTES
        from django.http import HttpRequest

        body = b"x" * (EMAIL_WEBHOOK_MAX_BODY_BYTES + 1)
        with patch.object(HttpRequest, "read", wraps=None) as read:
            response = self._raw(body)
        assert response.status_code == 413
        # Refused on the header alone: the body is never read.
        read.assert_not_called()
        assert not EmailProviderEvent.objects.exists()

    def test_a_non_numeric_content_length_is_refused(self):
        response = self._raw(b"{}", CONTENT_LENGTH="12abc")
        assert response.status_code == 413
        assert not EmailProviderEvent.objects.exists()

    def test_a_body_with_no_length_is_read_only_up_to_the_cap(self):
        """No Content-Length (chunked, under ASGI): the read stops one byte
        past the cap, and that is refused before any parsing."""
        from apps.core.constants import EMAIL_WEBHOOK_MAX_BODY_BYTES
        from django.http import HttpRequest

        oversized = b"x" * (EMAIL_WEBHOOK_MAX_BODY_BYTES + 1)
        with patch.object(HttpRequest, "read", return_value=oversized) as read:
            response = self._raw(b"", CONTENT_LENGTH="")
        assert response.status_code == 413
        read.assert_called_once_with(EMAIL_WEBHOOK_MAX_BODY_BYTES + 1)
        assert not EmailProviderEvent.objects.exists()

    def test_a_refused_signature_is_logged_below_warning(self):
        from apps.core.api import email_feedback as api

        with (
            patch.object(api.logger, "warning") as warning,
            patch.object(api.logger, "info") as info,
        ):
            response = _post(
                _event(EVENT_DELIVERED),
                secret="whsec_"  # pragma: allowlist secret
                + base64.b64encode(b"y" * 24).decode(),
            )
        assert response.status_code == 401
        # Any anonymous caller reaches this line: INFO, never WARNING.
        warning.assert_not_called()
        assert any("webhook refused" in c.args[0] for c in info.call_args_list)


@pytest.mark.django_db
def test_the_forum_outbox_records_a_provider_suppression_as_such(settings):
    from apps.core import delivery
    from apps.forum_host.tasks import send_forum_email_batch
    from apps.forum_host.tests.test_reply_email_links import _reply

    settings.SITE_URL = SITE
    settings.API_PUBLIC_URL = ""
    owner, _board, _topic, post = _reply("supx")
    _suppress(owner.email, Reason.HARD_BOUNCE)
    batch = delivery.record_batch(
        DeliveryIntent.Kind.FORUM_EMAIL,
        "reply_added",
        [owner.pk],
        {"post_id": str(post.pk)},
        subject_key=post.pk,
    )

    send_forum_email_batch(
        "reply_added", [owner.pk], {"post_id": str(post.pk)}, batch_id=batch
    )

    assert mail.outbox == []
    row = DeliveryIntent.objects.get(recipient=owner)
    assert (row.status, row.last_error) == (
        DeliveryIntent.Status.SUPPRESSED,
        "address_suppressed",
    )


@pytest.mark.django_db
def test_the_open_and_click_columns_stay_for_a_previous_release_worker():
    """Migration 0009 drops the fields from the model, not the columns: a
    previous-release worker that still inserts them succeeds, and this
    release's inserts, which omit them, get the database default."""
    from django.db import connection

    row = _notification()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT open_count, click_count, opened_at, clicked_at "
            "FROM core_emailnotification WHERE id = %s",
            [row.pk],
        )
        assert cursor.fetchone() == (0, 0, None, None)
        cursor.execute(
            "UPDATE core_emailnotification SET open_count = 2, click_count = 1 "
            "WHERE id = %s",
            [row.pk],
        )


@pytest.mark.django_db
def test_rows_left_opened_or_clicked_go_back_to_sent():
    import importlib

    from django.apps import apps as registry

    migration = importlib.import_module(
        "apps.core.migrations.0009_email_feedback_and_clicks"
    )
    opened, clicked, delivered = (_notification() for _ in range(3))
    EmailNotification.objects.filter(pk=opened.pk).update(status="opened")
    EmailNotification.objects.filter(pk=clicked.pk).update(status="clicked")
    EmailNotification.objects.filter(pk=delivered.pk).update(status="delivered")

    migration._untrack_opened_and_clicked(registry, None)

    assert dict(EmailNotification.objects.values_list("pk", "status")) == {
        opened.pk: "sent",
        clicked.pk: "sent",
        delivered.pk: "delivered",
    }
