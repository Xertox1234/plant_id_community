"""Browser (Web Push) delivery of forum events (todo 413)."""

from unittest.mock import patch

import pytest
from apps.users.models import PushSubscription
from apps.users.web_push import clean_subscription, is_allowed_push_endpoint
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from wagtail_forum.models import ForumProfile
from wagtail_forum.tests.factories import make_forum

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
    from wagtail_forum.models import Post, Topic, TopicSubscription

    topic_author = User.objects.create_user(username="wp-owner")
    replier = User.objects.create_user(username="wp-replier")
    board = make_forum(name="WP", slug="wp")
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


# --- Todo 456: shared session, no redirects, bulk last_used ------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_batch_shares_one_session_and_records_last_used_once():
    from apps.forum_host.tasks import send_forum_web_push_batch
    from apps.users.services import NoRedirectSession
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    users = [_subscribed(f"batch{i}") for i in range(3)]
    failing = PushSubscription.objects.get(user=users[1])

    def fake_send(subscription, **kwargs):
        return subscription.pk != failing.pk

    with (
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            side_effect=fake_send,
        ) as send,
        CaptureQueriesContext(connection) as queries,
    ):
        send_forum_web_push_batch(
            "reply_added",
            [u.pk for u in users],
            {"topic_id": "1", "post_id": "2", "actor_name": "Ada"},
        )

    sessions = {id(c.kwargs["requests_session"]) for c in send.call_args_list}
    assert len(send.call_args_list) == 3 and len(sessions) == 1
    assert isinstance(send.call_args.kwargs["requests_session"], NoRedirectSession)
    assert all(c.kwargs["mark_used"] is False for c in send.call_args_list)
    updates = [
        q["sql"]
        for q in queries.captured_queries
        if q["sql"].startswith('UPDATE "users_pushsubscription"')
    ]
    assert len(updates) == 1
    used = dict(PushSubscription.objects.values_list("user_id", "last_used"))
    assert used[users[0].pk] and used[users[2].pk]
    assert used[users[1].pk] is None  # a failed send is not "used"


def test_the_push_session_never_follows_a_redirect():
    import requests
    from apps.users.services import web_push_session

    with patch.object(requests.Session, "request") as parent:
        web_push_session().post("https://fcm.googleapis.com/fcm/send/x", data=b"")
    assert parent.call_args.kwargs["allow_redirects"] is False


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_single_send_uses_a_no_redirect_session_and_a_redirect_fails_it():
    from apps.users.services import NoRedirectSession, NotificationService

    subscription = PushSubscription.objects.get(user=_subscribed("redirect"))

    with patch("apps.users.services.webpush") as webpush:
        assert NotificationService.send_web_push_notification(
            subscription, title="t", body="b"
        )
    assert isinstance(webpush.call_args.kwargs["requests_session"], NoRedirectSession)

    # pywebpush raises for any status above 202, a 3xx included: the send
    # fails and is logged, and the row stays (a redirect is not "gone").
    with patch("apps.users.services.webpush", side_effect=_webpush_error(301)):
        assert not NotificationService.send_web_push_notification(
            subscription, title="t", body="b"
        )
    subscription.refresh_from_db()
    assert subscription.is_active is True


# --- Todo 456: the service worker's re-subscribe -----------------------------

RESUBSCRIBE_URL = "/api/v1/auth/push-notifications/resubscribe/"
NEW_ENDPOINT = "https://fcm.googleapis.com/fcm/send/new456"
NEW_KEYS = {"p256dh": "BNew-key", "auth": "new-secret"}  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _fresh_rate_limit_window():
    """The resubscribe limit is per IP in the shared cache: give each test its
    own empty in-memory cache, or earlier runs' POSTs 429 this one. Never
    cache.clear(): that flushes the whole configured cache, Redis in dev
    (todo 602 item 9). django-ratelimit looks its cache up per call, and a
    CACHES override resets Django's cache handler."""
    import uuid

    locmem = {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": f"web-push-test-{uuid.uuid4()}",
    }
    with override_settings(CACHES={"default": locmem, "renditions": locmem}):
        yield


