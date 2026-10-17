"""The account-wide master switches and the policy in
docs/notifications-policy.md (todo 620).

Web Settings and the mobile profile now edit the same fields through the same
two endpoints: ``/auth/user/update/`` (master switches) and
``/forum/me/profile/`` (digest + per-event matrix). The cross-client sequences
below drive those endpoints in turn, the way each client does, and assert the
other client's next read sees the write. The clients' own tests cover failed
saves and reload.
"""

from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from apps.core.services.email_service import EmailService, EmailType
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from wagtail_forum.models import DigestFrequency, ForumProfile

User = get_user_model()

USER_URL = "/api/v1/auth/user/"
USER_UPDATE_URL = "/api/v1/auth/user/update/"
FORUM_PROFILE_URL = "/api/v1/forum/me/profile/"


@pytest.fixture(autouse=True)
def _private_cache():
    """The digest run lock and the rate limiters live in the default cache;
    keep them off the shared Redis (todo 630)."""
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": f"notification-policy-tests-{uuid4().hex}",
            }
        }
    ):
        yield


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- cross-client sequences (AC2) -------------------------------------------


@pytest.mark.django_db
def test_master_switch_mobile_off_then_web_on_round_trips():
    user = User.objects.create_user(username="seq-a", email="a@x.test")
    mobile, web = _client(user), _client(user)

    off = mobile.patch(USER_UPDATE_URL, {"forum_notifications": False}, format="json")
    assert off.status_code == 200, off.content
    assert web.get(USER_URL).data["forum_notifications"] is False

    on = web.patch(USER_UPDATE_URL, {"forum_notifications": True}, format="json")
    assert on.status_code == 200, on.content
    assert mobile.get(USER_URL).data["forum_notifications"] is True


@pytest.mark.django_db
def test_master_switch_web_off_then_mobile_on_round_trips():
    user = User.objects.create_user(username="seq-b", email="b@x.test")
    mobile, web = _client(user), _client(user)

    web.patch(USER_UPDATE_URL, {"email_notifications": False}, format="json")
    assert mobile.get(USER_URL).data["email_notifications"] is False

    mobile.patch(USER_UPDATE_URL, {"email_notifications": True}, format="json")
    assert web.get(USER_URL).data["email_notifications"] is True


@pytest.mark.django_db
def test_matrix_cell_and_digest_mobile_off_web_on_and_back():
    user = User.objects.create_user(username="seq-c", email="c@x.test")
    mobile, web = _client(user), _client(user)

    # Mobile turns reply email off and the digest on.
    r = mobile.patch(
        FORUM_PROFILE_URL,
        {
            "notification_preferences": {"reply": {"email": False}},
            "digest_frequency": "weekly",
        },
        format="json",
    )
    assert r.status_code == 200, r.content
    seen = web.get(FORUM_PROFILE_URL).data
    assert seen["notification_preferences"]["reply"]["email"] is False
    assert seen["notification_preferences"]["reply"]["push"] is True  # untouched
    assert seen["digest_frequency"] == "weekly"

    # Web turns them back.
    web.patch(
        FORUM_PROFILE_URL,
        {
            "notification_preferences": {"reply": {"email": True}},
            "digest_frequency": "off",
        },
        format="json",
    )
    seen = mobile.get(FORUM_PROFILE_URL).data
    assert seen["notification_preferences"]["reply"]["email"] is True
    assert seen["digest_frequency"] == "off"


@pytest.mark.django_db
def test_a_master_switch_write_never_rewrites_the_per_event_choices():
    """No silent resubscribe or loss: the master switch sits above the
    matrix and digest, and toggling it leaves both exactly as stored."""
    user = User.objects.create_user(username="seq-d", email="d@x.test")
    profile = ForumProfile.for_user(user)
    profile.notification_preferences = {"mention": {"push": False}}
    profile.digest_frequency = DigestFrequency.WEEKLY
    profile.save(update_fields=["notification_preferences", "digest_frequency"])
    client = _client(user)

    client.patch(
        USER_UPDATE_URL,
        {"email_notifications": False, "forum_notifications": False},
        format="json",
    )
    client.patch(
        USER_UPDATE_URL,
        {"email_notifications": True, "forum_notifications": True},
        format="json",
    )

    profile.refresh_from_db()
    assert profile.notification_preferences == {"mention": {"push": False}}
    assert profile.digest_frequency == DigestFrequency.WEEKLY


# --- broad opt-outs follow the policy (AC3) ---------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email_type",
    [EmailType.FORUM_REPLY, EmailType.FORUM_MENTION, EmailType.FORUM_DIGEST],
)
def test_email_master_off_stops_every_optional_forum_email(email_type):
    user = User.objects.create_user(username=f"em-{email_type}", email="e@x.test")
    user.email_notifications = False
    assert EmailService()._should_send_email(user, email_type) is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "email_type",
    [
        EmailType.ACCOUNT_VERIFICATION,
        EmailType.PASSWORD_RESET,
        EmailType.SECURITY_ALERT,
    ],
)
def test_security_mail_is_exempt_from_both_master_switches(email_type):
    user = User.objects.create_user(username=f"sec-{email_type}", email="s@x.test")
    user.email_notifications = False
    user.forum_notifications = False
    assert EmailService()._should_send_email(user, email_type) is True


