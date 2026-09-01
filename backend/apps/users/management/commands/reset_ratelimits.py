"""
Django management command to clear django-ratelimit's counters.

Usage:
    python manage.py reset_ratelimits

Clears every django-ratelimit bucket (login, register, token refresh, plant
ID lookups, etc. — not just login) by deleting all cache keys under the
library's configured prefix and cache alias — resolved the same way
django-ratelimit's own `core.get_usage()` does
(`getattr(settings, 'RATELIMIT_USE_CACHE', 'default')` /
`getattr(settings, 'RATELIMIT_CACHE_PREFIX', 'rl:')`) so this stays correct
if either setting is ever introduced, rather than hardcoding today's
defaults. Login is today's motivating case (see todo 312 — local Playwright
runs share one IP-based 5/15m login budget across the `setup` project's real
login and this file's own valid/invalid login tests, so two runs in a row
reliably exhaust it), but this clears the whole namespace rather than
pretending to be login-specific.

For local E2E testing only (requires DEBUG=True) — mirrors create_test_user's
guard. Not meant for production use; there is no reason to run this against
a live deployment.
"""

from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Clear django-ratelimit counters for local E2E testing"

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG:
            raise CommandError(
                "reset_ratelimits clears rate-limit counters and is for local "
                "E2E testing only (requires DEBUG=True)."
            )

        cache_alias = getattr(settings, "RATELIMIT_USE_CACHE", "default")
        prefix = getattr(settings, "RATELIMIT_CACHE_PREFIX", "rl:")
        cache = caches[cache_alias]

        if not hasattr(cache, "delete_pattern"):
            # This command runs in its own process, separate from `runserver`.
            # On the LocMemCache fallback (Redis unreachable), the counters
            # live in runserver's own process memory — this process can never
            # reach them, so silently no-op'ing here would misreport success.
            raise CommandError(
                f"The '{cache_alias}' cache backend doesn't support "
                "delete_pattern (no Redis?) — reset_ratelimits can't reach "
                "the counters used by `manage.py runserver`. Start Redis "
                "(`brew services start redis`) and retry."
            )

        # IGNORE_EXCEPTIONS=True (settings.py) plus django_redis's own
        # @omit_exception wrapper means a Redis hiccup returns None instead of
        # raising — treat that as a hard failure too, not a false "0 cleared".
        deleted = cache.delete_pattern(f"{prefix}*")
        if deleted is None:
            raise CommandError(
                "delete_pattern returned None — the cache backend swallowed "
                "an error talking to Redis. Check Redis is reachable and retry."
            )

        if deleted == 0:
            # Not an error, but not silently green either: a REDIS_URL/db-index
            # mismatch between this command's process and `manage.py runserver`
            # would ALSO clear 0 keys — the E2E login would keep 429ing with no
            # signal anything is wrong if this printed as an unqualified success.
            self.stdout.write(
                self.style.WARNING(
                    "Cleared 0 rate-limit key(s) — if E2E logins are still "
                    "429ing, check that this process's REDIS_URL/db index "
                    "matches the one `manage.py runserver` is actually using."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Cleared {deleted} rate-limit key(s).")
            )
