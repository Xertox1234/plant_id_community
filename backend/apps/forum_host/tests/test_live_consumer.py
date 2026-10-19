"""The live topic socket: ws/forum/topics/<id>/ (forum live replies, slice 2).

Driven through the real ASGI ``application`` with asgiref's communicator (see
apps/core/tests/test_asgi_app.py for why not ``channels.testing``). Sync tests
call ``async_to_sync``; thread-sensitive DB work then runs back on the test's
thread, inside the test transaction.
"""

import json
import logging
from unittest import mock

import pytest
from apps.core.ratelimit import get_trusted_client_ip, trusted_client_ip_from_meta
from apps.core.tests.test_asgi_app import ApplicationCommunicator
from apps.forum_host import constants
from apps.forum_host.live import EVENT_HANDLER_TYPE, build_event, topic_group
from apps.forum_host.tests.test_live_events import _thread
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from plant_community_backend.asgi import application
from rest_framework_simplejwt.tokens import AccessToken
from wagtail.actions.unpublish import UnpublishAction
from wagtail_forum.models import ForumBoard

User = get_user_model()

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "forum-live-consumer-tests",
    }
}


@pytest.fixture(autouse=True)
def live_on():
    with override_settings(
        FORUM_LIVE_UPDATES_ENABLED=True,
        CACHES=LOCMEM,
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    ), mock.patch("channels.db.close_old_connections", lambda: None):
        # The communicator patches that only inside send_input/receive_output;
        # app DB work also runs while a test waits, and closing "old"
        # connections there would close the test transaction's own.
        cache.clear()
        yield
        cache.clear()


def _path(topic_id):
    return f"/ws/forum/topics/{topic_id}/"


def _headers(user=None, extra=()):
    headers = [(b"host", b"localhost")]
    if user is not None:
        token = str(AccessToken.for_user(user))
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return headers + list(extra)


class Socket:
    """One socket held open across awaits."""

    def __init__(self, topic_id, user=None, extra_headers=(), client=None):
        scope = {
            "type": "websocket",
            "path": _path(topic_id),
            "query_string": b"",
            "headers": _headers(user, extra_headers),
            "subprotocols": [],
        }
        if client is not None:
            scope["client"] = client
        self.comm = ApplicationCommunicator(application, scope)

    async def open(self):
        """Return (status, code): accepted | closed_after_accept | rejected."""
        await self.comm.send_input({"type": "websocket.connect"})
        msg = await self.comm.receive_output(timeout=5)
        if msg["type"] != "websocket.accept":
            return "rejected", msg.get("code")
        if not await self.comm.receive_nothing(timeout=0.1):
            nxt = await self.comm.receive_output(timeout=1)
            if nxt["type"] == "websocket.close":
                return "closed_after_accept", nxt.get("code")
        return "accepted", None

    async def send_text(self, text):
        await self.comm.send_input({"type": "websocket.receive", "text": text})

    async def receive_json(self, timeout=2):
        msg = await self.comm.receive_output(timeout=timeout)
        assert msg["type"] == "websocket.send", msg
        return json.loads(msg["text"])

    async def nothing(self, timeout=0.2):
        return await self.comm.receive_nothing(timeout=timeout)

    async def close(self):
        await self.comm.send_input({"type": "websocket.disconnect", "code": 1000})
        try:
            await self.comm.wait(timeout=1)
        except BaseException:  # the app may already have exited
            pass


def _open_once(topic_id, user=None, **kw):
    async def run():
        sock = Socket(topic_id, user, **kw)
        try:
            return await sock.open()
        finally:
            await sock.close()

    return async_to_sync(run)()


def _user(name):
    return User.objects.create_user(username=name)


@pytest.mark.django_db
def test_flag_off_closes_4503():
    topic, _o, author = _thread("ws-flag")
    with override_settings(FORUM_LIVE_UPDATES_ENABLED=False):
        assert _open_once(topic.pk, author) == ("closed_after_accept", 4503)


@pytest.mark.django_db
def test_anonymous_closes_4401():
    topic, _o, _author = _thread("ws-anon")
    assert _open_once(topic.pk) == ("closed_after_accept", 4401)


@pytest.mark.django_db
def test_unknown_topic_closes_4404():
    assert _open_once(987654, _user("ws-unknown")) == ("closed_after_accept", 4404)


