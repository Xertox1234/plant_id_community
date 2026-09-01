"""Tests for the reset_ratelimits management command."""

from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

LOCMEM_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "reset-ratelimits-test",
    },
}


class ResetRatelimitsCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_to_run_when_debug_false(self):
        with self.assertRaises(CommandError):
            call_command("reset_ratelimits")

    @override_settings(DEBUG=True)
    def test_clears_only_ratelimit_keys_when_delete_pattern_available(self):
        if not hasattr(cache, "delete_pattern"):
            self.skipTest("Configured cache backend has no delete_pattern (no Redis)")

        cache.set("rl:some-bucket-hash", 1, 900)
        cache.set("unrelated-key", "keep-me", 900)
        self.addCleanup(cache.delete, "rl:some-bucket-hash")
        self.addCleanup(cache.delete, "unrelated-key")

        call_command("reset_ratelimits")

        self.assertIsNone(cache.get("rl:some-bucket-hash"))
        self.assertEqual(cache.get("unrelated-key"), "keep-me")

    @override_settings(DEBUG=True)
    def test_errors_when_delete_pattern_returns_none(self):
        # Exercises the IGNORE_EXCEPTIONS-masked-Redis-error branch the
        # command's docstring calls out as its motivating design decision —
        # patch the real backend class (not the `cache` proxy, which forwards
        # attribute access onto the live instance rather than accepting a mock).
        if not hasattr(cache, "delete_pattern"):
            self.skipTest("Configured cache backend has no delete_pattern (no Redis)")

        with mock.patch(
            "django_redis.cache.RedisCache.delete_pattern", return_value=None
        ):
            with self.assertRaises(CommandError):
                call_command("reset_ratelimits")

    @override_settings(DEBUG=True, CACHES=LOCMEM_CACHES)
    def test_errors_when_cache_backend_lacks_delete_pattern(self):
        # Forces the LocMemCache branch deterministically, regardless of
        # whether Redis happens to be reachable on the machine running this.
        with self.assertRaises(CommandError):
            call_command("reset_ratelimits")
