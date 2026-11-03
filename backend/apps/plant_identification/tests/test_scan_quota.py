"""Plant.id quota counts real API calls and enforces the monthly cap (Scan 2.0 B1)."""

import base64
from unittest.mock import Mock, patch

import pytest
from apps.plant_identification.constants import (
    QUOTA_KEY_PREFIX_PLANT_ID_DAILY,
    QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY,
)
from apps.plant_identification.services.plant_id_service import PlantIDAPIService
from apps.plant_identification.services.quota_manager import QuotaManager
from django.core.cache import cache
from django.test import override_settings


class FakeRedis:
    """Just enough Redis for the quota counters (no fakeredis in this repo)."""

    def __init__(self):
        self.store: dict[str, int] = {}

    def ping(self):
        return True

    def get(self, key):
        return str(self.store[key]).encode() if key in self.store else None

    def incrby(self, key, amount=1):
        self.store[key] = self.store.get(key, 0) + amount
        return self.store[key]

    def expire(self, key, ttl):
        return True


@pytest.fixture
def redis_fake():
    return FakeRedis()


@pytest.fixture
def quota(redis_fake):
    manager = QuotaManager()
    manager.redis_client = redis_fake
    return manager


@pytest.fixture
def service(quota):
    cache.clear()
    svc = PlantIDAPIService(api_key="test-key")
    svc.quota_manager = quota
    svc.redis_client = None  # skip the distributed lock
    yield svc
    cache.clear()


@pytest.fixture(autouse=True)
def closed_circuit():
    from apps.plant_identification.services.plant_id_service import _plant_id_circuit

    _plant_id_circuit.close()
    yield
    _plant_id_circuit.close()


def _ok(payload):
    resp = Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def _post_router(calls):
    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/identification"):
            return _ok({"result": {"classification": {"suggestions": []}}})
        return _ok({"result": {}})

    return post


def test_can_call_checks_calls_and_reserve(quota, redis_fake):
    redis_fake.store[QUOTA_KEY_PREFIX_PLANT_ID_DAILY] = 1
    with override_settings(PLANT_ID_DAILY_QUOTA=3):
        assert quota.can_call_plant_id(calls=2) is True
        assert quota.can_call_plant_id(calls=1, reserve=2) is False


def test_monthly_cap_enforced(quota, redis_fake):
    redis_fake.store[QUOTA_KEY_PREFIX_PLANT_ID_MONTHLY] = 100
    with override_settings(PLANT_ID_MONTHLY_QUOTA=100):
        assert quota.can_call_plant_id() is False


def test_increment_adds_calls_to_both_counters(quota, redis_fake):
    quota.increment_plant_id(calls=2)
    assert quota.get_plant_id_daily_usage() == 2
    assert quota.get_plant_id_monthly_usage() == 2


def test_diagnosis_counts_two_calls(service, quota):
    calls: list = []
    with patch.object(service.session, "post", side_effect=_post_router(calls)):
        service.identify_plant(b"x", include_diseases=True)
    assert quota.get_plant_id_daily_usage() == 2
    assert quota.get_plant_id_monthly_usage() == 2


def test_identify_only_counts_one_call(service, quota):
    calls: list = []
    with patch.object(service.session, "post", side_effect=_post_router(calls)):
        service.identify_plant(b"x", include_diseases=False)
    assert quota.get_plant_id_daily_usage() == 1


def test_multiple_images_sent_and_health_uses_health_images(service):
    calls: list = []
    with patch.object(service.session, "post", side_effect=_post_router(calls)):
        service.identify_plant(None, images=[b"a", b"b"], health_images=[b"p"])
    by_endpoint = {url.rsplit("/", 1)[1]: kw["json"]["images"] for url, kw in calls}
    assert by_endpoint["identification"] == [
        base64.b64encode(b"a").decode(),
        base64.b64encode(b"b").decode(),
    ]
    assert by_endpoint["health_assessment"] == [base64.b64encode(b"p").decode()]


def test_health_falls_back_to_identification_images(service):
    calls: list = []
    with patch.object(service.session, "post", side_effect=_post_router(calls)):
        service.identify_plant(None, images=[b"a", b"b"])
    by_endpoint = {url.rsplit("/", 1)[1]: kw["json"]["images"] for url, kw in calls}
    assert len(by_endpoint["health_assessment"]) == 2


def test_cache_key_covers_health_images(service):
    calls: list = []
    with (
        override_settings(PLANT_ID_DAILY_QUOTA=10),
        patch.object(service.session, "post", side_effect=_post_router(calls)),
    ):
        service.identify_plant(None, images=[b"a"], health_images=[b"p"])
        service.identify_plant(None, images=[b"a"], health_images=[b"q"])
    assert len(calls) == 4  # second call was not served from the first's cache


def test_quota_reserve_blocks_identify_call(service, redis_fake):
    from apps.plant_identification.services.quota_manager import QuotaExceeded

    redis_fake.store[QUOTA_KEY_PREFIX_PLANT_ID_DAILY] = 1
    with override_settings(PLANT_ID_DAILY_QUOTA=3), pytest.raises(QuotaExceeded):
        service.identify_plant(b"x", include_diseases=False, quota_reserve=2)
