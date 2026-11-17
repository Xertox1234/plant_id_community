"""Redis read timeouts outlast every blocking wait on their pool (todo 710).

redis-py 8 changed the default ``socket_timeout`` from "wait forever" to 5 s.
Two pools block on the server for longer than that:

- the channel layer: each ``receive()`` BZPOPMINs for ``brpop_timeout`` (5 s),
  so an idle forum socket's receive raised ``TimeoutError`` after 5 s;
- the ``default`` cache pool: the Plant.id distributed lock BLPOPs for up to
  ``CACHE_LOCK_TIMEOUT`` (15 s), so a contended lock raised ``TimeoutError``
  instead of waiting.

Both were reproduced under redis 8.1 and were clean under 7.4.0.
"""

from __future__ import annotations

from apps.plant_identification.constants import CACHE_LOCK_TIMEOUT
from django.conf import settings
from django.test import SimpleTestCase
from plant_community_backend import settings as settings_module


class RedisSocketTimeoutInvariantTests(SimpleTestCase):
    def test_channel_layer_read_timeout_outlasts_its_bzpopmin(self) -> None:
        from channels_redis.core import RedisChannelLayer

        hosts = settings_module._REDIS_CHANNEL_LAYERS["default"]["CONFIG"]["hosts"]
        self.assertEqual(len(hosts), 1)
        host = hosts[0]
        self.assertIsInstance(host, dict, "a bare URL gets redis-py's 5 s default")
        self.assertEqual(host["address"], settings_module._redis_url)
        self.assertGreater(host["socket_timeout"], RedisChannelLayer.brpop_timeout)
        # The active setting, not just the dict it is built from: a Redis layer
        # in use must be this one (only DEBUG/test runs fall back to in-memory).
        active = settings.CHANNEL_LAYERS["default"]
        if active["BACKEND"] == "channels_redis.core.RedisChannelLayer":
            self.assertEqual(active, settings_module._REDIS_CHANNEL_LAYERS["default"])

    def test_cache_pool_read_timeout_outlasts_the_lock_wait(self) -> None:
        self.assertGreater(settings.REDIS_CACHE_SOCKET_TIMEOUT, CACHE_LOCK_TIMEOUT)
        default = settings.CACHES["default"]
        if default["BACKEND"] != "django_redis.cache.RedisCache":
            self.skipTest("Redis unreachable: the cache fell back to locmem")
        pool_kwargs = default["OPTIONS"]["CONNECTION_POOL_KWARGS"]
        self.assertEqual(
            pool_kwargs["socket_timeout"], settings.REDIS_CACHE_SOCKET_TIMEOUT
        )


class RedisBlockingWaitTests(SimpleTestCase):
    """Drive a real blocking wait longer than redis-py 8's 5 s default."""

    def test_blocking_pop_longer_than_five_seconds_returns_none(self) -> None:
        if settings.CACHES["default"]["BACKEND"] != "django_redis.cache.RedisCache":
            self.skipTest("Redis unreachable: the cache fell back to locmem")
        from django_redis import get_redis_connection

        client = get_redis_connection("default")
        # An empty key: BLPOP blocks the full 6 s, then returns None. Under the
        # 5 s default read timeout this raised TimeoutError.
        self.assertIsNone(client.blpop("todo710:never-pushed", timeout=6))