def _resubscribe(old_endpoint, old_auth, new_endpoint=NEW_ENDPOINT):
    # A cookie-less client that enforces CSRF, like a service worker's fetch.
    client = APIClient(enforce_csrf_checks=True)
    return client.post(
        RESUBSCRIBE_URL,
        {
            "old_subscription": {"endpoint": old_endpoint, "auth": old_auth},
            "subscription": {"endpoint": new_endpoint, "keys": NEW_KEYS},
        },
        format="json",
    )


@pytest.mark.django_db
def test_the_worker_swaps_in_the_new_subscription_with_the_old_secret():
    user = _subscribed("swap")
    old = PushSubscription.objects.get(user=user)

    response = _resubscribe(old.endpoint, KEYS["auth"])

    assert response.status_code == 200
    old.refresh_from_db()
    assert old.is_active is False
    new = PushSubscription.objects.get(endpoint=NEW_ENDPOINT)
    assert (new.user_id, new.is_active) == (user.pk, True)
    assert (new.p256dh_key, new.auth_key) == (NEW_KEYS["p256dh"], NEW_KEYS["auth"])


@pytest.mark.django_db
def test_a_wrong_secret_or_an_unknown_endpoint_is_one_404():
    user = _subscribed("guard")
    old = PushSubscription.objects.get(user=user)

    wrong = _resubscribe(old.endpoint, "not-the-secret")
    unknown = _resubscribe(f"{FCM_ENDPOINT}-nobody", KEYS["auth"])
    missing = _resubscribe(None, None)

    assert wrong.status_code == unknown.status_code == missing.status_code == 404
    assert wrong.data == unknown.data == missing.data
    assert not PushSubscription.objects.filter(endpoint=NEW_ENDPOINT).exists()
    old.refresh_from_db()
    assert old.is_active is True


@pytest.mark.django_db
def test_a_deactivated_subscription_cannot_be_revived():
    user = _subscribed("dead")
    old = PushSubscription.objects.get(user=user)
    old.deactivate()

    assert _resubscribe(old.endpoint, KEYS["auth"]).status_code == 404
    assert not PushSubscription.objects.filter(endpoint=NEW_ENDPOINT).exists()


@pytest.mark.django_db
def test_on_a_shared_browser_only_the_active_account_moves():
    """A released row for the previous account has the same endpoint and
    secret; the swap must go to the account that holds it now."""
    first = User.objects.create_user(username="before")
    second = User.objects.create_user(username="now")
    for user, active in ((first, False), (second, True)):
        PushSubscription.objects.create(
            user=user,
            endpoint=FCM_ENDPOINT,
            p256dh_key=KEYS["p256dh"],
            auth_key=KEYS["auth"],
            is_active=active,
        )

    assert _resubscribe(FCM_ENDPOINT, KEYS["auth"]).status_code == 200

    active = PushSubscription.objects.filter(is_active=True)
    assert list(active.values_list("user_id", "endpoint")) == [
        (second.pk, NEW_ENDPOINT)
    ]


@pytest.mark.django_db
def test_the_new_endpoint_must_pass_the_ssrf_allowlist():
    user = _subscribed("ssrf456")
    old = PushSubscription.objects.get(user=user)

    response = _resubscribe(old.endpoint, KEYS["auth"], "https://169.254.169.254/x")

    assert response.status_code == 400
    old.refresh_from_db()
    assert old.is_active is True


@pytest.mark.django_db
def test_the_subscription_list_carries_an_exact_endpoint_hash():
    import hashlib

    user = _subscribed("hash")
    client = APIClient()
    client.force_authenticate(user=user)

    rows = client.get("/api/v1/auth/me/push-notifications/").data["subscriptions"]

    endpoint = f"{FCM_ENDPOINT}-hash"
    assert [r["endpoint_sha256"] for r in rows] == [
        hashlib.sha256(endpoint.encode()).hexdigest()
    ]


@pytest.mark.django_db
def test_resubscribe_is_rate_limited_per_ip():
    from apps.users.constants import RATE_LIMIT_PUSH_RESUBSCRIBE

    limit = int(RATE_LIMIT_PUSH_RESUBSCRIBE.split("/")[0])
    statuses = [
        _resubscribe(f"{FCM_ENDPOINT}-guess", "guess").status_code
        for _ in range(limit + 1)
    ]

    assert statuses == [404] * limit + [429]


# --- Todo 602: follow-ups from PR #1051 --------------------------------------


