"""Browser (Web Push) delivery of forum events (todo 413)."""

from unittest.mock import patch

import pytest
from apps.users.models import PushSubscription
from apps.users.web_push import clean_subscription, is_allowed_push_endpoint
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile

User = get_user_model()

FCM_ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
KEYS = {"p256dh": "BPk-key", "auth": "auth-secret"}  # pragma: allowlist secret
SUBSCRIBE_URL = "/api/v1/auth/me/push-notifications/subscribe/"
PUBLIC_KEY_URL = "/api/v1/auth/me/push-notifications/public-key/"
# Web push is on only with both keys and a claims email (PR #852 review).
PUSH_ON = {
    "VAPID_PUBLIC_KEY": "BPub",
    "VAPID_PRIVATE_KEY": "priv",  # pragma: allowlist secret
    "VAPID_CLAIMS_EMAIL": "ops@example.com",
}


@pytest.mark.parametrize(
    "endpoint",
    [
        FCM_ENDPOINT,
        "https://updates.push.services.mozilla.com/wpush/v2/gAAA",
        "https://web.push.apple.com/QGuQyavXutnMH",
        "https://wns2-par02p.notify.windows.com/w/?token=x",
    ],
)
def test_browser_push_services_are_allowed(endpoint):
    assert is_allowed_push_endpoint(endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/x",  # not https
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata
        "https://localhost/internal",
        "https://evilfcm.googleapis.com/x",  # suffix without a dot boundary
        "https://fcm.googleapis.com.attacker.example/x",
        "https://user:pw@fcm.googleapis.com/x",  # credentials  # pragma: allowlist secret
        "https://fcm.googleapis.com:8443/x",  # odd port
        "https://fcm.googleapis.com/" + "a" * 600,  # over the column length
        "",
        None,
        42,
    ],
)
def test_anything_else_is_refused_as_ssrf(endpoint):
    assert not is_allowed_push_endpoint(endpoint)


def test_a_subscription_needs_both_keys():
    assert clean_subscription({"endpoint": FCM_ENDPOINT, "keys": KEYS})
    assert (
        clean_subscription({"endpoint": FCM_ENDPOINT, "keys": {"p256dh": "x"}}) is None
    )
    assert clean_subscription({"endpoint": FCM_ENDPOINT}) is None
    assert clean_subscription("not a dict") is None


@pytest.mark.django_db
def test_subscribe_refuses_an_unsafe_endpoint_and_stores_a_good_one():
    user = User.objects.create_user(username="sub")
    client = APIClient()
    client.force_authenticate(user=user)

    bad = client.post(
        SUBSCRIBE_URL,
        {"subscription": {"endpoint": "https://169.254.169.254/x", "keys": KEYS}},
        format="json",
    )
    assert bad.status_code == 400
    assert not PushSubscription.objects.exists()

    good = client.post(
        SUBSCRIBE_URL,
        {"subscription": {"endpoint": FCM_ENDPOINT, "keys": KEYS}},
        format="json",
    )
    assert good.status_code == 201
    assert PushSubscription.objects.get(user=user).endpoint == FCM_ENDPOINT


@pytest.mark.django_db
def test_the_public_key_endpoint_reports_whether_push_is_on():
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(username="pk"))

    with override_settings(VAPID_PUBLIC_KEY="", VAPID_PRIVATE_KEY=""):
        assert client.get(PUBLIC_KEY_URL).data == {"enabled": False, "public_key": ""}
    # Half a key pair is off too: a subscription the server can never use.
    with override_settings(VAPID_PUBLIC_KEY="BPub", VAPID_PRIVATE_KEY=""):
        assert client.get(PUBLIC_KEY_URL).data["enabled"] is False
    with override_settings(**{**PUSH_ON, "VAPID_CLAIMS_EMAIL": ""}):
        assert client.get(PUBLIC_KEY_URL).data["enabled"] is False
    with override_settings(**PUSH_ON):
        assert client.get(PUBLIC_KEY_URL).data == {
            "enabled": True,
            "public_key": "BPub",
        }


