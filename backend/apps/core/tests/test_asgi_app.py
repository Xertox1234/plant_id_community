"""The ASGI app that production serves with uvicorn (live forum replies, slice 1).

Sync tests that drive the app with ``async_to_sync``; the suite has no
pytest-asyncio. Plain ``django_db``, not ``transaction=True``: called from the
test's thread, ``async_to_sync`` runs thread-sensitive sync code back on that
thread, so it shares the test transaction, and a transactional teardown would
flush Wagtail's migration-seeded rows for later tests (docs/rules/testing.md).

The app is driven with asgiref's ``ApplicationCommunicator``, not
``channels.testing``: that package's ``__init__`` imports its live-server case,
which needs daphne, and daphne (with Twisted) is no longer installed.
"""

import json
import logging
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator as BaseApplicationCommunicator
from django.conf import settings
from django.test import override_settings
from plant_community_backend.asgi import application, build_websocket_app

from .ws_echo import ECHO_PATH, echo_routes

HEALTH_PATH = "/api/v1/plant-identification/health/"
# The communicator sends no Host header by default ("unknown:0" fails ALLOWED_HOSTS).
HOST = [(b"host", b"localhost")]


class ApplicationCommunicator(BaseApplicationCommunicator):
    """What ``channels.testing.ApplicationCommunicator`` does: channels'
    ``database_sync_to_async`` closes "old" connections around each call, which
    would close the test's own connection mid-test."""

    async def send_input(self, message):
        with mock.patch("channels.db.close_old_connections", lambda: None):
            return await super().send_input(message)

    async def receive_output(self, timeout=1):
        with mock.patch("channels.db.close_old_connections", lambda: None):
            return await super().receive_output(timeout)


async def http_get(path):
    """Return (status, body) for a GET of ``path`` through the ASGI app."""
    comm = ApplicationCommunicator(
        application,
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"",
            "headers": HOST,
        },
    )
    await comm.send_input({"type": "http.request", "body": b""})
    start = await comm.receive_output(timeout=10)
    body = b""
    while True:
        msg = await comm.receive_output(timeout=10)
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    await comm.wait(timeout=1)
    return start["status"], body


def _ws_scope(path, headers=(), query_string=b""):
    return {
        "type": "websocket",
        "path": path,
        "query_string": query_string,
        "headers": HOST + list(headers),
        "subprotocols": [],
    }


async def _close(comm):
    await comm.send_input({"type": "websocket.disconnect", "code": 1000})
    try:
        await comm.wait(timeout=1)
    except BaseException:  # the app may already have exited
        pass


async def ws_connect(path, headers=(), query_string=b"", app=None):
    """Open a socket on ``path``. Return ``(status, close_code)``, status one of
    "accepted", "closed_after_accept" (the code reached the client) or
    "rejected" (closed before accept: the client sees a handshake 403)."""
    comm = ApplicationCommunicator(
        app or application, _ws_scope(path, headers, query_string)
    )
    await comm.send_input({"type": "websocket.connect"})
    try:
        msg = await comm.receive_output(timeout=5)
        if msg["type"] != "websocket.accept":
            return "rejected", msg.get("code")
        try:
            nxt = await comm.receive_output(timeout=0.2)
        except Exception:  # nothing more: the socket stays open
            return "accepted", None
        if nxt["type"] == "websocket.close":
            return "closed_after_accept", nxt.get("code")
        return "accepted", None
    finally:
        await _close(comm)


async def ws_echo_user(headers=(), query_string=b""):
    """The ``user_id`` the echo consumer saw, through the real socket stack."""
    app = build_websocket_app(echo_routes)
    comm = ApplicationCommunicator(app, _ws_scope(ECHO_PATH, headers, query_string))
    await comm.send_input({"type": "websocket.connect"})
    try:
        accept = await comm.receive_output(timeout=5)
        assert accept["type"] == "websocket.accept", accept
        frame = await comm.receive_output(timeout=5)
        return json.loads(frame["text"])["user_id"]
    finally:
        await _close(comm)


def _bearer(token):
    return [(b"authorization", f"Bearer {token}".encode())]