@pytest.mark.django_db
@override_settings(**PUSH_ON)
def test_a_failed_last_used_update_never_fails_the_sent_batch():
    """Item 2: the bulk last_used UPDATE runs after every push went out. An
    OperationalError there must not reach the task's autoretry, which would
    send every notification again."""
    from apps.forum_host.tasks import send_forum_web_push_batch
    from django.db import OperationalError
    from django.db.models.query import QuerySet

    users = [_subscribed(f"bookkeeping{i}") for i in range(2)]

    with (
        patch(
            "apps.users.services.NotificationService.send_web_push_notification",
            return_value=True,
        ) as send,
        patch.object(
            QuerySet, "update", side_effect=OperationalError("db went away")
        ) as update,
    ):
        send_forum_web_push_batch(
            "reply_added",
            [u.pk for u in users],
            {"topic_id": "1", "post_id": "2", "actor_name": "Ada"},
        )

    assert send.call_count == 2
    update.assert_called_once()
    assert not PushSubscription.objects.filter(last_used__isnull=False).exists()


@pytest.mark.parametrize("body", [[], ["x"], "text", 7])
@pytest.mark.django_db
def test_a_non_object_json_body_is_a_400_not_a_500(body):
    """Item 4: an array or scalar body makes request.data a list or str."""
    client = APIClient(enforce_csrf_checks=True)

    response = client.post(RESUBSCRIBE_URL, body, format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_a_disabled_account_is_never_resubscribed():
    """Item 7: the unauthenticated swap must not refresh a banned user's row."""
    user = _subscribed("banned")
    user.is_active = False
    user.save(update_fields=["is_active"])
    old = PushSubscription.objects.get(user=user)

    assert _resubscribe(old.endpoint, KEYS["auth"]).status_code == 404
    assert not PushSubscription.objects.filter(endpoint=NEW_ENDPOINT).exists()
    old.refresh_from_db()
    assert old.is_active is True


@pytest.mark.parametrize(
    "new_endpoint",
    [
        "https://updates.push.services.mozilla.com/wpush/v2/moved",
        "https://web.push.apple.com/moved",
        "https://wns2-par02p.notify.windows.com/w/?token=moved",
    ],
)
@pytest.mark.django_db
def test_the_swap_stays_on_the_old_push_service(new_endpoint):
    """Item 1 (owner decision 2026-10-11): an endpoint + auth pair can move a
    row only within its own push service, never to another one."""
    user = _subscribed(f"svc{len(new_endpoint)}")
    old = PushSubscription.objects.get(user=user)

    assert _resubscribe(old.endpoint, KEYS["auth"], new_endpoint).status_code == 404
    assert not PushSubscription.objects.filter(endpoint=new_endpoint).exists()
    old.refresh_from_db()
    assert old.is_active is True


def test_the_push_service_is_the_matched_allowlist_suffix():
    from apps.users.web_push import push_service

    assert push_service(FCM_ENDPOINT) == "fcm.googleapis.com"
    assert (
        push_service("https://wns2-par02p.notify.windows.com/w/?token=x")
        == push_service("https://db5p.notify.windows.com/w/?token=y")
        == "notify.windows.com"
    )
    assert push_service("https://169.254.169.254/x") is None
    assert push_service(None) is None


@pytest.mark.django_db
def test_the_swap_locks_only_the_subscription_row():
    """Item 6: select_related('user') with a bare select_for_update() also
    locks the joined auth user row; FOR UPDATE OF names the table to lock."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    if not connection.features.has_select_for_update_of:
        pytest.skip("this database has no SELECT ... FOR UPDATE OF")
    old = PushSubscription.objects.get(user=_subscribed("lock"))

    with CaptureQueriesContext(connection) as queries:
        assert _resubscribe(old.endpoint, KEYS["auth"]).status_code == 200

    # The swap's lookup is the locking query that joins the user table
    # (update_or_create takes its own, unjoined, FOR UPDATE too).
    user_table = User._meta.db_table
    joined_locks = [
        q["sql"].split("FOR UPDATE", 1)
        for q in queries.captured_queries
        if "FOR UPDATE" in q["sql"] and user_table in q["sql"]
    ]
    assert len(joined_locks) == 1
    _select, lock_clause = joined_locks[0]
    assert "OF" in lock_clause
    assert PushSubscription._meta.db_table in lock_clause
    assert user_table not in lock_clause
