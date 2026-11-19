"""Register keeps its rate limit (todo 705 M4, declined).

Owner decision 2026-11-17: M4 (register tells whether an email has an
account) is declined to keep instant sign-in after register. What bounds the
enumeration is the per-IP limit on ``views.register``; this pins it unchanged.
The behaviour at the limit is covered by
``test_rate_limiting.RegistrationRateLimitingTestCase`` (the 4th register in an hour
from one IP is 429).
"""

import inspect

from apps.plant_identification.constants import RATE_LIMITS
from apps.users import views
from django.test import SimpleTestCase


class RegisterRateLimitUnchangedTest(SimpleTestCase):
    def test_the_register_rate_is_three_per_hour(self):
        self.assertEqual(RATE_LIMITS["auth_endpoints"]["register"], "3/h")

    def test_register_is_decorated_with_that_limit(self):
        source = inspect.getsource(views)
        register_at = source.index("def register(")
        decorators = source[source.rindex("@api_view", 0, register_at) : register_at]
        self.assertIn('rate=RATE_LIMITS["auth_endpoints"]["register"]', decorators)
        self.assertIn("block=True", decorators)