def _subscribed(username, preferences=None, *, forum_notifications=True):
    user = User.objects.create_user(username=username)
    if not forum_notifications:
        user.forum_notifications = False
        user.save(update_fields=["forum_notifications"])
    profile = ForumProfile.for_user(user)
    profile.notification_preferences = preferences or {}
    profile.save(update_fields=["notification_preferences"])
    PushSubscription.objects.create(
        user=user,
        endpoint=f"{FCM_ENDPOINT}-{username}",
        p256dh_key=KEYS["p256dh"],
        auth_key=KEYS["auth"],
    )
    return user


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_reply_goes_to_every_subscribed_browser_that_wants_it():
    from apps.forum_host.tasks import send_forum_web_push_batch

    wants = _subscribed("wants")
    opted_out = _subscribed("opted-out", {"reply": {"push": False}})
    switched_off = _subscribed("off", forum_notifications=False)

    with patch(
        "apps.users.services.NotificationService.send_web_push_notification",
        return_value=True,
    ) as send:
        send_forum_web_push_batch(
            "reply_added",
            [wants.pk, opted_out.pk, switched_off.pk],
            {
                "topic_id": "999",
                "post_id": "7",
                "topic_title": "Ferns",
                "actor_name": "Ada",
            },
        )

    assert [c.args[0].user_id for c in send.call_args_list] == [wants.pk]
    kwargs = send.call_args.kwargs
    assert kwargs["title"] and kwargs["body"]
    # No such topic here: the link falls back to the forum, never a 404 path.
    assert kwargs["data"] == {"url": "/forum", "event": "reply_added"}
    assert kwargs["tag"] == "forum-reply_added-7"


@pytest.mark.django_db
def test_nothing_is_sent_without_a_vapid_key_or_for_a_data_only_event():
    from apps.forum_host.tasks import send_forum_web_push_batch

    user = _subscribed("quiet")
    with patch(
        "apps.users.services.NotificationService.send_web_push_notification"
    ) as send:
        with override_settings(VAPID_PRIVATE_KEY=""):
            send_forum_web_push_batch("reply_added", [user.pk], {"topic_id": "1"})
        with override_settings(**PUSH_ON):
            # moderation_decided has no tray copy: nothing for a browser to show.
            send_forum_web_push_batch(
                "moderation_decided", [user.pk], {"topic_id": "1"}
            )

    send.assert_not_called()


@pytest.mark.django_db
def test_the_link_is_the_topic_at_the_post():
    from apps.forum_host.tasks import _web_topic_path

    from .test_tasks import _make_reply

    _author, _board, topic, reply = _make_reply("webpush")
    assert _web_topic_path(str(topic.pk), str(reply.pk)) == (
        f"/forum/{topic.board.id}-{topic.board.slug}/{topic.id}-{topic.slug}"
        f"#post-{reply.pk}"
    )


@pytest.mark.django_db
def test_a_reply_enqueues_the_web_push_beside_fcm(django_capture_on_commit_callbacks):
    from apps.forum_host.notifications import dispatch
    from wagtail.models import Page
    from wagtail_forum.models import (
        ForumBoard,
        ForumIndex,
        Post,
        Topic,
        TopicSubscription,
    )

    topic_author = User.objects.create_user(username="wp-owner")
    replier = User.objects.create_user(username="wp-replier")
    root = Page.objects.get(id=1)
    index = root.add_child(instance=ForumIndex(title="ForumWP", slug="forum-wp"))
    board = index.add_child(instance=ForumBoard(title="WP", slug="wp"))
    topic = Topic.objects.create(board=board, title="T", slug="t", author=topic_author)
    TopicSubscription.subscribe(topic_author, topic)

    with (
        patch("apps.forum_host.tasks.send_forum_push_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_email_batch.delay"),
        patch("apps.forum_host.tasks.send_forum_web_push_batch.delay") as web,
    ):
        post = Post.objects.create(topic=topic, author=replier)
        with django_capture_on_commit_callbacks(execute=True):
            dispatch("reply_added", topic=topic, post=post)

    web.assert_called_once()
    assert web.call_args.args[:2] == ("reply_added", [topic_author.pk])


# --- PR #852 round-1 repairs -------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com:abc/x",
        "https://fcm.googleapis.com:99999999999/x",
        "https://fcm.googleapis.com:-1/x",
    ],
)
@pytest.mark.django_db
def test_a_malformed_port_is_a_400_not_a_500(endpoint):
    client = APIClient()
    client.force_authenticate(user=User.objects.create_user(username="port"))

    response = client.post(
        SUBSCRIBE_URL,
        {"subscription": {"endpoint": endpoint, "keys": KEYS}},
        format="json",
    )

    assert response.status_code == 400
    assert not PushSubscription.objects.exists()


