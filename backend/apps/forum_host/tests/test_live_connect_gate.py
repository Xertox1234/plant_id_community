"""The per-IP connect-rate gate in front of the socket stack (live slice 5).

``WebsocketConnectRateLimit`` sits between the Origin check and the auth
stack, because the session and JWT lookups both query the database before a
consumer's ``connect()`` runs. A connect over the per-IP rate is accepted and
closed 4429 before any of that work.
"""

import logging
from unittest import mock

import pytest
from apps.core.tests.test_asgi_app import HEALTH_PATH, ApplicationCommunicator, http_get
from apps.forum_host import constants
from apps.forum_host.tests.test_live_consumer import (  # noqa: F401
    _headers,
    _user,
    live_on,
)
from apps.forum_host.tests.test_live_events import _thread
from asgiref.sync import async_to_sync
from django.test import override_settings
from plant_community_backend import asgi_middleware
from plant_community_backend.asgi import application

LIMIT = 3
CLIENT_IP = "203.0.113.9"
CLIENT = (CLIENT_IP, 5000)
# Any fixed instant: the counting tests must not straddle a window boundary.
FROZEN_NOW = 1_000_000.0


@pytest.fixture
def small_limit():
    with mock.patch.object(constants, "LIVE_CONNECT_RATE_PER_IP", LIMIT):
        yield


@pytest.fixture
def frozen_clock():
    with mock.patch.object(asgi_middleware, "time") as fake_time:
        fake_time.time.return_value = FROZEN_NOW
        yield fake_time


async def _connect(path, user=None, client=CLIENT, extra=()):
    """Open one socket and close it. Return (status, code) as ``Socket.open``."""
    scope = {
        "type": "websocket",
        "path": path,
        "query_string": b"",
        "headers": _headers(user, extra),
        "subprotocols": [],
    }
    if client is not None:
        scope["client"] = client
    comm = ApplicationCommunicator(application, scope)
    await comm.send_input({"type": "websocket.connect"})
    try:
        msg = await comm.receive_output(timeout=5)
        if msg["type"] != "websocket.accept":
            return "rejected", msg.get("code")
        if not await comm.receive_nothing(timeout=0.1):
            nxt = await comm.receive_output(timeout=1)
            if nxt["type"] == "websocket.close":
                return "closed_after_accept", nxt.get("code")
        return "accepted", None
    finally:
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        try:
            await comm.wait(timeout=1)
        except BaseException:  # the app may already have exited
            pass


def _topic_path(topic):
    return f"/ws/forum/topics/{topic.pk}/"


def _open_n(n, path, user=None, client=CLIENT, extra=()):
    async def run():
        return [await _connect(path, user, client, extra) for _ in range(n)]

    return async_to_sync(run)()


ACCEPTED = ("accepted", None)
LIMITED = ("closed_after_accept", constants.LIVE_CLOSE_LIMITED)


@pytest.mark.django_db
def test_fourth_connect_in_window_closes_4429(small_limit, frozen_clock):
    topic, _o, author = _thread("gate-fourth")
    results = _open_n(LIMIT + 1, _topic_path(topic), author)
    assert results == [ACCEPTED] * LIMIT + [LIMITED]


@pytest.mark.django_db
def test_rate_refusal_runs_no_queries(
    small_limit, frozen_clock, django_assert_num_queries
):
    """Refused before the JWT middleware could look its (valid) token up."""
    topic, _o, author = _thread("gate-noquery")
    path = _topic_path(topic)
    assert _open_n(LIMIT, path, author) == [ACCEPTED] * LIMIT
    with django_assert_num_queries(0):
        assert _open_n(1, path, author) == [LIMITED]


@pytest.mark.django_db
def test_next_window_admits_again(small_limit, frozen_clock):
    topic, _o, author = _thread("gate-window")
    path = _topic_path(topic)
    assert _open_n(LIMIT + 1, path, author)[-1] == LIMITED
    frozen_clock.time.return_value = (
        FROZEN_NOW + constants.LIVE_CONNECT_RATE_WINDOW_SECONDS
    )
    assert _open_n(1, path, author) == [ACCEPTED]


@pytest.mark.django_db
@override_settings(RATELIMIT_TRUSTED_PROXY_COUNT=1)
def test_budget_is_per_trusted_ip(small_limit, frozen_clock):
    """Two real clients behind the same proxy each get their own budget."""
    topic, _o, author = _thread("gate-perip")
    path = _topic_path(topic)
    proxy = ("10.9.9.9", 5000)
    first = [(b"x-forwarded-for", b"203.0.113.1")]
    second = [(b"x-forwarded-for", b"203.0.113.2")]
    assert _open_n(LIMIT + 1, path, author, proxy, first) == [ACCEPTED] * LIMIT + [
        LIMITED
    ]
    assert _open_n(LIMIT + 1, path, author, proxy, second) == [ACCEPTED] * LIMIT + [
        LIMITED
    ]


@pytest.mark.django_db
def test_uncountable_cache_admits(small_limit, frozen_clock):
    """Redis down: the project cache answers None, and the gate admits."""
    topic, _o, author = _thread("gate-nocache")
    fake_cache = mock.Mock()
    fake_cache.aadd = mock.AsyncMock(return_value=None)
    fake_cache.aincr = mock.AsyncMock(return_value=None)
    with mock.patch.object(asgi_middleware, "cache", fake_cache):
        results = _open_n(LIMIT + 2, _topic_path(topic), author)
    assert results == [ACCEPTED] * (LIMIT + 2)
    assert fake_cache.aincr.await_count == LIMIT + 2  # the gate did ask


@pytest.mark.django_db
def test_unresolvable_ip_admits(small_limit, frozen_clock):
    """No client address and no trusted header: admitted, never pooled into
    one shared bucket that a misconfigured proxy would make everyone share."""
    topic, _o, author = _thread("gate-noip")
    results = _open_n(LIMIT + 2, _topic_path(topic), author, client=None)
    assert results == [ACCEPTED] * (LIMIT + 2)


@pytest.mark.django_db
def test_refusal_logged_once_per_window(small_limit, frozen_clock, caplog):
    topic, _o, author = _thread("gate-log")
    gate_logger = logging.getLogger(asgi_middleware.__name__)
    gate_logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger=gate_logger.name)
    try:
        results = _open_n(LIMIT * 2, _topic_path(topic), author)
    finally:
        gate_logger.removeHandler(caplog.handler)
    assert results == [ACCEPTED] * LIMIT + [LIMITED] * LIMIT
    lines = [
        r.getMessage()
        for r in caplog.records
        if "[FORUM_LIVE] connect rate limited" in r.getMessage()
    ]
    assert len(lines) == 1
    assert CLIENT_IP not in caplog.text


@pytest.mark.django_db
def test_http_scope_untouched(small_limit, frozen_clock):
    topic, _o, author = _thread("gate-http")
    assert _open_n(LIMIT + 1, _topic_path(topic), author)[-1] == LIMITED
    status, _body = async_to_sync(http_get)(HEALTH_PATH)
    assert status == 200


@pytest.mark.django_db
def test_gate_also_covers_unknown_paths(small_limit, frozen_clock):
    """The catch-all route is behind the gate too: an exhausted IP gets 4429
    there, not the catch-all's 4404."""
    topic, _o, author = _thread("gate-nope")
    assert _open_n(LIMIT, _topic_path(topic), author) == [ACCEPTED] * LIMIT
    assert _open_n(1, "/ws/nope/") == [LIMITED]