def _make_user(django_user_model, username, **extra):
    return django_user_model.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="x-unused-1",  # pragma: allowlist secret
        **extra,
    )


@pytest.mark.django_db
def test_health_endpoint_answers_200_over_asgi():
    status, _body = async_to_sync(http_get)(HEALTH_PATH)
    assert status == 200


@pytest.mark.django_db
def test_stray_websocket_path_closes_4404():
    status, code = async_to_sync(ws_connect)("/ws/nope/")
    assert (status, code) == ("rejected", 4404)


@pytest.mark.django_db
def test_non_ws_prefix_socket_closes_4404():
    """Scanners probe paths outside /ws/ too. The catch-all matches every path,
    so no socket reaches URLRouter's no-route ValueError (a logged traceback)."""
    status, code = async_to_sync(ws_connect)("/api/v1/anything/")
    assert (status, code) == ("rejected", 4404)


@pytest.mark.django_db
def test_socket_token_is_not_logged(caplog, django_user_model):
    """No part of a socket's token, and no query string, reaches the logs."""
    from rest_framework_simplejwt.tokens import AccessToken

    user = _make_user(django_user_model, "ws-log")
    token = str(AccessToken.for_user(user))
    # The project's loggers do not propagate to the root, where caplog listens.
    mw_logger = logging.getLogger("plant_community_backend.channels_middleware")
    mw_logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger=mw_logger.name)

    try:
        async_to_sync(ws_echo_user)(_bearer(token), b"probe=QUERYMARK")
    finally:
        mw_logger.removeHandler(caplog.handler)
    # Positive control: the middleware's own line is captured, so an absent
    # token really means it was not logged (not that caplog saw nothing).
    assert "WS auth" in caplog.text
    assert token[:10] not in caplog.text
    assert "QUERYMARK" not in caplog.text


@pytest.mark.django_db
def test_bearer_header_authenticates(django_user_model):
    from rest_framework_simplejwt.tokens import AccessToken

    user = _make_user(django_user_model, "ws-bearer")
    token = str(AccessToken.for_user(user))
    assert async_to_sync(ws_echo_user)(_bearer(token)) == user.pk


@pytest.mark.django_db
def test_cookie_authenticates(django_user_model):
    from rest_framework_simplejwt.tokens import AccessToken

    user = _make_user(django_user_model, "ws-cookie")
    cookie = f"access_token={AccessToken.for_user(user)}".encode()
    assert async_to_sync(ws_echo_user)([(b"cookie", cookie)]) == user.pk


@pytest.mark.django_db
def test_query_token_is_ignored(django_user_model):
    from rest_framework_simplejwt.tokens import AccessToken

    user = _make_user(django_user_model, "ws-query")
    query = f"token={AccessToken.for_user(user)}".encode()
    assert async_to_sync(ws_echo_user)(query_string=query) is None


@pytest.mark.django_db
def test_inactive_user_token_is_anonymous(django_user_model):
    from rest_framework_simplejwt.tokens import AccessToken

    user = _make_user(django_user_model, "ws-inactive")
    token = str(AccessToken.for_user(user))
    user.is_active = False
    user.save(update_fields=["is_active"])
    cookie = f"access_token={token}".encode()
    assert async_to_sync(ws_echo_user)([(b"cookie", cookie)]) is None


@pytest.mark.django_db
def test_invalid_token_is_anonymous(django_user_model):
    assert async_to_sync(ws_echo_user)(_bearer("not-a-jwt")) is None


@pytest.mark.django_db
def test_session_user_survives_without_token(client, django_user_model):
    """The session stack runs OUTSIDE the JWT middleware, so a session-only
    socket keeps its user (the old order always overwrote it)."""
    user = _make_user(django_user_model, "ws-session")
    client.force_login(user)
    sessionid = client.cookies[settings.SESSION_COOKIE_NAME].value
    cookie = f"{settings.SESSION_COOKIE_NAME}={sessionid}".encode()
    assert async_to_sync(ws_echo_user)([(b"cookie", cookie)]) == user.pk