@pytest.mark.django_db
def test_subscribing_a_shared_browser_releases_the_previous_account():
    """User A subscribed this browser, then user B signs in on it and
    subscribes: A must stop receiving pushes on B's screen."""
    first = User.objects.create_user(username="first")
    second = User.objects.create_user(username="second")
    client = APIClient()
    body = {"subscription": {"endpoint": FCM_ENDPOINT, "keys": KEYS}}

    client.force_authenticate(user=first)
    assert client.post(SUBSCRIBE_URL, body, format="json").status_code == 201
    client.force_authenticate(user=second)
    assert client.post(SUBSCRIBE_URL, body, format="json").status_code == 201

    active = PushSubscription.objects.filter(endpoint=FCM_ENDPOINT, is_active=True)
    assert list(active.values_list("user_id", flat=True)) == [second.pk]


def _webpush_error(status_code):
    import requests
    from pywebpush import WebPushException

    response = requests.Response()
    response.status_code = status_code
    return WebPushException("push service said no", response=response)


@pytest.mark.parametrize(
    "status_code,deactivated",
    [(410, True), (404, True), (413, False), (429, False), (500, False)],
)
@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_only_a_gone_subscription_is_deactivated(status_code, deactivated):
    """A REAL requests.Response: it is falsy for any error status, which is
    what hid the old `if e.response and ...` check."""
    from apps.users.services import NotificationService

    user = _subscribed(f"gone{status_code}")
    subscription = PushSubscription.objects.get(user=user)

    with patch("apps.users.services.webpush", side_effect=_webpush_error(status_code)):
        sent = NotificationService.send_web_push_notification(
            subscription, title="t", body="b"
        )

    assert sent is False
    subscription.refresh_from_db()
    assert subscription.is_active is (not deactivated)


@pytest.mark.django_db
@override_settings(**{**PUSH_ON, "VAPID_CLAIMS_EMAIL": "mailto:ops@example.com"})
def test_a_send_waits_for_offline_browsers_and_is_bounded():
    from apps.users.constants import WEB_PUSH_TIMEOUT_SECONDS, WEB_PUSH_TTL_SECONDS
    from apps.users.services import NotificationService

    subscription = PushSubscription.objects.get(user=_subscribed("ttl"))

    with patch("apps.users.services.webpush") as webpush:
        assert NotificationService.send_web_push_notification(
            subscription, title="t", body="b"
        )

    kwargs = webpush.call_args.kwargs
    assert kwargs["ttl"] == WEB_PUSH_TTL_SECONDS > 0
    assert kwargs["timeout"] == WEB_PUSH_TIMEOUT_SECONDS
    # A configured "mailto:" prefix is not doubled.
    assert kwargs["vapid_claims"] == {"sub": "mailto:ops@example.com"}


@pytest.mark.django_db
def test_nothing_is_sent_without_the_public_key_or_a_claims_email():
    from apps.forum_host.tasks import send_forum_web_push_batch

    user = _subscribed("half")
    with patch(
        "apps.users.services.NotificationService.send_web_push_notification"
    ) as send:
        for missing in ("VAPID_PUBLIC_KEY", "VAPID_CLAIMS_EMAIL"):
            with override_settings(**{**PUSH_ON, missing: ""}):
                send_forum_web_push_batch("reply_added", [user.pk], {"topic_id": "1"})

    send.assert_not_called()


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_recipient_with_no_forum_profile_still_gets_the_push():
    """A mentioned member who never posted has no ForumProfile row; default
    preferences want the push."""
    from apps.forum_host.tasks import send_forum_web_push_batch

    lurker = User.objects.create_user(username="lurker")
    PushSubscription.objects.create(
        user=lurker,
        endpoint=f"{FCM_ENDPOINT}-lurker",
        p256dh_key=KEYS["p256dh"],
        auth_key=KEYS["auth"],
    )
    assert not ForumProfile.objects.filter(user=lurker).exists()

    with patch(
        "apps.users.services.NotificationService.send_web_push_notification",
        return_value=True,
    ) as send:
        send_forum_web_push_batch(
            "mention", [lurker.pk], {"topic_id": "1", "actor_name": "Ada"}
        )

    assert [c.args[0].user_id for c in send.call_args_list] == [lurker.pk]