@pytest.mark.django_db
def test_forum_master_off_stops_forum_email_but_not_other_optional_email():
    user = User.objects.create_user(username="fm", email="f@x.test")
    user.forum_notifications = False
    service = EmailService()
    assert service._should_send_email(user, EmailType.FORUM_REPLY) is False
    assert service._should_send_email(user, EmailType.COMMUNITY_UPDATE) is True


def _one_topic_digest(monkeypatch, sent):
    from wagtail_forum.digest import Digest, DigestTopic
    from wagtail_forum.management.commands import send_forum_digest

    topic = DigestTopic(
        id=1,
        title="Fresh",
        url="https://forum.example/t/1",
        board_title="General",
        reply_count=1,
        last_post_at=timezone.now(),
    )

    def build(user, since, profile=None):
        return Digest(user=user, since=since, watched=[topic])

    def send(digest):
        sent.append(digest.user.username)
        return True

    monkeypatch.setattr(send_forum_digest, "build_digest", build)
    monkeypatch.setattr(send_forum_digest, "send_digest", send)


def _weekly(username, **flags):
    user = User.objects.create_user(
        username=username, email=f"{username}@x.test", **flags
    )
    profile = ForumProfile.for_user(user)
    profile.digest_frequency = DigestFrequency.WEEKLY
    profile.save(update_fields=["digest_frequency"])
    return user


@pytest.mark.django_db
@override_settings(SITE_URL="https://forum.example")
def test_the_digest_honours_both_master_switches(monkeypatch):
    """The digest is sent by the package, not EmailService; the host's
    DIGEST_RECIPIENT_FILTER (settings.py) carries the master switches to it."""
    _weekly("dg-both-on")
    _weekly("dg-email-off", email_notifications=False)
    _weekly("dg-forum-off", forum_notifications=False)
    sent: list[str] = []
    _one_topic_digest(monkeypatch, sent)

    out = StringIO()
    call_command("send_forum_digest", frequency="weekly", stdout=out)

    assert sent == ["dg-both-on"]
    assert "recipients=1" in out.getvalue()
    # Opted-out members keep their own digest choice: no data is rewritten.
    assert ForumProfile.objects.get(user__username="dg-email-off").digest_frequency == (
        DigestFrequency.WEEKLY
    )


@pytest.mark.django_db
@override_settings(SITE_URL="https://forum.example")
def test_turning_the_master_switch_back_on_restores_the_digest(monkeypatch):
    user = _weekly("dg-returning", email_notifications=False)
    sent: list[str] = []
    _one_topic_digest(monkeypatch, sent)
    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())
    assert sent == []

    _client(user).patch(USER_UPDATE_URL, {"email_notifications": True}, format="json")
    call_command("send_forum_digest", frequency="weekly", stdout=StringIO())

    assert sent == ["dg-returning"]


@pytest.mark.django_db
def test_the_newsletter_is_independent_of_the_master_email_switch():
    """BlogNewsletter is its own double-opt-in consent keyed by address; the
    account master switch neither subscribes nor unsubscribes it."""
    from apps.blog import newsletter_digest
    from apps.blog.models import BlogNewsletter

    user = User.objects.create_user(
        username="nl", email="nl@x.test", email_notifications=False
    )
    subscriber = BlogNewsletter.objects.create(
        email=user.email, is_active=True, confirmed_at=timezone.now()
    )

    assert list(newsletter_digest.recipients()) == [subscriber]

    # Flipping the master switch through the endpoint both clients use
    # neither unsubscribes a subscriber nor subscribes anyone (todo 651:
    # the old second half never touched the switch at all).
    other = User.objects.create_user(username="nl-none", email="none@x.test")
    for target, value in [(user, True), (user, False), (other, False), (other, True)]:
        response = _client(target).patch(
            USER_UPDATE_URL, {"email_notifications": value}, format="json"
        )
        assert response.status_code == 200, response.content
        target.refresh_from_db()
        assert target.email_notifications is value
        assert list(newsletter_digest.recipients()) == [subscriber]
    assert BlogNewsletter.objects.filter(email="none@x.test").exists() is False
    subscriber.refresh_from_db()
    assert subscriber.is_active is True


@pytest.mark.django_db
def test_reply_email_is_held_by_the_email_master_even_with_the_cell_on():
    from apps.forum_host.tasks import send_forum_email_batch
    from apps.forum_host.tests.test_tasks import _make_reply

    topic_author, _, _, post = _make_reply("policy-email-off")
    topic_author.email_notifications = False
    topic_author.save(update_fields=["email_notifications"])

    with patch("apps.forum_host.tasks.wants_channel", return_value=True):
        send_forum_email_batch(
            "reply_added", [topic_author.pk], {"post_id": str(post.pk)}
        )

    assert mail.outbox == []