@pytest.mark.django_db
def test_unpublished_topic_closes_4404():
    topic, _o, author = _thread("ws-unpub")
    UnpublishAction(topic, user=None).execute(skip_permission_checks=True)
    assert _open_once(topic.pk, author) == ("closed_after_accept", 4404)


@pytest.mark.django_db
def test_hidden_board_closes_4404():
    topic, _o, author = _thread("ws-hidden")
    ForumBoard.objects.filter(pk=topic.board_id).update(live=False)
    assert _open_once(topic.pk, author) == ("closed_after_accept", 4404)


@pytest.mark.django_db
def test_visible_topic_accepts_and_receives_group_event():
    topic, _o, author = _thread("ws-event")
    event = build_event("post.created", topic.pk, 9)

    async def run():
        sock = Socket(topic.pk, author)
        try:
            assert await sock.open() == ("accepted", None)
            await get_channel_layer().group_send(
                topic_group(topic.pk), {"type": EVENT_HANDLER_TYPE, "event": event}
            )
            return await sock.receive_json()
        finally:
            await sock.close()

    assert async_to_sync(run)() == event


@pytest.mark.django_db
def test_ping_gets_pong():
    topic, _o, author = _thread("ws-ping")

    async def run():
        sock = Socket(topic.pk, author)
        try:
            await sock.open()
            await sock.send_text('{"type": "ping"}')
            return await sock.receive_json()
        finally:
            await sock.close()

    assert async_to_sync(run)() == {"v": 1, "type": "pong"}


@pytest.mark.django_db
def test_garbage_and_non_ping_frames_are_ignored():
    topic, _o, author = _thread("ws-garbage")
    event = build_event("topic.updated", topic.pk)

    async def run():
        sock = Socket(topic.pk, author)
        try:
            await sock.open()
            for text in ("not json", "[1, 2]", '{"type": "subscribe"}', '"ping"'):
                await sock.send_text(text)
            assert await sock.nothing()
            # Still open and still delivering.
            await get_channel_layer().group_send(
                topic_group(topic.pk), {"type": EVENT_HANDLER_TYPE, "event": event}
            )
            return await sock.receive_json()
        finally:
            await sock.close()

    assert async_to_sync(run)() == event


@pytest.mark.django_db
def test_user_cap_closes_4429_on_eleventh_socket():
    topic, _o, author = _thread("ws-cap")
    cap = constants.LIVE_MAX_SOCKETS_PER_USER

    async def run():
        socks = [Socket(topic.pk, author) for _ in range(cap + 1)]
        try:
            return [await s.open() for s in socks]
        finally:
            for s in socks:
                await s.close()

    results = async_to_sync(run)()
    assert results[:cap] == [("accepted", None)] * cap
    assert results[cap] == ("closed_after_accept", 4429)


@pytest.mark.django_db
def test_refused_connect_does_not_decrement_caps():
    """A refused socket still gets disconnect(); it must not give back a slot
    it never took, or the count drifts down and the cap stops holding."""
    topic, _o, author = _thread("ws-cap-drift")
    cap = constants.LIVE_MAX_SOCKETS_PER_USER

    async def run():
        held = [Socket(topic.pk, author) for _ in range(cap)]
        for s in held:
            assert await s.open() == ("accepted", None)
        try:
            for _ in range(2):
                extra = Socket(topic.pk, author)
                assert await extra.open() == ("closed_after_accept", 4429)
                await extra.close()
            await held.pop().close()
            again = Socket(topic.pk, author)
            assert await again.open() == ("accepted", None)
            held.append(again)
            extra = Socket(topic.pk, author)
            assert await extra.open() == ("closed_after_accept", 4429)
            await extra.close()
        finally:
            for s in held:
                await s.close()

    async_to_sync(run)()


@pytest.mark.django_db
def test_closing_sockets_gives_slots_back():
    topic, _o, author = _thread("ws-cap-return")
    cap = constants.LIVE_MAX_SOCKETS_PER_USER
    for _ in range(cap + 2):
        assert _open_once(topic.pk, author) == ("accepted", None)