def _origin(value):
    return [(b"origin", value.encode())]


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=["https://houseplant-md.com"])
def test_disallowed_origin_rejected_before_accept():
    """Cross-site WebSocket hijacking: a cookie socket from another site."""
    status, _code = async_to_sync(ws_connect)(
        ECHO_PATH, _origin("https://evil.example"), app=build_websocket_app(echo_routes)
    )
    assert status == "rejected"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=["https://houseplant-md.com"])
def test_allowed_origin_accepted():
    status, _code = async_to_sync(ws_connect)(
        ECHO_PATH,
        _origin("https://houseplant-md.com"),
        app=build_websocket_app(echo_routes),
    )
    assert status == "accepted"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=["https://houseplant-md.com"])
def test_missing_origin_accepted():
    """Browsers always send Origin on a socket; the mobile app sends none."""
    status, _code = async_to_sync(ws_connect)(
        ECHO_PATH, app=build_websocket_app(echo_routes)
    )
    assert status == "accepted"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=["https://houseplant-md.com"])
@pytest.mark.parametrize(
    "origin",
    [
        "https://houseplant-md.com.evil.example",
        "http://houseplant-md.com",
        "https://houseplant-md.com:8443",
        "null",
    ],
)
def test_origin_compare_is_exact(origin):
    status, _code = async_to_sync(ws_connect)(
        ECHO_PATH, _origin(origin), app=build_websocket_app(echo_routes)
    )
    assert status == "rejected"


@pytest.mark.django_db
@override_settings(CORS_ALLOWED_ORIGINS=["https://houseplant-md.com"])
def test_origin_compare_ignores_case():
    status, _code = async_to_sync(ws_connect)(
        ECHO_PATH,
        _origin("HTTPS://Houseplant-MD.com"),
        app=build_websocket_app(echo_routes),
    )
    assert status == "accepted"


def test_routing_import_error_is_loud():
    """A broken routing module must fail the boot, not serve zero routes."""
    import inspect

    from plant_community_backend import asgi

    assert "except Exception" not in inspect.getsource(asgi)


def _stub_app(started, release):
    """An inner ASGI app that holds each request until ``release`` is set."""

    async def app(scope, receive, send):
        started.append(scope["type"])
        if scope["type"] == "http":
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

    return app


async def _drive_http(app):
    comm = BaseApplicationCommunicator(
        app, {"type": "http", "method": "GET", "path": "/", "headers": HOST}
    )
    await comm.send_input({"type": "http.request", "body": b""})
    return comm


def test_http_limit_queues_excess_requests():
    import asyncio

    from plant_community_backend.asgi_middleware import HttpConcurrencyLimit

    async def run():
        started, release = [], asyncio.Event()
        app = HttpConcurrencyLimit(_stub_app(started, release), limit=2)
        comms = [await _drive_http(app) for _ in range(3)]
        await asyncio.sleep(0.05)
        in_flight = len(started)
        release.set()
        statuses = []
        for comm in comms:
            start = await comm.receive_output(timeout=2)
            statuses.append(start["status"])
            await comm.receive_output(timeout=2)
        return in_flight, statuses

    in_flight, statuses = async_to_sync(run)()
    assert in_flight == 2  # the third waits instead of getting a 503
    assert statuses == [200, 200, 200]


def test_http_limit_does_not_touch_websocket_scopes():
    import asyncio

    from plant_community_backend.asgi_middleware import HttpConcurrencyLimit

    async def run():
        started, release = [], asyncio.Event()
        app = HttpConcurrencyLimit(_stub_app(started, release), limit=0)
        comm = BaseApplicationCommunicator(app, {"type": "websocket", "path": "/"})
        await comm.send_input({"type": "websocket.connect"})
        await asyncio.sleep(0.05)
        return started

    assert async_to_sync(run)() == ["websocket"]


def test_application_bounds_http_with_the_configured_limit():
    from plant_community_backend import asgi
    from plant_community_backend.asgi_middleware import HttpConcurrencyLimit

    http_app = asgi.application.application_mapping["http"]
    assert isinstance(http_app, HttpConcurrencyLimit)
    assert http_app.limit == settings.WEB_HTTP_CONCURRENCY == 20
