"""Password reset links live one hour (todo 705 L7, audit 2026-11-10).

Django's default is three days. The value is read by Django's token
generator, which signs the Wagtail admin and allauth reset links.
"""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from freezegun import freeze_time

User = get_user_model()


class PasswordResetTimeoutTest(TestCase):
    def test_the_timeout_is_one_hour(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 60 * 60)

    def test_a_reset_token_expires_after_the_timeout(self):
        user = User.objects.create_user(
            username="resetter",
            email="resetter@example.com",
            password="Reset-Pa55word!",  # pragma: allowlist secret
        )
        with freeze_time() as frozen:
            token = default_token_generator.make_token(user)
            frozen.tick(timedelta(minutes=59))
            self.assertTrue(default_token_generator.check_token(user, token))
            frozen.tick(timedelta(minutes=2))
            self.assertFalse(default_token_generator.check_token(user, token))