@pytest.mark.django_db
@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
def test_ip_cap_uses_trusted_forwarded_ip():
    topic, _o, _author = _thread("ws-ip")
    xff = [(b"x-forwarded-for", b"203.0.113.7, 10.0.0.2")]
    users = [_user(f"ws-ip-{i}") for i in range(3)]

    with mock.patch.object(constants, "LIVE_MAX_SOCKETS_PER_IP", 2):

        async def run():
            socks = [Socket(topic.pk, u, xff, client=("10.9.9.9", 5000)) for u in users]
            other = Socket(
                topic.pk,
                _other,
                [(b"x-forwarded-for", b"198.51.100.4, 10.0.0.2")],
                client=("10.9.9.9", 5000),
            )
            try:
                results = [await s.open() for s in socks]
                results.append(await other.open())
                return results
            finally:
                for s in socks + [other]:
                    await s.close()

        _other = _user("ws-ip-other")
        results = async_to_sync(run)()
    # Same real client behind the same proxy: the third is over the IP cap; a
    # different real client behind that proxy is counted separately.
    assert results == [
        ("accepted", None),
        ("accepted", None),
        ("closed_after_accept", 4429),
        ("accepted", None),
    ]


@pytest.mark.django_db
def test_logs_have_no_token(caplog):
    topic, _o, author = _thread("ws-logs")
    token = str(AccessToken.for_user(author))
    loggers = [
        logging.getLogger("apps.forum_host.consumers"),
        logging.getLogger("plant_community_backend.channels_middleware"),
    ]
    for lg in loggers:
        lg.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger=loggers[0].name)
    caplog.set_level(logging.DEBUG, logger=loggers[1].name)
    try:

        async def run():
            sock = Socket(
                topic.pk, extra_headers=[(b"authorization", f"Bearer {token}".encode())]
            )
            try:
                return await sock.open()
            finally:
                await sock.close()

        assert async_to_sync(run)() == ("accepted", None)
    finally:
        for lg in loggers:
            lg.removeHandler(caplog.handler)
    assert "[FORUM_LIVE] connect" in caplog.text  # positive control
    assert token[:10] not in caplog.text


@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2)
def test_trusted_client_ip_from_meta_matches_request_helper():
    request = RequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="198.51.100.9, 10.0.0.1", REMOTE_ADDR="10.0.0.2"
    )
    assert trusted_client_ip_from_meta(request.META) == "198.51.100.9"
    assert get_trusted_client_ip(request) == "198.51.100.9"


@pytest.mark.parametrize(
    "headers",
    [
        # A client-sent underscore twin must not stand in for the proxy's header.
        [
            (b"x-forwarded-for", b"203.0.113.7, 10.0.0.2"),
            (b"x_forwarded_for", b"6.6.6.6, 10.0.0.2"),
        ],
        # Repeated headers are joined, not last-wins.
        [(b"x-forwarded-for", b"203.0.113.7"), (b"x-forwarded-for", b"10.0.0.2")],
    ],
)
def test_scope_meta_builds_headers_as_django_does(headers):
    """Sockets resolve the client IP exactly as the HTTP rate limiter does, so
    the scope's META view must follow Django's ASGI header rules."""
    import io

    from apps.forum_host.consumers import _scope_meta
    from django.core.handlers.asgi import ASGIRequest

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [(b"host", b"localhost")] + headers,
        "client": ("10.9.9.9", 5000),
    }
    django_meta = ASGIRequest(scope, io.BytesIO()).META
    ours = _scope_meta(scope)
    for key in ("REMOTE_ADDR", "HTTP_X_FORWARDED_FOR"):
        assert ours.get(key) == django_meta.get(key), key
    with override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=2):
        assert trusted_client_ip_from_meta(ours) == "203.0.113.7"


@pytest.mark.django_db
def test_topic_removed_is_delivered_then_the_socket_closes_4404():
    """A reader whose topic went away keeps no subscription to it."""
    topic, _o, author = _thread("ws-removed")
    removed = build_event("topic.removed", topic.pk)

    async def run():
        sock = Socket(topic.pk, author)
        try:
            assert await sock.open() == ("accepted", None)
            await get_channel_layer().group_send(
                topic_group(topic.pk), {"type": EVENT_HANDLER_TYPE, "event": removed}
            )
            frame = await sock.receive_json()
            close = await sock.comm.receive_output(timeout=2)
            return frame, close
        finally:
            await sock.close()

    frame, close = async_to_sync(run)()
    assert frame == removed
    assert close == {"type": "websocket.close", "code": 4404}
