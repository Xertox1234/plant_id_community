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

import logging
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator as BaseApplicationCommunicator
from plant_community_backend.asgi import application

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


async def ws_connect(path, query_string=b""):
    """Open a socket on ``path``; return (accepted, close_code)."""
    comm = ApplicationCommunicator(
        application,
        {
            "type": "websocket",
            "path": path,
            "query_string": query_string,
            "headers": HOST,
            "subprotocols": [],
        },
    )
    await comm.send_input({"type": "websocket.connect"})
    try:
        msg = await comm.receive_output(timeout=5)
    finally:
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        try:
            await comm.wait(timeout=1)
        except BaseException:  # the app may already have exited
            pass
    if msg["type"] == "websocket.accept":
        return True, None
    return False, msg.get("code")


@pytest.mark.django_db
def test_health_endpoint_answers_200_over_asgi():
    status, _body = async_to_sync(http_get)(HEALTH_PATH)
    assert status == 200


@pytest.mark.django_db
def test_stray_websocket_path_closes_4404():
    connected, code = async_to_sync(ws_connect)("/ws/nope/")
    assert connected is False
    assert code == 4404


@pytest.mark.django_db
def test_non_ws_prefix_socket_is_refused():
    """Only /ws/ paths are served. Anything else is the router's no-route error,
    which the server answers by refusing the handshake."""

    with pytest.raises(ValueError, match="No route found"):
        async_to_sync(ws_connect)("/api/v1/anything/")


@pytest.mark.xfail(strict=True, reason="slice 2 removes token logging")
@pytest.mark.django_db
def test_socket_token_is_not_logged(caplog, django_user_model):
    """No part of a socket's token reaches the logs. The middleware logs a
    10-character prefix for a VALID token, so the token here is a real one."""
    from rest_framework_simplejwt.tokens import AccessToken

    user = django_user_model.objects.create_user(
        username="ws-log",
        email="ws-log@example.com",
        password="x-unused-1",  # pragma: allowlist secret
    )
    token = str(AccessToken.for_user(user))
    # The project's loggers do not propagate to the root, where caplog listens.
    mw_logger = logging.getLogger("plant_community_backend.channels_middleware")
    mw_logger.addHandler(caplog.handler)
    caplog.set_level(logging.DEBUG, logger=mw_logger.name)

    try:
        async_to_sync(ws_connect)("/ws/nope/", f"token={token}".encode())
    finally:
        mw_logger.removeHandler(caplog.handler)
    # Positive control: the middleware's own line is captured, so an absent
    # token really means it was not logged (not that caplog saw nothing).
    assert "JWTAuthMiddleware" in caplog.text
    assert token[:10] not in caplog.text
