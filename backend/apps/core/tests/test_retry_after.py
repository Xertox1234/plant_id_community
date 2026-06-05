"""Unit tests for `_retry_after_seconds` rate-window parsing (audit L5).

Pre-fix, only bare-unit windows ('30/m') were handled; multi-unit windows like
'5/15m' fell through to the 1-hour fallback. The parser now reads the numeric
multiplier.
"""

from apps.core.exceptions import _retry_after_seconds
from django.test import SimpleTestCase


class RetryAfterSecondsTest(SimpleTestCase):
    def test_bare_unit_windows(self):
        self.assertEqual(_retry_after_seconds("10/s"), 1)
        self.assertEqual(_retry_after_seconds("30/m"), 60)
        self.assertEqual(_retry_after_seconds("100/h"), 3600)
        self.assertEqual(_retry_after_seconds("1/d"), 86400)

    def test_multi_unit_windows(self):
        # The L5 fix: the multiplier before the unit is honored.
        self.assertEqual(_retry_after_seconds("5/15m"), 900)
        self.assertEqual(_retry_after_seconds("20/30s"), 30)
        self.assertEqual(_retry_after_seconds("2/2h"), 7200)

    def test_unknown_or_invalid_rate_falls_back_to_one_hour(self):
        self.assertEqual(_retry_after_seconds(None), 3600)
        self.assertEqual(_retry_after_seconds("garbage"), 3600)
        self.assertEqual(_retry_after_seconds("5/xyz"), 3600)
        # Callable rates (django-ratelimit allows them) must not raise.
        self.assertEqual(_retry_after_seconds(lambda g, r: "5/m"), 3600)
