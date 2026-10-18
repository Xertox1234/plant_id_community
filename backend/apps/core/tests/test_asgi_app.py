"""The ASGI app that production serves with uvicorn (live forum replies, slice 1).

Sync tests that drive the app with ``async_to_sync``; the suite has no
pytest-asyncio. Plain ``django_db``, not ``transaction=True``: called from the
test's thread, ``async_to_sync`` runs thread-sensitive sync code back on that
thread, so it shares the test transaction, and a transactional teardown would
flush Wagtail's migration-seeded rows for later tests (docs/rules/testing.md).
"""

import logging

import pytest
from asgiref.sync import async_to_sync
from channels.testing import HttpCommunicator, WebsocketCommunicator
from plant_community_backend.asgi import application

HEALTH_PATH = "/api/v1/plant-identification/health/"
# The communicator sends no Host header by default ("unknown:0" fails ALLOWED_HOSTS).
HOST = [(b"host", b"localhost")]


@pytest.mark.django_db
def test_health_endpoint_answers_200_over_asgi():
    async def run():
        comm = HttpCommunicator(application, "GET", HEALTH_PATH, headers=HOST)
        return await comm.get_response(timeout=10)

    response = async_to_sync(run)()
    assert response["status"] == 200


@pytest.mark.django_db
def test_stray_websocket_path_closes_4404():
    async def run():
        comm = WebsocketCommunicator(application, "/ws/nope/")
        result = await comm.connect(timeout=5)
        await comm.disconnect()
        return result

    connected, code = async_to_sync(run)()
    assert connected is False
    assert code == 4404


@pytest.mark.django_db
def test_non_ws_prefix_socket_is_refused():
    """Only /ws/ paths are served. Anything else is the router's no-route error,
    which the server answers by refusing the handshake."""

    async def run():
        comm = WebsocketCommunicator(application, "/api/v1/anything/")
        try:
            return await comm.connect(timeout=5)
        finally:
            await comm.disconnect()

    with pytest.raises(ValueError, match="No route found"):
        async_to_sync(run)()


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

    async def run():
        comm = WebsocketCommunicator(application, f"/ws/nope/?token={token}")
        result = await comm.connect(timeout=5)
        await comm.disconnect()
        return result

    try:
        async_to_sync(run)()
    finally:
        mw_logger.removeHandler(caplog.handler)
    # Positive control: the middleware's own line is captured, so an absent
    # token really means it was not logged (not that caplog saw nothing).
    assert "JWTAuthMiddleware" in caplog.text
    assert token[:10] not in caplog.text
