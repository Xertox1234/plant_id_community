"""The Plant.id quota with Redis unavailable (todo 700 L3).

Owner decision 2026-11-17: keep failing open on a Redis outage, so scans keep
working, and raise a Sentry alert instead. These tests drive a real outage:
``get_redis_connection`` itself raises, or the live client errors mid-call.
"""

from unittest.mock import Mock, patch

import pytest
from apps.plant_identification.constants import PLANT_ID_QUOTA_FAIL_OPEN_ALERT_SECONDS
from apps.plant_identification.services import quota_manager as qm
from apps.plant_identification.services.quota_manager import QuotaManager
from redis.exceptions import ConnectionError as RedisConnectionError

# An obviously fake credential, only to prove the alert never carries it.
REDIS_URL_IN_ERROR = (
    "redis://:fake-pw-0000@redis.internal:6379/0"  # pragma: allowlist secret
)


@pytest.fixture(autouse=True)
def reset_alert_throttle():
    qm._last_fail_open_alert = None
    yield
    qm._last_fail_open_alert = None


@pytest.fixture
def sentry():
    with patch.object(qm.sentry_sdk, "capture_message") as capture:
        yield capture


@pytest.fixture
def redis_down():
    """Redis refuses the connection, as in an outage."""
    with patch.object(
        qm,
        "get_redis_connection",
        side_effect=RedisConnectionError(
            f"Error 111 connecting to {REDIS_URL_IN_ERROR}"
        ),
    ):
        yield


def test_outage_fails_open_and_alerts_once(redis_down, sentry):
    manager = QuotaManager()
    assert manager.redis_client is None

    assert manager.can_call_plant_id(calls=2) is True
    assert manager.reserve_plant_id(calls=2) is True
    # Every allowance GET builds a new manager and asks again: still one alert.
    for _ in range(5):
        assert QuotaManager().can_call_plant_id(calls=2) is True

    assert sentry.call_count == 1
    message = sentry.call_args.args[0]
    assert "Plant.id quota failing open" in message
    assert sentry.call_args.kwargs == {"level": "error"}


def test_alert_fires_again_after_the_throttle_window(redis_down, sentry):
    clock = Mock(return_value=1000.0)
    with patch.object(qm.monotonic_time, "monotonic", clock):
        QuotaManager().can_call_plant_id()
        clock.return_value = 1000.0 + PLANT_ID_QUOTA_FAIL_OPEN_ALERT_SECONDS - 1
        QuotaManager().can_call_plant_id()
        assert sentry.call_count == 1
        clock.return_value = 1000.0 + PLANT_ID_QUOTA_FAIL_OPEN_ALERT_SECONDS
        QuotaManager().can_call_plant_id()
    assert sentry.call_count == 2


@pytest.mark.parametrize("method", ["can_call_plant_id", "reserve_plant_id"])
def test_redis_dying_mid_call_fails_open_and_alerts(method, sentry):
    """The client connected, then Redis went away before the read/INCRBY."""
    client = Mock()
    client.ping.return_value = True
    error = RedisConnectionError(f"Connection lost to {REDIS_URL_IN_ERROR}")
    client.get.side_effect = error
    client.incrby.side_effect = error
    with patch.object(qm, "get_redis_connection", return_value=client):
        manager = QuotaManager()
    assert manager.redis_client is client

    assert getattr(manager, method)(calls=2) is True

    assert sentry.call_count == 1
    message = sentry.call_args.args[0]
    assert "ConnectionError" in message
    # The exception text can carry the Redis URL and password: never sent.
    assert "fake-pw-0000" not in message
    assert "redis.internal" not in message


def test_a_failing_sentry_never_breaks_the_quota_check(redis_down):
    with patch.object(qm.sentry_sdk, "capture_message", side_effect=RuntimeError):
        assert QuotaManager().can_call_plant_id() is True
        assert QuotaManager().reserve_plant_id() is True


def test_healthy_redis_raises_no_alert(sentry):
    client = Mock()
    client.ping.return_value = True
    client.get.return_value = None
    with patch.object(qm, "get_redis_connection", return_value=client):
        assert QuotaManager().can_call_plant_id(calls=2) is True
    sentry.assert_not_called()
